# Architecture — LOCUS RAG

## 1. Overview

LOCUS RAG is a four-plane institutional knowledge system built atop an existing Google Drive catalog (~29,252 items). It combines document retrieval, structured-data querying, evidence verification, and deterministic computation into a unified pipeline.

```
                        GOOGLE DRIVE (read-only)
                                 │
                   EXISTING LOCUS_DRIVE CATALOG (SQLite)
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
    DOCUMENT INGEST       STRUCTURED INGEST   DRIVE SYNC
    PDF/DOCX/Pages        XLS/CSV/Sheets     Changes API
              │                  │                  │
              ▼                  ▼                  │
    EXTRACTION + OCR      TABLE/DATA IR            │
              │                  │                  │
              └────────┬─────────┘                  │
                       ▼                            │
              INTEGRITY AUDIT                        │
                       │                            │
              ┌─────────┴─────────┐                 │
              ▼                   ▼                 │
        NORMALIZATION       SCHEMA/QUALITY          │
              │                   │                  │
              └────────┬─────────┘                 │
                       ▼                            │
              CLASSIFICATION                         │
              temporal / authority / dedup          │
                       │                            │
          ┌────────────┴────────────┐              │
          ▼                         ▼              │
    DOCUMENT INDEX              DATA ENGINE         │
    Dense + BM25 + Exact       DuckDB + Parquet     │
          │                         │               │
          └────────────┬────────────┘              │
                       ▼                            │
                 QUERY PLANNER                       │
                 intent + decomposition             │
                       │                            │
          ┌────────────┴────────────┐              │
          ▼                         ▼              │
     SEMANTIC RETRIEVAL        LEXICAL RETRIEVAL   │
          │                         │              │
          └────────────┬────────────┘              │
                       ▼                            │
                 RRF FUSION                         │
                       │                            │
                       ▼                            │
                  RERANKER                          │
                       │                            │
                       ▼                            │
             EVIDENCE ASSEMBLER                     │
             parent / neighbor / table            │
                       │                            │
                       ▼                            │
              RECALL SAFETY NET                     │
                       │                            │
          ┌────────────┴────────────┐              │
          ▼                         ▼              │
    LLM GENERATION             DETERMINISTIC       │
    evidence-only              COMPUTATION          │
          │                         │              │
          └────────────┬────────────┘              │
                       ▼                            │
                  VERIFICATION                      │
                  claims + numbers + dates          │
                       │                            │
                       ▼                            │
             CONFIDENCE + ABSTAIN                  │
                       │                            │
                       ▼                            │
             CITATIONS + PROVENANCE                │
                       │                            │
                       ▼                            │
                    USER OUTPUT
    Answer / Table / JSON / CSV / XLSX / Markdown
```

## 2. Data Planes

### 2.1 Document Knowledge Plane
Unstructured documents: PDF, DOCX, DOC, TXT, MD, ODT, Pages, Google Docs.

### 2.2 Structured Data Plane
Spreadsheets and tabular data: XLS, XLSX, CSV, TSV, Google Sheets, Apple Numbers. Stored in DuckDB/Parquet for deterministic computation.

### 2.3 Retrieval Plane
Three complementary retrieval paths:
- **Dense**: Semantic embeddings (BGE-M3 or comparable multilingual model)
- **BM25 / Lexical**: Exact keyword and phrase matching
- **Exact/Entity**: Names, acronyms, dates, IDs, monetary values

### 2.4 Evidence / Computation Plane
- Evidence assembly (parent, neighbor, table expansion)
- Deterministic calculations via DuckDB
- Aggregation, filtering, sorting, comparison
- Export to CSV, JSON, XLSX, Parquet, Markdown

## 3. Retrieval Architecture

### 3.1 Hybrid Retrieval

```
QUERY → [dense retrieval] ─┐
         [BM25 retrieval]  ─┼─→ candidate union → dedup → RRF → rerank → evidence expansion
         [exact/entity]   ─┤
         [metadata]       ─┘
```

### 3.2 Recall Safety Net

```
first retrieval
      │
      ▼ insufficient
expanded pool
      │
      ▼
exact phrase search
      │
      ▼
broadened lexical
      │
      ▼
query reformulation
      │
      ▼
document-level search
```

Each step has trigger conditions, maximum work limits, stop conditions, and logging.

## 4. Query Classification

Queries are classified into intents:
- `EXACT_LOOKUP`, `ENTITY_LOOKUP`, `SEMANTIC`, `NUMERIC`, `DATE`, `CURRENCY`
- `COMPARISON`, `AGGREGATION`, `TEMPORAL`, `MULTI_DOCUMENT`
- `SPREADSHEET`, `METADATA`, `EXTRACTION`, `TRANSFORMATION`, `EXPORT`
- `AMBIGUOUS`, `OUT_OF_DOMAIN`

A query may have multiple intents. The planner routes to appropriate retrieval and computation paths.

## 5. Provenance Model

Every chunk and answer carries provenance that survives the full pipeline:
```
drive_file_id → filename → folder_path → mime_type → revision_id
  → page → section → heading_path → table_id → sheet_name
  → row → column → cell → chunk_id → source_view_link
```

## 6. Model Registry

Models are configured centrally, not hardcoded:
```
embedding_model, reranker_model, contextualization_model,
generation_model, verification_model, ocr_model
```

## 7. Key Design Decisions (ADR Summary)

| ADR | Topic | Decision |
|-----|-------|----------|
| ADR-001 | Extraction engine | TBD (candidate: Docling) |
| ADR-002 | OCR engine | TBD (candidates: Tesseract, Surya) |
| ADR-003 | Embedding model | TBD (candidates: BGE-M3, Qwen3-Embedding) |
| ADR-004 | Vector store | TBD (candidates: LanceDB, Qdrant) |
| ADR-005 | BM25 engine | TBD (candidates: bm25s, SQLite FTS5) |
| ADR-006 | Chunking strategy | TBD (heading-aware, page-aware, table-aware) |
| ADR-007 | Structured data engine | DuckDB + Parquet |
| ADR-008 | Generation model | TBD (local vs API benchmark) |

## 8. Concurrency

The system is a single-process local application. No distributed infrastructure in V1. The architecture supports future scale without architectural rewrite.

## 9. Non-Negotiable Rules

1. Drive is READ-ONLY. Narrowest OAuth scopes.
2. Never full-reindex on a single Drive change.
3. Never mutate a live index during migration.
4. Never let an LLM do deterministic arithmetic when structured data exists.
5. Never silently resolve conflicts.
6. Never optimize latency before protecting recall.
7. Never declare success without benchmark evidence.
