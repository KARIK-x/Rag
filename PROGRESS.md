# PROGRESS - LOCUS RAG

## Current Phase
- **Phase 7: Query Understanding + Retrieval Orchestration** (complete)

## Completed

### Phase 0 — Reconnaissance + Foundation ✅
- Inspected existing locus_drive repository (`/Users/ashim/locus_drive`).
- Verified existing SQLite catalog (`locus_drive.db`, 29,252 items, 2,396 folders).
- Catalog schema inspected: `files`, `sync_state`, `page_tokens`, `folder_queue`.

### Phase 1 — Golden Benchmark + Baseline ✅
- 18/18 unit tests pass.
- Baseline pipeline, seed benchmark (15 cases).

### Phase 2 — Ingestion + Extraction ✅
- IngestionClient: read-only Drive, Workspace export (Google Docs→text, Sheets→CSV).
- ExtractionPipeline: text/markdown, CSV/TSV, PDF (PyMuPDF), DOCX (zip+XML).
- IntegrityAuditor: text yield, page count, headings, tables, warnings.
- DocumentStateMachine: DISCOVERED→...→INDEXED, FAILED/REQUIRES_REVIEW/DEAD_LETTER.
- Idempotent re-ingestion, crash recovery.

### Phase 3 — Normalization + Structured Data ✅
- **Normalization**: Unicode, whitespace, currency, dates, Devanagari.
- **StructuredDataEngine**: DuckDB+Parquet, deterministic computation.
- **ExactEntityIndex**: tokenized lookup, Drive-ID support.

### Phase 4 — Classification + Dedup + Authority ✅
- **DocumentClassifier**: domain (event/sponsorship/budget/...), authority (draft/final/proposal/signed/...).
- **Deduplicator**: exact-hash + normalized-hash + near-dup (Jaccard, threshold 0.60).
- **DedupIndex**: persistent SQLite canonical/alias store.
- **80/80 unit tests pass**.

### Phase 5 — Chunking + Indexing ✅
- **StructuralChunker**: heading/page/table/sheet-aware, contextual prefixes.
- **Indexes**: Dense, BM25/lexical, Exact/Entity, Metadata, DedupIndex.
- **98/98 unit tests pass**.

### Phase 6 — Hybrid Retrieval + Reranking ✅
- **HybridRetriever**: dense + BM25 + exact + metadata → RRF fusion.
- **retrieve()**: candidate fusion, filters, provenance preserved.
- **Test results**: 94/94 pass.

### Phase 7 — Query Understanding + Retrieval Orchestration ✅
- **Intent classification**: 10+ intents via rule-based patterns.
- **Query normalizer**: currency/date/name protection, abbreviation expansion.
- **RetrievalRouter**: intent→strategy mapping, filters, temporal constraints.
- **Compound query decomposition**: independent sub-query handling.
- **Multi-query expansion**: selective abbreviation/entity alias expansion.
- **Temporal reasoning**: years, before/after, during, historical vs current.
- **Structured-data routing**: DuckDB/PParquet routing for aggregation/filter/sort.
- **Safe ambiguity handling**: open retrieval, no premature closure.
- **Phase 6 integration**: reuses Phase 6 HybridRetriever, no duplication.

**Phase 7 Tests**: 105/105 across all phases passing.

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