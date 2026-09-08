"""
LOCUS RAG Query Cache — Phase 13 (Caching + Performance).

Per spec §131–§135:
  - Version/snapshot-aware query caching
  - Safe invalidation on corpus/index changes
  - Batch-friendly: keys based on query hash + corpus_version + index_version
  - Latency and resource monitoring support (hit/miss counters, stats)
  - No secret leakage; cache lives entirely in locus_rag
  - Cache correctness: a hit must never return stale evidence merely
    because the query string is identical

Layers:
  - ``MemoryCache``   — in-process store (LRU-ish eviction)
  - ``SqliteCache``   — durable restart-safe store on SQLite (WAL mode)
  - ``QueryCache``    — query→answer cache (values JSON-serializable)
  - ``RetrievalCache``— query→retrieval candidates (reuse across related queries)
  - ``EmbeddingCache``— text→embedding reuse, keyed by content + model/version
  - ``CachedRetriever``— narrow wrapper around HybridRetriever.retrieve

Keying rules (correctness over speed):
  - Every key embeds ``corpus_version`` and ``index_version``; a source change
    that the incremental-sync pipeline publishes bumps these versions, which
    invalidates affected entries automatically.
  - Retrieval-cache keys additionally embed every argument that materially
    changes the result: ``top_k``, ``rrf_k``, and a canonical ``filters``
    fingerprint.  A cached result is only ever reused when the whole query
    context matches.
  - Embedding keys embed the model name **and** version so embeddings from
    incompatible models/configs are never reused.

Failure safety:
  - Corrupted/unreadable cache entries become misses (never raise).
  - A failed ingestion never bumps a version, so a partially-updated corpus
    cannot produce a stale hit.
"""

import hashlib
import json
import logging
import sqlite3
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.indexing.vector import RetrievalCandidate

from src.indexing.vector import RetrievalCandidate

logger = logging.getLogger(__name__)

# ─── Hashing helper ──────────────────────────────────────────────────────────

def _sha(text: str) -> str:
    """16-hex sha256 of the input (queries, text)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


# ─── JSON round-trip (safe decode) ────────────────────────────────────────────

def _json_encode(value: Any) -> str:
    """Encode a cache value as a JSON string for durable storage."""
    return json.dumps(value, default=str, ensure_ascii=False)


def _json_decode(raw: Any) -> tuple[Any, bool]:
    """Decode a stored JSON string back to its Python value.

    Returns (value, ok) where ok is True if decoding succeeded.
    If the payload was stored as JSON, returns (decoded_value, True).
    If it is not valid JSON (corrupted entry), returns (raw_string, False).
    """
    try:
        return json.loads(raw), True
    except (TypeError, ValueError):
        return raw, False


def _is_corrupt(value: Any) -> bool:
    """A stored value is corrupt if it is a non-JSON string that survived
    storage (i.e. it is a str that is not itself valid JSON)."""
    if not isinstance(value, str):
        return False
    try:
        json.loads(value)
        return False
    except (TypeError, ValueError):
        return True


# ─── Cache metadata ───────────────────────────────────────────────────────────

@dataclass
class CacheEntry:
    """A single cache entry with provenance (versions) and TTL."""
    key: str
    value: Any
    created_at: float
    corpus_version: int
    index_version: int
    accessed_at: float
    access_count: int = 0
    ttl_seconds: Optional[float] = None

    @property
    def is_expired(self) -> bool:
        if self.ttl_seconds is None:
            return False
        return time.time() - self.created_at > self.ttl_seconds

    def is_stale(self, current_corpus_version: int, current_index_version: int) -> bool:
        return (self.corpus_version != current_corpus_version or
                self.index_version != current_index_version)


# ─── Abstract backend ─────────────────────────────────────────────────────────

class BaseCache(ABC):
    """Cache backend. All keys are opaque strings → CacheEntry."""

    @abstractmethod
    def get(self, key: str) -> Optional[CacheEntry]:
        ...

    @abstractmethod
    def set(self, entry: CacheEntry) -> None:
        ...

    @abstractmethod
    def delete(self, key: str) -> None:
        ...

    @abstractmethod
    def clear(self) -> None:
        ...

    @abstractmethod
    def keys(self) -> List[str]:
        """All stored keys (for version-based invalidation)."""

    def entries(self) -> List[Tuple[str, CacheEntry]]:
        """All stored (key, entry) pairs, WITHOUT touching access metadata."""
        return [(k, self.get(k)) for k in self.keys()]


# ─── In-memory backend ────────────────────────────────────────────────────────

class MemoryCache(BaseCache):
    """Small in-process store with TTL, LRU-ish eviction, hit/miss counters."""

    def __init__(self, max_size: int = 1024, default_ttl: Optional[float] = 300.0):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._store: Dict[str, CacheEntry] = {}
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[CacheEntry]:
        entry = self._store.get(key)
        if entry is None:
            self.misses += 1
            return None
        if entry.is_expired:
            self._store.pop(key, None)
            self.misses += 1
            return None
        # Refresh access metadata
        entry.accessed_at = time.time()
        entry.access_count += 1
        self.hits += 1
        return entry

    def set(self, entry: CacheEntry) -> None:
        # Evict the least-accessed entry when at capacity (LRU-ish).
        if len(self._store) >= self.max_size and entry.key not in self._store:
            victim = min(self._store, key=lambda k: self._store[k].access_count)
            self.delete(victim)
        entry.accessed_at = time.time()
        self._store[entry.key] = entry

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()

    def keys(self) -> List[str]:
        return list(self._store.keys())

    def entries(self) -> List[Tuple[str, CacheEntry]]:
        # Read directly (no access-counter bump) — used by invalidation.
        return list(self._store.items())

    def get_stats(self) -> Dict[str, Any]:
        total = len(self._store)
        return {
            "backend": "memory",
            "total_entries": total,
            "expired_entries": sum(1 for e in self._store.values() if e.is_expired),
            "utilization": (total / self.max_size) if self.max_size else 0.0,
            "hits": self.hits,
            "misses": self.misses,
        }


# ─── Durable disk backend (SQLite, WAL) ──────────────────────────────────────

class SqliteCache(BaseCache):
    """Restart-safe cache backend on SQLite (WAL journal mode for read-heavy
    workloads and concurrent readers). All files live inside locus_rag."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.hits = 0
        self.misses = 0
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        # WAL: readers don't block writers; robust for a single-machine service.
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS cache_entries (
                key            TEXT PRIMARY KEY,
                value          TEXT,
                created_at     REAL,
                corpus_version INTEGER,
                index_version  INTEGER,
                accessed_at    REAL,
                access_count   INTEGER,
                ttl_seconds    REAL
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cache_versions"
            " ON cache_entries (corpus_version, index_version)"
        )
        self._conn.commit()

    # ── helpers ──
    def _row_to_entry(self, row) -> Optional[CacheEntry]:
        if row is None:
            return None
        key, value, created_at, cv, iv, accessed_at, acc, ttl = row
        # row[1] from the database is already decoded by the caller or row builder
        return CacheEntry(
            key=key,
            value=value,
            created_at=float(created_at),
            corpus_version=int(cv),
            index_version=int(iv),
            accessed_at=float(accessed_at),
            access_count=int(acc),
            ttl_seconds=float(ttl) if ttl is not None else None,
        )

    def get(self, key: str) -> Optional[CacheEntry]:
        cur = self._conn.execute(
            "SELECT key, value, created_at, corpus_version, index_version,"
            " accessed_at, access_count, ttl_seconds FROM cache_entries WHERE key = ?",
            (key,),
        )
        row = cur.fetchone()
        if row is None:
            self.misses += 1
            return None
        value, ok = _json_decode(row[1])
        if not ok:
            # Corrupted payload — treat as miss (and drop it)
            self.delete(key)
            self.misses += 1
            return None
        entry = self._row_to_entry((row[0], value, row[2], row[3], row[4],
                                     row[5], row[6], row[7]))
        if entry is None:
            self.misses += 1
            return None
        if entry.is_expired:
            self._conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
            self._conn.commit()
            self.misses += 1
            return None
        entry.accessed_at = time.time()
        entry.access_count += 1
        self._conn.execute(
            "UPDATE cache_entries SET accessed_at = ?, access_count = access_count + 1"
            " WHERE key = ?",
            (entry.accessed_at, key),
        )
        self._conn.commit()
        self.hits += 1
        return entry

    def set(self, entry: CacheEntry) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO cache_entries"
            " (key, value, created_at, corpus_version, index_version,"
            "  accessed_at, access_count, ttl_seconds)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (entry.key,
             _json_encode(entry.value),
             float(entry.created_at),
             int(entry.corpus_version),
             int(entry.index_version),
             float(entry.accessed_at),
             int(entry.access_count),
             entry.ttl_seconds),
        )
        self._conn.commit()

    def delete(self, key: str) -> None:
        self._conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
        self._conn.commit()

    def clear(self) -> None:
        self._conn.execute("DELETE FROM cache_entries")
        self._conn.commit()

    def keys(self) -> List[str]:
        cur = self._conn.execute("SELECT key FROM cache_entries")
        return [r[0] for r in cur.fetchall()]

    def entries(self) -> List[Tuple[str, CacheEntry]]:
        """Read all (key, entry) pairs without touching access metadata."""
        cur = self._conn.execute(
            "SELECT key, value, created_at, corpus_version, index_version,"
            " accessed_at, access_count, ttl_seconds FROM cache_entries"
        )
        return [(row[0], self._row_to_entry(row)) for row in cur.fetchall()]

    def get_stats(self) -> Dict[str, Any]:
        cur = self._conn.execute("SELECT COUNT(*) FROM cache_entries")
        total = cur.fetchone()[0]
        return {
            "backend": "sqlite",
            "total_entries": total,
            "hits": self.hits,
            "misses": self.misses,
        }

    def close(self) -> None:
        self._conn.close()


# ─── Version-aware lookup helper ──────────────────────────────────────────────

def _versioned_get(backend: BaseCache, key: str,
                   corpus_version: int, index_version: int) -> Optional[CacheEntry]:
    """Fetch `key` but treat a version-mismatched entry as a miss (and evict it)."""
    entry = backend.get(key)
    if entry is None:
        return None
    if entry.is_stale(corpus_version, index_version):
        backend.delete(key)
        return None
    return entry


# ─── Query cache (query → answer) ────────────────────────────────────────────

class QueryCache:
    """Version-aware cache of query → answer (JSON-serializable value)."""

    def __init__(self, cache: Optional[BaseCache] = None,
                 default_ttl: Optional[float] = 300.0):
        self.cache = cache or MemoryCache(default_ttl=default_ttl)
        self.default_ttl = default_ttl

    def _key(self, query: str, cv: int, iv: int) -> str:
        return f"q{_sha(query)}:c{cv}:i{iv}"

    def lookup(self, query: str, corpus_version: int, index_version: int) -> Optional[Any]:
        entry = _versioned_get(self.cache, self._key(query, corpus_version, index_version),
                               corpus_version, index_version)
        return entry.value if entry is not None else None

    def store(self, query: str, value: Any, corpus_version: int, index_version: int,
              ttl: Optional[float] = None) -> None:
        entry = CacheEntry(
            key=self._key(query, corpus_version, index_version),
            value=value,
            created_at=time.time(),
            corpus_version=corpus_version,
            index_version=index_version,
            accessed_at=time.time(),
            ttl_seconds=ttl if ttl is not None else self.default_ttl,
        )
        self.cache.set(entry)

    def invalidate_corpus(self, old_version: int) -> None:
        """Drop every entry tagged with an old corpus version."""
        self._drop_matching(lambda e: e.corpus_version == old_version,
                            f"corpus v{old_version}")

    def invalidate_index(self, old_version: int) -> None:
        """Drop every entry tagged with an old index version."""
        self._drop_matching(lambda e: e.index_version == old_version,
                            f"index v{old_version}")

    def _drop_matching(self, pred: Callable[[CacheEntry], bool], label: str) -> int:
        """Backend-agnostic version invalidation via ``entries()``."""
        doomed = [k for k, e in self.cache.entries() if pred(e)]
        for k in doomed:
            self.cache.delete(k)
        logger.info("Invalidated %d cache entries (%s)", len(doomed), label)
        return len(doomed)

    def clear(self) -> None:
        self.cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        return self.cache.get_stats()


# ─── Retrieval candidate cache ───────────────────────────────────────────────

def _filters_fingerprint(filters: Optional[Dict[str, Any]]) -> str:
    """Canonical, order-independent fingerprint of metadata filters."""
    if not filters:
        return ""
    items = sorted((str(k), repr(v)) for k, v in filters.items())
    return hashlib.sha256(repr(items).encode("utf-8")).hexdigest()[:12]


class RetrievalCache:
    """Cache the ranked retrieval candidate list for a query, keyed by query
    hash + corpus/index versions + top_k + rrf_k + filters. Values are
    lists of RetrievalCandidate."""

    def __init__(self, cache: Optional[BaseCache] = None,
                 default_ttl: Optional[float] = 300.0):
        self.cache = cache or MemoryCache(default_ttl=default_ttl)
        self.default_ttl = default_ttl

    @staticmethod
    def _key(query: str, corpus_version: int, index_version: int,
             top_k: int, rrf_k: int, filters: Optional[Dict[str, Any]]) -> str:
        return (f"r{_sha(query)}:c{corpus_version}:i{index_version}:"
                f"k{top_k}:rk{rrf_k}:f{_filters_fingerprint(filters)}")

    def lookup(self, query: str, corpus_version: int, index_version: int,
               top_k: int, rrf_k: int, filters: Optional[Dict[str, Any]]) -> Optional[List[Any]]:
        key = self._key(query, corpus_version, index_version, top_k, rrf_k, filters)
        entry = _versioned_get(self.cache, key, corpus_version, index_version)
        if entry is None:
            return None
        value = entry.value
        if not isinstance(value, list):
            # Corrupted payload — treat as miss (and drop it)
            self.cache.delete(key)
            return None
        return _deserialize_candidates(value)

    def store(self, query: str, candidates: List[Any], corpus_version: int,
              index_version: int, top_k: int, rrf_k: int,
              filters: Optional[Dict[str, Any]], ttl: Optional[float] = None) -> None:
        key = self._key(query, corpus_version, index_version, top_k, rrf_k, filters)
        entry = CacheEntry(
            key=key,
            value=_serialize_candidates(candidates),
            created_at=time.time(),
            corpus_version=corpus_version,
            index_version=index_version,
            accessed_at=time.time(),
            ttl_seconds=ttl if ttl is not None else self.default_ttl,
        )
        self.cache.set(entry)

    def invalidate_corpus(self, old_version: int) -> None:
        self._drop(lambda e: e.corpus_version == old_version, f"corpus v{old_version}")

    def invalidate_index(self, old_version: int) -> None:
        self._drop(lambda e: e.index_version == old_version, f"index v{old_version}")

    def _drop(self, pred: Callable[[CacheEntry], bool], label: str) -> int:
        doomed = [k for k, e in self.cache.entries() if pred(e)]
        for k in set(doomed):
            self.cache.delete(k)
        logger.info("Invalidated %d retrieval-cache entries (%s)", len(set(doomed)), label)
        return len(set(doomed))

    def clear(self) -> None:
        self.cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        return self.cache.get_stats()


def _serialize_candidates(candidates: List[Any]) -> List[Dict[str, Any]]:
    """RetrievalCandidate (or dict) list → compact JSON-safe dict list."""
    out = []
    for c in candidates:
        if hasattr(c, "chunk_id"):
            out.append({
                "chunk_id": c.chunk_id,
                "doc_id": getattr(c, "doc_id", ""),
                "score": float(getattr(c, "score", 0.0)),
                "text": getattr(c, "text", ""),
                "source_locator": dict(getattr(c, "source_locator", {}) or {}),
                "index_name": getattr(c, "index_name", ""),
                "metadata": dict(getattr(c, "metadata", {}) or {}),
            })
        else:
            out.append(dict(c))
    return out


def _deserialize_candidates(raw: Any) -> List[Any]:
    """JSON-safe dict list → RetrievalCandidate list (objects preserved on read)."""
    from src.indexing.vector import RetrievalCandidate
    out = []
    for d in raw:
        if isinstance(d, dict) and "chunk_id" in d:
            out.append(RetrievalCandidate(
                chunk_id=d.get("chunk_id", ""),
                doc_id=d.get("doc_id", ""),
                score=d.get("score", 0.0),
                text=d.get("text", ""),
                source_locator=d.get("source_locator", {}) or {},
                index_name=d.get("index_name", ""),
                metadata=d.get("metadata", {}) or {},
            ))
        else:
            out.append(d)
    return out


# ─── Embedding reuse cache ────────────────────────────────────────────────────

class EmbeddingCache:
    """Cache of text→embedding vector list, keyed by sha256(text) *and* the
    embedding model name/version so incompatible embeddings are never reused.

    Embedding computation dominates re-index cost; if a document changes but
    most chunk text is unchanged, the unchanged chunk embeddings are reused
    (incremental invalidation by content, not by doc).
    """

    def __init__(self, cache: Optional[BaseCache] = None,
                 default_ttl: Optional[float] = None):
        self.cache = cache or MemoryCache(default_ttl=default_ttl)
        self.default_ttl = default_ttl

    def _key(self, text: str, model_name: str, model_version: str) -> str:
        return f"e{_sha(text)}:m{_sha(model_name)}:v{_sha(model_version)}"

    def lookup(self, text: str, model_name: str = "default",
               model_version: str = "0") -> Optional[List[float]]:
        entry = self.cache.get(self._key(text, model_name, model_version))
        return entry.value if entry is not None else None

    def store(self, text: str, embedding: List[float], model_name: str = "default",
              model_version: str = "0", ttl: Optional[float] = None) -> None:
        entry = CacheEntry(
            key=self._key(text, model_name, model_version),
            value=embedding,
            created_at=time.time(),
            corpus_version=0,
            index_version=0,
            accessed_at=time.time(),
            ttl_seconds=ttl,
        )
        self.cache.set(entry)

    def get_stats(self) -> Dict[str, Any]:
        return self.cache.get_stats()


# ─── Cached retriever (narrow wrapper) ───────────────────────────────────────

class CachedRetriever:
    """Wrap a HybridRetriever with a RetrievalCache.

    The wrapper sits at the *retrieval* boundary — everything upstream
    (evidence assembly, verification, answer generation) always runs against
    the returned candidates.  The cache only short-circuits the expensive
    index scans; it never bypasses evidence/verification logic.

    Correctness: the cache key includes query, corpus/index versions, top_k,
    rrf_k and the filters fingerprint, so no cached result can be served for a
    different retrieval context.
    """

    def __init__(
        self,
        inner: Any,
        retrieval_cache: Optional[RetrievalCache] = None,
        corpus_version: int = 0,
        index_version: int = 0,
        rrf_k: int = 60,
    ):
        self.inner = inner
        self.cache = retrieval_cache or RetrievalCache()
        self.corpus_version = corpus_version
        self.index_version = index_version
        self.rrf_k = rrf_k

    def retrieve(
        self,
        query: str,
        top_k: int = 20,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[RetrievalCandidate]:
        # Full context key (top_k + rrf_k + filters) ensures we never reuse a
        # result that would differ under these parameters.
        cached = self.cache.lookup(query, self.corpus_version, self.index_version,
                                   top_k, self.rrf_k, filters)
        if cached is not None:
            return cached

        fresh = self.inner.retrieve(query, top_k=top_k, filters=filters)
        self.cache.store(query, fresh, self.corpus_version, self.index_version,
                         top_k, self.rrf_k, filters)
        return fresh

    def invalidate(self) -> None:
        """Explicitly clear the retrieval cache (e.g. after a fresh ingest that
        did not bump versions through the pipeline)."""
        self.cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        return self.cache.get_stats()


def cached_retrieve(
    query: str,
    dense_index: Optional[Any] = None,
    bm25_index: Optional[Any] = None,
    exact_index: Optional[Any] = None,
    metadata_index: Optional[Any] = None,
    top_k: int = 20,
    filters: Optional[Dict[str, Any]] = None,
    retrieval_cache: Optional[RetrievalCache] = None,
    corpus_version: int = 0,
    index_version: int = 0,
    rrf_k: int = 60,
) -> List[RetrievalCandidate]:
    """Module-level convenience mirroring ``src.retrieval.hybrid.retrieve`` but
    with a retrieval cache wrapped around it."""
    from src.retrieval.hybrid import HybridRetriever
    inner = HybridRetriever(
        dense=dense_index,
        bm25=bm25_index,
        exact=exact_index,
        metadata=metadata_index,
        rrf_k=rrf_k,
    )
    cached = CachedRetriever(
        inner=inner,
        retrieval_cache=retrieval_cache,
        corpus_version=corpus_version,
        index_version=index_version,
        rrf_k=rrf_k,
    )
    return cached.retrieve(query, top_k=top_k, filters=filters)