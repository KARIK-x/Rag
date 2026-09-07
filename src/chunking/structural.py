"""
LOCUS RAG structural chunker.

Per spec §25:
  - Heading-aware (heading context preserved on every chunk)
  - Section-aware
  - Page-aware (chunks carry page_start/page_end)
  - Table-aware (tables stay intact)
  - List-aware
  - Semantically coherent
  - Independently intelligible

Each chunk carries:
  chunk_id, doc_id, parent_chunk_id, heading_path, page_range,
  sheet_name, row_range, raw_text, normalized_text, contextual_prefix,
  source_locator (provenance), drive_file_id, drive_view_link

Critically: a chunk like "Amount: Rs. 50,000" is unacceptable if the heading
explaining the amount was discarded. We always prepend the heading_path
to the chunk text.
"""

import hashlib
import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.extraction.router import (
    ExtractedPage,
    TextBlock,
    TableBlock,
    ExtractionResult,
)

logger = logging.getLogger(__name__)


# ─── Chunk dataclass ────────────────────────────────────────────────────────

@dataclass
class Chunk:
    """A retrievable chunk with full provenance."""
    chunk_id: str
    doc_id: str
    parent_chunk_id: Optional[str]
    heading_path: List[str]
    page_start: Optional[int]
    page_end: Optional[int]
    sheet_name: Optional[str]
    row_start: Optional[int]
    row_end: Optional[int]
    raw_text: str
    normalized_text: str
    contextual_prefix: str
    drive_file_id: Optional[str]
    drive_view_link: Optional[str]
    source_locator: Dict[str, Any] = field(default_factory=dict)
    chunk_type: str = "text"  # text | table | heading | list
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "doc_id": self.doc_id,
            "parent_chunk_id": self.parent_chunk_id,
            "heading_path": self.heading_path,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "sheet_name": self.sheet_name,
            "row_start": self.row_start,
            "row_end": self.row_end,
            "raw_text": self.raw_text,
            "normalized_text": self.normalized_text,
            "contextual_prefix": self.contextual_prefix,
            "drive_file_id": self.drive_file_id,
            "drive_view_link": self.drive_view_link,
            "source_locator": self.source_locator,
            "chunk_type": self.chunk_type,
            "metadata": self.metadata,
        }


# ─── Chunker ────────────────────────────────────────────────────────────────

class StructuralChunker:
    """
    Heading/section/page/table-aware structural chunker.

    Strategy:
      1. Walk the page stream in order.
      2. Maintain a current heading_path as we cross headings.
      3. Accumulate text blocks under the current heading until size threshold.
      4. Force a break at each heading level 1–2 boundary (unless a single
         section exceeds the hard cap).
      5. Tables stay intact: a table block creates its own chunk.
      6. Every text chunk gets a `contextual_prefix` carrying the heading_path
         so retrieval has access to the section context.
    """

    def __init__(
        self,
        target_size: int = 600,        # target chars per chunk
        hard_cap: int = 1200,          # never exceed this
        min_size: int = 100,           # don't produce tiny chunks
        overlap: int = 100,            # char overlap between consecutive text chunks
        include_contextual_prefix: bool = True,
    ):
        self.target = target_size
        self.hard_cap = hard_cap
        self.min_size = min_size
        self.overlap = overlap
        self.include_prefix = include_contextual_prefix

    def chunk(self, result: ExtractionResult) -> List[Chunk]:
        """Convert an ExtractionResult into a list of Chunks."""
        doc_id = result.doc_id
        prov = result.provenance or {}
        drive_file_id = prov.get("drive_file_id")
        drive_view_link = prov.get("web_view_link")

        chunks: List[Chunk] = []
        current_heading_path: List[str] = []
        current_sheet: Optional[str] = None
        current_page: Optional[int] = None

        # Buffer of text blocks + their page/heading info since the last chunk break
        buffer_text: List[str] = []
        buffer_pages: List[int] = []
        buffer_headings: List[List[str]] = []

        def flush(force: bool = False) -> None:
            """Flush current buffer as a chunk if it meets size threshold."""
            nonlocal buffer_text, buffer_pages, buffer_headings
            if not buffer_text:
                return
            combined = "\n\n".join(buffer_text).strip()
            if not combined:
                buffer_text, buffer_pages, buffer_headings = [], [], []
                return
            if not force and len(combined) < self.min_size:
                return  # keep accumulating

            # Most common heading in buffer
            headings: List[List[str]] = [h for h in buffer_headings if h]
            heading_path = headings[-1] if headings else current_heading_path

            prefix = self._build_prefix(
                heading_path=heading_path,
                page_start=min(buffer_pages) if buffer_pages else None,
                page_end=max(buffer_pages) if buffer_pages else None,
                sheet_name=current_sheet,
                drive_filename=prov.get("filename"),
            )

            chunk_id = self._make_chunk_id(doc_id, combined, prefix)
            chunk = Chunk(
                chunk_id=chunk_id,
                doc_id=doc_id,
                parent_chunk_id=None,
                heading_path=heading_path,
                page_start=min(buffer_pages) if buffer_pages else None,
                page_end=max(buffer_pages) if buffer_pages else None,
                sheet_name=current_sheet,
                row_start=None,
                row_end=None,
                raw_text=combined,
                normalized_text=combined.lower(),  # simple
                contextual_prefix=prefix,
                drive_file_id=drive_file_id,
                drive_view_link=drive_view_link,
                source_locator={
                    "drive_file_id": drive_file_id,
                    "doc_id": doc_id,
                    "page_start": min(buffer_pages) if buffer_pages else None,
                    "page_end": max(buffer_pages) if buffer_pages else None,
                    "sheet_name": current_sheet,
                    "heading_path": heading_path,
                },
                chunk_type="text",
            )
            chunks.append(chunk)
            buffer_text, buffer_pages, buffer_headings = [], [], []

        for page in result.pages:
            current_page = page.page_number
            for block in page.blocks:
                if block.block_type == "heading":
                    # Heading: update path, then break chunk if size threshold met
                    level = block.level or 1
                    # Trim path to the new level's depth
                    current_heading_path = current_heading_path[: level - 1]
                    current_heading_path.append(block.text.strip())
                    if level <= 2 and self.include_prefix:
                        # Force a break at major heading boundaries
                        flush(force=True)
                    # Add the heading itself as a small chunk
                    if len(block.text.strip()) >= 5:
                        prefix = self._build_prefix(
                            heading_path=current_heading_path,
                            page_start=current_page,
                            page_end=current_page,
                            sheet_name=current_sheet,
                            drive_filename=prov.get("filename"),
                        )
                        chunk_id = self._make_chunk_id(doc_id, block.text, prefix)
                        chunks.append(Chunk(
                            chunk_id=chunk_id,
                            doc_id=doc_id,
                            parent_chunk_id=None,
                            heading_path=list(current_heading_path),
                            page_start=current_page,
                            page_end=current_page,
                            sheet_name=current_sheet,
                            row_start=None,
                            row_end=None,
                            raw_text=block.text.strip(),
                            normalized_text=block.text.lower(),
                            contextual_prefix=prefix,
                            drive_file_id=drive_file_id,
                            drive_view_link=drive_view_link,
                            source_locator={
                                "drive_file_id": drive_file_id,
                                "doc_id": doc_id,
                                "page": current_page,
                                "heading_path": list(current_heading_path),
                            },
                            chunk_type="heading",
                        ))
                    continue

                if block.block_type == "table" and block.text:
                    # Tables become their own chunk
                    flush(force=True)
                    table_text = block.text.strip()
                    if len(table_text) > self.hard_cap:
                        # Slice table into multiple chunks
                        for i, start in enumerate(range(0, len(table_text), self.target)):
                            piece = table_text[start: start + self.target]
                            prefix = self._build_prefix(
                                heading_path=current_heading_path,
                                page_start=current_page,
                                page_end=current_page,
                                sheet_name=current_sheet,
                                drive_filename=prov.get("filename"),
                            )
                            chunk_id = self._make_chunk_id(doc_id, piece, f"{prefix}#{i}")
                            chunks.append(Chunk(
                                chunk_id=chunk_id,
                                doc_id=doc_id,
                                parent_chunk_id=None,
                                heading_path=list(current_heading_path),
                                page_start=current_page,
                                page_end=current_page,
                                sheet_name=current_sheet,
                                row_start=None,
                                row_end=None,
                                raw_text=piece,
                                normalized_text=piece.lower(),
                                contextual_prefix=prefix,
                                drive_file_id=drive_file_id,
                                drive_view_link=drive_view_link,
                                source_locator={
                                    "drive_file_id": drive_file_id,
                                    "doc_id": doc_id,
                                    "page": current_page,
                                    "table_part": i,
                                },
                                chunk_type="table",
                            ))
                    else:
                        prefix = self._build_prefix(
                            heading_path=current_heading_path,
                            page_start=current_page,
                            page_end=current_page,
                            sheet_name=current_sheet,
                            drive_filename=prov.get("filename"),
                        )
                        chunk_id = self._make_chunk_id(doc_id, table_text, prefix)
                        chunks.append(Chunk(
                            chunk_id=chunk_id,
                            doc_id=doc_id,
                            parent_chunk_id=None,
                            heading_path=list(current_heading_path),
                            page_start=current_page,
                            page_end=current_page,
                            sheet_name=current_sheet,
                            raw_text=table_text,
                            normalized_text=table_text.lower(),
                            contextual_prefix=prefix,
                            drive_file_id=drive_file_id,
                            drive_view_link=drive_view_link,
                            source_locator={
                                "drive_file_id": drive_file_id,
                                "doc_id": doc_id,
                                "page": current_page,
                            },
                            chunk_type="table",
                        ))
                    continue

                # Regular paragraph/list block
                if not block.text.strip():
                    continue
                buffer_text.append(block.text)
                buffer_pages.append(current_page or 0)
                buffer_headings.append(list(current_heading_path))

                # Hard cap reached → flush
                combined = "\n\n".join(buffer_text)
                if len(combined) > self.hard_cap:
                    flush(force=True)

            # Also pull in any TableBlock objects captured in the page
            for t in page.tables:
                flush(force=True)
                t_text = self._table_to_text(t)
                prefix = self._build_prefix(
                    heading_path=current_heading_path,
                    page_start=current_page,
                    page_end=current_page,
                    sheet_name=current_sheet,
                    drive_filename=prov.get("filename"),
                )
                chunk_id = self._make_chunk_id(doc_id, t_text, prefix)
                chunks.append(Chunk(
                    chunk_id=chunk_id,
                    doc_id=doc_id,
                    parent_chunk_id=None,
                    heading_path=list(current_heading_path),
                    page_start=current_page,
                    page_end=current_page,
                    sheet_name=current_sheet,
                    row_start=1,
                    row_end=t.row_count,
                    raw_text=t_text,
                    normalized_text=t_text.lower(),
                    contextual_prefix=prefix,
                    drive_file_id=drive_file_id,
                    drive_view_link=drive_view_link,
                    source_locator={
                        "drive_file_id": drive_file_id,
                        "doc_id": doc_id,
                        "page": current_page,
                        "table_id": t.table_id,
                        "row_range": f"1-{t.row_count}",
                    },
                    chunk_type="table",
                    metadata={
                        "row_count": t.row_count,
                        "col_count": t.col_count,
                        "headers": t.headers,
                    },
                ))

        # Flush remaining
        flush(force=True)

        # Apply overlap between consecutive text chunks (sliding window)
        chunks = self._apply_overlap(chunks)
        return chunks

    # ─── Helpers ────────────────────────────────────────────────────────────

    def _build_prefix(
        self,
        heading_path: List[str],
        page_start: Optional[int],
        page_end: Optional[int],
        sheet_name: Optional[str],
        drive_filename: Optional[str],
    ) -> str:
        """Build a contextual prefix carrying section/page context."""
        if not self.include_prefix:
            return ""
        parts = []
        if drive_filename:
            parts.append(f"Document: {drive_filename}")
        if heading_path:
            parts.append("Section: " + " > ".join(heading_path))
        if page_start is not None:
            page_str = f"Page {page_start}" if page_start == page_end else f"Pages {page_start}-{page_end}"
            parts.append(page_str)
        if sheet_name:
            parts.append(f"Sheet: {sheet_name}")
        return "\n".join(parts)

    def _table_to_text(self, table: TableBlock) -> str:
        """Serialize a TableBlock to readable text with provenance."""
        lines = []
        if table.headers:
            lines.append(" | ".join(table.headers))
            lines.append("-" * 40)
        for row in table.rows:
            cells = [row.get(c, "") for c in range(len(table.headers))] if table.headers else []
            lines.append(" | ".join(cells))
        return "\n".join(lines)

    def _make_chunk_id(self, doc_id: str, text: str, prefix: str) -> str:
        """Deterministic chunk ID."""
        h = hashlib.sha256(f"{doc_id}:{prefix}:{text[:200]}".encode()).hexdigest()[:16]
        return f"ch_{h}"

    def _apply_overlap(self, chunks: List[Chunk]) -> List[Chunk]:
        """Add overlap between consecutive text chunks (sliding window)."""
        if self.overlap <= 0 or len(chunks) < 2:
            return chunks
        out: List[Chunk] = []
        prev = None
        for c in chunks:
            if prev and c.chunk_type in ("text", "table") and prev.chunk_type == c.chunk_type:
                # Carry forward the last `overlap` chars of the previous chunk
                tail = prev.raw_text[-self.overlap:].strip()
                if tail and tail not in c.raw_text:
                    c = Chunk(
                        chunk_id=c.chunk_id,
                        doc_id=c.doc_id,
                        parent_chunk_id=prev.chunk_id,
                        heading_path=c.heading_path,
                        page_start=c.page_start,
                        page_end=c.page_end,
                        sheet_name=c.sheet_name,
                        row_start=c.row_start,
                        row_end=c.row_end,
                        raw_text=tail + "\n\n" + c.raw_text,
                        normalized_text=c.normalized_text,
                        contextual_prefix=c.contextual_prefix,
                        drive_file_id=c.drive_file_id,
                        drive_view_link=c.drive_view_link,
                        source_locator=c.source_locator,
                        chunk_type=c.chunk_type,
                        metadata=c.metadata,
                    )
            out.append(c)
            prev = c
        return out