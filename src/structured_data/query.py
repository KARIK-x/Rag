"""
LOCUS RAG structured-data query router.

Per spec §14 (structured query safety):
  1. Retrieve relevant table
  2. Identify exact rows/columns
  3. Execute deterministic computation
  4. Retain source coordinates
  5. Verify the computation
  6. Cite the source rows

The LLM MAY plan (pick intent: sum/avg/filter/sort/join).
The engine MUST execute the computation deterministically — never let
an LLM do the arithmetic.
"""

import json
import logging
import sqlite3
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.structured_data.engine import (
    StructuredDataEngine,
    ComputationEngine,
    ComputationResult,
)

logger = logging.getLogger(__name__)


# ─── Intents for structured queries ──────────────────────────────────────────

class StructuredIntent:
    AGGREGATE_GROUP = "aggregate_group"   # SUM/AVG/COUNT/MIN/MAX by category
    TOTAL = "total"                        # total sponsorship, total budget
    FILTER = "filter"                      # contributors above X
    SORT = "sort"                          # sort sponsors by amount
    COMPARE = "compare"                    # compare two subsets

    @classmethod
    def all(cls):
        return [cls.AGGREGATE_GROUP, cls.TOTAL, cls.FILTER, cls.SORT, cls.COMPARE]


@dataclass
class StructuredQueryResult:
    """Result of a structured query with full provenance."""
    intent: str
    table_id: Optional[str]
    headers: List[str]
    rows: List[Dict[str, Any]]
    computation_sql: Optional[str]
    source_table_ids: List[str]
    source_cells: List[Dict[str, Any]]
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent,
            "table_id": self.table_id,
            "headers": self.headers,
            "rows": self.rows,
            "computation_sql": self.computation_sql,
            "source_table_ids": self.source_table_ids,
            "source_cells": self.source_cells,
            "error": self.error,
        }


class StructuredQueryRouter:
    """Route spreadsheet questions to the deterministic computation engine."""

    def __init__(
        self,
        data_dir: str = "/Users/ashim/locus_rag/data",
        state_db_path: Optional[str] = None,
    ):
        if state_db_path is None:
            state_db_path = str(Path(data_dir) / "db" / "rag_state.db")
        self.engine = StructuredDataEngine(data_dir=data_dir, state_db_path=state_db_path)
        self.compute = ComputationEngine(engine=self.engine, data_dir=data_dir)
        self.data_dir = Path(data_dir)
        self.state_db_path = state_db_path

    def list_tables(self) -> List[Dict[str, Any]]:
        """List all structured tables registered in SQLite."""
        conn = sqlite3.connect(self.state_db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT table_id, doc_id, sheet_name, row_count, col_count, headers, provenance "
            "FROM structured_tables ORDER BY created_at DESC"
        )
        rows = cur.fetchall()
        conn.close()
        return [
            {
                "table_id": r[0],
                "doc_id": r[1],
                "sheet_name": r[2],
                "row_count": r[3],
                "col_count": r[4],
                "headers": json.loads(r[5]) if r[5] else [],
                "provenance": json.loads(r[6]) if r[6] else {},
            }
            for r in rows
        ]

    def find_table(self, table_id: str) -> Optional[Dict[str, Any]]:
        """Look up a specific table."""
        for t in self.list_tables():
            if t["table_id"] == table_id:
                return t
        return None

    def plan(
        self, table_id: str, query: str
    ) -> Dict[str, Any]:
        """
        PLAN a structured query (the LLM provides the intent; the engine
        executes). For V1 we use deterministic heuristics + regex to map
        common questions to SQL templates. The interface is designed so an
        LLM planner can call the same methods.
        """
        q = query.lower()
        headers = self._table_headers(table_id) or []

        # Determine numeric columns
        numeric_cols = self._detect_numeric_cols(table_id, headers)
        amount_cols = [c for c in numeric_cols if any(k in c for k in
                       ("amount", "amt", "contribution", "revenue", "budget",
                        "cost", "spend", "total", "price", "value", "sum"))]
        group_cols = [c for c in headers if c not in numeric_cols]

        plan = {
            "table_id": table_id,
            "headers": headers,
            "numeric_cols": numeric_cols,
            "amount_cols": amount_cols or numeric_cols,
            "group_cols": group_cols,
            "intent": None,
            "sql": None,
        }

        # SORT (highest priority after TOTAL — "sort by amount" must not become aggregate)
        sort_kw = re.search(r"\b(sort|largest|highest|maximum|top|biggest|ranking|descending|lowest|smallest)\b", q)
        if sort_kw and not re.search(r"\bsum\b", q):
            col = self._amount_col_for(q, amount_cols, numeric_cols) or (numeric_cols[0] if numeric_cols else None)
            if col:
                plan["intent"] = StructuredIntent.SORT
                plan["amount_col"] = col
                plan["sql"] = (
                    f'SELECT * FROM read_parquet('
                    f"'{self.compute._parquet_path(table_id)}') "
                    f'ORDER BY "{col}" DESC'
                )
                return plan

        # TOTAL — literal "total" (not ambiguous "sum" which may combine with group-by)
        if re.search(r"\btotal\b|\bsum of\b|\boverall\b", q) and ("sponsorship" in q or "amount" in q or "revenue" in q or "budget" in q):
            col = self._amount_col_for(q, amount_cols, numeric_cols)
            plan["intent"] = StructuredIntent.TOTAL
            plan["amount_col"] = col
            plan["sql"] = (
                f'SELECT SUM("{col}") AS total FROM read_parquet('
                f"'{self.compute._parquet_path(table_id)}')"
            )
            return plan

        # GROUP BY category + SUM
        if re.search(r"\b(by|per|each|group)\b", q):
            group = self._group_col_for(q, group_cols)
            col = self._amount_col_for(q, amount_cols, numeric_cols)
            if group and col:
                plan["intent"] = StructuredIntent.AGGREGATE_GROUP
                plan["group_col"] = group
                plan["amount_col"] = col
                plan["sql"] = (
                    f'SELECT "{group}", SUM("{col}") AS total FROM read_parquet('
                    f"'{self.compute._parquet_path(table_id)}') "
                    f'GROUP BY "{group}" ORDER BY total DESC'
                )
                return plan

        # FILTER: above/threshold/over (checked before GROUP so "above 200000" doesn't become group)
        num_match = re.search(r"(above|over|greater than|more than|exceeding|at least|>=|>)\s*([\d,]+)", q)
        if num_match and amount_cols:
            cond = num_match.group(2).replace(",", "")
            col = self._amount_col_for(q, amount_cols, numeric_cols)
            op = ">=" if "at least" in q else ">"
            plan["intent"] = StructuredIntent.FILTER
            plan["amount_col"] = col
            plan["threshold"] = cond
            plan["sql"] = (
                f'SELECT * FROM read_parquet('
                f"'{self.compute._parquet_path(table_id)}') "
                f'WHERE "{col}" {op} {cond}'
            )
            return plan

        return plan

    def _table_headers(self, table_id: str) -> List[str]:
        t = self.find_table(table_id)
        return t["headers"] if t else []

    def _detect_numeric_cols(self, table_id: str, headers: List[str]) -> List[str]:
        """Determine which columns hold numbers (via schema FROM parquet)."""
        try:
            import duckdb
            con = duckdb.connect()
            schema = con.execute(
                f"DESCRIBE SELECT * FROM read_parquet('{self.compute._parquet_path(table_id)}')"
            ).fetchall()
            return [
                col[0]
                for col in schema
                if col[1] in ("INTEGER", "BIGINT", "DOUBLE", "FLOAT", "DECIMAL", "HUGEINT")
            ]
        except Exception:
            return []

    def _amount_col_for(self, q: str, amount_cols: List[str], numeric_cols: List[str]) -> Optional[str]:
        """Pick the amount column most relevant to the query."""
        if not amount_cols and not numeric_cols:
            return None
        # Prefer column whose name appears in query
        for c in (amount_cols + numeric_cols):
            if c.lower() in q:
                return c
        return amount_cols[0] if amount_cols else numeric_cols[0]

    def _group_col_for(self, q: str, group_cols: List[str]) -> Optional[str]:
        # Prefer a column that appears in the query as the group target
        # (word-boundary match; e.g. "category" in "sponsors by category").
        for c in group_cols:
            if re.search(rf"\b{re.escape(c.lower())}\b", q):
                return c
        # Prefer categorical/semantic columns over entity lists
        for preferred in ("category", "year", "tier", "type", "level",
                          "month", "department", "faculty", "event"):
            if preferred in group_cols:
                return preferred
        # Fall back to the column explicitly named with a boundary
        for c in group_cols:
            if re.search(rf"\b{re.escape(c.lower())}s?\b", q):
                return c
        return group_cols[0] if group_cols else None

    def execute(self, plan: Dict[str, Any]) -> StructuredQueryResult:
        """Execute a plan deterministically via DuckDB."""
        table_id = plan.get("table_id")
        sql = plan.get("sql")
        intent = plan.get("intent")
        if not table_id or not sql or not intent:
            return StructuredQueryResult(
                intent=intent or "unknown",
                table_id=table_id,
                headers=[],
                rows=[],
                computation_sql=sql,
                source_table_ids=[table_id] if table_id else [],
                source_cells=[],
                error="Invalid plan",
            )

        res = self.compute.query_table(table_id, sql)
        return StructuredQueryResult(
            intent=intent,
            table_id=table_id,
            headers=res.columns,
            rows=res.rows,
            computation_sql=sql,
            source_table_ids=[table_id],
            source_cells=[],  # source row/col mapping added later
            error=res.error,
        )