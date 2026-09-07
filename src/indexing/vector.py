"""
LOCUS RAG indexing layer.

Per spec §27–§31:
  - Dense semantic index (embeddings)
  - BM25 / lexical index
  - Exact/entity index (names, dates, IDs, amounts)
  - Metadata index

The LLM sits above these systems. This module provides the retrieval interfaces
with stdlib fallbacks when libraries (lancedb, qdrant, sentence_transformers,
bm25s, rank_bm25) are not installed.
"""

import hashlib
import json
import logging
import math
import sqlite3
import re
from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)


# ─── Data structures ────────────────────────────────────────────────────────

@dataclass
class RetrievalCandidate:
    """A candidate retrieved from any index."""
    chunk_id: str
    doc_id: str
    score: float
    text: str
    source_locator: Dict[str, Any]
    index_name: str  # "dense" | "bm25" | "exact" | "metadata"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchQuery:
    """Analyzed query for retrieval."""
    raw_query: str
    normalized_query: str
    terms: List[str]
    entities: List[str] = field(default_factory=list)
    dates: List[str] = field(default_factory=list)
    amounts: List[str] = field(default_factory=list)
    filters: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ─── Abstract index interface ───────────────────────────────────────────────

class BaseIndex(ABC):
    """Abstract base for any retrieval index."""

    @abstractmethod
    def add(self, chunk_id: str, text: str, metadata: Dict[str, Any]) -> None: ...

    @abstractmethod
    def search(self, query: SearchQuery, top_k: int) -> List[RetrievalCandidate]: ...

    @abstractmethod
    def delete(self, chunk_ids: List[str]) -> None: ...

    @abstractmethod
    def clear(self) -> None: ...


# ─── Exact / Entity Index (stdlib) ──────────────────────────────────────────

class ExactEntityIndex(BaseIndex):
    """
    Exact-match index for:
      - Person names
      - Organization names
      - Event names
      - Acronyms
      - Drive file IDs / document IDs
      - Dates (ISO and variants)
      - Years
      - Monetary values
      - Sponsorship names
      - Project names
      - Email addresses
      - Phone numbers
      - Spreadsheet identifiers

    Uses an inverted index (token → set of chunk_ids) for fast exact lookup.
    """

    def __init__(self, db_path: Optional[str] = None):
        self._index: Dict[str, Set[str]] = {}  # token → chunk_ids
        self._chunk_texts: Dict[str, str] = {}  # chunk_id → text
        self._chunk_meta: Dict[str, Dict] = {}
        self.db_path = db_path
        if db_path:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            self._init_db()
            self._load()
            self._load()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS exact_index (
                token TEXT PRIMARY KEY,
                chunk_ids TEXT NOT NULL  -- JSON array
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS exact_chunks (
                chunk_id TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                meta TEXT NOT NULL  -- JSON
            )
        """)
        conn.commit()
        conn.close()

    def _persist_token(self, token: str, chunk_ids: Set[str]):
        if not self.db_path:
            return
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO exact_index (token, chunk_ids) VALUES (?, ?)",
            (token, json.dumps(sorted(chunk_ids))),
        )
        conn.commit()
        conn.close()

    def _load(self):
        """Reload persisted tokens + chunk texts from SQLite."""
        if not self.db_path or not Path(self.db_path).exists():
            return
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT token, chunk_ids FROM exact_index")
        for token, ids_json in cur.fetchall():
            self._index[token] = set(json.loads(ids_json))
        try:
            cur.execute("SELECT chunk_id, text, meta FROM exact_chunks")
            for cid, txt, meta_json in cur.fetchall():
                self._chunk_texts[cid] = txt
                self._chunk_meta[cid] = json.loads(meta_json)
        except Exception:
            pass
        conn.close()

    def _persist_chunk(self, chunk_id: str, text: str, meta):
        if not self.db_path:
            return
        import json as _json
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO exact_chunks (chunk_id, text, meta) VALUES (?, ?, ?)",
            (chunk_id, text, _json.dumps(meta or {})),
        )
        conn.commit()
        conn.close()

    def _tokenize(self, text: str) -> List[str]:
        """Extract exact-match tokens from text."""
        tokens = []
        # Acronyms (CAPS, 2+ chars)
        tokens.extend(re.findall(r"\b[A-Z]{2,}\b", text))
        # Email
        tokens.extend(re.findall(r"[\w.-]+@[\w.-]+", text))
        # Dates
        tokens.extend(re.findall(r"\b\d{4}[-/.]\d{1,2}[-/.]\d{1,2}\b", text))
        tokens.extend(re.findall(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", text))
        # Years
        tokens.extend(re.findall(r"\b(19|20)\d{2}\b", text))
        # Currency amounts (also catch lakh/crore/etc.)
        tokens.extend(re.findall(r"NPR\s*[\d,]+(?:\.\d+)?", text, re.I))
        tokens.extend(re.findall(r"Rs\.?\s*[\d,]+(?:\.\d+)?", text, re.I))
        tokens.extend(re.findall(r"\$[\d,]+(?:\.\d+)?", text))
        # lakh/crore form
        for prefix in ("NPR", "Rs", "Rs.", "$", "USD", "AED"):
            tokens.extend(re.findall(rf"{prefix}\s*\d+(?:\.\d+)?\s*(lakh|crore|thousand|million)", text, re.I))
        # Drive file IDs (28-char base64)
        tokens.extend(re.findall(r"[A-Za-z0-9_-]{28}", text))
        # Names (Title Case sequences of 2+ words)
        tokens.extend(re.findall(r"\b(?:[A-Z][a-z]+\s){1,3}[A-Z][a-z]+\b", text))
        # Phone
        tokens.extend(re.findall(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", text))
        # Lowercase variants for case-insensitive matching
        tokens_lower = [t.lower() for t in tokens]
        return list(set(tokens + tokens_lower))

    def add(self, chunk_id: str, text: str, metadata: Dict[str, Any]) -> None:
        self._chunk_texts[chunk_id] = text
        self._chunk_meta[chunk_id] = metadata
        self._persist_chunk(chunk_id, text, metadata)
        tokens = self._tokenize(text)
        for tok in tokens:
            if tok not in self._index:
                self._index[tok] = set()
            self._index[tok].add(chunk_id)
            self._persist_token(tok, self._index[tok])

    def search(self, query: SearchQuery, top_k: int) -> List[RetrievalCandidate]:
        """Exact lookup: match query terms against indexed tokens."""
        candidates: Dict[str, Tuple[float, str]] = {}
        score = 1.0 / max(len(query.terms), 1)

        # Normalize query terms the same way the tokenizer does (strip commas,
        # currency prefixes, lowercase) so "50000" matches "50,000" and "NPR 50,000"
        # matches "npr 50000".
        def _norm(t: str) -> str:
            s = t.lower().replace(",", "")
            for prefix in ("npr ", "rs ", "rs. ", "$", "usd "):
                if s.startswith(prefix):
                    s = s[len(prefix):]
            return s.strip()

        query_terms = [_norm(t) for t in query.terms]
        # Also normalize entities/dates/amounts
        query_terms += [_norm(e) for e in query.entities + query.dates + query.amounts]

        # Also try the raw query tokens (e.g. "Ncell" as a name)
        query_terms += [_norm(t) for t in re.findall(r"[\w'-]+", query.raw_query)]

        for term in query_terms:
            if not term:
                continue
            # Exact match on normalized form
            if term in self._index:
                for cid in self._index[term]:
                    if cid in candidates:
                        candidates[cid] = (candidates[cid][0] + score, self._chunk_texts.get(cid, ""))
                    else:
                        candidates[cid] = (score, self._chunk_texts.get(cid, ""))
            # Also try matching against the raw token (e.g. "NPR 50,000" vs "npr 50000")
            for tok, cids in self._index.items():
                if _norm(tok) == term:
                    for cid in cids:
                        if cid in candidates:
                            candidates[cid] = (candidates[cid][0] + score, self._chunk_texts.get(cid, ""))
                        else:
                            candidates[cid] = (score, self._chunk_texts.get(cid, ""))
            # Long alphanumeric token (likely a drive ID) — substring match
            if len(term) >= 20 and re.match(r"^[a-z0-9_-]+$", term):
                for tok, cids in self._index.items():
                    if term in tok or tok in term:
                        for cid in cids:
                            if cid in candidates:
                                candidates[cid] = (candidates[cid][0] + score, self._chunk_texts.get(cid, ""))
                            else:
                                candidates[cid] = (score, self._chunk_texts.get(cid, ""))
            # Long alphanumeric token (likely a drive ID) — substring match
            if len(term) >= 20 and re.match(r"^[a-z0-9_-]+$", term):
                for tok, cids in self._index.items():
                    if term in tok or tok in term:
                        for cid in cids:
                            if cid in candidates:
                                candidates[cid] = (candidates[cid][0] + score, self._chunk_texts.get(cid, ""))
                            else:
                                candidates[cid] = (score, self._chunk_texts.get(cid, ""))

        results = []
        for cid, (sc, txt) in sorted(candidates.items(), key=lambda x: -x[1][0])[:top_k]:
            results.append(RetrievalCandidate(
                chunk_id=cid,
                doc_id=self._chunk_meta.get(cid, {}).get("doc_id", ""),
                score=sc,
                text=txt,
                source_locator=self._chunk_meta.get(cid, {}).get("source_locator", {}),
                index_name="exact",
            ))
        return results

    def delete(self, chunk_ids: List[str]) -> None:
        for cid in chunk_ids:
            if cid in self._chunk_texts:
                # Remove from index
                for tok, cids in self._index.items():
                    if cid in cids:
                        cids.remove(cid)
                        self._persist_token(tok, cids)
                del self._chunk_texts[cid]
                del self._chunk_meta[cid]

    def clear(self) -> None:
        self._index.clear()
        self._chunk_texts.clear()
        self._chunk_meta.clear()
        if self.db_path:
            conn = sqlite3.connect(self.db_path)
            conn.execute("DELETE FROM exact_index")
            conn.commit()
            conn.close()


# ─── BM25 Index (stdlib fallback) ───────────────────────────────────────────

class BM25Index(BaseIndex):
    """
    BM25 lexical index using only stdlib.

    Fallback when bm25s/rank_bm25 not installed.
    Implements the BM25 scoring formula:
      score = sum( IDF(term) * (freq * (k1+1)) / (freq + k1*(1-b+b*dl/avgdl)) )
    """

    def __init__(
        self,
        k1: float = 1.2,
        b: float = 0.75,
        db_path: Optional[str] = None,
    ):
        self.k1 = k1
        self.b = b
        self.doc_ids: List[str] = []
        self.doc_texts: Dict[str, str] = {}
        self.doc_lens: Dict[str, int] = {}
        self.doc_meta: Dict[str, Dict[str, Any]] = {}  # chunk_id -> raw metadata (provenance)
        self.term_freqs: Dict[str, Dict[str, int]] = {}  # term -> doc_id -> freq
        self.doc_freq: Dict[str, int] = {}  # term -> n_docs
        self.avgdl: float = 0.0
        self.N: int = 0
        self.db_path = db_path
        if db_path:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS bm25_docs (
                chunk_id TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                length INTEGER NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS bm25_terms (
                term TEXT PRIMARY KEY,
                doc_freq INTEGER NOT NULL,
                postings TEXT NOT NULL  -- JSON: {chunk_id: freq}
            )
        """)
        conn.commit()
        conn.close()

    def _tokenize(self, text: str) -> List[str]:
        """Simple word tokenizer."""
        return [t for t in re.findall(r"[\w'-]+", text.lower()) if len(t) > 1]

    def add(self, chunk_id: str, text: str, metadata: Dict[str, Any]) -> None:
        tokens = self._tokenize(text)
        freq = Counter(tokens)
        self.doc_ids.append(chunk_id)
        self.doc_texts[chunk_id] = text
        self.doc_lens[chunk_id] = len(tokens)
        self.doc_meta[chunk_id] = dict(metadata or {})
        self.term_freqs[chunk_id] = dict(freq)
        self.N = len(self.doc_ids)
        self.avgdl = sum(self.doc_lens.values()) / self.N if self.N else 0.0

        for term, f in freq.items():
            self.doc_freq[term] = self.doc_freq.get(term, 0) + 1
            if self.db_path:
                conn = sqlite3.connect(self.db_path)
                cur = conn.cursor()
                cur.execute(
                    "INSERT OR REPLACE INTO bm25_terms (term, doc_freq, postings) VALUES (?, ?, ?)",
                    (term, self.doc_freq[term], json.dumps({chunk_id: f})),
                )
                conn.commit()
                conn.close()

        if self.db_path:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute(
                "INSERT OR REPLACE INTO bm25_docs (chunk_id, text, length) VALUES (?, ?, ?)",
                (chunk_id, text, len(tokens)),
            )
            conn.commit()
            conn.close()

    def _idf(self, term: str) -> float:
        df = self.doc_freq.get(term, 0)
        if df == 0:
            return 0.0
        return math.log((self.N - df + 0.5) / (df + 0.5) + 1.0)

    def search(self, query: SearchQuery, top_k: int) -> List[RetrievalCandidate]:
        q_terms = query.terms
        if not q_terms:
            return []

        scores: Dict[str, float] = {}
        for term in q_terms:
            idf = self._idf(term)
            if idf == 0:
                continue
            # Docs containing term
            for cid in self.doc_ids:
                tf = self.term_freqs.get(cid, {}).get(term, 0)
                if tf == 0:
                    continue
                dl = self.doc_lens[cid]
                numer = tf * (self.k1 + 1)
                denom = tf + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
                scores[cid] = scores.get(cid, 0.0) + idf * numer / denom

        results = []
        for cid, sc in sorted(scores.items(), key=lambda x: -x[1])[:top_k]:
            meta = self.doc_meta.get(cid, {})
            # Normalize doc_id / source_locator from stored metadata so
            # provenance survives the BM25 path untouched.
            doc_id = meta.get("doc_id", "")
            source_locator = meta.get("source_locator")
            if source_locator is None and "provenance" in meta:
                source_locator = meta["provenance"]
            results.append(RetrievalCandidate(
                chunk_id=cid,
                doc_id=doc_id,
                score=sc,
                text=self.doc_texts.get(cid, ""),
                source_locator=source_locator or {},
                index_name="bm25",
                metadata=meta,
            ))
        return results

    def delete(self, chunk_ids: List[str]) -> None:
        for cid in chunk_ids:
            if cid in self.doc_ids:
                self.doc_ids.remove(cid)
                del self.doc_texts[cid]
                del self.doc_lens[cid]
                self.doc_meta.pop(cid, None)
                tf = self.term_freqs.pop(cid, {})
                for term, f in tf.items():
                    self.doc_freq[term] -= f
                    if self.doc_freq[term] <= 0:
                        del self.doc_freq[term]
        self.N = len(self.doc_ids)
        self.avgdl = sum(self.doc_lens.values()) / self.N if self.N else 0.0

    def clear(self) -> None:
        self.doc_ids.clear()
        self.doc_texts.clear()
        self.doc_lens.clear()
        self.doc_meta.clear()
        self.term_freqs.clear()
        self.doc_freq.clear()
        self.N = 0
        self.avgdl = 0.0


# ─── Dense Vector Index (fallback) ──────────────────────────────────────────

class DenseVectorIndex(BaseIndex):
    """
    Dense semantic vector index.

    Fallback: uses sqlite + simple cosine similarity on precomputed embeddings.
    When sentence_transformers/lancedb/qdrant available, they should replace this.
    """

    def __init__(self, dim: int = 768, db_path: Optional[str] = None):
        self.dim = dim
        self.embeddings: Dict[str, List[float]] = {}
        self.chunk_texts: Dict[str, str] = {}
        self.chunk_meta: Dict[str, Dict] = {}
        self.db_path = db_path
        if db_path:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS dense_index (
                chunk_id TEXT PRIMARY KEY,
                embedding TEXT NOT NULL  -- JSON array of floats
            )
        """)
        conn.commit()
        conn.close()

    def add(self, chunk_id: str, text: str, metadata: Dict[str, Any]) -> None:
        # Embedding must be provided in metadata['embedding']
        emb = metadata.get("embedding")
        if not emb or not isinstance(emb, list):
            raise ValueError("Dense index requires embedding in metadata['embedding']")
        self.embeddings[chunk_id] = emb
        self.chunk_texts[chunk_id] = text
        self.chunk_meta[chunk_id] = metadata
        if self.db_path:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute(
                "INSERT OR REPLACE INTO dense_index (chunk_id, embedding) VALUES (?, ?)",
                (chunk_id, json.dumps(emb)),
            )
            conn.commit()
            conn.close()

    @staticmethod
    def _cosine(a: List[float], b: List[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
        return dot / (na * nb) if na and nb else 0.0

    def search(self, query: SearchQuery, top_k: int) -> List[RetrievalCandidate]:
        # Requires query_embedding in query.metadata
        q_emb = query.metadata.get("query_embedding")
        if not q_emb:
            return []

        scores: Dict[str, float] = {}
        for cid, emb in self.embeddings.items():
            sc = self._cosine(q_emb, emb)
            scores[cid] = sc

        results = []
        for cid, sc in sorted(scores.items(), key=lambda x: -x[1])[:top_k]:
            results.append(RetrievalCandidate(
                chunk_id=cid,
                doc_id=self.chunk_meta.get(cid, {}).get("doc_id", ""),
                score=sc,
                text=self.chunk_texts.get(cid, ""),
                source_locator=self.chunk_meta.get(cid, {}).get("source_locator", {}),
                index_name="dense",
            ))
        return results

    def delete(self, chunk_ids: List[str]) -> None:
        for cid in chunk_ids:
            self.embeddings.pop(cid, None)
            self.chunk_texts.pop(cid, None)
            self.chunk_meta.pop(cid, None)

    def clear(self) -> None:
        self.embeddings.clear()
        self.chunk_texts.clear()
        self.chunk_meta.clear()


# ─── Metadata Index ─────────────────────────────────────────────────────────

class MetadataIndex(BaseIndex):
    """
    Metadata filter index (page range, sheet name, doc type, authority, etc.).
    """

    def __init__(self, db_path: Optional[str] = None):
        self.chunk_meta: Dict[str, Dict] = {}
        self.db_path = db_path

    def add(self, chunk_id: str, text: str, metadata: Dict[str, Any]) -> None:
        self.chunk_meta[chunk_id] = metadata

    def search(self, query: SearchQuery, top_k: int) -> List[RetrievalCandidate]:
        # Metadata filters are applied post-retrieval by the retriever
        return []

    def filter(self, candidates: List[RetrievalCandidate], filters: Dict[str, Any]) -> List[RetrievalCandidate]:
        """Filter candidates by metadata constraints."""
        if not filters:
            return candidates

        out = []
        for c in candidates:
            meta = self.chunk_meta.get(c.chunk_id, {})
            ok = True
            for k, v in filters.items():
                if k == "doc_type" and meta.get("doc_type") != v:
                    ok = False
                    break
                if k == "sheet_name" and meta.get("sheet_name") != v:
                    ok = False
                    break
                if k == "page_range":
                    ps = meta.get("page_start", 0)
                    pe = meta.get("page_end", 0)
                    if not (v[0] <= ps <= v[1] or v[0] <= pe <= v[1]):
                        ok = False
                        break
                if k == "authority" and meta.get("authority_status") != v:
                    ok = False
                    break
            if ok:
                out.append(c)
        return out

    def add(self, chunk_id: str, text: str, metadata: Dict[str, Any]) -> None:
        self.chunk_meta[chunk_id] = metadata

    def delete(self, chunk_ids: List[str]) -> None:
        for cid in chunk_ids:
            self.chunk_meta.pop(cid, None)

    def search(self, query: SearchQuery, top_k: int) -> List[RetrievalCandidate]:
        return []

    def clear(self) -> None:
        self.chunk_meta.clear()


# ─── Query Analyzer ──────────────────────────────────────────────────────────

class QueryAnalyzer:
    """Parse a raw query into a SearchQuery with terms, entities, dates, amounts."""

    def __init__(self):
        pass

    def analyze(self, raw_query: str) -> SearchQuery:
        text = raw_query.strip()
        normalized = text.lower()
        terms = [t for t in re.findall(r"[\w'-]+", normalized) if len(t) > 1]

        # Extract entities
        entities = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", raw_query)
        dates = re.findall(r"\b\d{4}[-/.]\d{1,2}[-/.]\d{1,2}\b", raw_query)
        dates += re.findall(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", raw_query)
        amounts = re.findall(r"(?:NPR|Rs\.?|\$)\s*[\d,]+", raw_query, re.I)

        # NOTE: filters are intentionally NOT inferred here. Auto-injecting
        # metadata filters from keyword heuristics ("sponsor" → doc_type=sponsorship)
        # causes premature closure: the query "Ncell sponsorship" would only
        # return documents pre-labeled sponsorship, discarding relevant evidence
        # that lacks the metadata tag. Spec: "If uncertain about routing, retrieve
        # broadly rather than prematurely skipping evidence." Filter routing is the
        # responsibility of the Phase 7 QueryRouter, which applies explicit filters.

        return SearchQuery(
            raw_query=raw_query,
            normalized_query=normalized,
            terms=terms,
            entities=entities,
            dates=dates,
            amounts=amounts,
            filters={},
        )


# ─── Hybrid Retriever ────────────────────────────────────────────────────────

class HybridRetriever:
    """
    Hybrid retrieval combining dense + BM25 + exact + metadata.

    Spec §32: RRF fusion after candidate union.
    """

    def __init__(
        self,
        dense: Optional[DenseVectorIndex] = None,
        bm25: Optional[BM25Index] = None,
        exact: Optional[ExactEntityIndex] = None,
        metadata: Optional[MetadataIndex] = None,
        rrf_k: int = 60,
    ):
        self.dense = dense
        self.bm25 = bm25
        self.exact = exact
        self.metadata = metadata or MetadataIndex()
        self.rrf_k = rrf_k
        self.analyzer = QueryAnalyzer()

    def retrieve(
        self,
        query: str,
        top_k: int = 20,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[RetrievalCandidate]:
        search_query = self.analyzer.analyze(query)
        if filters:
            search_query.filters.update(filters)

        candidates = []

        # Parallel retrieval from all available indexes
        if self.dense:
            candidates.extend(self.dense.search(search_query, top_k * 2))
        if self.bm25:
            candidates.extend(self.bm25.search(search_query, top_k * 2))
        if self.exact:
            candidates.extend(self.exact.search(search_query, top_k * 2))

        # Deduplicate by chunk_id (keep highest score)
        dedup: Dict[str, RetrievalCandidate] = {}
        for c in candidates:
            if c.chunk_id not in dedup or c.score > dedup[c.chunk_id].score:
                dedup[c.chunk_id] = c

        # RRF fusion
        ranked = self._rrf_fusion(list(dedup.values()))

        # Apply metadata filters
        filtered = self.metadata.filter(ranked, search_query.filters)

        return filtered[:top_k]

    def _rrf_fusion(self, candidates: List[RetrievalCandidate]) -> List[RetrievalCandidate]:
        """Reciprocal Rank Fusion across indexes."""
        index_scores: Dict[str, Dict[str, float]] = {}
        for idx, c in enumerate(candidates):
            idx_name = c.index_name
            if idx_name not in index_scores:
                index_scores[idx_name] = {}
            index_scores[idx_name][c.chunk_id] = idx + 1

        # RRF score for each chunk_id
        fused: Dict[str, float] = {}
        for idx_name, ranks in index_scores.items():
            for cid, rank in ranks.items():
                fused[cid] = fused.get(cid, 0.0) + 1.0 / (self.rrf_k + rank)

        # Return top candidates with fused scores
        fused_candidates = []
        for cid, score in sorted(fused.items(), key=lambda x: -x[1]):
            # Find a representative candidate to copy
            rep = next(c for c in candidates if c.chunk_id == cid)
            fused_candidates.append(RetrievalCandidate(
                chunk_id=cid,
                doc_id=rep.doc_id,
                score=score,
                text=rep.text,
                source_locator=rep.source_locator,
                index_name="hybrid",
            ))
        return fused_candidates