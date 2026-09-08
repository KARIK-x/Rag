"""
Per-document state machine and pipeline orchestrator for LOCUS RAG.

Per spec §51:
  DISCOVERED → DOWNLOADING → DOWNLOADED → EXTRACTED → NORMALIZED
  → CLASSIFIED → DEDUPLICATED → CHUNKED → EMBEDDED → INDEXED

Failures transition to:
  FAILED, REQUIRES_REVIEW, DEAD_LETTER

Every transition is logged to database and disk.
"""

import logging
import sqlite3
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class DocumentState(Enum):
    DISCOVERED = "discovered"
    DOWNLOADING = "downloading"
    DOWNLOADED = "downloaded"
    EXTRACTED = "extracted"
    NORMALIZED = "normalized"
    CLASSIFIED = "classified"
    DEDUPLICATED = "deduplicated"
    CHUNKED = "chunked"
    EMBEDDED = "embedded"
    INDEXED = "indexed"
    FAILED = "failed"
    REQUIRES_REVIEW = "requires_review"
    DEAD_LETTER = "dead_letter"


# Valid state transitions
VALID_TRANSITIONS: Dict[DocumentState, List[DocumentState]] = {
    DocumentState.DISCOVERED: [DocumentState.DOWNLOADING, DocumentState.FAILED],
    DocumentState.DOWNLOADING: [DocumentState.DOWNLOADED, DocumentState.FAILED, DocumentState.REQUIRES_REVIEW],
    DocumentState.DOWNLOADED: [DocumentState.EXTRACTED, DocumentState.FAILED, DocumentState.REQUIRES_REVIEW],
    DocumentState.EXTRACTED: [DocumentState.NORMALIZED, DocumentState.FAILED, DocumentState.REQUIRES_REVIEW],
    DocumentState.NORMALIZED: [DocumentState.CLASSIFIED, DocumentState.FAILED],
    DocumentState.CLASSIFIED: [DocumentState.DEDUPLICATED, DocumentState.FAILED],
    DocumentState.DEDUPLICATED: [DocumentState.CHUNKED, DocumentState.FAILED],
    DocumentState.CHUNKED: [DocumentState.EMBEDDED, DocumentState.FAILED],
    DocumentState.EMBEDDED: [DocumentState.INDEXED, DocumentState.FAILED],
    DocumentState.INDEXED: [],  # terminal success
    DocumentState.FAILED: [DocumentState.DISCOVERED, DocumentState.DEAD_LETTER],  # retry or dead-letter
    DocumentState.REQUIRES_REVIEW: [DocumentState.DISCOVERED, DocumentState.DEAD_LETTER],
    DocumentState.DEAD_LETTER: [],  # terminal failure
}


@dataclass
class StateTransition:
    doc_id: str
    from_state: Optional[str]
    to_state: str
    timestamp: str
    error_message: Optional[str] = None
    attempt: int = 1


class DocumentStateMachine:
    """Manages document processing states and logs all transitions to SQLite."""

    def __init__(self, db_path: str = "/Users/ashim/locus_rag/data/db/rag_state.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        return sqlite3.connect(str(self.db_path))

    def _init_db(self):
        conn = self._connect()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS state_machine_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id TEXT NOT NULL,
                from_state TEXT,
                to_state TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                error_message TEXT,
                attempt INTEGER DEFAULT 1
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS document_states (
                doc_id TEXT PRIMARY KEY,
                current_state TEXT NOT NULL,
                last_updated TEXT NOT NULL,
                attempt_count INTEGER DEFAULT 1,
                last_error TEXT
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_doc_states_current
            ON document_states(current_state)
        """)

        conn.commit()
        conn.close()

    def get_state(self, doc_id: str) -> Optional[DocumentState]:
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("SELECT current_state FROM document_states WHERE doc_id = ?", (doc_id,))
        row = cursor.fetchone()
        conn.close()
        if row is None:
            return None
        return DocumentState(row[0])

    def transition(
        self,
        doc_id: str,
        to_state: DocumentState,
        error_message: Optional[str] = None,
        force: bool = False,
    ) -> bool:
        """
        Transition a document to a new state.

        Validates against VALID_TRANSITIONS unless force=True.
        Logs the transition to SQLite.
        """
        current = self.get_state(doc_id)
        from_str = current.value if current else None
        to_str = to_state.value

        if current is not None and not force:
            allowed = VALID_TRANSITIONS.get(current, [])
            if to_state not in allowed:
                logger.error(
                    "Invalid state transition for %s: %s → %s (allowed: %s)",
                    doc_id, from_str, to_str, [s.value for s in allowed]
                )
                return False

        timestamp = datetime.now(timezone.utc).isoformat()
        conn = self._connect()
        cursor = conn.cursor()

        # Update or insert current state
        cursor.execute("""
            INSERT INTO document_states (doc_id, current_state, last_updated, attempt_count, last_error)
            VALUES (?, ?, ?, CASE WHEN ? = 'failed' THEN 1 ELSE 0 END, ?)
            ON CONFLICT(doc_id) DO UPDATE SET
                current_state = excluded.current_state,
                last_updated = excluded.last_updated,
                attempt_count = CASE WHEN ? = 'failed' THEN attempt_count + 1 ELSE attempt_count END,
                last_error = COALESCE(?, last_error)
        """, (doc_id, to_str, timestamp, to_str, error_message, to_str, error_message))

        # Log transition
        cursor.execute("""
            INSERT INTO state_machine_log (doc_id, from_state, to_state, timestamp, error_message)
            VALUES (?, ?, ?, ?, ?)
        """, (doc_id, from_str, to_str, timestamp, error_message))

        conn.commit()
        conn.close()

        logger.info("Document %s transitioned: %s → %s", doc_id, from_str or "NONE", to_str)
        return True

    def get_documents_in_state(self, state: DocumentState) -> List[str]:
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("SELECT doc_id FROM document_states WHERE current_state = ?", (state.value,))
        rows = cursor.fetchall()
        conn.close()
        return [r[0] for r in rows]

    def get_attempt_count(self, doc_id: str) -> int:
        """Return the persistent failed-attempt count for a document.

        Attempt count lives in ``document_states.attempt_count`` and is
        incremented by ``transition(... to_state=FAILED)`` across runs, so it
        survives process restarts. No schema change needed — column exists.
        """
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT attempt_count FROM document_states WHERE doc_id = ?",
            (doc_id,),
        )
        row = cursor.fetchone()
        conn.close()
        if row is None:
            return 0
        return int(row[0])

    def get_state_counts(self) -> Dict[str, int]:
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute("SELECT current_state, COUNT(*) FROM document_states GROUP BY current_state")
        rows = cursor.fetchall()
        conn.close()
        return dict(rows)
