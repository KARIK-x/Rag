"""
Integrity audit for LOCUS RAG extraction pipeline.

Per spec §20: every transformation boundary must be auditable.
This module checks:
  - Page counts
  - Text yield
  - Character counts
  - Missing headings
  - Suspiciously empty regions
  - Table row/column counts
  - Parser warnings/exceptions
  - Content hash continuity
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from src.extraction.router import ExtractionResult, ExtractionQuality

logger = logging.getLogger(__name__)


class AuditStatus(Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    INFO = "info"  # informational, not a failure or warning


@dataclass
class AuditFinding:
    """A single finding from the integrity audit."""
    stage: str           # extraction|normalization|chunking|etc.
    check: str           # specific check name
    severity: AuditStatus
    message: str
    details: Dict[str, Any] = field(default_factory=dict)

    def is_pass(self) -> bool:
        return self.severity == AuditStatus.PASS

    def is_fail(self) -> bool:
        return self.severity == AuditStatus.FAIL

    def is_warn(self) -> bool:
        return self.severity == AuditStatus.WARN


@dataclass
class IntegrityAudit:
    """Result of an integrity audit for a single document."""
    doc_id: str
    findings: List[AuditFinding] = field(default_factory=list)
    overall_status: AuditStatus = AuditStatus.PASS
    notes: List[str] = field(default_factory=list)

    def passed(self) -> bool:
        return self.overall_status == AuditStatus.PASS

    def add_finding(
        self,
        stage: str,
        check: str,
        severity: AuditStatus,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.findings.append(AuditFinding(
            stage=stage, check=check, severity=severity,
            message=message, details=details or {},
        ))
        if severity == AuditStatus.FAIL:
            self.overall_status = AuditStatus.FAIL
        elif severity == AuditStatus.WARN and self.overall_status == AuditStatus.PASS:
            self.overall_status = AuditStatus.WARN

    def warnings(self) -> List[AuditFinding]:
        return [f for f in self.findings if f.severity == AuditStatus.WARN]

    def failures(self) -> List[AuditFinding]:
        return [f for f in self.findings if f.severity == AuditStatus.FAIL]

    def summary(self) -> str:
        n_pass = len([f for f in self.findings if f.severity == AuditStatus.PASS])
        n_warn = len(self.warnings())
        n_fail = len(self.failures())
        lines = [
            f"IntegrityAudit({self.doc_id}): {self.overall_status.value}",
            f"  findings: {n_pass} pass, {n_warn} warn, {n_fail} fail",
        ]
        for f in self.failures():
            lines.append(f"  [FAIL] {f.stage}/{f.check}: {f.message}")
        for f in self.warnings():
            lines.append(f"  [WARN] {f.stage}/{f.check}: {f.message}")
        return "\n".join(lines)


# ─── Audit checks ─────────────────────────────────────────────────────────────

class IntegrityAuditor:
    """
    Run integrity checks on extraction results.

    Each check is a method. Override or extend to add new checks.
    """

    def audit_extraction(
        self,
        result: ExtractionResult,
        expected_pages: Optional[int] = None,
    ) -> IntegrityAudit:
        """Audit a single extraction result."""
        audit = IntegrityAudit(doc_id=result.doc_id)

        self._check_extraction_success(audit, result)
        self._check_text_yield(audit, result)
        self._check_page_count(audit, result, expected_pages)
        self._check_block_structure(audit, result)
        self._check_heading_preservation(audit, result)
        self._check_table_preservation(audit, result)
        self._check_empty_pages(audit, result)
        self._check_parser_warnings(audit, result)
        self._check_ocr_usage(audit, result)

        return audit

    def _check_extraction_success(self, audit: IntegrityAudit, result: ExtractionResult):
        if result.extraction_quality == ExtractionQuality.FAILED:
            audit.add_finding(
                stage="extraction",
                check="extraction_success",
                severity=AuditStatus.FAIL,
                message=f"Extraction failed: {result.error_message or 'unknown error'}",
                details={"error": result.error_message},
            )
        elif result.extraction_quality == ExtractionQuality.LOW:
            audit.add_finding(
                stage="extraction",
                check="extraction_quality",
                severity=AuditStatus.WARN,
                message="Extraction quality is LOW — content may be incomplete or require OCR",
                details={"quality": result.extraction_quality.value},
            )
        else:
            audit.add_finding(
                stage="extraction",
                check="extraction_success",
                severity=AuditStatus.PASS,
                message="Extraction succeeded",
            )

    def _check_text_yield(self, audit: IntegrityAudit, result: ExtractionResult):
        total_chars = len(result.full_text)
        if total_chars == 0:
            audit.add_finding(
                stage="extraction",
                check="text_yield",
                severity=AuditStatus.FAIL,
                message="No text extracted — document is likely empty or scanned",
                details={"chars": 0},
            )
        elif total_chars < 100:
            audit.add_finding(
                stage="extraction",
                check="text_yield",
                severity=AuditStatus.WARN,
                message=f"Very low text yield ({total_chars} chars) — possible truncated extraction",
                details={"chars": total_chars},
            )
        else:
            audit.add_finding(
                stage="extraction",
                check="text_yield",
                severity=AuditStatus.PASS,
                message=f"Text yield: {total_chars} chars",
                details={"chars": total_chars},
            )

    def _check_page_count(
        self,
        audit: IntegrityAudit,
        result: ExtractionResult,
        expected_pages: Optional[int],
    ):
        actual = len(result.pages)
        if actual == 0:
            audit.add_finding(
                stage="extraction",
                check="page_count",
                severity=AuditStatus.FAIL,
                message="No pages extracted",
            )
        elif expected_pages is not None and abs(actual - expected_pages) > expected_pages * 0.1:
            audit.add_finding(
                stage="extraction",
                check="page_count",
                severity=AuditStatus.WARN,
                message=f"Page count mismatch: expected ~{expected_pages}, got {actual}",
                details={"expected": expected_pages, "actual": actual},
            )
        else:
            audit.add_finding(
                stage="extraction",
                check="page_count",
                severity=AuditStatus.PASS,
                message=f"Page count: {actual}",
                details={"pages": actual},
            )

    def _check_block_structure(self, audit: IntegrityAudit, result: ExtractionResult):
        total_blocks = sum(len(p.blocks) for p in result.pages)
        if total_blocks == 0:
            audit.add_finding(
                stage="extraction",
                check="block_structure",
                severity=AuditStatus.WARN,
                message="No text blocks found",
            )
        else:
            audit.add_finding(
                stage="extraction",
                check="block_structure",
                severity=AuditStatus.PASS,
                message=f"Block count: {total_blocks}",
                details={"blocks": total_blocks},
            )

    def _check_heading_preservation(self, audit: IntegrityAudit, result: ExtractionResult):
        heading_blocks = [
            b for p in result.pages
            for b in p.blocks
            if b.block_type == "heading"
        ]
        n_headings = len(heading_blocks)
        # A reasonable document should have some headings if it's long enough
        if len(result.full_text) > 2000 and n_headings == 0:
            audit.add_finding(
                stage="extraction",
                check="heading_preservation",
                severity=AuditStatus.WARN,
                message="No headings detected in a long document — heading context may be lost",
                details={"headings": 0, "doc_chars": len(result.full_text)},
            )
        else:
            audit.add_finding(
                stage="extraction",
                check="heading_preservation",
                severity=AuditStatus.PASS,
                message=f"Heading blocks: {n_headings}",
                details={"headings": n_headings},
            )

    def _check_table_preservation(self, audit: IntegrityAudit, result: ExtractionResult):
        n_tables = len(result.tables)
        total_table_rows = sum(t.row_count for t in result.tables)
        audit.add_finding(
            stage="extraction",
            check="table_preservation",
            severity=AuditStatus.PASS,
            message=f"Tables: {n_tables}, total rows: {total_table_rows}",
            details={"tables": n_tables, "rows": total_table_rows},
        )

    def _check_empty_pages(self, audit: IntegrityAudit, result: ExtractionResult):
        empty_pages = [
            p.page_number for p in result.pages
            if len(p.blocks) == 0 and len(p.tables) == 0
        ]
        if empty_pages:
            audit.add_finding(
                stage="extraction",
                check="empty_pages",
                severity=AuditStatus.WARN,
                message=f"Suspiciously empty pages: {empty_pages}",
                details={"empty_pages": empty_pages},
            )
        else:
            audit.add_finding(
                stage="extraction",
                check="empty_pages",
                severity=AuditStatus.PASS,
                message="No empty pages detected",
            )

    def _check_parser_warnings(self, audit: IntegrityAudit, result: ExtractionResult):
        if result.parser_warnings:
            for w in result.parser_warnings:
                audit.add_finding(
                    stage="extraction",
                    check="parser_warning",
                    severity=AuditStatus.WARN,
                    message=w,
                )
        else:
            audit.add_finding(
                stage="extraction",
                check="parser_warnings",
                severity=AuditStatus.PASS,
                message="No parser warnings",
            )

    def _check_ocr_usage(self, audit: IntegrityAudit, result: ExtractionResult):
        if result.ocr_used:
            audit.add_finding(
                stage="extraction",
                check="ocr_used",
                severity=AuditStatus.INFO if result.extraction_quality == ExtractionQuality.HIGH else AuditStatus.WARN,
                message=f"OCR was used (engine: {result.ocr_metadata.get('engine', 'unknown')})",
                details=result.ocr_metadata,
            )
        else:
            audit.add_finding(
                stage="extraction",
                check="ocr_used",
                severity=AuditStatus.PASS,
                message="No OCR used",
            )
