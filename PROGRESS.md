# PROGRESS - LOCUS RAG

## Current Phase
- **Phase 14 — Resilience + Security** ✅ (Complete)

## Completed

### Phase 0 to Phase 7 — Foundation, Ingestion, Extraction, Normalization, Classification, Dedup, Indexing, Hybrid Retrieval, Query Understanding ✅
- 114/114 unit tests pass cleanly.
- Real LOCUS corpus benchmarked (21 extracted documents).
- Fixed critical retrieval provenance defect in BM25Index.
- Removed premature query-analyzer filtering anti-pattern.

### Phase 11 — Advanced Retrieval Safety (Recall Safety Net) ✅
- Implemented bounded retrieval ladder (`RecallSafetyNet`): initial hybrid → expanded pool → exact phrase → broadened lexical → query reformulation → document-level.
- Verified robust fallback behavior and zero-crash on unanswerable queries.

### Phase 8 — Evidence Assembly & Verification & Generation ✅
- Implemented `EvidenceAssembler` with parent/neighbor expansion, sufficiency checks, and conflict detection (draft vs final).
- Implemented `Verifier` with faith/confidence scoring and ABSTAIN triggering on insufficient evidence.
- Implemented `AnswerBuilder` with evidence-grounded answer synthesis and `[N]` citation markers.
- All modules integrate with `src/pipeline/models.EvidenceSet` provenance.
- 15 unit tests pass for evidence/verification/generation/export path.

### Phase 10 — Structured Actions/Outputs ✅
- Implemented `Exporter` with CSV, TSV, JSON, Markdown formats.
- Export artifacts include metadata/mime_type/filename for provenance.
- All formats respect missing values and preserve source coordinates.
- 6 unit tests pass for export formats.

### Phase 12 — Sync/Incremental Processing ✅
- Drive Changes API integration with the existing catalog
- Changed-document detection via `modified_time` + `size` comparison (no fictional `revision_id`)
- Selective reprocessing: only process what changed
- Stale-index invalidation
- Versioned corpus/index snapshots with atomic swaps
- Permission-aware design (catalog read-only, all writes in locus_rag)
- Idempotent operation; crash recovery support
- Catalog is strictly read-only — all writes to engine's own `rag_state.db`
- Failure-retry watermark: baseline advances only when all files succeed; failed files stay retryable
- Trashed/deleted file exclusion (`trashed = 0` filter)
- Checkpoint-aware significant-change detection: unchanged files skipped even if appearing as "changed"
- 9/9 incremental-sync tests passed

## Open Issues / Next Actions
- Track the "NPR" exact-match issue as a known retrieval/indexing edge case.
- Begin Phase 13: Caching + Performance when ready.

## Decisions (ADRs)
- ADR-001 PyMuPDF ✅, ADR-002 Tesseract ✅, ADR-003 Dense embeddings ✅, ADR-004 BM25 ✅, ADR-005 Exact/Entity ✅, ADR-006 Chunking ✅, ADR-007 Structured Data ✅, ADR-008 Normalizer ✅, ADR-008 Dedup ✅, ADR-009 Retrieval Defect Fixes ✅

## Test Results Summary
- **138/138 unit tests pass** across all phases (0–12).
- **18 real LOCUS documents** benchmarked: 8/9 queries pass (1 known NPR exact-match edge case).
- **Locust corpus**: 224 chunks indexed, 5 quality tiers (failed/high/medium/low/unknown).
- **Phase 12 focused tests**: 9/9 passed (no-changes, with-changes, trashed exclusion, checkpoint-aware skip, failure-retry watermark).

## Next Phase
- **Phase 14 — Resilience + Security**: ✅ Complete.
  - Bounded exponential-backoff retry keyed to transient-failure classification (`retry_with_backoff` /
    `is_transient_error`); permanent errors (auth/permission/404/unsupported) fail immediately, never retried.
  - Safe-subpath construction and Drive boundary enforcement: `safe_subpath` rejects path traversal from
    Drive-file-ID-derived paths; `assert_not_in_locus_drive` refuses any write under /Users/ashim/locus_drive.
  - Document-level dead-lettering: persistent failed-attempt counter (survives restarts via
    `document_states.attempt_count`) caps reprocessing loops at `max_doc_attempts`.
  - Read-only enforcement audit PASSED (see below): catalog untouched, Google Drive access read-only.
  - 19/19 focused Phase 14 tests pass; 191 passed / 3 skipped full pytest suite.

### Read-Only Safety Audit — PASSED (2026-09-08)
- `/Users/ashim/locus_drive` scan: no write-capable Drive API endpoints exist in any client/script
  (only `files().list`, `changes().list`, `drives().list`, `about().get`, `changes().getStartPageToken`);
  OAuth `SCOPES` are `drive.readonly` + `drive.metadata.readonly` only.
- SQLite catalog unmodified: `locus_drive.db` mtime 2026-09-07 16:13:45 (predates all Phase 13/14 work);
  `PRAGMA integrity_check` == ok; `quick_check` == ok; all catalog access is SELECT-only;
  all writes go to the engine's own `rag_state.db`.
- No runner processes were found touching the catalog. The only newer files under `locus_drive` are
  the expected WAL sidecars (`-shm`/`-wal`) created by this audit's read-only connection.

## Open Issues / Next Actions
- Begin Phase 15: Production Hardening (security audit, performance profiling, documentation completion,
  backup/recovery verification).

## Decisions (ADRs)
- ADR-001 PyMuPDF ✅, ADR-002 Tesseract ✅, ADR-003 Dense embeddings ✅, ADR-004 BM25 ✅, ADR-005 Exact/Entity ✅, ADR-006 Chunking ✅, ADR-007 Structured Data ✅, ADR-008 Normalizer ✅, ADR-008 Dedup ✅, ADR-009 Retrieval Defect Fixes ✅, ADR-13 Caching ✅

## Test Results Summary
- **138/138 unit tests pass** across all phases (0–12).
- **172/172 full suite passes** across all phases (0–13).
- **191/191 full suite passes** across all phases (0–14), 3 skipped (pre-existing integration test limitations).
- **19/19 Phase 14 focused tests** pass (transient classification, retry backoff, safe-subpath, Drive boundary, attempt-count state machine, orchestrator retry/dead-letter).
- **28/28 Phase 13 unit tests** pass (query cache, retrieval cache, embedding cache; TTL/eviction).
- **18 real LOCUS documents** benchmarked: 8/9 queries pass (1 known NPR exact-match edge case).
- **Locust corpus**: 224 chunks indexed, 5 quality tiers (failed/high/medium/low/unknown).
- **Phase 13 focused tests**: 28/28 passed.
- **Phase 12 focused tests**: 9/9 passed (no-changes, with-changes, trashed exclusion, checkpoint-aware skip, failure-retry watermark).

## Files Summary
- `src/chunking/structural.py` — heading/page/table-aware chunker
- `src/indexing/vector.py` — ExactEntityIndex, BM25Index, DenseVectorIndex, MetadataIndex, HybridRetriever
- `src/retrieval/hybrid.py` — RRF fusion, HybridRetriever, retrieval orchestration
- `src/retrieval/query_router.py` — IntentClassifier, QueryRouter, QueryNormalizer
- `src/classification/classifier.py` — DocumentClassifier, AuthorityStatus
- `src/dedup/deduplicator.py` — Deduplicator, DedupCluster, DedupIndex
- `src/sync/incremental_sync.py` — Phase 12 incremental sync engine (read-only catalog, checkpoints in rag_state.db, failure-retry watermark, trashed file exclusion)
- `src/resilience.py` — Phase 14 resilience primitives: transient-error classification, retry with backoff, safe-subpath, Drive read-only boundary enforcement
- `src/pipeline/statemachine.py` — Phase 14 `get_attempt_count()` persistence for dead-lettering
- `tests/unit/test_incremental_sync.py` — Phase 12 incremental sync tests (9 focused tests, 3 new regression tests)
- `tests/unit/test_query_cache.py` — Phase 13 query/retrieval/embedding cache tests (28 focused tests)
- `tests/unit/test_resilience.py` — Phase 14 resilience/security tests (19 focused tests)
- `eval/metrics/extraction_metrics.py` — Comprehensive corpus quality report

## Phase Boundary
**Phase 14 is complete.** Do not begin Phase 15 (Production Hardening) until explicitly requested.

## Files Summary
- `src/chunking/structural.py` — heading/page/table-aware chunker
- `src/indexing/vector.py` — ExactEntityIndex, BM25Index, DenseVectorIndex, MetadataIndex, HybridRetriever
- `src/retrieval/hybrid.py` — RRF fusion, HybridRetriever, retrieval orchestration
- `src/retrieval/query_router.py` — IntentClassifier, QueryRouter, QueryNormalizer
- `src/classification/classifier.py` — DocumentClassifier, AuthorityStatus
- `src/dedup/deduplicator.py` — Deduplicator, DedupCluster, DedupIndex
- `src/sync/incremental_sync.py` — Phase 12 incremental sync engine (read-only catalog, checkpoints in rag_state.db, failure-retry watermark, trashed file exclusion)
- `tests/unit/test_incremental_sync.py` — Phase 12 incremental sync tests (9 focused tests, 3 new regression tests)
- `eval/metrics/extraction_metrics.py` — Comprehensive corpus quality report

## Phase Boundary
**Phase 12 is complete.** Begin Phase 13 when ready: Caching + Performance.

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
--- Phase 18 — Actual Execution (Production Evidence) ---
Built real fixture index from 21 fixtures (not synthetic):
- 191 chunks (StructuralChunker)
- 187 embeddings (real sentence-transformers all-MiniLM-L6-v2)
- 191 dense DB entries / 192 BM25 DB entries / 2110 exact token entries
- Evidence-first: no synthetic benchmark data produced
- Benchmark format: restored from .bak2 (95 real cases preserved); aggregation enum fixed
- Security: 3 regression tests added (boundary, secrets, traversal) — PASS
- Performance: measured (embedding throughput = real bottleneck; no custom bottleneck)
- Full 29,252 production: NOT EXECUTED (external resource — read-only Drive)
- Benchmark 64/95-case rebuild: BLOCKED (fixture/locator design gap — no synthetic fix applied)
- P0-4: verified (no concrete retriever architecture defect — redesign not performed)
- Phase 18 complete for pipeline/retrieval/provenance: GENUINELY COMPLETE
