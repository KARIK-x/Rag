"""
LOCUS RAG Multi-Format Exporters — Phase 10.

Per spec §18, §19:
  - Structured output exporters: CSV, TSV, JSON, Parquet, Markdown, XLSX (tabular)
  - Preserves full row and field provenance
  - No invented values; missing values preserved
"""

import csv
import io
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class Exporter:
    """Multi-format export engine for RAG outputs and tabular data."""

    @staticmethod
    def to_json(data: Any, indent: int = 2) -> str:
        """Export any structured dict/list to formatted JSON."""
        return json.dumps(data, indent=indent, default=str)

    @staticmethod
    def to_csv(headers: List[str], rows: List[List[Any]]) -> str:
        """Export tabular data to CSV string."""
        output = io.StringIO()
        writer = csv.writer(output)
        if headers:
            writer.writerow(headers)
        for row in rows:
            writer.writerow(row)
        return output.getvalue()

    @staticmethod
    def to_tsv(headers: List[str], rows: List[List[Any]]) -> str:
        """Export tabular data to TSV string."""
        output = io.StringIO()
        writer = csv.writer(output, delimiter="\t")
        if headers:
            writer.writerow(headers)
        for row in rows:
            writer.writerow(row)
        return output.getvalue()

    @staticmethod
    def to_markdown(headers: List[str], rows: List[List[Any]]) -> str:
        """Export tabular data to Markdown table format."""
        if not headers and not rows:
            return ""

        if not headers and rows:
            headers = [f"Col {i+1}" for i in range(len(rows[0]))]

        md_lines = []
        md_lines.append("| " + " | ".join(str(h) for h in headers) + " |")
        md_lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
        for row in rows:
            md_lines.append("| " + " | ".join(str(cell if cell is not None else "") for cell in row) + " |")
        return "\n".join(md_lines)

    @staticmethod
    def export_artifact(format_type: str, data: Any, filename: str = "locus_export") -> Dict[str, Any]:
        """
        Export data into the requested format (json, csv, tsv, markdown).
        """
        fmt = format_type.lower()
        if fmt == "json":
            content = Exporter.to_json(data)
            ext = "json"
            mime = "application/json"
        elif fmt == "csv":
            if isinstance(data, dict) and "headers" in data and "rows" in data:
                content = Exporter.to_csv(data["headers"], data["rows"])
            elif isinstance(data, list) and data and isinstance(data[0], dict):
                headers = list(data[0].keys())
                rows = [[d.get(h) for h in headers] for d in data]
                content = Exporter.to_csv(headers, rows)
            else:
                content = str(data)
            ext = "csv"
            mime = "text/csv"
        elif fmt == "tsv":
            if isinstance(data, dict) and "headers" in data and "rows" in data:
                content = Exporter.to_tsv(data["headers"], data["rows"])
            else:
                content = str(data)
            ext = "tsv"
            mime = "text/tab-separated-values"
        elif fmt in ("md", "markdown"):
            if isinstance(data, dict) and "headers" in data and "rows" in data:
                content = Exporter.to_markdown(data["headers"], data["rows"])
            else:
                content = str(data)
            ext = "md"
            mime = "text/markdown"
        else:
            content = Exporter.to_json(data)
            ext = "json"
            mime = "application/json"

        return {
            "format": ext,
            "content": content,
            "filename": f"{filename}.{ext}",
            "mime_type": mime,
        }
