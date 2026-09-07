# Schemas — LOCUS RAG

## 1. Database Schema (SQLite)

### 1.1 Source Catalog (existing, read-only)
**Path:** `/Users/ashim/locus_drive/locus_drive.db`

Contains `files`, `sync_state`, `page_tokens`, `folder_queue` — **do not modify**.

### 1.2 RAG State Database
**Path:** `{data_dir}/db/rag_state.db`

#### `documents` table
```sql
CREATE TABLE documents (
    doc_id           TEXT PRIMARY KEY,
    catalog_ref     TEXT NOT NULL,          -- Drive file ID
    mime_type       TEXT NOT NULL,
    doc_type        TEXT NOT NULL,          -- DocType enum
    title           TEXT,
    folder_path     TEXT,
    created_at      TEXT,
    modified_at     TEXT,
    content_hash    TEXT,
    size_bytes      INTEGER,
    processing_state TEXT NOT NULL,          -- ProcessingState enum
    extraction_quality REAL DEFAULT 0.0,
    ocr_used        INTEGER DEFAULT 0,
    canonical_doc_id TEXT,                  -- for deduplication
    content_date_start TEXT,
    content_date_end   TEXT,
    reporting_period_start TEXT,
    reporting_period_end TEXT,
    authority_status  TEXT,                  -- draft, final, proposal, confirmed
    last_error      TEXT,
    last_updated    TEXT NOT NULL,
    FOREIGN KEY (catalog_ref) REFERENCES files(id)
);
CREATE INDEX idx_documents_catalog_ref ON documents(catalog_ref);
CREATE INDEX idx_documents_doc_type   ON documents(doc_type);
CREATE INDEX idx_documents_state      ON documents(processing_state);
CREATE INDEX idx_documents_hash       ON documents(content_hash);
```

#### `chunks` table
```sql
CREATE TABLE chunks (
    chunk_id         TEXT PRIMARY KEY,
    doc_id          TEXT NOT NULL,
    parent_chunk_id  TEXT,
    heading_path    TEXT,                   -- JSON array
    page_start      INTEGER,
    page_end        INTEGER,
    sheet_name      TEXT,
    row_start       INTEGER,
    row_end         INTEGER,
    raw_text        TEXT NOT NULL,
    normalized_text TEXT NOT NULL,
    contextual_prefix TEXT,
    embedding_model TEXT NOT NULL,
    index_version   INTEGER NOT NULL,
    source_locator  TEXT NOT NULL,          -- JSON provenance
    FOREIGN KEY (doc_id) REFERENCES documents(doc_id),
    FOREIGN KEY (parent_chunk_id) REFERENCES chunks(chunk_id)
);
CREATE INDEX idx_chunks_doc_id    ON chunks(doc_id);
CREATE INDEX idx_chunks_page      ON chunks(page_start, page_end);
CREATE INDEX idx_chunks_sheet     ON chunks(sheet_name);
```

#### `structured_tables` table
```sql
CREATE TABLE structured_tables (
    table_id        TEXT PRIMARY KEY,
    doc_id          TEXT NOT NULL,
    sheet_name      TEXT,
    row_count       INTEGER,
    col_count       INTEGER,
    headers         TEXT,                  -- JSON array
    parquet_path    TEXT NOT NULL,         -- path to Parquet file
    created_at      TEXT NOT NULL,
    FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
);
CREATE INDEX idx_struct_tables_doc_id ON structured_tables(doc_id);
```

#### `processing_logs` table
```sql
CREATE TABLE processing_logs (
    log_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id          TEXT NOT NULL,
    stage           TEXT NOT NULL,         -- ingestion, extraction, chunking, etc.
    attempt         INTEGER DEFAULT 1,
    status          TEXT NOT NULL,         -- started, completed, failed
    error_type      TEXT,
    error_message   TEXT,
    duration_ms     REAL,
    timestamp       TEXT NOT NULL,
    FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
);
CREATE INDEX idx_logs_doc_id ON processing_logs(doc_id);
CREATE INDEX idx_logs_stage  ON processing_logs(stage);
```

#### `retrieval_cache` table
```sql
CREATE TABLE retrieval_cache (
    cache_key       TEXT PRIMARY KEY,      -- hash of query + index_version
    query           TEXT NOT NULL,
    normalized_query TEXT NOT NULL,
    index_version   INTEGER NOT NULL,
    corpus_version  INTEGER NOT NULL,
    answer         TEXT NOT NULL,
    evidence_ids   TEXT,                   -- JSON array of chunk_ids
    cited_doc_versions TEXT,              -- JSON
    created_at     TEXT NOT NULL,
    expires_at     TEXT
);
CREATE INDEX idx_cache_version ON retrieval_cache(index_version, corpus_version);
```

#### `index_versions` table
```sql
CREATE TABLE index_versions (
    version_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    version_name    TEXT NOT NULL,
    embedding_model TEXT NOT NULL,
    embedding_version TEXT,
    created_at      TEXT NOT NULL,
    chunk_count     INTEGER,
    is_active      INTEGER DEFAULT 0,
    note            TEXT
);
```

## 2. Document Intermediate Representation (JSON/objects)

Each extracted document is normalized to:

```json
{
  "doc_id": "string",
  "provenance": {
    "drive_file_id": "string",
    "filename": "string",
    "folder_path": "string",
    "mime_type": "string",
    "revision_id": "string|null",
    "source_view_link": "string|null"
  },
  "metadata": {
    "title": "string|null",
    "created_at": "ISO8601|null",
    "modified_at": "ISO8601|null",
    "content_date_start": "ISO8601|null",
    "content_date_end": "ISO8601|null",
    "size_bytes": "number",
    "authority_status": "draft|final|proposal|confirmed|null",
    "contains_pii": "boolean"
  },
  "pages": [
    {
      "page_number": 1,
      "width": 612,
      "height": 792,
      "blocks": [
        {
          "block_type": "heading|paragraph|table|list|figure",
          "block_id": "string",
          "text": "string",
          "level": 1,
          "bbox": [x0, y0, x1, y1],
          "parent_block_id": "string|null"
        }
      ]
    }
  ],
  "tables": [
    {
      "table_id": "string",
      "page_number": 1,
      "row_count": 10,
      "col_count": 4,
      "headers": ["col1", "col2", "col3", "col4"],
      "rows": [
        {"row_index": 0, "cells": ["A1", "B1", "C1", "D1"]},
        {"row_index": 1, "cells": ["A2", "B2", "C2", "D2"]}
      ],
      "bbox": [x0, y0, x1, y1]
    }
  ],
  "extraction_quality": 0.95,
  "ocr_used": false,
  "ocr_metadata": {
    "engine": "string|null",
    "model_version": "string|null",
    "confidence": "number|null"
  }
}
```

## 3. Structured Table IR (Parquet Schema)

Each spreadsheet row stored with full provenance:

```python
{
    "workbook": string,        # original filename
    "sheet": string,           # sheet name
    "table_id": string,
    "row": int,
    "column": int,
    "cell_ref": "A1",          # e.g. "B3"
    "raw_value": string,       # as stored in cell
    "parsed_value": any,        # parsed numeric/date/etc.
    "unit": string|null,
    "currency": string|null,   # NPR, USD, etc.
    "display_value": string,
    "data_type": "string|number|date|currency|boolean|mixed",
    "provenance": {
        "drive_file_id": string,
        "source_chunk_id": string,
        "source_page": int|null
    }
}
```

## 4. Evidence JSON Schema

```json
{
  "query": "string",
  "intent": ["EXTRACT", "AGGREGATION"],
  "items": [
    {
      "chunk_id": "string",
      "doc_id": "string",
      "score": 0.87,
      "text": "string (text excerpt or table)",
      "provenance": {
        "drive_file_id": "string",
        "filename": "string",
        "folder_path": "string",
        "page": 3,
        "heading_path": ["3.2", "Sponsorship Revenue"],
        "table_id": "string|null",
        "row": 5,
        "cell": "B5"
      },
      "authority_score": 0.9
    }
  ],
  "is_sufficient": true,
  "missing_aspects": [],
  "conflicts_detected": false
}
```

## 5. Answer Output Schema

```json
{
  "answer_type": "FACTUAL|LIST|TABLE|COMPARISON|AGGREGATION|CALCULATION|TIMELINE|EXPORT|ABSTENTION|CONFLICT",
  "answer": "string",
  "table": [{"header": "string", "values": []}] | null,
  "verification": {
    "is_faithful": true,
    "unsupported_claims": [],
    "completeness": 1.0,
    "confidence": "HIGH|MEDIUM|LOW|ABSTAIN",
    "reasoning": "string"
  },
  "provenance": [
    {
      "drive_file_id": "string",
      "filename": "string",
      "folder_path": "string",
      "page": 3,
      "row": 5,
      "chunk_id": "string",
      "source_view_link": "string"
    }
  ],
  "completeness_breakdown": {
    "sub_answer_1": "HIGH",
    "sub_answer_2": "HIGH",
    "overall": "3/3 supported"
  }
}
```
