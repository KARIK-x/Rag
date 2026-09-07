# ADR-007: Structured Data Engine

**Status:** DECIDED

## Problem
LOCUS contains 631 Google Sheets, 169 CSVs, and 55 XLSX files with structured sponsorship, budget, and event data. This data must not be reduced to text chunks — it needs a first-class structured representation for deterministic computation (SUM, AVG, GROUP BY, JOIN).

## Decision
**DuckDB + Parquet** as the structured data engine.

### Why DuckDB
- Embedded analytical database — no server, no installation beyond Python package
- Excellent Parquet support (read and write)
- Can query XLSX and CSV directly via extensions
- Fast aggregation, filtering, sorting, joins
- Deterministic computation — no LLM hallucination risk
- Exports to CSV, JSON, Parquet natively

### Why Parquet
- Columnar format — efficient for analytical queries
- Schema preservation
- Compressed storage
- DuckDB-native

## Alternative Rejected
| Alternative | Reason for Rejection |
|-------------|----------------------|
| SQLite | Good for metadata, weaker analytical queries |
| Pandas | In-memory only; no persistent queries |
| PostgreSQL | Requires server; overkill for local V1 |
| Polars | Good but DuckDB has better SQL surface and export |

## Implementation Notes
- Each spreadsheet → one Parquet file with full cell-level provenance
- DuckDB used for: filtering, aggregation, sorting, comparison, year-over-year calculations
- Results returned with source row/column/cell provenance
- Parquet files stored in `data/structured/`

## Revisit Conditions
- Re-evaluate if LOCUS adds >100GB of structured data
- Re-evaluate if complex multi-workbook JOINs become common
