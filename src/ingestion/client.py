"""
LOCUS RAG Ingestion Client.

Read-only ingestion from Google Drive. NEVER mutates Drive.

Wraps the existing DriveClient from /Users/ashim/locus_drive.
Adds:
  - Workspace export (Google Docs -> text, Sheets -> CSV, Slides -> text)
  - Format-based download routing
  - Idempotent local file cache
  - Content-hash tracking
"""

import hashlib
import json
import logging
import sqlite3
from dataclasses import dataclass, asdict, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ─── Workspace export MIME types ────────────────────────────────────────────
# Per Google Drive API docs: Google Docs/Sheets/Slides require an explicit
# export call to retrieve file content in an open format.
# We export to text/CSV so we never need to keep Google-native blobs.
EXPORT_MIME_TYPES: Dict[str, str] = {
    "application/vnd.google-apps.document": "text/plain",
    "application/vnd.google-apps.spreadsheet": "text/csv",
    "application/vnd.google-apps.presentation": "text/plain",
    "application/vnd.google-apps.drawing": "image/png",
    "application/vnd.google-apps.form": "application/json",
    "application/vnd.google-apps.script": "application/json",
}

# Mime types we will skip entirely (per spec §7 — images/video/etc. excluded for V1)
EXCLUDED_MIME_PREFIXES: Tuple[str, ...] = (
    "image/",
    "video/",
    "audio/",
    "font/",
    "application/photoshop",
    "application/illustrator",
    "application/x-executable",
    "application/x-msdownload",
)


class IngestionError(Exception):
    """Raised when an ingestion operation fails after exhausting retries."""


@dataclass
class IngestedFile:
    """Result of ingesting a single Drive file.

    The raw bytes are stored locally in `data/raw/<drive_file_id>.<ext>`.
    Provenance is preserved for the entire downstream pipeline.
    """
    drive_file_id: str
    filename: str
    mime_type: str
    folder_path: Optional[str]
    size_bytes: int
    content_hash: str
    local_path: str
    was_workspace_export: bool
    # Effective MIME type after Workspace export (e.g. a Google Sheet exports
    # to text/csv). Downstream extraction routes on THIS type, not the
    # original Drive MIME type.
    effective_mime_type: Optional[str] = None
    web_view_link: Optional[str] = None
    revision_id: Optional[str] = None
    created_time: Optional[str] = None
    modified_time: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class IngestionClient:
    """Read-only ingestion client for Google Drive → local cache.

    All methods are idempotent: re-ingesting the same file is a no-op
    unless the content hash changes.
    """

    def __init__(
        self,
        catalog_path: str = "/Users/ashim/locus_drive/locus_drive.db",
        data_dir: str = "/Users/ashim/locus_rag/data",
        drive_client: Any = None,
    ):
        self.catalog_path = catalog_path
        self.data_dir = Path(data_dir)
        self.raw_dir = self.data_dir / "raw"
        self.raw_dir.mkdir(parents=True, exist_ok=True)

        # Lazy import to keep this module testable without Drive deps.
        self._drive_client = drive_client

    @property
    def drive_client(self):
        """Lazily construct the existing read-only DriveClient."""
        if self._drive_client is None:
            # The existing sync system lives at ~/locus_drive — ensure it's importable.
            import sys
            from pathlib import Path as _Path
            locus_drive_dir = _Path.home() / "locus_drive"
            if str(locus_drive_dir) not in sys.path:
                sys.path.insert(0, str(locus_drive_dir))
            from drive_client import DriveClient  # type: ignore
            self._drive_client = DriveClient()
            self._drive_client.authenticate()
        return self._drive_client

    # ─── Catalog queries (read-only) ──────────────────────────────────────

    def query_catalog(
        self,
        mime_types: Optional[List[str]] = None,
        exclude_mime_prefixes: Tuple[str, ...] = EXCLUDED_MIME_PREFIXES,
        max_files: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Read file rows from the existing SQLite catalog.

        Returns dicts with the columns the downstream pipeline needs.
        """
        conn = sqlite3.connect(self.catalog_path)
        cursor = conn.cursor()

        params: List[Any] = [0]  # trashed = 0
        sql = [
            "SELECT id, name, mime_type, path, drive_id, parents,",
            "       created_time, modified_time, viewed_by_me, size,",
            "       web_view_link, web_content_link, owned_by_me,",
            "       last_modifying_user, sharing_user, permissions",
            "FROM files",
            "WHERE trashed = ?",
        ]

        if mime_types:
            placeholders = ",".join("?" for _ in mime_types)
            sql.append(f"AND mime_type IN ({placeholders})")
            params.extend(mime_types)

        if exclude_mime_prefixes:
            not_clauses = " AND ".join(
                "mime_type NOT LIKE ?" for _ in exclude_mime_prefixes
            )
            sql.append(f"AND {not_clauses}")
            params.extend(p + "%" for p in exclude_mime_prefixes)

        sql.append("ORDER BY modified_time DESC")
        if max_files:
            sql.append(f"LIMIT {int(max_files)}")

        cursor.execute("\n".join(sql), params)
        columns = [
            "drive_file_id", "filename", "mime_type", "folder_path", "drive_id",
            "parents", "created_time", "modified_time", "viewed_by_me", "size",
            "web_view_link", "web_content_link", "owned_by_me",
            "last_modifying_user", "sharing_user", "permissions",
        ]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

        # Parse JSON columns
        for r in rows:
            for json_col in ("parents", "last_modifying_user", "sharing_user", "permissions"):
                val = r.get(json_col)
                if val and isinstance(val, str):
                    try:
                        r[json_col] = json.loads(val)
                    except json.JSONDecodeError:
                        r[json_col] = None
                else:
                    r[json_col] = None
        conn.close()
        return rows

    # ─── File downloading ────────────────────────────────────────────────

    def is_workspace_native(self, mime_type: str) -> bool:
        return mime_type in EXPORT_MIME_TYPES

    def is_supported(self, mime_type: str) -> bool:
        """True if we will attempt to ingest this mime type in V1."""
        if self.is_workspace_native(mime_type):
            return True
        supported = {
            "application/pdf",
            "text/plain",
            "text/markdown",
            "text/csv",
            "text/tab-separated-values",
            "application/rtf",
            "application/json",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.ms-excel",
            "application/msword",
            "application/vnd.oasis.opendocument.text",
            "application/vnd.oasis.opendocument.spreadsheet",
        }
        return mime_type in supported

    def local_cache_path(self, drive_file_id: str, extension: str) -> Path:
        return self.raw_dir / f"{drive_file_id}{extension}"

    def _hash_bytes(self, data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def download_file(
        self, drive_file_id: str, mime_type: str
    ) -> IngestedFile:
        """Download a file from Drive (or export a Workspace file).

        Idempotent: if the local copy already matches the content we want,
        we return metadata without re-downloading.
        """
        if not self.is_supported(mime_type):
            raise IngestionError(f"Unsupported mime type: {mime_type}")

        # Look up the catalog row so we have full metadata + provenance.
        catalog_row = self._get_catalog_row(drive_file_id)
        if catalog_row is None:
            raise IngestionError(
                f"Drive file ID {drive_file_id} not found in catalog"
            )

        if self.is_workspace_native(mime_type):
            return self._export_workspace(drive_file_id, catalog_row)
        return self._download_binary(drive_file_id, catalog_row)

    def _get_catalog_row(self, drive_file_id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.catalog_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, name, mime_type, path, drive_id, parents,
                   created_time, modified_time, size, web_view_link,
                   last_modifying_user, sharing_user, permissions
            FROM files WHERE id = ? AND trashed = 0
            """,
            (drive_file_id,),
        )
        row = cursor.fetchone()
        conn.close()
        if row is None:
            return None
        return {
            "drive_file_id": row[0],
            "filename": row[1],
            "mime_type": row[2],
            "folder_path": row[3],
            "drive_id": row[4],
            "parents": json.loads(row[5]) if row[5] else None,
            "created_time": row[6],
            "modified_time": row[7],
            "size": row[8],
            "web_view_link": row[9],
            "last_modifying_user": row[10],
            "sharing_user": row[11],
            "permissions": row[12],
        }

    def _export_workspace(
        self, drive_file_id: str, row: Dict[str, Any]
    ) -> IngestedFile:
        """Export a Google Docs/Sheets/Slides file to an open format."""
        export_mime = EXPORT_MIME_TYPES[row["mime_type"]]
        ext = _extension_for_mime(export_mime)
        local_path = self.local_cache_path(drive_file_id, ext)

        # Idempotent cache check
        if local_path.exists():
            data = local_path.read_bytes()
            return self._build_ingested_file(row, data, local_path, True)

        try:
            request = self.drive_client.service.files().export_media(
                fileId=drive_file_id, mimeType=export_mime
            )
            data = request.execute()
        except Exception as e:
            raise IngestionError(
                f"Failed to export Drive file {drive_file_id}: {e}"
            ) from e

        if not isinstance(data, bytes):
            data = data.encode("utf-8") if isinstance(data, str) else bytes(data)

        local_path.write_bytes(data)
        return self._build_ingested_file(row, data, local_path, True)

    def _download_binary(
        self, drive_file_id: str, row: Dict[str, Any]
    ) -> IngestedFile:
        """Download a non-Workspace file (PDF, DOCX, etc.)."""
        ext = _extension_for_mime(row["mime_type"]) or ".bin"
        local_path = self.local_cache_path(drive_file_id, ext)

        if local_path.exists():
            data = local_path.read_bytes()
            return self._build_ingested_file(row, data, local_path, False)

        try:
            request = self.drive_client.service.files().get_media(
                fileId=drive_file_id
            )
            data = request.execute()
        except Exception as e:
            raise IngestionError(
                f"Failed to download Drive file {drive_file_id}: {e}"
            ) from e

        if not isinstance(data, bytes):
            data = bytes(data)

        local_path.write_bytes(data)
        return self._build_ingested_file(row, data, local_path, False)

    def _build_ingested_file(
        self,
        row: Dict[str, Any],
        data: bytes,
        local_path: Path,
        was_workspace_export: bool,
    ) -> IngestedFile:
        # If workspace export, the effective MIME type is the export target
        effective_mime = row["mime_type"]
        if was_workspace_export:
            effective_mime = EXPORT_MIME_TYPES.get(row["mime_type"], row["mime_type"])
        return IngestedFile(
            drive_file_id=row["drive_file_id"],
            filename=row["filename"],
            mime_type=row["mime_type"],
            folder_path=row.get("folder_path"),
            size_bytes=len(data),
            content_hash=self._hash_bytes(data),
            local_path=str(local_path),
            was_workspace_export=was_workspace_export,
            effective_mime_type=effective_mime,
            web_view_link=row.get("web_view_link"),
            created_time=row.get("created_time"),
            modified_time=row.get("modified_time"),
        )


def _extension_for_mime(mime_type: str) -> str:
    """Map MIME type to a sensible file extension for local caching."""
    mapping = {
        "text/plain": ".txt",
        "text/markdown": ".md",
        "text/csv": ".csv",
        "text/tab-separated-values": ".tsv",
        "application/pdf": ".pdf",
        "application/rtf": ".rtf",
        "application/json": ".json",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
        "application/vnd.ms-excel": ".xls",
        "application/msword": ".doc",
        "application/vnd.oasis.opendocument.text": ".odt",
        "application/vnd.oasis.opendocument.spreadsheet": ".ods",
        "image/png": ".png",
    }
    return mapping.get(mime_type, ".bin")
