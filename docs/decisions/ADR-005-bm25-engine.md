# ADR-005: BM25 Engine

**Status:** Proposed

## Problem
Robust lexical retrieval is essential for exact matches, acronyms, IDs, and names that semantic embeddings may miss. A BM25 implementation is needed alongside dense retrieval.

## Candidates Considered
1. **bm25s** — Pure Python + NumPy; fast; good memory efficiency; local
2. **rank_bm25** — Simple; widely used; pure Python
3. **SQLite FTS5** — Built-in; no extra dependency; excellent full-text search; persistent
4. **Elasticsearch** — Powerful; distributed; requires infrastructure; overkill for local V1

## Experiment Plan
1. Index 5,000 representative LOCUS chunks
2. Test on exact queries (names, IDs, amounts), acronym queries, misspelled queries, partial name queries
3. Measure: retrieval precision, query latency, index size, memory usage
4. Compare with and without BM25 in hybrid RRF fusion

## Decision Criteria
- Exact match recall ≥ 98% for known entity names
- Query latency p95 < 50ms
- Index size < 10% of corpus text size
- Persistent storage (survives restart)

## Revisit Conditions
- Re-evaluate if query volume exceeds single-machine capacity
- Re-evaluate if corpus exceeds 1M chunks
