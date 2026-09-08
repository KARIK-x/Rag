# PROGRESS - LOCUS RAG

## Current Phase
- **Phase 8 — Evidence Assembly & Verification & Generation** (in progress)

## Completed

### Phase 0 to Phase 7 — Foundation, Ingestion, Extraction, Normalization, Classification, Dedup, Indexing, Hybrid Retrieval, Query Understanding ✅
- 114/114 unit tests pass cleanly.
- Real LOCUS corpus benchmarked (21 extracted documents).
- Fixed critical retrieval provenance defect in BM25Index.
- Removed premature query-analyzer filtering anti-pattern.

### Phase 11 — Advanced Retrieval Safety (Recall Safety Net) ✅
- Implemented bounded retrieval ladder (`RecallSafetyNet`): initial hybrid → expanded pool → exact phrase → broadened lexical → query reformulation → document-level.
- Verified robust fallback behavior and zero-crash on unanswerable queries.

## Open Issues / Next Actions
- Track the "NPR" exact-match issue as a known retrieval/indexing edge case.
- Phase 8 (User Feedback Loop) can be added later per spec §101.

## Decisions (ADRs)
- ADR-001 PyMuPDF ✅, ADR-002 Tesseract ✅, ADR-003 Dense embeddings ✅, ADR-004 BM25 ✅, ADR-005 Exact/Entity ✅, ADR-006 Chunking ✅, ADR-007 Structured Data ✅, ADR-008 Normalizer ✅, ADR-008 Dedup ✅

## Test Results Summary
- **105/105 unit tests pass** across all phases (0–7).
- **18 real LOCUS documents** benchmarked: 8/9 queries pass (1 known edge-case flagged).
- **Locust corpus**: 224 chunks indexed, 5 quality tiers (failed/high/medium/low/unknown).

## Next Phase (Not Yet Implemented)
- **Phase 8 — User Feedback Loop**: capture → review → root cause → regression test → controlled split.

## Files Summary
- `src/chunking/structural.py` — heading/page/table-aware chunker
- `src/indexing/vector.py` — ExactEntityIndex, BM25Index, DenseVectorIndex, MetadataIndex, HybridRetriever
- `src/retrieval/hybrid.py` — RRF fusion, HybridRetriever, retrieval orchestration
- `src/retrieval/query_router.py` — IntentClassifier, QueryRouter, QueryNormalizer
- `src/classification/classifier.py` — DocumentClassifier, AuthorityStatus
- `src/dedup/deduplicator.py` — Deduplicator, DedupCluster, DedupIndex
- `tests/unit/` — 105+ unit tests across all phases
- `eval/metrics/extraction_metrics.py` — Comprehensive corpus quality report

## Phase Boundary
**Phase 7 is complete.** Do not implement Phase 8 (User Feedback Loop) unless explicitly requested. The architecture is ready for Phase 8 integration per spec §101.