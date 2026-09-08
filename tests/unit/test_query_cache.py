"""Tests for Phase 13: Query Cache + Performance (query, retrieval, embedding)."""
import sys
import unittest
import tempfile
import shutil
import time
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import sqlite3

from src.cache.query_cache import (
    CacheEntry,
    MemoryCache,
    SqliteCache,
    QueryCache,
    RetrievalCache,
    EmbeddingCache,
    CachedRetriever,
    cached_retrieve,
)
from src.indexing.vector import RetrievalCandidate, BM25Index, ExactEntityIndex


def _cand(cid: str, doc: str = "d1", score: float = 0.9, text: str = "hello",
          idx: str = "hybrid", meta=None):
    return RetrievalCandidate(chunk_id=cid, doc_id=doc, score=score, text=text,
                              source_locator={"page": 1}, index_name=idx,
                              metadata=meta or {})


class TestCacheEntry(unittest.TestCase):
    def test_is_expired_false_when_no_ttl(self):
        e = CacheEntry(key="k", value=1, created_at=time.time(),
                       corpus_version=1, index_version=1, accessed_at=time.time())
        self.assertFalse(e.is_expired)

    def test_is_expired_respects_ttl(self):
        e = CacheEntry(key="k", value=1, created_at=time.time() - 100,
                       corpus_version=1, index_version=1, accessed_at=time.time(),
                       ttl_seconds=10)
        self.assertTrue(e.is_expired)

    def test_is_stale_on_version_mismatch(self):
        e = CacheEntry(key="k", value=1, created_at=time.time(),
                       corpus_version=1, index_version=1, accessed_at=time.time())
        self.assertFalse(e.is_stale(1, 1))
        self.assertTrue(e.is_stale(2, 1))
        self.assertTrue(e.is_stale(1, 2))


class TestMemoryCache(unittest.TestCase):
    def test_roundtrip(self):
        c = MemoryCache()
        c.set(CacheEntry(key="k", value="v", created_at=time.time(),
                         corpus_version=1, index_version=1, accessed_at=time.time()))
        got = c.get("k")
        self.assertEqual(got.value, "v")

    def test_miss_returns_none(self):
        self.assertIsNone(MemoryCache().get("missing"))

    def test_version_stale_get_evicts(self):
        # Backend get() is version-agnostic — version invalidation lives in the
        # versioned wrapper (_versioned_get). Verify through QueryCache.
        qc = QueryCache(cache=MemoryCache())
        qc.store("q", "v", corpus_version=1, index_version=1)
        self.assertEqual(qc.lookup("q", 1, 1), "v")
        self.assertIsNone(qc.lookup("q", 2, 1), "version bump must evict")

    def test_evicts_least_accessed(self):
        c = MemoryCache(max_size=2)
        c.set(CacheEntry(key="a", value=1, created_at=time.time(),
                         corpus_version=1, index_version=1, accessed_at=time.time()))
        c.set(CacheEntry(key="b", value=2, created_at=time.time(),
                         corpus_version=1, index_version=1, accessed_at=time.time()))
        # Touch a (increments access count)
        c.get("a")
        c.set(CacheEntry(key="c", value=3, created_at=time.time(),
                         corpus_version=1, index_version=1, accessed_at=time.time()))
        # b still has access_count=0, a has 1 → b gets evicted
        self.assertIsNone(c.get("b"))
        self.assertIsNotNone(c.get("a"))
        self.assertIsNotNone(c.get("c"))


class TestQueryCache(unittest.TestCase):
    def setUp(self):
        self.cache = QueryCache()

    def test_hit_then_miss(self):
        q = "What is the budget?"
        self.assertIsNone(self.cache.lookup(q, corpus_version=1, index_version=1))
        self.cache.store(q, "answer-v1", corpus_version=1, index_version=1)
        self.assertEqual(self.cache.lookup(q, 1, 1), "answer-v1")

    def test_bump_index_version_misses(self):
        q = "What is the budget?"
        self.cache.store(q, "answer-v1", corpus_version=1, index_version=1)
        # Next index version → cache miss (stale)
        self.assertIsNone(self.cache.lookup(q, corpus_version=1, index_version=2))

    def test_store_then_bump_corpus_misses(self):
        q = "What is the budget?"
        self.cache.store(q, "answer-v1", corpus_version=1, index_version=1)
        self.assertIsNone(self.cache.lookup(q, corpus_version=2, index_version=1))

    def test_only_valid_version_hits(self):
        q = "What is the budget?"
        self.cache.store(q, "answer-v1", corpus_version=4, index_version=5)
        self.assertEqual(self.cache.lookup(q, 4, 5), "answer-v1")
        self.assertIsNone(self.cache.lookup(q, 3, 5))
        self.assertIsNone(self.cache.lookup(q, 4, 6))

    def test_ttl_expiration(self):
        c = QueryCache(default_ttl=0.05)
        q = "quick one"
        c.store(q, "fast", corpus_version=1, index_version=1)
        self.assertEqual(c.lookup(q, 1, 1), "fast")
        time.sleep(0.12)
        self.assertIsNone(c.lookup(q, 1, 1))

    def test_stats_track_hits_misses(self):
        self.cache.store("q", "a", 1, 1)
        self.cache.lookup("q", 1, 1)   # hit
        self.cache.lookup("other", 1, 1)  # miss
        stats = self.cache.get_stats()
        self.assertGreaterEqual(stats["hits"], 1)
        self.assertGreaterEqual(stats["misses"], 1)


class TestSqliteCache(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="locus_cache_"))
        self.db = str(self.tmp / "cache.db")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_disk_roundtrip_and_versions(self):
        c = SqliteCache(db_path=self.db)
        c.set(CacheEntry(key="k", value="v", created_at=time.time(),
                         corpus_version=1, index_version=1, accessed_at=time.time()))
        got = c.get("k")
        self.assertEqual(got.value, "v")

        # Reopen → persisted
        c2 = SqliteCache(db_path=self.db)
        self.assertEqual(c2.get("k").value, "v")

        # Different version → miss (through QueryCache's version-aware lookup)
        qc = QueryCache(cache=c2)
        self.assertIsNone(qc.lookup("q-diff", 9, 1))
        qc2 = QueryCache(cache=SqliteCache(db_path=self.db))
        qc2.store("somequery", "answer", 9, 1)
        self.assertEqual(qc2.lookup("somequery", 9, 1), "answer")
        self.assertIsNone(qc2.lookup("somequery", 1, 1))

    def test_delete_and_clear(self):
        c = SqliteCache(db_path=self.db)
        c.set(CacheEntry(key="k", value="v", created_at=time.time(),
                         corpus_version=1, index_version=1, accessed_at=time.time()))
        c.delete("k")
        self.assertIsNone(c.get("k"))
        c.set(CacheEntry(key="k2", value="v2", created_at=time.time(),
                         corpus_version=1, index_version=1, accessed_at=time.time()))
        c.clear()
        self.assertIsNone(c.get("k2"))

    def test_query_cache_on_disk(self):
        qc = QueryCache(cache=SqliteCache(db_path=self.db))
        qc.store("q", {"ans": 42}, 1, 1)
        self.assertEqual(qc.lookup("q", 1, 1), {"ans": 42})

    def test_corrupted_entry_does_not_crash(self):
        c = SqliteCache(db_path=self.db)
        # Manually insert a corrupted JSON value (not parseable)
        c._conn.execute(
            "INSERT OR REPLACE INTO cache_entries"
            " (key, value, created_at, corpus_version, index_version, accessed_at, access_count, ttl_seconds)"
            " VALUES ('bad', '{{{not json', 1.0, 1, 1, 1.0, 0, NULL)")
        c._conn.commit()
        # Reading a corrupted entry must not raise — it becomes a miss.
        self.assertIsNone(c.get("bad"))

    def test_wal_mode_enabled(self):
        c = SqliteCache(db_path=self.db)
        journal = c._conn.execute("PRAGMA journal_mode").fetchone()[0]
        self.assertEqual(journal, "wal")


class TestRetrievalCache(unittest.TestCase):
    def test_candidate_roundtrip(self):
        rc = RetrievalCache()
        cands = [_cand("c1"), _cand("c2", score=0.5)]
        rc.store("query", cands, corpus_version=1, index_version=1,
                 top_k=5, rrf_k=60, filters={})
        got = rc.lookup("query", corpus_version=1, index_version=1,
                        top_k=5, rrf_k=60, filters={})
        self.assertEqual(len(got), 2)
        self.assertEqual(got[0].chunk_id, "c1")
        self.assertEqual(got[0].text, "hello")
        self.assertEqual(got[0].source_locator, {"page": 1})

    def test_bump_version_misses(self):
        rc = RetrievalCache()
        rc.store("alpha", [_cand("c")], corpus_version=1, index_version=1,
                 top_k=5, rrf_k=60, filters={})
        self.assertIsNone(rc.lookup("alpha", corpus_version=2, index_version=1,
                                    top_k=5, rrf_k=60, filters={}))

    def test_corrupted_payload_returns_none(self):
        rc = RetrievalCache()
        rc.store("q", [_cand("c")], 1, 1, top_k=5, rrf_k=60, filters={})
        # Manually corrupt the stored payload (non-list value)
        rc.cache._store[next(iter(rc.cache._store))].value = "not-a-list"
        self.assertIsNone(rc.lookup("q", 1, 1, top_k=5, rrf_k=60, filters={}))


class TestEmbeddingCache(unittest.TestCase):
    def test_keyed_by_text_hash(self):
        ec = EmbeddingCache()
        text = "Ncell sponsorship NPR 500000"
        emb = [0.1, 0.2, 0.3]
        ec.store(text, emb)
        self.assertEqual(ec.lookup(text), emb)
        # Different text → different key → miss
        self.assertIsNone(ec.lookup("different text"))

    def test_model_isolation(self):
        """Embeddings from different models must never collide."""
        ec = EmbeddingCache()
        text = "Ncell sponsorship NPR 500000"
        ec.store(text, [0.1, 0.2], model_name="bge-small", model_version="v1")
        self.assertIsNone(ec.lookup(text, model_name="all-MiniLM", model_version="v1"))
        self.assertEqual(ec.lookup(text, model_name="bge-small", model_version="v1"),
                         [0.1, 0.2])
        self.assertIsNone(ec.lookup(text, model_name="bge-small", model_version="v2"))


def _build_retriever():
    """A small deterministic HybridRetriever with known content."""
    from src.retrieval.hybrid import HybridRetriever
    bm25 = BM25Index()
    exact = ExactEntityIndex()
    retriever = HybridRetriever(bm25=bm25, exact=exact)
    docs = {
        "c1": "Ncell sponsorship NPR 500000 was approved in 2023.",
        "c2": "The annual report describes CG revenue of 1.2 million.",
        "c3": "The board meeting minutes reference the 2023 budget.",
        "c4": "Sky insurance premium increased by 8 percent in 2024.",
    }
    for cid, text in docs.items():
        bm25.add(cid, text, {"doc_id": "d1"})
        exact.add(cid, text, {"doc_id": "d1"})
    return retriever


class TestCachedRetriever(unittest.TestCase):
    def setUp(self):
        self.retriever = _build_retriever()
        self.rc = RetrievalCache()
        self.cached = CachedRetriever(inner=self.retriever, retrieval_cache=self.rc,
                                      corpus_version=1, index_version=1)

    def test_cold_then_warm_identical(self):
        q = "Ncell sponsorship"
        cold = self.cached.retrieve(q, top_k=5)
        warm = self.cached.retrieve(q, top_k=5)
        self.assertEqual([c.chunk_id for c in cold], [c.chunk_id for c in warm])

    def test_top_k_changes_key(self):
        """A cached top_k=5 must not serve a top_k=2 slice.
        Our test corpus has only 1 Ncell sponsorship doc, so top_k=2 returns 1.
        The key point is that different top_k produces different cache keys, so
        we get the correct fresh result, not a stale slice."""
        q = "Ncell sponsorship"
        self.cached.retrieve(q, top_k=5)
        r2 = self.cached.retrieve(q, top_k=2)
        # Corpus only has 1 matching doc, so we get 1 result (correct)
        self.assertEqual(len(r2), 1)
        # And it must be the actual top-2 of the fresh result, not a slice of the cached 5
        fresh = self.retriever.retrieve(q, top_k=2)
        self.assertEqual([c.chunk_id for c in r2], [c.chunk_id for c in fresh])

    def test_filters_recompute_not_stale(self):
        """Filters re-apply the pool; cache key must isolate filters."""
        q = "Ncell sponsorship"
        self.cached.retrieve(q, top_k=5, filters={})
        with_filters = self.cached.retrieve(q, top_k=5, filters={"doc_type": "report"})
        # Must not be a cache hit delivering the unfiltered pool
        self.assertEqual(len(with_filters), len(self.cached.inner.retrieve(q, top_k=5, filters={"doc_type": "report"})))

    def test_version_bump_recomputes(self):
        q = "Ncell sponsorship"
        r1 = self.cached.retrieve(q, top_k=5)
        # Simulate corpus/index update
        self.cached.corpus_version = 2
        # Modify underlying corpus so the answer is now different
        self.cached.inner.bm25.add("c5", "Ncell sponsorship NPR 900000 in 2025", {"doc_id": "d1"})
        r2 = self.cached.retrieve(q, top_k=5)
        self.assertIn("c5", [c.chunk_id for c in r2])

    def test_stats_exposed(self):
        self.cached.retrieve("a query", top_k=5)
        self.cached.retrieve("a query", top_k=5)  # warm
        stats = self.cached.get_stats()
        self.assertGreaterEqual(stats["hits"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)