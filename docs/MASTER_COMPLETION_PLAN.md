# MASTER COMPLETION PLAN — LOCUS RAG (reconstructed Phase 15–18)
Prepared: 2026-09-11 | Author: autonomous RAG engineer | Evidence: repo + test runs + graph
Status: Phase 14 (resilience/security) VERIFIED. Phase 15 PARTIAL (spec exists, not executed). Phase 16 inferred. Phase 17/18 RECONSTRUCTED (no source spec — documented).

## WHAT IS GENUINELY COMPLETE (verified, not claimed)
- Phase 0–7: ingestion→extraction→normalization→classification→dedup→chunking→hybrid retrieval (tests pass; 21 docs extracted; 6 structured parquet; 21 raw files)
- Phase 8–11: EvidenceAssembler, Verifier, AnswerBuilder, Exporters, RecallSafetyNet (tests pass; provenance preserved)
- Phase 12: Sync/incremental (tests 9/9)
- Phase 13: Cache (tests 28/28)
- Phase 14: Resilience/security (tests 19/19; boundary enforcement; dead-letter; retry; idempotency; drive read-only verified)
- Safety fixes (verified by direct python run + full suite 220 pass / 3 skipped, excluding 19 broken benchmark): duplicate `metadata` (vector.py); `normalize()` missing restore (query_router.py)
- `/Users/ashim/locus_drive` READ-ONLY confirmed (catalog mtime predates work; assert_not_in_locus_drive active)

## WHAT IS PARTIAL / MISSING / FALSELY CLAIMED
- Phase 15 (security audit / profiling / docs / backup): spec in PHASES.md line 187-193; work NOT executed in previous session
- Phase 16: NOT DEFINED in docs/; inferred only by graph-dependency sequence
- Phase 17 / 18: RECONSTRUCTED — no body text; only dependency edges and external spec references (exporters cite §18/§19). Cannot declare complete.
- Index artifacts EMPTY (`data/indexes/`, `data/chunks/`, `data/normalized/`, `data/exports/`) — pipeline stages beyond extraction unverified on actual artifacts
- Benchmark suite BROKEN: 19 failures in `test_phase1_benchmark.py` (all `datetime.timezone` shadow error — `import datetime` shadows module; `datetime.timezone.utc` fails because `datetime` is the class, not module). Previous "236 pass" excluded this suite; actual = 220 + 19 failed.
- `rag_state.db`: 22 document_states (1 failed attempt=6, 3 requires_review, rest normalized) — needs resolution before production claim.
- `baseline.db`: has `baseline_chunks` / `baseline_documents`; `rag_state.db` chunks table exists (fixture); discrepancy noted honestly.
- Benchmark Gate-A (`scripts/build_benchmark_gateA.py`) exists, NOT executed.
- `seed_cases.json` modified (git M); benchmark gate rebuild needed.
- Dual HybridRetriever split (`hybrid.py` + `vector.py`) — architecture split unresolved (needs design decision; not safe auto-merge).
- `utcnow()` deprecation (22 warnings) — cosmetic, deferred.

## MASTER PLAN — TASKS (ordered by dependency)

P0 — CORRECTNESS / BLOCKING (do first)
P0-1 [BLOCKING] Fix benchmark `datetime.timezone` shadow error in `eval/benchmark/schemas.py` + `failure_attribution.py` → replace `datetime.timezone.utc` with `datetime.datetime.now(datetime.timezone.utc)` or import `timezone` from `datetime`. Verify all 19 tests + full suite.
P0-2 [BLOCKING] Resolve `rag_state.db` 1 failed + 3 requires_review (inspect failure reasons; retry or dead-letter).
P0-3 [BLOCKING] Build index artifacts from fixtures: chunk (`structural.py`), embed, index (BM25 + dense + exact), produce `data/indexes/`, `data/chunks/`, `data/normalized/`, `data/exports/`. Verify count matches 224 claimed chunks.
P0-4 [BLOCKING] Fix dual HybridRetriever architecture split (design decision document + either merge or clarify split contract). Must not silently merge.

P1 — PRODUCTION READINESS
P1-1 Build/rebuild benchmark Gate-A (`scripts/build_benchmark_gateA.py`); verify `seed_cases.json` integrity after modifications.
P1-2 Phase 15 execution: security audit (permission audit, oauth scope verify, path traversal retest), performance profiling (retrieval latency on fixtures), docs update, backup/recovery verification.
P1-3 Define Phase 16 spec (from architecture / graph dependencies / benchmark needs: likely production monitoring, batch ingestion, multi-tenancy, or advanced temporal reasoning — document RECONSTRUCTED).
P1-4 Phase 17/18: since requirements unrecoverable, document RECONSTRUCTED acceptance criteria (evidence quality, citation accuracy, abstention rate, contradiction surface, temporal reasoning, structured-data arithmetic, provenance chain, resumption, idempotency) and implement ONLY safe verifiable pieces (citation verification, structured-data regression, provenance audit).

P2 — ROBUSTNESS / PERFORMANCE
P2-1 Full index build from 21-document fixture (not 40-50 GB — document scale limitation honestly).
P2-2 End-to-end retrieval adversarial test (exact / entity / semantic / numeric / comparison / aggregation / temporal / negative / conflict / spreadsheet / multi-doc / ambiguous / absent / contradictory).
P2-3 Resilience tests: malformed doc, extraction failure, partial index, interrupted build, restart with checkpoint, duplicate reprocessing, stale-state, corrupted artifact.
P2-4 Performance: retrieval latency, embedding throughput, index build time on fixtures.
P2-5 Clean `utcnow()` deprecations.

P3 — DOCUMENTATION / CLEANUP
P3-1 Update `PROGRESS.md` to reflect real state (not false Phase 14-complete-with-everything-after).
P3-2 Update `docs/FINAL_ENGINEERING_VALIDATION.md` with final evidence (this document extends it).
P3-3 Refresh `graphify-out/` after all changes.
P3-4 Confirm `locus_drive` unread (final audit).

## DEPENDENCIES
P0-1 → P0-2, P0-3 (benchmark must pass to trust measurements)
P0-3 → P1-3 (index artifacts needed for Phase 16 spec validation)
P0-4 → P1-1 (design decision before benchmark build relies on retrieval contract)
P1-2, P1-3 → P1-4 (spec before reconstructed-phase acceptance)
P2-1 → P2-2 → P2-3 (build before adversarial before resilience)

## VALIDATION CRITERION (Phase 18 strengthened — RECONSTRUCTED)
PER CRITERION: VERIFIED / PARTIAL / BLOCKED + evidence file + test name.
- Ingest/Extraction: data/raw 21 + extracted 21 (verified)
- Normalization/Classification/Dedup: code + fixtures (verified)
- Chunking/Indexing: MUST have artifacts in data/indexes/ + chunks/ (currently BLOCKED — build required)
- Hybrid Retrieval: test_hybrid_retrieval passes + direct python verified (verified; architecture split BLOCKED)
- Evidence/Verification/Answer/Export: 15 new tests + direct inspection (verified)
- Citations/Provenance/Abstention/Contradiction: pipeline/models + verifier + assembler (verified; needs regression on artifacts)
- Structured Data: parquet + provenance (verified; arithmetic deterministic — never LLM)
- Temporal/Resumability/Idempotency: sync + resilience + state-machine (verified; needs full-restart test)
- Observability: events + health + main (verified; new, untracked — needs integration)
- Security: boundary + read-only audit (verified; needs audit doc)
- Corpus scale: 21 docs (documented limitation — not 40-50 GB)
- Benchmark Gate-A: BLOCKED until build executed
- Forensic review: completed (duplicate metadata, normalize restore, datetime shadow, empty indexes, dual retriever)

## COMPLETION DEFINITION
Not "code written" — "artifacts exist, tests pass (all benchmark included), evidence verified independently, provenance preserved, drive untouched, limitations documented, reconstructed phases have explicit criteria." Release: NOT READY until P0-1, P0-2, P0-3, P0-4 + P1-2 + P1-3 + benchmark gate-A.
