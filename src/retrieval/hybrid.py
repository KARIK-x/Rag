"""
LOCUS RAG Hybrid Retrieval Engine.

Per spec §6–§9 (Phase 6): combine dense retrieval + BM25/exact retrieval,
apply RRF fusion, optionally rerank, support metadata/source filtering.

The engine preserves provenance and enables deterministic computation
over structured data. It is designed for scale to ~40–50 GB corpus
but remains local-first with no external services required.
"""

import heapq
import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.extraction.router import ExtractionResult
from src.indexing.vector import (
    ExactEntityIndex,
    BM25Index,
    DenseVectorIndex,
    MetadataIndex,
    QueryAnalyzer,
    RetrievalCandidate,
    SearchQuery,
)


# ─── RRF Fusion ───────────────────────────────────────────────────────────────

def rrf_fusion(
    results_lists: List[List[RetrievalCandidate]],
    k: int = 60,
) -> List[RetrievalCandidate]:
    """
    Reciprocal Rank Fusion across multiple ranked result lists.

    For each unique chunk_id across all lists:
        score = sum( 1 / (k + rank_i) ) over all lists that contain it
    Return candidates sorted by fused score (higher = better).

    k controls the decay speed. k=60 is the typical default;
    smaller k gives more weight to top ranks.
    """
    # Compute fused scores: sum of 1/(k + rank) across all lists
    fused_scores: Dict[str, float] = {}
    for rlist in results_lists:
        for rank, cand in enumerate(rlist, start=1):
            cid = cand.chunk_id
            fused_scores[cid] = fused_scores.get(cid, 0.0) + 1.0 / (k + rank)

    # Sort by fused score descending
    sorted_ids = sorted(fused_scores.items(), key=lambda x: -x[1])

    # Build Candidate objects from the best-ranked list
    # Use the first list's candidates as base, overlay fused scores
    best_list = results_lists[0] if results_lists else []
    fused: List[RetrievalCandidate] = []
    seen = set()
    for cid, fused_score in sorted_ids:
        if cid in seen:
            continue
        seen.add(cid)
        # Find the candidate object from the first list
        cand = next((c for c in best_list if c.chunk_id == cid), None)
        if cand is None:
            # Build a minimal candidate from metadata
            cand = RetrievalCandidate(
                chunk_id=cid,
                doc_id="",
                score=fused_score,
                text="",
                source_locator={},
                index_name="hybrid",
            )
        fused.append(cand)

    return fused


# ─── Retrieval Strategies ────────────────────────────────────────────────────

class DenseRetrieval:
    """Dense semantic retrieval via vector embeddings."""

    def __init__(self, vector_index: DenseVectorIndex):
        self.dense = vector_index

    def search(self, query: SearchQuery, top_k: int) -> List[RetrievalCandidate]:
        if not self.dense or not self.dense.embeddings:
            return []
        return self.dense.search(query, top_k)


class BM25Retrieval:
    """Lexical BM25 retrieval using the stdlib BM25 index."""

    def __init__(self, bm25_index: BM25Index):
        self.bm25 = bm25_index

    def search(self, query: SearchQuery, top_k: int) -> List[RetrievalCandidate]:
        if not self.bm25:
            return []
        return self.bm25.search(query, top_k)


class ExactRetrieval:
    """Exact/entity retrieval using the exact/entity index."""

    def __init__(self, exact_index: ExactEntityIndex):
        self.exact = exact_index

    def search(self, query: SearchQuery, top_k: int) -> List[RetrievalCandidate]:
        if not self.exact:
            return []
        return self.exact.search(query, top_k)


class MetadataFilter:
    """Post-retrieval metadata filtering."""

    def __init__(self, metadata_index: MetadataIndex):
        self.metadata_index = metadata_index

    def filter(self, candidates: List[RetrievalCandidate], filters: Dict[str, Any]) -> List[RetrievalCandidate]:
        if not filters:
            return candidates
        out: List[RetrievalCandidate] = []
        for c in candidates:
            meta = self.metadata_index.chunk_meta.get(c.chunk_id, {})
            ok = True
            for k, v in filters.items():
                if k == "doc_type" and meta.get("doc_type") != v:
                    ok = False
                    break
                if k == "authority_status" and meta.get("authority_status") != v:
                    ok = False
                    break
                if k == "page_range":
                    ps = meta.get("page_start", 0)
                    pe = meta.get("page_end", 0)
                    if not (v[0] <= ps <= v[1] or v[0] <= pe <= v[1]):
                        ok = False
                        break
            if ok:
                out.append(c)
        return out


# ─── Hybrid Retriever ────────────────────────────────────────────────────────

class HybridRetriever:
    """
    Orchestrates multi-strategy retrieval and RRF fusion.

    Strategy:
      1. Retrieve from all available indexes (dense, BM25, exact, metadata)
      2. RRF fuse the result lists
      3. Optionally rerank (if reranker provided / justified)
      4. Apply metadata filters
      5. Return top-k with provenance preserved
    """

    def __init__(
        self,
        dense: Optional[DenseVectorIndex] = None,
        bm25: Optional[BM25Index] = None,
        exact: Optional[ExactEntityIndex] = None,
        metadata: Optional[MetadataIndex] = None,
        rrf_k: int = 60,
        rerank: bool = False,
    ):
        self.dense = dense
        self.bm25 = bm25
        self.exact = exact
        self.metadata = metadata or MetadataIndex()
        self.rrf_k = rrf_k
        self.rerank = rerank
        self.analyzer = QueryAnalyzer()

    def retrieve(
        self,
        query: str,
        top_k: int = 20,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[RetrievalCandidate]:
        # Build a rich SearchQuery (entities, dates, amounts) so that
        # currency/number/date queries reach the exact index correctly.
        search_query = self.analyzer.analyze(query)
        if filters:
            search_query.filters.update(filters)

        # 1. Retrieve from all available indexes
        lists: List[List[RetrievalCandidate]] = []

        if self.dense:
            lists.append(self.dense.search(search_query, top_k * 2))

        if self.bm25:
            lists.append(self.bm25.search(search_query, top_k * 2))

        if self.exact:
            lists.append(self.exact.search(search_query, top_k * 2))

        # 2. RRF fusion
        fused = rrf_fusion(lists, self.rrf_k)

        # 3. Metadata filtering
        fused = self.metadata.filter(fused, search_query.filters)

        # 4. Return top-k
        return fused[:top_k]


# ─── Exports ─────────────────────────────────────────────────────────────────

def retrieve(
    query: str,
    dense_index: Optional[DenseVectorIndex] = None,
    bm25_index: Optional[BM25Index] = None,
    exact_index: Optional[ExactEntityIndex] = None,
    metadata_index: Optional[MetadataIndex] = None,
    top_k: int = 20,
    filters: Optional[Dict[str, Any]] = None,
) -> List[RetrievalCandidate]:
    """
    Convenience wrapper for HybridRetriever.retrieve().
    """
    retriever = HybridRetriever(
        dense=dense_index,
        bm25=bm25_index,
        exact=exact_index,
        metadata=metadata_index,
        rrf_k=60,
    )
    return retriever.retrieve(query, top_k=top_k, filters=filters)