# Phases — LOCUS RAG Build Roadmap

## Phase 0 — Reconnaissance + Foundation ✅
**Status:** Near complete.
- [x] Inspect existing locus_drive repository
- [x] Verify SQLite catalog schema (files, sync_state, page_tokens, folder_queue)
- [x] Query mime-type distribution (12,380 images, 2,766 PDFs, 951 Google Docs, 631 Google Sheets, etc.)
- [x] Create project directory structure
- [x] Write CLAUDE.md, PROGRESS.md
- [x] Define core data models and module interfaces

**Definition of Done:** Repository understood, catalog reused, architecture documented, tests run, Drive safety test exists.

---

## Phase 1 — Golden Benchmark + Baseline
**Goal:** Establish measurement baseline before architectural complexity.
- [ ] Create seed benchmark (~40–60 cases) covering:
  - Exact lookups (names, IDs, acronyms)
  - Semantic questions
  - Numerical/currency queries
  - Date/temporal queries
  - Spreadsheet queries
  - Buried answers (long documents)
  - Misspellings / abbreviations
  - Multi-document / comparison
  - Negative / unanswerable
  - Conflicting sources
  - Nepali/English mixed
- [ ] Implement simplest baseline pipeline:
  1. Format routing (PDF → text, DOCX → text, CSV → structured)
  2. Simple heading-aware chunking
  3. Single embedding model (candidate: BGE-M3)
  4. Dense retrieval + simple top-k
- [ ] Measure: Recall@K, MRR, NDCG, candidate-pool recall, latency

**Definition of Done:** Baseline numbers recorded. Every failure attributed to earliest causal stage.

---

## Phase 2 — Ingestion + Extraction
**Goal:** Reliable, auditable extraction from every supported format.
- [ ] Drive fetch via existing catalog
- [ ] Workspace export (Google Docs/Sheets)
- [ ] Format routing (PDF, DOCX, XLSX, CSV, Pages, ODT)
- [ ] Primary extractor + quality evaluation
- [ ] OCR fallback (Tesseract/Surya evaluation)
- [ ] Integrity audit (page counts, text yield, table detection)
- [ ] State machine (DISCOVERED → INDEXED, FAILED, REQUIRES_REVIEW)
- [ ] Crash recovery and dead-letter queue

**Definition of Done:** Sample corpus successfully processed. No unexplained documents.

---

## Phase 3 — Normalization + Structured Data
**Goal:** Normalized text and first-class tabular representation.
- [ ] Text normalization (Unicode, whitespace, encoding)
- [ ] Number/currency/date normalization with locale awareness
- [ ] Temporal metadata extraction
- [ ] Spreadsheet → DuckDB/Parquet pipeline
- [ ] Deterministic computation tests

**Definition of Done:** Structured queries work correctly on fixture datasets.

---

## Phase 4 — Classification + Dedup + Authority
**Goal:** Correct handling of duplicates, conflicts, and document authority.
- [ ] Metadata classification (event, sponsorship, budget, meeting, etc.)
- [ ] Temporal classification
- [ ] Source authority scoring (draft, final, proposal, signed)
- [ ] Deduplication (content hash, normalized hash, near-duplicate)
- [ ] Canonical/alias relationships

**Definition of Done:** Known duplicate/conflict cases behave correctly.

---

## Phase 5 — Chunking + Indexing
**Goal:** High-quality chunks with multiple retrieval indexes.
- [ ] Structural chunking (heading, page, table boundaries)
- [ ] Contextual prefixes (benchmark-validated)
- [ ] Dense embeddings (candidate evaluation: BGE-M3 vs Qwen3-Embedding)
- [ ] BM25 / lexical index (bm25s or SQLite FTS5)
- [ ] Exact/entity index (names, dates, IDs, amounts)
- [ ] Metadata index

**Definition of Done:** Hybrid-capable indexes exist. ADR-003 and ADR-004 decided.

---

## Phase 6 — Hybrid Retrieval
**Goal:** Combine multiple retrieval paths with RRF fusion.
- [ ] Query analysis (intent classification)
- [ ] Dense + BM25 + exact/entity retrieval
- [ ] RRF fusion
- [ ] Dynamic candidate depth (query-dependent)
- [ ] Candidate deduplication

**Definition of Done:** Hybrid retrieval beats baseline or has documented reason why not.

---

## Phase 7 — Reranking + Evidence Assembly
**Goal:** Bring most relevant evidence to the top with proper context.
- [ ] Cross-encoder reranking (benchmark-validated)
- [ ] Parent/neighbor/table evidence expansion
- [ ] Evidence validation

**Definition of Done:** Measured reranking benefit documented.

---

## Phase 8 — Recall Safety Net
**Goal:** Prevent the founding failure — an indexed, retrievable answer being missed.
- [ ] Bounded retrieval ladder (exact phrase → broadened lexical → query reformulation → document-level)
- [ ] Trigger conditions and stop conditions per rung
- [ ] Regression test: first retrieval misses → expanded retrieval recovers

**Definition of Done:** Founding failure has a direct regression test.

---

## Phase 9 — Query Routing + Decomposition
**Goal:** Correctly route and decompose compound queries.
- [ ] Intent classification
- [ ] Compound decomposition
- [ ] Temporal/spreadsheet/export routing

**Definition of Done:** Multi-part queries work correctly.

---

## Phase 10 — Generation + Verification
**Goal:** Evidence-only generation with claim-level verification.
- [ ] Evidence-only generation
- [ ] Claim extraction and verification
- [ ] Completeness scoring
- [ ] Conflict handling
- [ ] Confidence + abstention

**Definition of Done:** Faithfulness and citation targets measured.

---

## Phase 11 — Cache + Incremental Sync
**Goal:** Efficient incremental updates without full reindexing.
- [ ] Drive Changes API integration
- [ ] Page token persistence
- [ ] Changed-document reprocessing
- [ ] Index versioning and atomic swaps
- [ ] Corpus-versioned cache invalidation

**Definition of Done:** Edit one source document → detection → reprocessing → new answer, without full rebuild.

---

## Phase 12 — Full Benchmark
**Goal:** Comprehensive evaluation on development, validation, and held-out test splits.
- [ ] Full benchmark suite (~100+ cases)
- [ ] All failures attributed to earliest causal stage

**Definition of Done:** Every failure has stage attribution.

---

## Phase 13 — Adversarial + Chaos Testing
**Goal:** Verify safe failure modes under adverse conditions.
- [ ] OCR/parser failures
- [ ] Drive API failures
- [ ] Process crashes and recovery
- [ ] Malformed spreadsheets
- [ ] Duplicate/conflicting sources

**Definition of Done:** All named failure classes have safe behavior.

---

## Phase 14 — User Feedback Loop
**Goal:** Continuous improvement from production use.
- [ ] User feedback → review → root cause → benchmark case
- [ ] Deliberate split assignment

---

## Phase 15 — Production Hardening
**Goal:** Shippable, maintainable system.
- [ ] Security audit
- [ ] Performance profiling
- [ ] Documentation completion
- [ ] Backup and recovery verification
