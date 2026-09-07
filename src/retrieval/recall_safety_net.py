"""
LOCUS RAG Recall Safety Net — Phase 8.

Implements a bounded retrieval ladder to prevent the founding failure:
an indexed, retrievable answer being missed.

Ladder:
  1. Initial retrieval (HybridRetriever)
  2. If insufficient: expanded candidate pool (increase top_k)
  3. If still insufficient: exact phrase search
  4. If still insufficient: broadened lexical search (stemming, synonyms)
  5. If still insufficient: query reformulation (abbreviation expansion, etc.)
  6. If still insufficient: document-level search (return whole documents)

Each step has trigger conditions, maximum work limits, and stop conditions.

Based on ARCHITECTURE.md §3.2 and BENCHMARK.md §4.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from src.indexing.vector import SearchQuery, RetrievalCandidate
from src.retrieval.hybrid import HybridRetriever
from src.retrieval.query_router import QueryRouter, QueryIntentResult

logger = logging.getLogger(__name__)


class RecallSafetyNet:
    """
    Wraps a HybridRetriever and provides a retrieve method with recall safety net.

    The safety net implements a ladder of increasingly broad retrieval strategies
    when the initial retrieval yields insufficient results.
    """

    def __init__(
        self,
        hybrid_retriever: HybridRetriever,
        query_router: Optional[QueryRouter] = None,
        # Ladder configuration
        initial_top_k: int = 20,
        expanded_top_k: int = 100,
        exact_phrase_top_k: int = 20,
        broadened_top_k: int = 20,
        reformulation_top_k: int = 20,
        document_level_top_k: int = 5,
        # Trigger thresholds
        insufficient_results_threshold: int = 3,
        low_score_threshold: float = 0.3,
        # Maximum work limits to prevent runaway
        max_candidates_per_step: int = 200,
    ):
        self.hybrid = hybrid_retriever
        self.query_router = query_router or QueryRouter()
        self.initial_top_k = initial_top_k
        self.expanded_top_k = expanded_top_k
        self.exact_phrase_top_k = exact_phrase_top_k
        self.broadened_top_k = broadened_top_k
        self.reformulation_top_k = reformulation_top_k
        self.document_level_top_k = document_level_top_k
        self.insufficient_results_threshold = insufficient_results_threshold
        self.low_score_threshold = low_score_threshold
        self.max_candidates_per_step = max_candidates_per_step
        logger.info("RecallSafetyNet initialized")

    def retrieve(
        self,
        query: str,
        top_k: int = 20,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[RetrievalCandidate]:
        """
        Retrieve with recall safety net ladder.

        Returns:
            List of RetrievalCandidate, length up to top_k.
        """
        logger.info(f"Starting recall safety net for query: {query[:50]}...")

        # Step 1: Initial retrieval
        candidates = self._initial_retrieval(query, self.initial_top_k, filters)
        if self._is_sufficient(candidates, query):
            logger.info(f"Initial retrieval sufficient: {len(candidates)} candidates")
            return candidates[:top_k]

        # Step 2: Expanded candidate pool
        logger.info("Initial insufficient, trying expanded pool")
        candidates = self._expanded_pool_retrieval(query, self.expanded_top_k, filters)
        if self._is_sufficient(candidates, query):
            logger.info(f"Expanded pool sufficient: {len(candidates)} candidates")
            return candidates[:top_k]

        # Step 3: Exact phrase search
        logger.info("Expanded insufficient, trying exact phrase")
        candidates = self._exact_phrase_search(query, self.exact_phrase_top_k, filters)
        if self._is_sufficient(candidates, query):
            logger.info(f"Exact phrase sufficient: {len(candidates)} candidates")
            return candidates[:top_k]

        # Step 4: Broadened lexical search
        logger.info("Exact phrase insufficient, trying broadened lexical")
        candidates = self._broadened_lexical_search(query, self.broadened_top_k, filters)
        if self._is_sufficient(candidates, query):
            logger.info(f"Broadened lexical sufficient: {len(candidates)} candidates")
            return candidates[:top_k]

        # Step 5: Query reformulation
        logger.info("Broadened lexical insufficient, trying query reformulation")
        candidates = self._query_reformulation_search(
            query, self.reformulation_top_k, filters
        )
        if self._is_sufficient(candidates, query):
            logger.info(f"Query reformulation sufficient: {len(candidates)} candidates")
            return candidates[:top_k]

        # Step 6: Document-level search
        logger.info("Reformulation insufficient, trying document-level")
        candidates = self._document_level_search(
            query, self.document_level_top_k, filters
        )
        logger.info(f"Document-level complete: {len(candidates)} candidates")
        return candidates[:top_k]

    # ─── Ladder Steps ────────────────────────────────────────────────────────────────
    def _initial_retrieval(
        self, query: str, top_k: int, filters: Optional[Dict[str, Any]]
    ) -> List[RetrievalCandidate]:
        return self.hybrid.retrieve(query, top_k=top_k, filters=filters)

    def _expanded_pool_retrieval(
        self, query: str, top_k: int, filters: Optional[Dict[str, Any]]
    ) -> List[RetrievalCandidate]:
        # Simply increase top_k for hybrid retrieval
        return self.hybrid.retrieve(query, top_k=min(top_k, self.max_candidates_per_step), filters=filters)

    def _exact_phrase_search(
        self, query: str, top_k: int, filters: Optional[Dict[str, Any]]
    ) -> List[RetrievalCandidate]:
        # Search for the exact phrase by quoting it
        exact_query = f'"{query}"'
        return self.hybrid.retrieve(
            exact_query, top_k=min(top_k, self.max_candidates_per_step), filters=filters
        )

    def _broadened_lexical_search(
        self, query: str, top_k: int, filters: Optional[Dict[str, Any]]
    ) -> List[RetrievalCandidate]:
        # Implement broadening: remove punctuation, lowercase, add synonyms?
        # For now, we'll use the query router to get expanded queries and search each
        expanded_queries = self.query_router.normalizer.expand_abbreviations(query)
        # Also try removing extra whitespace and lowercasing
        broadened = re.sub(r"[^\w\s]", " ", expanded_queries).lower()
        broadened = re.sub(r"\s+", " ", broadened).strip()
        # If broadened is different, search it
        if broadened and broadened != query.lower():
            return self.hybrid.retrieve(
                broadened, top_k=min(top_k, self.max_candidates_per_step), filters=filters
            )
        return []

    def _query_reformulation_search(
        self, query: str, top_k: int, filters: Optional[Dict[str, Any]]
    ) -> List[RetrievalCandidate]:
        # Use the query router's expanded queries (abbreviation expansion, synonyms)
        intent_result = self.query_router.classifier.classify(query)
        candidates: List[RetrievalCandidate] = []
        seen_chunk_ids = set()
        for expanded in intent_result.expanded_queries:
            if expanded == query:
                continue
            res = self.hybrid.retrieve(
                expanded,
                top_k=min(top_k // max(len(intent_result.expanded_queries), 1), self.max_candidates_per_step),
                filters=filters,
            )
            for c in res:
                if c.chunk_id not in seen_chunk_ids:
                    seen_chunk_ids.add(c.chunk_id)
                    candidates.append(c)
        return candidates

    def _document_level_search(
        self, query: str, top_k: int, filters: Optional[Dict[str, Any]]
    ) -> List[RetrievalCandidate]:
        # Return whole documents: we don't have a document index, so we'll
        # retrieve chunks and then group by doc_id, returning one chunk per doc
        # (the highest scoring chunk per doc) up to top_k docs.
        res = self.hybrid.retrieve(
            query, top_k=min(top_k * 3, self.max_candidates_per_step), filters=filters
        )
        # Group by doc_id
        best_per_doc: Dict[str, RetrievalCandidate] = {}
        for c in res:
            doc_id = c.doc_id or "unknown"
            if doc_id not in best_per_doc or c.score > best_per_doc[doc_id].score:
                best_per_doc[doc_id] = c
        return list(best_per_doc.values())[:top_k]

    # ─── Helper Methods ────────────────────────────────────────────────────────────────
    def _is_sufficient(
        self, candidates: List[RetrievalCandidate], query: str
    ) -> bool:
        """
        Determine if the candidate set is sufficient to stop the ladder.

        Heuristics:
          - At least N candidates with score above threshold
          - Or, the top candidate has a high score (exact match indicator)
        """
        if not candidates:
            return False
        if len(candidates) >= self.insufficient_results_threshold:
            # Check if top candidate has high score (>= 0.8) indicating strong match
            if candidates[0].score >= 0.8:
                return True
            # Check if we have enough candidates with reasonable score
            sufficient_scores = [
                c for c in candidates if c.score >= self.low_score_threshold
            ]
            if len(sufficient_scores) >= self.insufficient_results_threshold:
                return True
        return False