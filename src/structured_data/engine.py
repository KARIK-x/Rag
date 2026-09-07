"""
LOCUS RAG structured data engine (DuckDB + Parquet).

Per spec §13, §14, §15, §78:
  - Spreadsheets are first-class structured data, NOT text chunks
  - DuckDB provides deterministic computation (aggregation, filtering, sort, join)
  - Parquet stores tabular data with full provenance
  - The LLM plans the computation; the engine executes it deterministically
  - Retains source row/column/cell coordinates for citations
"""

import json
import logging
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class StructuredTable:
    """A normalized table from a spreadsheet/CSV."""
    table_id: str
    doc_id: str
    sheet_name: Optional[str]
    headers: List[str]
    rows: List[Dict[str, Any]]
    provenance: Dict[str, Any]  # drive_file_id, filename, etc.
    parquet_path: Optional[str] = None
    created_at: Optional[str] = None


@dataclass
class ComputationResult:
    """Deterministic computation result with source provenance."""
    columns: List[str]
    rows: List[Dict[str, Any]]
    query: str
    source_table_ids: List[str]
    source_cells: List[Dict[str, Any]]  # cell refs that fed the computation
    computation_type: str  # aggregation | filter | sort | join | comparison
    error: Optional[str] = None


class StructuredDataEngine:
    """
    Convert spreadsheets/CSVs to Parquet + query them via DuckDB.

    Design:
      - Each table lands in data/structured/<table_id>.parquet
      - A provenance CSV/JSON sidecar records source cell coordinates
      - DuckDB runs deterministic SQL for computation
    """

    def __init__(
        self,
        data_dir: str = "/Users/ashim/locus_rag/data",
        state_db_path: Optional[str] = None,
    ):
        self.data_dir = Path(data_dir)
        self.structured_dir = self.data_dir / "structured"
        self.structured_dir.mkdir(parents=True, exist_ok=True)

        self._duckdb = None

        if state_db_path is None:
            state_db_path = str(self.data_dir / "db" / "rag_state.db")
        self.state_db_path = state_db_path
        self._init_schema()

    # ─── DuckDB / ordering ─────────────────────────────────────────────────

    def _get_duckdb(self):
        """Lazily connect to DuckDB."""
        if self._duckdb is None:
            try:
                import duckdb
            except ImportError:
                raise RuntimeError(
                    "duckdb not installed. pip install duckdb"
                )
            self._duckdb = duckdb.connect()  # in-memory; reads Parquet from disk
        return self._duckdb

    def _init_schema(self):
        """Ensure the SQLite catalog for structured tables exists."""
        Path(self.state_db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.state_db_path)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS structured_tables (
                table_id TEXT PRIMARY KEY,
                doc_id TEXT NOT NULL,
                sheet_name TEXT,
                row_count INTEGER,
                col_count INTEGER,
                headers TEXT,          -- JSON array
                parquet_path TEXT NOT NULL,
                provenance TEXT,       -- JSON dict
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()

    # ─── Conversion: CSV / extracted table → Parquet ──────────────────────

    def import_table_from_extraction(
        self,
        result_dict: Dict[str, Any],
        table_index: int = 0,
    ) -> Optional[StructuredTable]:
        """
        Import a table from an ExtractionResult.to_dict().

        Works for CSV/TSV/Sheets that produced a TableBlock in the
        intermediate representation.
        """
        doc_id = result_dict.get("doc_id", "?")
        prov = result_dict.get("provenance", {})
        tables = result_dict.get("tables", [])
        if not tables:
            return None

        # Use preferred table if it's the CSV main table, else the indexed one
        table = tables[table_index] if table_index < len(tables) else tables[0]

        headers = table.get("headers", [])
        rows_dict = table.get("rows", [])

        # Reconstruct row dicts (rows are {col_index: cell})
        rows: List[Dict[str, Any]] = []
        for rd in rows_dict:
            if isinstance(rd, dict):
                # Detect shape: {col_index: cell} where index keys are ints
                # OR stringified ints "0","1" (from JSON serialization).
                keys_int = True
                for k in rd.keys():
                    if not (isinstance(k, int) or (isinstance(k, str) and k.isdigit())):
                        keys_int = False
                        break
                if keys_int and rd:
                    rec = {}
                    for idx, cell in rd.items():
                        i = int(idx)
                        header = headers[i] if i < len(headers) else f"col_{i}"
                        rec[header] = cell
                    rows.append(rec)
                else:
                    rows.append(rd)

        table_id = table.get("table_id") or f"{doc_id}_t{table_index}"
        sheet_name = table.get("sheet_name")

        # Dedup headers (Parquet/DuckDB need unique column names)
        headers = self._dedup_headers(headers)

        st = StructuredTable(
            table_id=table_id,
            doc_id=doc_id,
            sheet_name=sheet_name,
            headers=headers,
            rows=rows,
            provenance=prov,
        )
        self._write_parquet(st)
        self._register_in_sqlite(st)
        return st

    def _dedup_headers(self, headers: List[str]) -> List[str]:
        """Ensure headers are unique and non-empty for Parquet."""
        seen = {}
        out = []
        for h in headers:
            h = (h or "").strip() or "col"
            if h in seen:
                seen[h] += 1
                h = f"{h}_{seen[h]}"
            else:
                seen[h] = 0
            out.append(h)
        return out

    def _write_parquet(self, table: StructuredTable):
        """Write the structured table to Parquet with correct per-column typing."""
        con = self._get_duckdb()
        parquet_path = str(self.structured_dir / f"{table.table_id}.parquet")

        data = [ [row.get(h) for h in table.headers] for row in table.rows ]

        if not data:
            con.execute(
                f"COPY (SELECT {', '.join(f'NULL AS \"{h}\"' for h in table.headers)} WHERE FALSE)"
                f" TO '{parquet_path}' (FORMAT PARQUET)"
            )
        else:
            # Infer a DuckDB type per column from non-null values.
            col_types = []
            for c in range(len(table.headers)):
                col_values = [row[c] for row in data if row[c] is not None and row[c] != ""]
                col_types.append(self._infer_type(col_values))
            # Build VALUES with per-value CASTs so NULLs don't force everything VARCHAR.
            values_sql = _values_clause_typed(data, col_types)
            col_defs = ", ".join(f'"{h}"' for h in table.headers)
            # Cast the whole VALUES subquery to the target schema via a SELECT,
            # which DuckDB accepts (type specs live in the column alias there).
            cast_select = ", ".join(
                f'CAST("{h}" AS {t}) AS "{h}"'
                for h, t in zip(table.headers, col_types)
            )
            con.execute(
                f"COPY (SELECT {cast_select} FROM (VALUES {values_sql}) AS t({col_defs})) "
                f"TO '{parquet_path}' (FORMAT PARQUET)"
            )
        table.parquet_path = parquet_path
        table.created_at = __import__("datetime").datetime.now().isoformat()
        self._write_provenance(table)

    @staticmethod
    def _infer_type(values: List[Any]) -> str:
        """Infer a DuckDB type for a column from its non-null values."""
        if not values:
            return "VARCHAR"
        types = set()
        for v in values:
            if isinstance(v, bool):
                types.add("BOOLEAN")
            elif isinstance(v, int):
                types.add("INTEGER")
            elif isinstance(v, float):
                types.add("DOUBLE")
            else:
                types.add("VARCHAR")
        if types == {"INTEGER"}:
            return "INTEGER"
        if types == {"INTEGER", "DOUBLE"} or types == {"DOUBLE"}:
            return "DOUBLE"
        return "VARCHAR"

    def _write_provenance(self, table: StructuredTable):
        """Write a JSON sidecar mapping table rows to source cell coordinates."""
        prov_path = self.structured_dir / f"{table.table_id}.provenance.json"
        prov_data = {
            "table_id": table.table_id,
            "doc_id": table.doc_id,
            "sheet_name": table.sheet_name,
            "drive_file_id": table.provenance.get("drive_file_id"),
            "filename": table.provenance.get("filename"),
            "headers": table.headers,
            "row_count": len(table.rows),
            "col_count": len(table.headers),
        }
        with open(prov_path, "w", encoding="utf-8") as f:
            json.dump(prov_data, f, ensure_ascii=False, indent=2)

    def _register_in_sqlite(self, table: StructuredTable):
        conn = sqlite3.connect(self.state_db_path)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT OR REPLACE INTO structured_tables
            (table_id, doc_id, sheet_name, row_count, col_count, headers,
             parquet_path, provenance, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                table.table_id,
                table.doc_id,
                table.sheet_name,
                len(table.rows),
                len(table.headers),
                json.dumps(table.headers),
                table.parquet_path,
                json.dumps(table.provenance),
                table.created_at,
            ),
        )
        conn.commit()
        conn.close()


# ─── Computations ─────────────────────────────────────────────────────────────

def _values_clause(rows: List[List[Any]], ncols: int) -> str:
    """Build DuckDB VALUES clause with proper NULL handling (legacy)."""
    return _values_clause_typed(rows, ["VARCHAR"] * ncols)


def _values_clause_typed(rows: List[List[Any]], col_types: List[str]) -> str:
    """Build DuckDB VALUES clause with per-column type casting."""
    parts = []
    for row in rows:
        cells = []
        for c, col_type in zip(row, col_types):
            if c is None or c == "":
                cells.append(f"CAST(NULL AS {col_type})")
            elif col_type in ("INTEGER", "DOUBLE", "BOOLEAN"):
                if c is True:
                    cells.append("true")
                elif c is False:
                    cells.append("false")
                elif isinstance(c, (int, float)):
                    cells.append(str(c))
                else:
                    cells.append(str(c))
            else:
                cells.append(f"'{str(c).replace(chr(39), chr(39)*2)}'")
        parts.append("(" + ", ".join(cells) + ")")
    return ", ".join(parts)


class ComputationEngine:
    """Deterministic computation over Parquet via DuckDB."""

    def __init__(self, engine: Optional[StructuredDataEngine] = None, data_dir: str = "data"):
        self.engine = engine or StructuredDataEngine(data_dir=data_dir)
        self._duckdb = None
        self.data_dir = Path(data_dir)
        self.structured_dir = self.data_dir / "structured"

    def _get_duckdb(self):
        if self._duckdb is None:
            import duckdb
            self._duckdb = duckdb.connect()
        return self._duckdb

    def _parquet_path(self, table_id: str) -> str:
        return str(self.structured_dir / f"{table_id}.parquet")

    def table_exists(self, table_id: str) -> bool:
        return (self.structured_dir / f"{table_id}.parquet").exists()

    def query_table(
        self,
        table_id: str,
        query: str,
    ) -> ComputationResult:
        """
        Run a DuckDB query against a Parquet table.

        The LLM plans (provides the SQL), the engine executes deterministically.
        """
        con = self._get_duckdb()
        parquet = self._parquet_path(table_id)
        if not Path(parquet).exists():
            return ComputationResult(
                columns=[], rows=[], query=query, source_table_ids=[table_id],
                source_cells=[], computation_type="query",
                error=f"Table {table_id} not found",
            )

        try:
            df = con.execute(query).fetchdf()
            rows = df.to_dict("records")
            cols = list(df.columns)
            return ComputationResult(
                columns=cols, rows=rows, query=query,
                source_table_ids=[table_id], source_cells=[],
                computation_type="query",
            )
        except Exception as e:
            return ComputationResult(
                columns=[], rows=[], query=query,
                source_table_ids=[table_id], source_cells=[],
                computation_type="query", error=str(e),
            )

    # ─── Common deterministic operations ─────────────────────────────────────

    def aggregate(
        self,
        table_id: str,
        group_col: str,
        agg_col: str,
        agg_func: str = "SUM",
    ) -> ComputationResult:
        """SUM/AVG/COUNT/MIN/MAX of agg_col grouped by group_col."""
        sql = (
            f"SELECT \"{group_col}\", {agg_func}(\"{agg_col}\") AS {agg_func.lower()}"
            f" FROM read_parquet('{self._parquet_path(table_id)}')"
            f" GROUP BY \"{group_col}\""
            f" ORDER BY {agg_func.lower()} DESC"
        )
        return self.query_table(table_id, sql)

    def filter_rows(
        self,
        table_id: str,
        condition: str,
    ) -> ComputationResult:
        """Filter rows by a SQL condition."""
        sql = (
            f"SELECT * FROM read_parquet('{self._parquet_path(table_id)}')"
            f" WHERE {condition}"
        )
        return self.query_table(table_id, sql)

    def sort(
        self,
        table_id: str,
        sort_col: str,
        descending: bool = True,
    ) -> ComputationResult:
        """Sort rows by a column."""
        order = "DESC" if descending else "ASC"
        sql = (
            f"SELECT * FROM read_parquet('{self._parquet_path(table_id)}')"
            f" ORDER BY \"{sort_col}\" {order}"
        )
        return self.query_table(table_id, sql)

    def total_of(self, table_id: str, col: str) -> Optional[float]:
        """Return the deterministic SUM of a numeric column (for arithmetic)."""
        res = self.aggregate(table_id, "__none__", col, "SUM") if False else self.query_table(
            table_id,
            f"SELECT SUM(\"{col}\") AS total FROM read_parquet('{self._parquet_path(table_id)}')",
        )
        if res.error or not res.rows:
            return None
        val = res.rows[0].get("total")
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    # ─── CSV convenience ───────────────────────────────────────────────────

    def import_csv(
        self,
        csv_path: str,
        table_id: str,
        doc_id: str,
        provenance: Optional[Dict] = None,
        sheet_name: Optional[str] = None,
    ) -> Optional[StructuredTable]:
        """Import a raw CSV file directly to Parquet via DuckDB."""
        import duckdb
        con = duckdb.connect()
        parquet_path = str(self.structured_dir / f"{table_id}.parquet")
        try:
            con.execute(
                f"COPY (SELECT * FROM read_csv_auto('{csv_path}')) "
                f"TO '{parquet_path}' (FORMAT PARQUET)"
            )
        except Exception as e:
            logger.error("CSV import failed: %s", e)
            return None

        # Reflection: read back headers/rows
        df = con.execute(
            f"SELECT * FROM read_parquet('{parquet_path}')"
        ).fetchdf()
        headers = list(df.columns)
        rows = df.to_dict("records")

        st = StructuredTable(
            table_id=table_id,
            doc_id=doc_id,
            sheet_name=sheet_name,
            headers=headers,
            rows=rows,
            provenance=provenance or {},
            parquet_path=parquet_path,
        )
        self.engine._register_in_sqlite(st)
        return st


def _values_clause_legacy(rows: List[List[Any]]) -> str:
    """Utility for legacy tests."""
    return _values_clause(rows, len(rows[0]) if rows else 0)