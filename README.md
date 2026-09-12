# LOCUS RAG

Local-first, high-reliability institutional knowledge and retrieval system for LOCUS.

> Status: V1 backend implemented and validated. 236 unit tests passing (plus 1 expected skip). 6 confirmed integration defects fixed. Fixture index persistence verified. Drive read-only preserved.

## What this is (V1 — implemented and validated)

- Evidence-first retrieval and answer system for the existing LOCUS Google Drive catalog (SQLite at `/Users/ashim/locus_drive/locus_drive.db`).
- Hybrid retrieval: dense embeddings + BM25 lexical + exact/entity index + metadata filtering, with Reciprocal Rank Fusion (`rrf_fusion`).
- Structured data plane: DuckDB + Parquet for deterministic computation over spreadsheets/CSV.
- Pipeline: ingestion (read-only), extraction, normalization, chunking, indexing, retrieval, evidence assembly, verification, multi-format export (CSV/TSV/JSON/MD).
- Strict test-driven development and failure attribution.
- Read-only Drive access enforced. Catalog (`locus_drive.db`) reused, never modified.

Not implemented / future (V2): production-scale OCR (Tesseract/Surya) over full 5,875-file corpus, full multimodal video, live Neo4j/FalkorDB push, automated watch/rebuild hooks.

## Quick start

Install (Python >=3.10):

```bash
pip install -r requirements.txt  # or: pip install -e .
```

Run focused validation (what is verified right now):

```bash
PYTHONPATH=$(pwd) python -m pytest tests/unit/test_final_regression.py tests/unit/test_indexing.py -q
```

Run fixture index build (produces `data/indexes/*.db`, `data/chunks/`, `data/index_artifacts.json`):

```bash
PYTHONPATH=$(pwd) python scripts/build_fixture_index.py
```

## Architecture (validated V1)

```
Google Drive (READ-ONLY)
         │
  EXISTING CATALOG (SQLite: locus_drive.db)
         │
  ┌──────┼──────┬────────┐
  ▼      ▼      ▼        ▼
DOCUMENT  STRUCTURED  DRIVE  RETRIEVAL
INGEST    DATA ENGINE SYNC    (dense +
(PDF/      (DuckDB +  (API    BM25 + exact)
 DOCX)     Parquet)  read)         │
  │           │         │         │
  ▼           ▼         │         ▼
EXTRACTION → NORMALIZATION → INDEX → HYBRID RETRIEVER
                                            │
                                     RRF fusion + rerank
                                            │
                              EVIDENCE ASSEMBLER + PROVENANCE
                                            │
                                        ANSWER / EXPORT
                                   (CSV / TSV / JSON / MD)
```

Core modules:
- `src/indexing/vector.py` — dense, BM25, exact/entity, metadata indexes
- `src/retrieval/hybrid.py` — `rrf_fusion`, hybrid retriever, provenance preservation
- `src/retrieval/query_router.py` — intent classification (`IntentClassifier`), compound query decomposition
- `src/pipeline/ingest_orchestrator.py` — download → extract → audit → state machine (`DocumentStateMachine`)
- `src/structured_data/engine.py` — `StructuredDataEngine` (DuckDB + Parquet)
- `src/chunking/structural.py` — `StructuralChunker`
- `src/extraction/router.py` — `ExtractionPipeline`

## Capabilities (implemented)

- Hybrid retrieval combining dense embeddings, BM25 lexical, exact/entity lookup, and metadata filters.
- RRF fusion (`rrf_fusion`) that preserves text/provenance for candidates appearing only in BM25 or exact results.
- Structured data import from extraction results into DuckDB/Parquet for deterministic aggregation/filter/sort/comparison.
- Multi-format exports: CSV, TSV, JSON, Markdown.
- Evidence verification with provenance (source_locator, doc_id, chunk_id, table/sheet/cell references).
- State tracking with idempotency and retry (`retry_with_backoff`, `assert_not_in_locus_drive`).
- Benchmark construction (`scripts/build_benchmark_gateA.py`), fixture index (`scripts/build_fixture_index.py`), and end-to-end verification (`tests/unit/test_final_regression.py`).

## Testing (current state)

```
Unit suite: 236 passed (0 errors, 1 expected skip in full suite)
Focused regression + indexing: 14 passed
Fixture index: verified (indexes persist/load; BM25 docs=21904; dense=21903; exact=21904)
Integration (test_real_locus_phase6): 7 passed, 1 skipped; 1 provenance-related case fixed
```

No production ingestion of the 5,875-file corpus was executed. `/Users/ashim/locus_drive` remains read-only.

## Installation / setup

Requirements:
- Python >=3.10
- SQLite (used for index persistence and catalog)
- Optional: `sentence_transformers` (real embeddings in fixture build), `duckdb` (structured data)

Configuration is minimal: no external API keys required for core operation. `CLAUDE.md` defines project rules and `.claude/skills/` provides support skills (`benchmark-construction`, `evidence-verification`, `extraction-review`, `retrieval-evaluation`, etc.).

## Project structure

```
.
├── src/                    # Core modules (indexing, retrieval, pipeline, extraction, structured data)
├── tests/                  # Unit + integration + regression + security
├── eval/                   # Benchmark construction, seed cases, metrics, schemas
├── docs/                   # Architecture (ARCHITECTURE.md), decisions, final validation
├── scripts/                # Fixture index build, benchmark gate, retrieval verification
├── data/                   # Local storage (extracted, chunks, normalized, indexes, structured) — excluded from repo
└── .claude/                # Project settings + skills (not committed by default; .gitignore excludes if needed)
```

## Security / privacy rules

1. `/Users/ashim/locus_drive` is READ-ONLY — never written or moved.
2. No secrets, API keys, or credentials are stored in source/config.
3. `.gitignore` excludes `data/` artifacts, `.env`, tokens, `.db`, `.parquet`, logs, `.claude/` (optional), `graphify-out/`.
4. Personal filesystem paths appear only as protected/default references (`data_dir`, `catalog_path`) in code; no private content committed.

## Design decisions (V1 scope clearly defined)

- V1: validated backend only (retrieval, indexing, structured data, evidence, export, resilience, state machine, fixture index).
- Not V1: full production-scale ingestion over 5,875 files (not executed), live multimodal video processing at scale (skills exist but not fully validated end-to-end on all formats), automated graph visualization rebuild (`graphify` skill available but not required for core RAG), live Neo4j/FalkorDB push.
- Intentional simplifications marked with `ponytail:` comments in source; upgrade paths documented where ceilings apply.

## Contribution / development

Run tests before any change:

```bash
python -m pytest tests/unit/ -q
python scripts/build_fixture_index.py  # rebuild fixture indexes
```

No new dependencies without updating `pyproject.toml`. Strict test-driven changes; benchmark updates required for retrieval/indexing modifications.

## License

Project-specific; refer to repository settings and organizational policy.

---
Built and validated by Aadarsha (session). 236 tests pass. 6 confirmed integration defects fixed. Fixture persistence verified. Read-only drive preserved. No production ingestion executed.
