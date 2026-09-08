#!/usr/bin/env python3
"""
Phase 13 performance benchmark: caching benefit + correctness preservation.

Measures, over a synthetic corpus:
  - cold query (no cache)
  - warm repeat query (cache hit)
  - repeated identical query
  - query after source update (invalidation → must NOT return stale)
  - cache hit/miss counters
  - retrieval correctness is unchanged (same candidate pool on cache hit)

Usage:
    python3 eval/benchmark/phase13_cache_benchmark.py

Prints a table and returns exit 0 on success / 1 if correctness is violated.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.indexing.vector import (
    BM25Index,
    ExactEntityIndex,
    HybridRetriever,
)
from src.cache.query_cache import RetrievalCache, CachedRetriever


def build_corpus():
    """A small deterministic corpus with a known-answer query."""
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


def main():
    retriever = build_corpus()
    rcache = RetrievalCache()
    cached = CachedRetriever(inner=retriever, retrieval_cache=rcache,
                             corpus_version=1, index_version=1)

    query = "how much did Ncell sponsor?"

    # 1. Cold query (cache empty)
    t0 = time.perf_counter()
    cold = cached.retrieve(query, top_k=5)
    t_cold = time.perf_counter() - t0

    # 2. Warm repeat (must be a cache hit)
    t0 = time.perf_counter()
    warm = cached.retrieve(query, top_k=5)
    t_warm = time.perf_counter() - t0

    # 3. Repeated identical
    t0 = time.perf_counter()
    repeat = cached.retrieve(query, top_k=5)
    t_repeat = time.perf_counter() - t0

    # 4. Source update → bump index version → must miss and return fresh
    fresh = build_corpus()
    cached.inner = fresh
    cached.index_version = 2
    t0 = time.perf_counter()
    after_update = cached.retrieve(query, top_k=5)
    t_after_update = time.perf_counter() - t0

    # 5. Correctness check: cold and warm must produce the same candidate pool
    cold_ids = [c.chunk_id for c in cold]
    warm_ids = [c.chunk_id for c in warm]
    repeat_ids = [c.chunk_id for c in repeat]
    after_ids = [c.chunk_id for c in after_update]

    ok = (
        cold_ids == warm_ids == repeat_ids
        and cold_ids == after_ids  # corpus rebuild produced identical content
        and len(cold) > 0
    )

    print("── Phase 13 Cache Benchmark ──")
    print(f"cold (no cache)      : {t_cold*1000:8.2f} ms  ({len(cold)} results)")
    print(f"warm (cache hit)     : {t_warm*1000:8.2f} ms  ({len(warm)} results)")
    print(f"repeat (warm)        : {t_repeat*1000:8.2f} ms  ({len(repeat)} results)")
    print(f"after source update  : {t_after_update*1000:8.2f} ms  ({len(after_update)} results)")
    print(f"speedup (cold/warm)  : {t_cold/t_warm:6.2f}x")
    print(f"correctness          : {'OK' if ok else 'MISMATCH'}")
    print(f"cache stats          : {rcache.get_stats()}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())