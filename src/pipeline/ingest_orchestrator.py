"""
LOCUS RAG ingestion orchestrator.

Ties together:
  - IngestionClient (read-only Drive download / Workspace export)
  - ExtractionPipeline (format routing + extractors)
  - IntegrityAuditor (extraction quality gates)
  - DocumentStateMachine (per-document state tracking)

Per spec §51 and §52:
  - Every document transition is logged
  - Failures go to FAILED / REQUIRES_REVIEW / DEAD_LETTER — never silently skipped
  - Operations are idempotent and resumable
"""

import logging
import sqlite3
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.extraction.router import (
    ExtractionPipeline,
    ExtractionResult,
    ExtractionQuality,
)
from src.ingestion.client import IngestionClient, IngestedFile, IngestionError
from src.integrity.audit import IntegrityAuditor, IntegrityAudit, AuditStatus
from src.pipeline.statemachine import DocumentStateMachine, DocumentState
from src.structured_data.engine import StructuredDataEngine
from src.chunking.structural import StructuralChunker
from src.resilience import retry_with_backoff, assert_not_in_locus_drive

logger = logging.getLogger(__name__)


class ProcessingResult:
    """Outcome of processing a single document."""

    def __init__(
        self,
        drive_file_id: str,
        filename: str,
        mime_type: str,
        status: str,  # success | failed | requires_review | skipped
        state: DocumentState,
        extraction_quality: Optional[str] = None,
        chunks: int = 0,
        error: Optional[str] = None,
        audit: Optional[IntegrityAudit] = None,
        local_path: Optional[str] = None,
        was_workspace_export: Optional[bool] = None,
    ):
        self.drive_file_id = drive_file_id
        self.filename = filename
        self.mime_type = mime_type
        self.status = status
        self.state = state
        self.extraction_quality = extraction_quality
        self.chunks = chunks
        self.error = error
        self.audit = audit
        self.local_path = local_path
        self.was_workspace_export = was_workspace_export


class IngestionOrchestrator:
    """Coordinates download → extract → audit → state tracking for LOCUS files."""

    def __init__(
        self,
        data_dir: str = "/Users/ashim/locus_rag/data",
        state_db_path: str = None,
        catalog_path: str = "/Users/ashim/locus_drive/locus_drive.db",
        drive_client: Any = None,
    ):
        self.data_dir = Path(data_dir)
        self.extracted_dir = self.data_dir / "extracted"
        self.extracted_dir.mkdir(parents=True, exist_ok=True)
        self.raw_dir = self.data_dir / "raw"
        self.raw_dir.mkdir(parents=True, exist_ok=True)

        if state_db_path is None:
            state_db_path = str(self.data_dir / "db" / "rag_state.db")

        self.ingestion = IngestionClient(
            catalog_path=catalog_path,
            data_dir=str(self.data_dir),
            drive_client=drive_client,
        )
        self.extraction = ExtractionPipeline()
        self.auditor = IntegrityAuditor()
        self.state_machine = DocumentStateMachine(db_path=state_db_path)
        self.structured = StructuredDataEngine(
            data_dir=str(self.data_dir),
            state_db_path=state_db_path,
        )
        self.chunker = StructuralChunker()
        self.chunker = StructuralChunker()

    # ─── Core processing ────────────────────────────────────────────────────

    def process_one(
        self,
        drive_file_id: str,
        mime_type: str,
        filename: str = None,
        folder_path: str = None,
        max_chars: int = 100_000,
        ocr_mode: str = "auto",
        max_doc_attempts: int = 5,
    ) -> ProcessingResult:
        """
        Process a single document: download/export → extract → audit → state.

        Never mutates Drive. Idempotent: re-processing the same file
        will not re-download (cached by content hash).

        Args:
            ocr_mode: "auto" (only scanned pages), "always" (all PDF pages), "never"
            max_doc_attempts: persistent document-level failed-attempt cap.
                Once a document reaches this many FAILED transitions (the count
                survives restarts in document_states.attempt_count), it is
                dead-lettered instead of reprocessed indefinitely.
        """
        sm = self.state_machine

        try:
            # Re-processing a previously-failed/review/partial document must
            # re-enter the discovery flow (spec §51 retry path). The persistent
            # attempt count (survives restarts) caps infinite retry loops:
            # once a document fails max_doc_attempts times it is dead-lettered
            # instead of being reprocessed.
            current = sm.get_state(drive_file_id)
            if current is not None and current not in (
                DocumentState.INDEXED, DocumentState.DEAD_LETTER
            ):
                if sm.get_attempt_count(drive_file_id) >= max_doc_attempts:
                    sm.transition(
                        drive_file_id,
                        DocumentState.DEAD_LETTER,
                        error_message=(
                            f"Exceeded {max_doc_attempts} failed processing attempts"
                        ),
                        force=True,
                    )
                    return ProcessingResult(
                        drive_file_id=drive_file_id,
                        filename=filename or drive_file_id,
                        mime_type=mime_type,
                        status="dead_letter",
                        state=DocumentState.DEAD_LETTER,
                        error="Exceeded max processing attempts",
                    )
                sm.transition(drive_file_id, DocumentState.DISCOVERED, force=True)

            sm.transition(drive_file_id, DocumentState.DOWNLOADING)

            # Download / export (read-only) with bounded transient retry.
            # Only genuinely transient failures (network/timeout/5xx/rate
            # limit) are retried with backoff; permanent errors
            # (auth/permission/unsupported/not-found) fail immediately and are
            # NOT multiplied by the document-level attempt counter.
            ingested = retry_with_backoff(
                lambda: self.ingestion.download_file(drive_file_id, mime_type),
                attempts=3,
                base_delay=0.5,
                max_delay=8.0,
            )
            assert_not_in_locus_drive(Path(ingested.local_path))
            sm.transition(drive_file_id, DocumentState.DOWNLOADED)

            # Extract — route on the EFFECTIVE mime type (workspace exports
            # become text/plain or text/csv, not the Google-native mime).
            sm.transition(drive_file_id, DocumentState.EXTRACTED)
            extraction_mime = ingested.effective_mime_type or mime_type
            extraction_meta = {
                "doc_id": drive_file_id,
                "mime_type": extraction_mime,
                "provenance": {
                    "drive_file_id": drive_file_id,
                    "filename": filename or ingested.filename,
                    "folder_path": folder_path,
                    "mime_type": mime_type,
                    "effective_mime_type": extraction_mime,
                    "web_view_link": ingested.web_view_link,
                },
                "doc_metadata": {
                    "title": filename or ingested.filename,
                    "created_time": ingested.created_time,
                    "modified_time": ingested.modified_time,
                },
                "ocr_mode": ocr_mode,
            }

            result = self.extraction.extract(ingested.local_path, extraction_meta)

            # Persist extracted representation for downstream
            self._save_extracted(drive_file_id, result)

            # Integrity audit
            audit = self.auditor.audit_extraction(result)

            # Merge audit status into result and decide outcome
            if audit.overall_status == AuditStatus.FAIL or result.extraction_quality == ExtractionQuality.FAILED:
                # Mark REQUIRES_REVIEW (can be re-processed later)
                sm.transition(
                    drive_file_id,
                    DocumentState.REQUIRES_REVIEW,
                    error_message=(
                        result.error_message
                        or next((f.message for f in audit.failures()), "extraction/audit failed")
                    ),
                )
                return ProcessingResult(
                    drive_file_id=drive_file_id,
                    filename=filename or ingested.filename,
                    mime_type=mime_type,
                    status="requires_review",
                    state=DocumentState.REQUIRES_REVIEW,
                    extraction_quality=result.extraction_quality.value,
                    error=result.error_message,
                    audit=audit,
                    local_path=ingested.local_path,
                    was_workspace_export=ingested.was_workspace_export,
                )

            if result.extraction_quality in (ExtractionQuality.LOW, ExtractionQuality.MEDIUM):
                # Accept for now, note for potential OCR later
                logger.info(
                    "Document %s extraction quality: %s",
                    drive_file_id, result.extraction_quality.value,
                )

            # Structured data plane: if this doc produced tables (CSV/Sheet),
            # import them to DuckDB/Parquet for deterministic computation.
            if result.tables:
                try:
                    imported = self.structured.import_table_from_extraction(
                        result.to_dict()
                    )
                    if imported:
                        logger.info(
                            "Imported structured table %s (%d rows) from %s",
                            imported.table_id, len(imported.rows), drive_file_id,
                        )
                except Exception as e:
                    logger.warning(
                        "Structured import failed for %s: %s", drive_file_id, e
                    )

            sm.transition(drive_file_id, DocumentState.NORMALIZED)

            return ProcessingResult(
                drive_file_id=drive_file_id,
                filename=filename or ingested.filename,
                mime_type=mime_type,
                status="success",
                state=DocumentState.NORMALIZED,
                extraction_quality=result.extraction_quality.value,
                audit=audit,
                local_path=ingested.local_path,
                was_workspace_export=ingested.was_workspace_export,
            )

        except IngestionError as e:
            logger.warning("Ingestion error for %s: %s", drive_file_id, e)
            sm.transition(drive_file_id, DocumentState.FAILED, error_message=str(e))
            return ProcessingResult(
                drive_file_id=drive_file_id,
                filename=filename or drive_file_id,
                mime_type=mime_type,
                status="failed",
                state=DocumentState.FAILED,
                error=str(e),
            )
        except Exception as e:
            logger.exception("Unexpected error processing %s", drive_file_id)
            sm.transition(drive_file_id, DocumentState.REQUIRES_REVIEW, error_message=str(e))
            return ProcessingResult(
                drive_file_id=drive_file_id,
                filename=filename or drive_file_id,
                mime_type=mime_type,
                status="requires_review",
                state=DocumentState.REQUIRES_REVIEW,
                error=str(e),
            )

    def process_batch(
        self,
        items: List[Dict[str, Any]],
        max_items: Optional[int] = None,
        ocr_mode: str = "auto",
    ) -> List[ProcessingResult]:
        """
        Process a batch of documents sequentially.

        Each item: {drive_file_id, mime_type, filename, folder_path}
        """
        results: List[ProcessingResult] = []
        for i, item in enumerate(items):
            if max_items and i >= max_items:
                break
            try:
                # Inject OCR mode into the item before processing
                item_to_use = dict(item)
                item_to_use.setdefault("ocr_mode", ocr_mode)
                result = self.process_one(**item_to_use)
                results.append(result)
            except Exception as e:
                logger.exception("Failed to process batch item %s", item)
                results.append(ProcessingResult(
                    drive_file_id=item.get("drive_file_id", "?"),
                    filename=item.get("filename", "?"),
                    mime_type=item.get("mime_type", "?"),
                    status="failed",
                    state=DocumentState.FAILED,
                    error=str(e),
                ))
        return results

    def reprocess_extraction(
        self,
        drive_file_id: str,
        mime_type: str,
        filename: str = None,
        folder_path: str = None,
        ocr_mode: str = "auto",
    ) -> ProcessingResult:
        """
        Re-run ONLY extraction+audit on an already-downloaded raw file.

        Skips the Drive download (idempotent cache hit). Replaces the
        persisted extracted JSON if extraction succeeds.
        """
        sm = self.state_machine

        # Force-reset non-terminal state
        current = sm.get_state(drive_file_id)
        if current is not None and current not in (
            DocumentState.INDEXED, DocumentState.DEAD_LETTER
        ):
            sm.transition(drive_file_id, DocumentState.DISCOVERED, force=True)
        sm.transition(drive_file_id, DocumentState.DOWNLOADING)
        sm.transition(drive_file_id, DocumentState.DOWNLOADED)
        sm.transition(drive_file_id, DocumentState.EXTRACTED)

        # Find local raw file
        raw_dir = Path(self.ingestion.raw_dir)
        candidates = sorted(raw_dir.glob(f"{drive_file_id}.*"))
        if not candidates:
            sm.transition(drive_file_id, DocumentState.FAILED, error_message="No local raw file")
            return ProcessingResult(
                drive_file_id=drive_file_id, filename=filename or drive_file_id,
                mime_type=mime_type, status="failed", state=DocumentState.FAILED,
                error="No local raw file (download first)",
            )

        local_path = str(candidates[0])

        # Effective mime: derive from file extension for workspace exports
        ext = candidates[0].suffix.lower()
        ext_to_mime = {
            ".txt": "text/plain", ".md": "text/markdown", ".csv": "text/csv",
            ".tsv": "text/tab-separated-values", ".pdf": "application/pdf",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".json": "application/json",
        }
        effective_mime = ext_to_mime.get(ext, mime_type)

        extraction_meta = {
            "doc_id": drive_file_id,
            "mime_type": effective_mime,
            "provenance": {
                "drive_file_id": drive_file_id,
                "filename": filename or drive_file_id,
                "folder_path": folder_path,
                "mime_type": mime_type,
                "effective_mime_type": effective_mime,
            },
            "doc_metadata": {
                "title": filename or drive_file_id,
            },
            "ocr_mode": ocr_mode,
        }

        result = self.extraction.extract(local_path, extraction_meta)
        self._save_extracted(drive_file_id, result)

        # Structured data plane: import tables (CSV/Sheets) to Parquet
        if result.tables:
            try:
                imported = self.structured.import_table_from_extraction(
                    result.to_dict()
                )
                if imported:
                    logger.info(
                        "Imported structured table %s (%d rows) from %s",
                        imported.table_id, len(imported.rows), drive_file_id,
                    )
            except Exception as e:
                logger.warning(
                    "Structured import failed for %s: %s", drive_file_id, e
                )

        audit = self.auditor.audit_extraction(result)

        if audit.overall_status == AuditStatus.FAIL or result.extraction_quality == ExtractionQuality.FAILED:
            sm.transition(drive_file_id, DocumentState.REQUIRES_REVIEW,
                          error_message=result.error_message or "extraction failed")
            return ProcessingResult(
                drive_file_id=drive_file_id, filename=filename or drive_file_id,
                mime_type=mime_type, status="requires_review",
                state=DocumentState.REQUIRES_REVIEW,
                extraction_quality=result.extraction_quality.value,
                error=result.error_message, audit=audit, local_path=local_path,
            )

        sm.transition(drive_file_id, DocumentState.NORMALIZED)
        return ProcessingResult(
            drive_file_id=drive_file_id, filename=filename or drive_file_id,
            mime_type=mime_type, status="success", state=DocumentState.NORMALIZED,
            extraction_quality=result.extraction_quality.value,
            audit=audit, local_path=local_path,
        )

    # ─── Persistence ────────────────────────────────────────────────────────

    def _save_extracted(self, drive_file_id: str, result: ExtractionResult):
        """Persist the extracted representation (JSON) for downstream pipelines.

        The file path is derived from ``drive_file_id`` (trusted catalog input),
        so it is passed through the safe-subpath guard to prevent traversal, and
        the Drive directory boundary is enforced before any write.
        """
        from src.resilience import safe_subpath, assert_not_in_locus_drive
        out_path = safe_subpath(self.extracted_dir, f"{drive_file_id}.json")
        assert_not_in_locus_drive(out_path)
        data = result.to_dict()
        data["saved_at"] = datetime.now(timezone.utc).isoformat()
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def summary_from_results(
        self, results: List[ProcessingResult]
    ) -> Dict[str, Any]:
        """Summarize batch processing results."""
        statuses = {}
        for r in results:
            statuses[r.status] = statuses.get(r.status, 0) + 1

        quality_counts = {}
        for r in results:
            if r.extraction_quality:
                quality_counts[r.extraction_quality] = (
                    quality_counts.get(r.extraction_quality, 0) + 1
                )

        return {
            "total": len(results),
            "statuses": statuses,
            "extraction_quality": quality_counts,
            "errors": [
                {"drive_file_id": r.drive_file_id, "error": r.error}
                for r in results if r.error
            ],
        }

    # ─── State inspection ─────────────────────────────────────────────────────

    def review_queue(self) -> List[str]:
        """Documents in REQUIRES_REVIEW state."""
        return self.state_machine.get_documents_in_state(DocumentState.REQUIRES_REVIEW)

    def dead_letter_queue(self) -> List[str]:
        """Documents in DEAD_LETTER state."""
        return self.state_machine.get_documents_in_state(DocumentState.DEAD_LETTER)

    def state_counts(self) -> Dict[str, int]:
        return self.state_machine.get_state_counts()


# ─── CLI entry point (dev tool, not production library) ─────────────────────

def ingest_sample(
    data_dir: str = "/Users/ashim/locus_rag/data",
    max_files: int = 10,
    prefer_types: List[str] = None,
    seed: Optional[int] = None,
    verbose: bool = True,
    ocr_mode: str = "auto",
) -> Dict[str, Any]:
    """
    Ingest a small sample of actual LOCUS files.

    This is the Phase 2b smoke test: pick a few real files from the
    existing catalog, download them read-only, extract, and audit.
    """
    import random

    # Build orchestrator
    orch = IngestionOrchestrator(data_dir=data_dir)

    # Discover from catalog
    rows = orch.ingestion.query_catalog(
        mime_types=prefer_types,
        max_files=max_files * 5,  # oversample, then pick
    )
    if seed is not None:
        random.seed(seed)

    # Deterministic pseudo-random pick across types
    from collections import defaultdict
    by_type = defaultdict(list)
    for r in rows:
        by_type[r["mime_type"]].append(r)

    picked: List[Dict[str, Any]] = []
    per_type_budget = {}

    # Respect prefer_types ordering for a balanced sample
    if prefer_types:
        for mt in prefer_types:
            per_type_budget[mt] = max_files // len(prefer_types) or 1
    else:
        total_types = len(by_type)
        per_type_budget = {mt: max(1, max_files // total_types) for mt in by_type}

    for mt, budget in per_type_budget.items():
        pool = by_type.get(mt, [])
        random.shuffle(pool)
        for r in pool[:budget]:
            picked.append({
                "drive_file_id": r["drive_file_id"],
                "mime_type": r["mime_type"],
                "filename": r["filename"],
                "folder_path": r.get("folder_path"),
            })

    if verbose:
        print(f"\n{'='*60}")
        print(f"LOCUS RAG — Phase 2b Sample Ingestion")
        print(f"{'='*60}")
        print(f"Picked {len(picked)} files for ingestion:")

    results = orch.process_batch(picked, ocr_mode=ocr_mode)

    if verbose:
        summary = orch.summary_from_results(results)
        print(f"\n{'='*60}")
        print(f"Summary: {summary['total']} files processed")
        print(f"  Statuses: {summary['statuses']}")
        print(f"  Extraction quality: {summary['extraction_quality']}")
        print(f"  Errors: {len(summary['errors'])}")
        for e in summary["errors"][:5]:
            print(f"    - {e['drive_file_id']}: {e['error']}")
        print(f"\n  State counts: {orch.state_counts()}")
        print(f"  Review queue: {orch.review_queue()}")
        print(f"{'='*60}\n")

    return summary


if __name__ == "__main__":
    import sys
    # CLI: python -m src.pipeline.ingest_orchestrator [max_files] [--types ...]
    max_f = 10
    types = None
    if len(sys.argv) > 1:
        try:
            max_f = int(sys.argv[1])
        except ValueError:
            pass
    if "--types" in sys.argv:
        idx = sys.argv.index("--types")
        types = sys.argv[idx + 1].split(",")
    ocr = "auto"
    if "--ocr" in sys.argv:
        idx = sys.argv.index("--ocr")
        ocr = sys.argv[idx + 1].lower()
    ingest_sample(
        data_dir="/Users/ashim/locus_rag/data",
        max_files=max_f,
        prefer_types=types,
        ocr_mode=ocr,
    )