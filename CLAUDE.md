# LOCUS RAG

Local-first, high-reliability, high-recall institutional knowledge and retrieval system for LOCUS.

## Mission
Build an evidence-first system that acts as an institutional search engine, document intelligence system, structured-data analysis engine, evidence verification system, answer generation layer, and export/transformation engine.

## Core Rules
1. Google Drive is READ-ONLY. Never modify, create, delete, or move Drive files or permissions.
2. Reuse the existing SQLite catalog at `/Users/ashim/locus_drive/locus_drive.db`.
3. Evidence-first: LLM is not the authority; source documents and structured data are the authority.
4. Support deterministic calculations, table/spreadsheet querying via DuckDB/Parquet, and structured multi-format exports.
5. Strict test-driven development, benchmarking, and failure attribution.

## Key Directories
- `src/`: Core Python modules
- `eval/`: Benchmark datasets and metrics
- `tests/`: Unit, integration, e2e, regression tests
- `docs/`: Architecture specifications, ADRs, schemas, phase definitions
- `data/`: Local storage for raw copies, extracted text, chunks, DuckDB/Parquet tables, indexes
