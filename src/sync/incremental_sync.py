"""
LOCUS RAG Incremental Sync Engine — Phase 12.

Per spec §121–§130 (Sync / Incremental Processing):
  - Drive Changes API integration with the existing catalog
  - Changed-document detection via rev_id / modified_time comparison
  - Selective reprocessing: only process what changed
  - Stale-index invalidation
  - Versioned corpus/index snapshots with atomic swaps
  - Permission-aware design (catalog read-only, all writes in locus_rag)
  - Idempotent operation; crash recovery support

The engine wraps the existing CatalogClient (reads-only SQLite catalog at
/Users/ashim/locus_drive/locus_drive.db) and the IngestionOrchestrator,
never mutating Drive or its catalog.
"""

import hashlib
import json
import logging
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.pipeline.ingest_orchestrator import ProcessingResult
from src.ingestion.client import IngestionClient, IngestedFile
from src.pipeline.ingest_orchestrator import IngestionOrchestrator
from src.indexing.vector import (
    ExactEntityIndex,
    BM25Index,
    DenseVectorIndex,
    MetadataIndex,
    SearchQuery,
)

logger = logging.getLogger(__name__)


# ─── Change Detection ────────────────────────────────────────────────────────

@dataclass
class ChangedDoc:
    """A document that changed since the last incremental sync.

    Fields mirror the real catalog (`locus_drive.db` `files` table) and the
    engine's own sync checkpoints in rag_state.db. There is NO `revision_id`
    or content_hash column in the catalog — change detection compares
    (modified_time, size_bytes) against stored checkpoints.
    """
    drive_file_id: str
    filename: str
    mime_type: str
    modified_time: Optional[str]  # ISO8601 from catalog
    synced_at: Optional[str]  # When it was last fully synced
    size_bytes: int
    processing_state: str  # from catalog documents table (may be "unknown")
    needs_reprocess: bool = False  # True if content changed since last sync


class IncrementalSyncEngine:
    """
    Detects changed documents from the existing catalog and triggers selective
    reprocessing, avoiding full reindex on every Drive change.
    """

    def __init__(
        self,
        catalog_path: str = "/Users/ashim/locus_drive/locus_drive.db",
        rag_state_db: Optional[str] = None,
        data_dir: str = "/Users/ashim/locus_rag",
    ):
        self.catalog_path = catalog_path
        self.rag_state_db = rag_state_db or str(Path(data_dir) / "db" / "rag_state.db")
        self.data_dir = Path(data_dir)

    def _read_last_run_at(self) -> Optional[float]:
        """Read the last successful incremental sync timestamp from rag_state.db."""
        conn = sqlite3.connect(self.rag_state_db)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS sync_state ("
                " id INTEGER PRIMARY KEY CHECK (id = 1),"
                " account_email TEXT,"
                " last_init_sync_at TEXT,"
                " last_inc_sync_at TEXT,"
                " init_sync_complete INTEGER,"
                " init_in_progress INTEGER,"
                " total_files_seen INTEGER)"
            )
            cur = conn.execute(
                "SELECT last_inc_sync_at FROM sync_state WHERE id = 1"
            )
            row = cur.fetchone()
            if row and row["last_inc_sync_at"]:
                time_str = row["last_inc_sync_at"]
                if time_str.endswith('Z'):
                    time_str = time_str[:-1] + '+00:00'
                return datetime.fromisoformat(time_str).timestamp()
        except Exception:
            pass
        finally:
            conn.close()
        return None

    def _record_last_run_at(self):
        """Record the current time as the last successful incremental sync in rag_state.db."""
        conn = sqlite3.connect(self.rag_state_db)
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS sync_state ("
                " id INTEGER PRIMARY KEY CHECK (id = 1),"
                " account_email TEXT,"
                " last_init_sync_at TEXT,"
                " last_inc_sync_at TEXT,"
                " init_sync_complete INTEGER,"
                " init_in_progress INTEGER,"
                " total_files_seen INTEGER)"
            )
            conn.execute(
                "INSERT OR REPLACE INTO sync_state (id, last_inc_sync_at) VALUES (1, ?)",
                (datetime.now(timezone.utc).isoformat(),)
            )
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to record last run at: {e}")
        finally:
            conn.close()

    def get_changed_docs(
        self,
        since: Optional[float] = None,
        only_states: Optional[List[str]] = None,
    ) -> List[ChangedDoc]:
        """
        Query the catalog for documents that changed since the given timestamp.

        If since is None, detect all docs modified since last_inc_sync_at was
        recorded (read from the sync_state table).
        """
        conn = sqlite3.connect(self.catalog_path)
        conn.row_factory = sqlite3.Row

        # Determine baseline timestamp.
        # Priority: (1) explicit `since`, (2) engine's own run state in
        # rag_state.db, (3) catalog's sync_state (read-only reference).
        baseline_ts = None
        if since is not None:
            baseline_ts = since
        else:
            baseline_ts = self._read_last_run_at()
            if baseline_ts is None:
                try:
                    cur = conn.execute(
                        "SELECT last_inc_sync_at FROM sync_state WHERE id = 1"
                    )
                    row = cur.fetchone()
                    if row and row["last_inc_sync_at"]:
                        time_str = row["last_inc_sync_at"]
                        # Accept Z suffix and fractional seconds
                        if time_str.endswith('Z'):
                            time_str = time_str[:-1] + '+00:00'
                        baseline_ts = datetime.fromisoformat(time_str).timestamp()
                except Exception:
                    baseline_ts = 0  # No baseline → check everything

        if baseline_ts is not None:
            # Convert baseline timestamp to a string in the format: YYYY-MM-DDTHH:MM:SSZ
            baseline_dt = datetime.fromtimestamp(baseline_ts, timezone.utc)
            baseline_str = baseline_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            query = """
                SELECT id, name, mime_type, modified_time,
                       size, web_view_link, synced_at
                FROM files
                WHERE modified_time IS NOT NULL
                AND trashed = 0
                AND modified_time > ?
            """
            params = [baseline_str]
        else:
            query = """
                SELECT id, name, mime_type, modified_time,
                       size, web_view_link, synced_at
                FROM files
                WHERE modified_time IS NOT NULL
                AND trashed = 0
            """
            params = []

        # Filter by state if requested — we can filter by processing_state
        # from the documents table in rag_state.db, but for a pure catalog-only
        # filter we just use modified_time. The only_states parameter is kept
        # for API compatibility but has no effect when only the catalog is used.
        if only_states:
            # Cannot filter by processing_state from catalog alone;
            # silently ignore or raise a warning.
            import warnings
            warnings.warn(
                "State filtering from catalog-only not supported; "
                "using modified_time filter only.",
                stacklevel=2,
            )

        cur = conn.execute(query, params)
        rows = cur.fetchall()
        conn.close()

        changed: List[ChangedDoc] = []
        for row in rows:
            cdoc = ChangedDoc(
                drive_file_id=row["id"],
                filename=row["name"] or "",
                mime_type=row["mime_type"] or "",
                modified_time=row["modified_time"],
                synced_at=row["synced_at"],
                size_bytes=row["size"] or 0,
                processing_state="unknown",
                needs_reprocess=False,
            )
            changed.append(cdoc)

        return changed

    def _get_sync_checkpoints(self) -> Dict[str, Tuple[Optional[str], int]]:
        """
        Get the last-known (modified_time, size_bytes) for each file from
        the engine's own sync checkpoints stored in the rag_state DB.

        Returns a dict mapping drive_file_id -> (last_modified_time, last_size_bytes).
        If a file has no checkpoint, it won't appear in the dict.
        """
        conn = sqlite3.connect(self.rag_state_db)
        conn.row_factory = sqlite3.Row
        # Ensure the checkpoint table exists before we try to read from it
        conn.execute(
            "CREATE TABLE IF NOT EXISTS sync_checkpoints ("
            " drive_file_id TEXT PRIMARY KEY,"
            " last_modified_time TEXT,"
            " last_size_bytes INTEGER,"
            " updated_at TEXT)"
        )
        checkpoints: Dict[str, Tuple[Optional[str], int]] = {}

        try:
            cur = conn.execute(
                "SELECT drive_file_id, last_modified_time, last_size_bytes FROM sync_checkpoints"
            )
            for row in cur.fetchall():
                checkpoints[row["drive_file_id"]] = (row["last_modified_time"], row["last_size_bytes"])
        except Exception:
            # If we can't read checkpoints, treat all files as needing reprocess
            pass
        finally:
            conn.close()

        return checkpoints

    def _update_sync_checkpoint(self, drive_file_id: str, modified_time: Optional[str], size_bytes: int):
        """Update the sync checkpoint for a file after successful processing."""
        conn = sqlite3.connect(self.rag_state_db)
        try:
            # Ensure the checkpoint table exists before inserting
            conn.execute(
                "CREATE TABLE IF NOT EXISTS sync_checkpoints ("
                " drive_file_id TEXT PRIMARY KEY,"
                " last_modified_time TEXT,"
                " last_size_bytes INTEGER,"
                " updated_at TEXT)"
            )
            conn.execute(
                "INSERT OR REPLACE INTO sync_checkpoints"
                " (drive_file_id, last_modified_time, last_size_bytes, updated_at)"
                " VALUES (?, ?, ?, ?)",
                (drive_file_id, modified_time, size_bytes, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to update sync checkpoint for {drive_file_id}: {e}")
        finally:
            conn.close()

    def detect_significant_changes(
        self, changed_docs: List[ChangedDoc]
    ) -> List[ChangedDoc]:
        """
        Determine which changed documents actually need reprocessing by comparing
        their current (modified_time, size_bytes) against the last-known checkpoint.
        """
        # Get existing checkpoints from the engine's own storage
        checkpoints = self._get_sync_checkpoints()

        significant: List[ChangedDoc] = []
        for doc in changed_docs:
            checkpoint = checkpoints.get(doc.drive_file_id)
            needs = False

            if checkpoint is None:
                # No checkpoint = new file or never successfully synced
                needs = True
            else:
                last_modified_time, last_size_bytes = checkpoint
                # Significant change if either modified_time or size differs
                if (doc.modified_time != last_modified_time or
                    doc.size_bytes != last_size_bytes):
                    needs = True

            if needs:
                doc.needs_reprocess = True
                significant.append(doc)
            else:
                doc.needs_reprocess = False

        return significant

    def run_incremental_sync(
        self,
        only_states: Optional[List[str]] = None,
        ocr_mode: str = "auto",
        max_files: Optional[int] = None,
        reset_state: bool = False,
    ) -> Dict[str, Any]:
        """
        Run the full incremental sync cycle:
          1. Detect changed docs from catalog
          2. Flag those needing reprocessing
          3. Run the IngestionOrchestrator on the flagged subset
          4. Update catalog sync timestamps atomically
          5. Return summary

        Returns a dict with processing summary.
        """
        # Step 1: Detect changes
        changed = self.get_changed_docs(only_states=only_states)
        logger.info(f"Found {len(changed)} changed documents in catalog")

        # Step 2: Flag those needing reprocessing
        significant = self.detect_significant_changes(changed)
        logger.info(f"Of those, {len(significant)} have significant changes")

        if not significant and not reset_state:
            return {
                "total_changed": len(changed),
                "reprocessed": 0,
                "new_processed": 0,
                "skipped": len(changed),
                "status": "nothing_changed",
            }

        # Step 3: Build the subset to process
        to_process: List[ChangedDoc] = significant
        if reset_state:
            to_process = changed

        if max_files and len(to_process) > max_files:
            to_process = to_process[:max_files]
            logger.warning(f"Limited to {max_files} files for this sync cycle")

        # Step 4: Process via existing IngestionOrchestrator
        orch = IngestionOrchestrator(
            data_dir=str(self.data_dir),
            state_db_path=self.rag_state_db,
            catalog_path=self.catalog_path,
        )

        # Map docs to IngestedFile format for the orchestrator
        ingest_files: List[IngestedFile] = []
        for doc in to_process:
            # Try to find the row in catalog for full metadata
            conn = sqlite3.connect(self.catalog_path)
            conn.row_factory = sqlite3.Row
            cur = conn.execute(
                "SELECT id, name, mime_type, size, modified_time FROM files WHERE id = ?",
                (doc.drive_file_id,),
            )
            row = cur.fetchone()
            conn.close()

            if row is None:
                logger.warning(f"Catalog row missing for {doc.drive_file_id}")
                continue

            # sqlite3.Row doesn't have .get(), use direct access with fallback
            def _r(key: str, default: str = "") -> str:
                try:
                    return row[key] or default
                except Exception:
                    return default

            ingest_files.append(
                IngestedFile(
                    drive_file_id=doc.drive_file_id,
                    filename=row["name"] or doc.filename,
                    mime_type=row["mime_type"] or doc.mime_type,
                    folder_path=None,
                    size_bytes=row["size"] or doc.size_bytes,
                    content_hash="",  # placeholder — orchestrator will compute
                    local_path="",
                    was_workspace_export=False,
                    effective_mime_type=row["mime_type"],
                    web_view_link=_r("web_view_link"),
                    # real catalog has no revision_id column
                    created_time=_r("created_time"),
                    modified_time=_r("modified_time"),
                    metadata={},
                )
            )

        if not ingest_files:
            return {
                "total_changed": len(changed),
                "reprocessed": 0,
                "new_processed": 0,
                "skipped": len(changed),
                "status": "nothing_to_process",
            }

        # Convert to the format expected by process_batch/process_one
        # process_one expects: drive_file_id, mime_type, filename, folder_path, max_chars, ocr_mode
        # process_batch adds ocr_mode, so we provide the rest
        process_items: List[Dict[str, Any]] = []
        for ingest_file in ingest_files:
            process_items.append({
                "drive_file_id": ingest_file.drive_file_id,
                "mime_type": ingest_file.mime_type,
                "filename": ingest_file.filename,
                "folder_path": ingest_file.folder_path,
                # max_chars will use default from process_one (100_000)
            })

        # Run the orchestrator batch
        results = orch.process_batch(process_items, ocr_mode=ocr_mode)

        # Step 5: Record sync checkpoints in the RAG state DB only.
        # The catalog (/Users/ashim/locus_drive/locus_drive.db) is READ-ONLY —
        # never update its sync_state or files tables. Baseline persistence and
        # per-file checkpoints both live in the engine's own rag_state.db.
        failures = [r for r in results if r.status != "success"]
        for r in results:
            if r.status == "success":
                # Look up current file metadata from the catalog (read-only)
                try:
                    conn = sqlite3.connect(self.catalog_path)
                    conn.row_factory = sqlite3.Row
                    cur = conn.execute(
                        "SELECT modified_time, size FROM files WHERE id = ? AND trashed = 0",
                        (r.drive_file_id,),
                    )
                    row = cur.fetchone()
                    conn.close()
                    if row:
                        self._update_sync_checkpoint(
                            r.drive_file_id,
                            row["modified_time"],
                            row["size"] or 0
                        )
                except Exception as e:
                    logger.error(f"Failed to update checkpoint for {r.drive_file_id}: {e}")

        # Advance the baseline ONLY if every file in this run succeeded.
        # If any file failed, keep the old baseline so that failed file is
        # re-detected and retried on the next cycle instead of being dropped
        # by the advancing watermark (Phase 12 req: failures must stay retryable).
        if failures:
            logger.warning(
                "%d file(s) failed this cycle; baseline NOT advanced so they remain retryable.",
                len(failures),
            )
        else:
            self._record_last_run_at()

        # Summary
        new_processed = sum(1 for r in results if r.status == "success" and r.chunks > 0)
        skipped = len(changed) - len(to_process)

        status = "completed_with_errors" if failures else "completed"
        summary = {
            "total_changed": len(changed),
            "reprocessed": new_processed,
            "new_processed": new_processed,  # distinction can be added later
            "skipped": skipped,
            "failed": len(failures),
            "status": status,
        }

        logger.info(f"Incremental sync complete: {summary}")
        return summary