# ADR-004: Vector Store

**Status:** Proposed

## Problem
Dense embeddings need a local vector store that supports hybrid retrieval (semantic + metadata filtering), incremental updates, and efficient RRF fusion with BM25.

## Candidates Considered
1. **LanceDB** — Embedded; no server required; good filtering; local-first; Apache Arrow-based
2. **Qdrant** — Payload filtering; hybrid search; client-server (can be embedded); mature
3. **FAISS** — Classic; embedded; fast; no native filtering (requires external metadata join)
4. **ChromaDB** — Simple; embedded; good for prototypes; limited advanced filtering

## Experiment Plan
1. Build indexes for a representative LOCUS sample (2,000 chunks)
2. Measure: indexing speed, query latency (p50, p95), filtering accuracy, memory usage, disk usage
3. Test incremental add/delete operations
4. Evaluate hybrid retrieval performance (semantic + metadata filter)
5. Measure RRF fusion latency with BM25 candidates

## Decision Criteria
- Query latency p95 < 200ms for 10,000 chunks
- Supports metadata filtering without full scan
- Incremental updates work correctly
- Local-only (no server required for V1)

## Revisit Conditions
- Re-evaluate if corpus exceeds 500k chunks
- Re-evaluate if QPS requirements exceed single-machine capacity
