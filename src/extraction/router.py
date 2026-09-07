"""
Extraction router and primary extractors for LOCUS RAG.

Each extractor returns a common ExtractionResult dict (the intermediate
representation defined in SCHEMAS.md).

This module is designed to be swappable: replace any extractor by passing
a different implementation to ExtractionPipeline.
"""

import json
import logging
import re
import sqlite3
import zipfile
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Callable

logger = logging.getLogger(__name__)


# ─── Quality tiers ───────────────────────────────────────────────────────────

class ExtractionQuality(Enum):
    HIGH = "high"       # Clean machine-readable text, full structure
    MEDIUM = "medium"   # Partial structure, some noise
    LOW = "low"         # OCR-quality or fragmented
    FAILED = "failed"   # Could not extract


# ─── Dataclasses ──────────────────────────────────────────────────────────────

@dataclass
class TextBlock:
    """A single block of text within a page."""
    block_id: str
    block_type: str  # heading|paragraph|table|list|figure|caption
    text: str
    level: int = 1
    bbox: Optional[Tuple[float, float, float, float]] = None
    parent_block_id: Optional[str] = None


@dataclass
class TableBlock:
    """A table extracted from a document."""
    table_id: str
    page_number: int
    row_count: int
    col_count: int
    headers: List[str]
    rows: List[Dict[int, str]]  # row_index -> cells list
    bbox: Optional[Tuple[float, float, float, float]] = None


@dataclass
class ExtractedPage:
    page_number: int
    width: Optional[float] = None
    height: Optional[float] = None
    blocks: List[TextBlock] = field(default_factory=list)
    tables: List[TableBlock] = field(default_factory=list)


@dataclass
class ExtractionResult:
    """
    Common intermediate representation for all extracted documents.

    Schema matches docs/SCHEMAS.md §2.
    """
    doc_id: str
    provenance: Dict[str, Any]  # drive_file_id, filename, etc.
    metadata: Dict[str, Any]     # title, dates, authority, etc.
    pages: List[ExtractedPage]
    tables: List[TableBlock]      # flat list of all tables
    full_text: str               # concatenated text for simple chunking
    extraction_quality: ExtractionQuality
    ocr_used: bool
    ocr_metadata: Dict[str, Any] = field(default_factory=dict)
    parser_warnings: List[str] = field(default_factory=list)
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "doc_id": self.doc_id,
            "provenance": self.provenance,
            "metadata": self.metadata,
            "pages": [
                {
                    "page_number": p.page_number,
                    "width": p.width,
                    "height": p.height,
                    "blocks": [
                        {
                            "block_id": b.block_id,
                            "block_type": b.block_type,
                            "text": b.text,
                            "level": b.level,
                            "bbox": b.bbox,
                            "parent_block_id": b.parent_block_id,
                        }
                        for b in p.blocks
                    ],
                    "tables": [
                        {
                            "table_id": t.table_id,
                            "page_number": t.page_number,
                            "row_count": t.row_count,
                            "col_count": t.col_count,
                            "headers": t.headers,
                            "rows": t.rows,
                            "bbox": t.bbox,
                        }
                        for t in p.tables
                    ],
                }
                for p in self.pages
            ],
            "tables": [
                {
                    "table_id": t.table_id,
                    "page_number": t.page_number,
                    "row_count": t.row_count,
                    "col_count": t.col_count,
                    "headers": t.headers,
                    "rows": t.rows,
                    "bbox": t.bbox,
                }
                for t in self.tables
            ],
            "full_text": self.full_text,
            "extraction_quality": self.extraction_quality.value,
            "ocr_used": self.ocr_used,
            "ocr_metadata": self.ocr_metadata,
            "parser_warnings": self.parser_warnings,
            "error_message": self.error_message,
        }
        return d


# ─── Extractor registry ───────────────────────────────────────────────────────

# Map mime type → extractor function
_EXTRACTORS: Dict[str, Callable[[str, Dict], ExtractionResult]] = {}


def register_extractor(mime_types: List[str]):
    """Decorator to register an extractor function."""
    def decorator(func: Callable[[str, Dict], ExtractionResult]):
        for mt in mime_types:
            _EXTRACTORS[mt] = func
        return func
    return decorator


def get_extractor(mime_type: str) -> Optional[Callable]:
    return _EXTRACTORS.get(mime_type)


def supported_mime_types() -> List[str]:
    return list(_EXTRACTORS.keys())


# ─── Extraction helpers ────────────────────────────────────────────────────────

def _block_id(doc_id: str, prefix: str) -> str:
    import hashlib
    h = hashlib.sha256(f"{doc_id}:{prefix}".encode()).hexdigest()[:12]
    return f"{doc_id}_{h}"


def _heading_level(text: str) -> int:
    """Infer heading level from text patterns."""
    text = text.strip()
    if text.startswith("#"):
        stripped = text.lstrip("#")
        return len(text) - len(stripped)
    if len(text) < 80 and text.isupper() and '\n' not in text:
        return 2
    return 1


def _build_full_text(pages: List[ExtractedPage]) -> str:
    """Concatenate page text preserving paragraph boundaries."""
    parts = []
    for page in pages:
        for block in page.blocks:
            if block.text.strip():
                parts.append(block.text.strip())
        parts.append("")  # page break marker
    return "\n\n".join(parts)


def _assess_quality(result: ExtractionResult) -> ExtractionQuality:
    """
    Assess extraction quality based on text yield and structural features.

    This is the first-pass quality gate before OCR fallback.
    """
    total_chars = sum(
        len(b.text) for p in result.pages for b in p.blocks
    )
    total_blocks = sum(len(p.blocks) for p in result.pages)
    total_tables = len(result.tables)

    if total_chars < 10:
        return ExtractionQuality.FAILED
    if total_blocks == 0:
        return ExtractionQuality.FAILED

    if total_chars > 500 and total_blocks > 10:
        if total_tables > 0:
            return ExtractionQuality.HIGH
        if total_chars > 1000:
            return ExtractionQuality.HIGH
        return ExtractionQuality.MEDIUM

    if total_chars > 100 and total_blocks > 3:
        return ExtractionQuality.MEDIUM

    return ExtractionQuality.LOW


# ─── Text/plain extractor ─────────────────────────────────────────────────────

@register_extractor(["text/plain", "text/markdown", "text/rtf"])
def extract_text(file_path: str, metadata: Dict) -> ExtractionResult:
    """Extract plain text or Markdown documents."""
    try:
        raw = Path(file_path).read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("latin-1")
    except Exception as e:
        return _failed_result(metadata.get("doc_id", ""), str(e))

    paragraphs = re.split(r"\n{2,}", text)
    blocks = []
    for i, para in enumerate(paragraphs):
        para = para.strip()
        if not para:
            continue
        block_type = "heading" if (
            (para.startswith("#") and not para.startswith("```")) or
            (len(para) < 80 and para.isupper())
        ) else "paragraph"
        blocks.append(TextBlock(
            block_id=_block_id(metadata.get("doc_id", ""), f"para_{i}"),
            block_type=block_type,
            text=para,
            level=_heading_level(para) if block_type == "heading" else 1,
        ))

    page = ExtractedPage(page_number=1, blocks=blocks)
    result = ExtractionResult(
        doc_id=metadata.get("doc_id", ""),
        provenance=metadata.get("provenance", {}),
        metadata=metadata.get("doc_metadata", {}),
        pages=[page],
        tables=[],
        full_text=text.strip(),
        extraction_quality=ExtractionQuality.MEDIUM,
        ocr_used=False,
    )
    result.extraction_quality = _assess_quality(result)
    return result


# ─── CSV/TSV extractor ────────────────────────────────────────────────────────

@register_extractor(
    [
        "text/csv",
        "text/tab-separated-values",
        "text/tsv",
        "application/json",
        "application/vnd.google-apps.spreadsheet",
    ]
)
def extract_csv(file_path: str, metadata: Dict) -> ExtractionResult:
    """Extract CSV/TSV as a table representation."""
    doc_id = metadata.get("doc_id", "")
    try:
        raw = Path(file_path).read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("latin-1")
    except Exception as e:
        return _failed_result(doc_id, str(e))

    delimiter = (
        "\t"
        if metadata.get("mime_type") in ("text/tab-separated-values", "text/tsv")
        else ","
    )
    lines = text.splitlines()
    if not lines:
        return _failed_result(doc_id, "Empty CSV file")

    headers = _parse_csv_line(lines[0], delimiter)
    rows: List[Dict[int, str]] = []
    for i, line in enumerate(lines[1:], start=1):
        cells = _parse_csv_line(line, delimiter)
        cells = cells + [""] * (len(headers) - len(cells))
        rows.append({j: cells[j] for j in range(len(headers))})

    table = TableBlock(
        table_id=_block_id(doc_id, "csv_main"),
        page_number=1,
        row_count=len(rows),
        col_count=len(headers),
        headers=headers,
        rows=rows,
    )

    blocks = [TextBlock(
        block_id=_block_id(doc_id, "csv_header"),
        block_type="heading",
        text=" | ".join(headers),
        level=1,
    )]
    for i, row in enumerate(rows):
        row_text = " | ".join(row.get(j, "") for j in range(len(headers)))
        blocks.append(TextBlock(
            block_id=_block_id(doc_id, f"csv_row_{i}"),
            block_type="paragraph",
            text=row_text,
        ))

    page = ExtractedPage(page_number=1, blocks=blocks, tables=[table])
    result = ExtractionResult(
        doc_id=doc_id,
        provenance=metadata.get("provenance", {}),
        metadata=metadata.get("doc_metadata", {}),
        pages=[page],
        tables=[table],
        full_text=text.strip(),
        extraction_quality=ExtractionQuality.HIGH,
        ocr_used=False,
    )
    result.extraction_quality = _assess_quality(result)
    return result


def _parse_csv_line(line: str, delimiter: str) -> List[str]:
    """Simple CSV parser handling quoted fields."""
    result = []
    current = ""
    in_quotes = False
    for char in line:
        if char == '"':
            in_quotes = not in_quotes
        elif char == delimiter and not in_quotes:
            result.append(current.strip())
            current = ""
        else:
            current += char
    result.append(current.strip())
    return result


# ─── PDF extractor ──────────────────────────────────────────────────────────

@register_extractor(["application/pdf"])
def extract_pdf(file_path: str, metadata: Dict) -> ExtractionResult:
    """
    Extract text from PDFs.

    Production path uses PyMuPDF (fitz), which preserves page structure,
    headings (via font-size heuristics), and detects scanned pages requiring OCR.
    """
    doc_id = metadata.get("doc_id", "")
    result = _extract_pdf_pymupdf(file_path, doc_id, metadata)
    return result


def _basic_pdf_extraction(
    file_path: str, doc_id: str, metadata: Dict
) -> ExtractionResult:
    """
    Basic PDF text extraction using only stdlib.

    This is a last-resort extractor used when PyMuPDF is unavailable.
    """
    try:
        raw = Path(file_path).read_bytes()
    except Exception as e:
        return _failed_result(doc_id, f"Cannot read file: {e}")

    text_chunks: List[str] = []
    try:
        raw_text = raw.decode("latin-1", errors="replace")
    except Exception:
        return _failed_result(doc_id, "Cannot decode PDF as text")

    tj_pattern = re.compile(r'\(([^)]*)\)\s*Tj')
    for m in tj_pattern.finditer(raw_text):
        t = m.group(1).strip()
        if t and len(t) > 1:
            t = t.replace('\\n', '\n').replace('\\r', '\r').replace('\\t', '\t')
            text_chunks.append(t)

    if not text_chunks:
        page = ExtractedPage(page_number=1, blocks=[])
        return ExtractionResult(
            doc_id=doc_id,
            provenance=metadata.get("provenance", {}),
            metadata=metadata.get("doc_metadata", {}),
            pages=[page],
            tables=[],
            full_text="",
            extraction_quality=ExtractionQuality.FAILED,
            ocr_used=False,
            parser_warnings=["No text extracted — likely a scanned PDF"],
        )

    full_text = "\n\n".join(text_chunks)
    paragraphs = re.split(r"\n{2,}", full_text)
    blocks = []
    for i, para in enumerate(paragraphs):
        para = para.strip()
        if not para:
            continue
        blocks.append(TextBlock(
            block_id=_block_id(doc_id, f"pdf_para_{i}"),
            block_type="paragraph",
            text=para,
        ))

    page = ExtractedPage(page_number=1, blocks=blocks)
    result = ExtractionResult(
        doc_id=doc_id,
        provenance=metadata.get("provenance", {}),
        metadata=metadata.get("doc_metadata", {}),
        pages=[page],
        tables=[],
        full_text=full_text,
        extraction_quality=ExtractionQuality.MEDIUM,
        ocr_used=False,
    )
    result.extraction_quality = _assess_quality(result)
    return result


# ─── PyMuPDF extractor (production-quality) ──────────────────────────────────

def _run_ocr_on_page(file_path: str, page_number: int) -> Optional[str]:
    """Run OCR on a single PDF page via the OCRProvider."""
    try:
        from src.ocr.engine import OCRProvider
        provider = OCRProvider(languages=["eng"])
        result = provider.ocr_pdf_page(
            file_path, page_number, language="eng"
        )
        return result.text if result.used and result.text else None
    except Exception as e:
        logger.warning("OCR on page %d failed: %s", page_number, e)
        return None


def _extract_pdf_pymupdf(
    file_path: str, doc_id: str, metadata: Dict
) -> ExtractionResult:
    """Extract text from PDFs using PyMuPDF (fitz)."""
    result = ExtractionResult(
        doc_id=doc_id,
        provenance=metadata.get("provenance", {}),
        metadata=metadata.get("doc_metadata", {}),
        pages=[],
        tables=[],
        full_text="",
        extraction_quality=ExtractionQuality.MEDIUM,
        ocr_used=False,
        ocr_metadata={"needs_ocr": False},
    )

    try:
        import fitz  # PyMuPDF
    except ImportError:
        result.extraction_quality = ExtractionQuality.FAILED
        result.error_message = ("PyMuPDF (fitz) not installed. "
                                "pip install pymupdf")
        return result

    try:
        pdf = fitz.open(file_path)
    except Exception as e:
        result.extraction_quality = ExtractionQuality.FAILED
        result.error_message = f"Cannot open PDF with PyMuPDF: {e}"
        return result

    page_count = pdf.page_count
    scanned_pages: List[int] = []
    ocr_mode = (metadata.get("ocr_mode") or "auto").lower()  # auto|always|never

    for page_num in range(page_count):
        page = pdf[page_num]

        try:
            raw_blocks = page.get_text(
                "dict",
                flags=fitz.TEXT_PRESERVE_LIGATURES | fitz.TEXT_PRESERVE_WHITESPACE,
            )
            blocks = raw_blocks.get("blocks", []) if isinstance(raw_blocks, dict) else []
        except Exception:
            blocks = []

        page_blocks: List[TextBlock] = []
        page_width = page.rect.width
        page_height = page.rect.height

        for bi, block in enumerate(blocks):
            if block.get("type") != 0:
                continue
            text = ""
            max_font_size = 0.0
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text += span.get("text", "")
                    max_font_size = max(max_font_size, span.get("size", 0))

            text = text.strip()
            if not text:
                continue

            is_heading = False
            level = 1
            if max_font_size > 0:
                if max_font_size > 18:
                    is_heading, level = True, 1
                elif max_font_size > 14:
                    is_heading, level = True, 2
                elif max_font_size > 12:
                    is_heading, level = True, 3

            page_blocks.append(TextBlock(
                block_id=_block_id(doc_id, f"pg{page_num}_b{bi}"),
                block_type="heading" if is_heading else "paragraph",
                text=text,
                level=level,
                bbox=tuple(block.get("bbox", (0, 0, 0, 0))),
            ))

        has_image = False
        try:
            for img in page.get_images(full=True):
                if img:
                    has_image = True
                    break
        except Exception:
            has_image = False

        text_chars = sum(len(b.text) for b in page_blocks)
        is_scanned = text_chars < 20 and has_image
        if is_scanned:
            scanned_pages.append(page_num + 1)

        if ocr_mode == "always" or (ocr_mode == "auto" and is_scanned):
            ocr_text = _run_ocr_on_page(file_path, page_num + 1)
            if ocr_text:
                page_blocks.append(TextBlock(
                    block_id=_block_id(doc_id, f"pg{page_num}_ocr"),
                    block_type="paragraph",
                    text=ocr_text,
                ))
                result.ocr_used = True

        page_obj = ExtractedPage(
            page_number=page_num + 1,
            width=page_width,
            height=page_height,
            blocks=page_blocks,
        )
        result.pages.append(page_obj)

    pdf.close()

    for page in result.pages:
        for block in page.blocks:
            lines = re.split(r"\n+", block.text)
            if len(lines) >= 2:
                tabular_lines = [
                    l for l in lines
                    if len(re.split(r"\s{2,}|\t|\|", l)) >= 3
                ]
                if len(tabular_lines) >= 3:
                    table = TableBlock(
                        table_id=_block_id(doc_id, f"tbl_{page.page_number}"),
                        page_number=page.page_number,
                        row_count=len(tabular_lines),
                        col_count=4,
                        headers=tabular_lines[0].split(),
                        rows=[{0: list(filter(None, l.split()))} for l in tabular_lines],
                        bbox=block.bbox,
                    )
                    result.tables.append(table)

    full_text_parts = []
    for page in result.pages:
        for block in page.blocks:
            if not block.text.startswith("[OCR REQUIRED"):
                full_text_parts.append(block.text)

    result.full_text = "\n\n".join(full_text_parts)
    result.ocr_metadata["needs_ocr"] = bool(scanned_pages)
    result.ocr_metadata["scanned_pages"] = scanned_pages
    if scanned_pages and not result.ocr_used:
        result.ocr_metadata["ocr_output"] = False

    result.extraction_quality = _assess_quality(result)
    if scanned_pages and not result.ocr_used:
        result.parser_warnings.append(
            f"Scanned pages detected (page numbers: {scanned_pages}). "
            "OCR required for full text."
        )

    return result


def extract_pdf_pymupdf(file_path: str, metadata: Dict) -> ExtractionResult:
    """Public entry: extract PDF with PyMuPDF (production path)."""
    doc_id = metadata.get("doc_id", "")
    return _extract_pdf_pymupdf(file_path, doc_id, metadata)


# ─── DOCX extractor (basic) ──────────────────────────────────────────────────

@register_extractor([
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
])
def extract_docx(file_path: str, metadata: Dict) -> ExtractionResult:
    """Extract text from DOCX/DOC files using stdlib zipfile."""
    doc_id = metadata.get("doc_id", "")
    mime = metadata.get("mime_type", "")

    if mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return _extract_docx_zip(file_path, doc_id, metadata)
    return _extract_plain_doc(file_path, doc_id, metadata)


def _extract_docx_zip(
    file_path: str, doc_id: str, metadata: Dict
) -> ExtractionResult:
    """Parse DOCX (ZIP) to extract text from document.xml."""
    try:
        with zipfile.ZipFile(file_path, "r") as z:
            with z.open("word/document.xml") as f:
                xml_data = f.read()
    except Exception as e:
        return _failed_result(doc_id, f"Cannot read DOCX ZIP: {e}")

    try:
        xml_text = xml_data.decode("utf-8", errors="replace")
    except Exception as e:
        return _failed_result(doc_id, f"Cannot decode document.xml: {e}")

    paragraphs = re.split(r"</w:p>", xml_text)
    para_texts: List[str] = []
    for para in paragraphs:
        runs = re.findall(r"<w:t[^>]*>([^<]*)</w:t>", para)
        text = "".join(runs).strip()
        if text:
            para_texts.append(text)

    blocks = []
    for i, para_text in enumerate(para_texts):
        if not para_text:
            continue
        is_heading = (
            para_text.startswith("#") or
            (len(para_text) < 80 and para_text.isupper())
        )
        blocks.append(TextBlock(
            block_id=_block_id(doc_id, f"docx_para_{i}"),
            block_type="heading" if is_heading else "paragraph",
            text=para_text,
            level=_heading_level(para_text) if is_heading else 1,
        ))

    full_text = "\n\n".join(para_texts)
    page = ExtractedPage(page_number=1, blocks=blocks)
    result = ExtractionResult(
        doc_id=doc_id,
        provenance=metadata.get("provenance", {}),
        metadata=metadata.get("doc_metadata", {}),
        pages=[page],
        tables=[],
        full_text=full_text,
        extraction_quality=ExtractionQuality.MEDIUM,
        ocr_used=False,
    )
    result.extraction_quality = _assess_quality(result)
    return result


def _extract_plain_doc(
    file_path: str, doc_id: str, metadata: Dict
) -> ExtractionResult:
    """Fallback for binary .doc files — extract visible text."""
    try:
        raw = Path(file_path).read_bytes()
        words = re.findall(rb"[\x20-\x7e]{3,}", raw)
        readable = b" ".join(words).decode("latin-1", errors="replace")
    except Exception as e:
        return _failed_result(doc_id, str(e))

    lines = [l.strip() for l in readable.splitlines() if l.strip()][:500]
    blocks = [
        TextBlock(
            block_id=_block_id(doc_id, f"doc_para_{i}"),
            block_type="paragraph",
            text=line,
        )
        for i, line in enumerate(lines)
    ]
    page = ExtractedPage(page_number=1, blocks=blocks)
    result = ExtractionResult(
        doc_id=doc_id,
        provenance=metadata.get("provenance", {}),
        metadata=metadata.get("doc_metadata", {}),
        pages=[page],
        tables=[],
        full_text="\n".join(lines),
        extraction_quality=ExtractionQuality.LOW,
        ocr_used=False,
        parser_warnings=["Binary .doc extraction is unreliable. Consider converting to .docx."],
    )
    result.extraction_quality = _assess_quality(result)
    return result


# ─── Failed result factory ─────────────────────────────────────────────────────

def _failed_result(doc_id: str, error_message: str) -> ExtractionResult:
    return ExtractionResult(
        doc_id=doc_id,
        provenance={},
        metadata={},
        pages=[],
        tables=[],
        full_text="",
        extraction_quality=ExtractionQuality.FAILED,
        ocr_used=False,
        error_message=error_message,
    )


# ─── Top-level extraction pipeline ────────────────────────────────────────────

class ExtractionPipeline:
    """
    Route files to the appropriate extractor.

    Usage:
        pipeline = ExtractionPipeline()
        result = pipeline.extract("/path/to/file.pdf", {
            "doc_id": "doc_123",
            "mime_type": "application/pdf",
            "provenance": {...},
        })
    """

    def __init__(self, raise_on_unsupported: bool = False):
        self.raise_on_unsupported = raise_on_unsupported

    def extract(self, file_path: str, metadata: Dict) -> ExtractionResult:
        """Extract content from a file."""
        mime_type = metadata.get("mime_type", "")
        extractor = get_extractor(mime_type)

        if extractor is None:
            msg = f"No extractor registered for mime type: {mime_type}"
            if self.raise_on_unsupported:
                raise ValueError(msg)
            logger.warning(msg)
            return _failed_result(
                metadata.get("doc_id", ""),
                f"Unsupported mime type: {mime_type}",
            )

        try:
            result = extractor(file_path, metadata)
            logger.info(
                "Extracted %s (quality=%s, pages=%d, chars=%d)",
                metadata.get("doc_id", ""),
                result.extraction_quality.value,
                len(result.pages),
                len(result.full_text),
            )
            return result
        except Exception as e:
            logger.exception("Extractor failed for %s", metadata.get("doc_id", ""))
            return _failed_result(metadata.get("doc_id", ""), str(e))

    def extract_batch(
        self, items: List[Dict]
    ) -> List[ExtractionResult]:
        """Extract a batch of files."""
        return [self.extract(item["file_path"], item) for item in items]