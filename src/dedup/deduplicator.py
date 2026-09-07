"""
LOCUS RAG deduplication.

Per spec §24:
  Deduplicate using multiple signals:
    1. Drive file ID
    2. Content hash
    3. Normalized content hash
    4. Near-duplicate similarity
    5. Metadata relationships

Maintain canonical/alias relationships. Never destroy provenance.
Never silently overwrite a previous version.
A duplicate may still represent a later revision / superseded version /
draft / renamed copy.
"""

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from src.normalization.text import normalize_text

logger = logging.getLogger(__name__)


@dataclass
class DedupCandidate:
    """A document considered for dedup."""
    doc_id: str
    drive_file_id: str
    filename: str
    content_hash: Optional[str]
    normalized_hash: Optional[str]
    size_bytes: Optional[int]
    modified_time: Optional[str]
    text: str = ""

    @classmethod
    def from_extraction(
        cls,
        result_dict: Dict[str, Any],
    ) -> "DedupCandidate":
        prov = result_dict.get("provenance", {})
        full_text = result_dict.get("full_text", "")
        normalized = normalize_text(full_text, lower=True)
        return cls(
            doc_id=result_dict.get("doc_id", "?"),
            drive_file_id=prov.get("drive_file_id", "?"),
            filename=result_dict.get("metadata", {}).get("title", "") or prov.get("filename", "?"),
            content_hash=hashlib.sha256(full_text.encode("utf-8")).hexdigest() if full_text else None,
            normalized_hash=hashlib.sha256(normalized.encode("utf-8")).hexdigest() if normalized else None,
            size_bytes=len(full_text.encode("utf-8")),
            modified_time=result_dict.get("metadata", {}).get("modified_time"),
            text=full_text,
        )


@dataclass
class DedupCluster:
    """A cluster of duplicate/near-duplicate documents."""
    cluster_id: str
    canonical_id: Optional[str]          # chosen canonical
    member_ids: List[str]                # doc_ids
    member_drive_ids: List[str]
    relation: str  # exact_duplicate | near_duplicate | different_revision
    similarity: float                    # 1.0 = exact
    provenance_map: Dict[str, Any] = field(default_factory=dict)  # member → provenance

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "canonical_id": self.canonical_id,
            "member_ids": self.member_ids,
            "member_drive_ids": self.member_drive_ids,
            "relation": self.relation,
            "similarity": self.similarity,
            "provenance_map": self.provenance_map,
        }


class Deduplicator:
    """Detect duplicate / near-duplicate / revision documents."""

    def __init__(self, similarity_threshold: float = 0.60):
        self.threshold = similarity_threshold

    def cluster(
        self,
        candidates: List[DedupCandidate],
    ) -> List[DedupCluster]:
        """
        Cluster candidates into duplicate groups using:
          - exact content hash
          - normalized hash
          - near-duplicate similarity (fallback)
        """
        clusters: List[DedupCluster] = []

        # Build hash → candidate map
        by_hash: Dict[str, List[DedupCandidate]] = {}
        for c in candidates:
            key = c.normalized_hash or c.content_hash
            if key:
                by_hash.setdefault(key, []).append(c)

        # Exact/normalized-duplicate clusters
        processed: Set[str] = set()
        for hash_key, group in by_hash.items():
            if len(group) <= 1:
                continue
            clusters.append(self._make_cluster(group, "exact_duplicate", 1.0))
            for c in group:
                processed.add(c.doc_id)

        # Near-duplicate: compare candidates that share no exact hash
        seen_pairs: Set[Tuple[str, str]] = set()

        for i, c1 in enumerate(candidates):
            if c1.doc_id in processed:
                continue
            for c2 in candidates[i + 1:]:
                if c2.doc_id in processed:
                    continue
                if not c1.text or not c2.text:
                    continue
                pair = tuple(sorted([c1.doc_id, c2.doc_id]))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                sim = self._similarity(c1.text, c2.text)
                if sim >= self.threshold:
                    cluster = self._make_cluster([c1, c2], "near_duplicate", sim)
                    clusters.append(cluster)
                    processed.add(c1.doc_id)
                    processed.add(c2.doc_id)
                    break

        return clusters

    def _make_cluster(
        self,
        group: List[DedupCandidate],
        relation: str,
        similarity: float,
    ) -> DedupCluster:
        """Build a cluster, choosing canonical by modified_time recency."""
        cluster_id = hashlib.sha256(
            ",".join(sorted(c.doc_id for c in group)).encode()
        ).hexdigest()[:12]

        # Canonical: most recently modified (NOT necessarily most authoritative —
        # authority is handled separately in Phase 4 classification).
        canonical = max(
            group,
            key=lambda c: c.modified_time or "",
        )
        prov_map = {
            c.doc_id: {
                "drive_file_id": c.drive_file_id,
                "filename": c.filename,
                "size_bytes": c.size_bytes,
                "modified_time": c.modified_time,
            }
            for c in group
        }

        return DedupCluster(
            cluster_id=cluster_id,
            canonical_id=canonical.doc_id,
            member_ids=[c.doc_id for c in group],
            member_drive_ids=[c.drive_file_id for c in group],
            relation=relation,
            similarity=similarity,
            provenance_map=prov_map,
        )

    # ─── Similarity helpers ────────────────────────────────────────────────

    @staticmethod
    def _similarity(a: str, b: str) -> float:
        """Normalized n-gram Jaccard similarity (fast, memory-safe)."""
        if not a or not b:
            return 0.0
        na = a.lower()
        nb = b.lower()
        if na == nb:
            return 1.0

        def ngrams(s: str, n: int = 4):
            return {s[i:i+n] for i in range(max(1, len(s) - n + 1))}

        ga = ngrams(na)
        gb = ngrams(nb)
        if not ga or not gb:
            return 0.0
        inter = len(ga & gb)
        union = len(ga | gb)
        return inter / union

# ─── Persistent dedup index (canonical/alias relationships) ─────────────────

class DedupIndex:
    """Persist dedup clusters to SQLite for canonical/alias lookups."""

    def __init__(self, db_path: str = "/Users/ashim/locus_rag/data/db/rag_state.db"):
        self.db_path = db_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        import sqlite3
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        import sqlite3
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS dedup_clusters (
                cluster_id TEXT PRIMARY KEY,
                canonical_id TEXT,
                relation TEXT,
                similarity REAL,
                members TEXT,        -- JSON list of doc_ids
                drive_ids TEXT,      -- JSON list
                provenance TEXT,     -- JSON map
                created_at TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS canonical_aliases (
                doc_id TEXT PRIMARY KEY,
                canonical_id TEXT NOT NULL,
                cluster_id TEXT
            )
        """)
        conn.commit()
        conn.close()

    def save_clusters(self, clusters: List[DedupCluster]) -> int:
        import sqlite3
        from datetime import datetime, timezone
        conn = self._connect()
        cur = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()
        count = 0
        for cl in clusters:
            cur.execute("""
                INSERT OR REPLACE INTO dedup_clusters
                (cluster_id, canonical_id, relation, similarity, members,
                 drive_ids, provenance, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                cl.cluster_id, cl.canonical_id, cl.relation, cl.similarity,
                json.dumps(cl.member_ids), json.dumps(cl.member_drive_ids),
                json.dumps(cl.provenance_map), now,
            ))
            for doc_id in cl.member_ids:
                cur.execute("""
                    INSERT OR REPLACE INTO canonical_aliases (doc_id, canonical_id, cluster_id)
                    VALUES (?, ?, ?)
                """, (doc_id, cl.canonical_id, cl.cluster_id))
            count += 1
        conn.commit()
        conn.close()
        return count

    def canonical_for(self, doc_id: str) -> Optional[str]:
        import sqlite3
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT canonical_id FROM canonical_aliases WHERE doc_id = ?", (doc_id,))
        row = cur.fetchone()
        conn.close()
        return row[0] if row else None

    def aliases_for(self, canonical_id: str) -> List[str]:
        import sqlite3
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT doc_id FROM canonical_aliases WHERE canonical_id = ?", (canonical_id,))
        rows = cur.fetchall()
        conn.close()
        return [r[0] for r in rows]


# ─── Persistent dedup index (canonical/alias relationships) ─────────────────

class DedupIndex:
    """Persist dedup clusters to SQLite for canonical/alias lookups."""

    def __init__(self, db_path: str = "/Users/ashim/locus_rag/data/db/rag_state.db"):
        self.db_path = db_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        import sqlite3
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        import sqlite3
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS dedup_clusters (
                cluster_id TEXT PRIMARY KEY,
                canonical_id TEXT,
                relation TEXT,
                similarity REAL,
                members TEXT,        -- JSON list of doc_ids
                drive_ids TEXT,      -- JSON list
                provenance TEXT,     -- JSON map
                created_at TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS canonical_aliases (
                doc_id TEXT PRIMARY KEY,
                canonical_id TEXT NOT NULL,
                cluster_id TEXT
            )
        """)
        conn.commit()
        conn.close()

    def save_clusters(self, clusters: List[DedupCluster]) -> int:
        import sqlite3
        from datetime import datetime, timezone
        conn = self._connect()
        cur = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()
        count = 0
        for cl in clusters:
            cur.execute("""
                INSERT OR REPLACE INTO dedup_clusters
                (cluster_id, canonical_id, relation, similarity, members,
                 drive_ids, provenance, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                cl.cluster_id, cl.canonical_id, cl.relation, cl.similarity,
                json.dumps(cl.member_ids), json.dumps(cl.member_drive_ids),
                json.dumps(cl.provenance_map), now,
            ))
            for doc_id in cl.member_ids:
                cur.execute("""
                    INSERT OR REPLACE INTO canonical_aliases (doc_id, canonical_id, cluster_id)
                    VALUES (?, ?, ?)
                """, (doc_id, cl.canonical_id, cl.cluster_id))
            count += 1
        conn.commit()
        conn.close()
        return count

    def canonical_for(self, doc_id: str) -> Optional[str]:
        import sqlite3
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT canonical_id FROM canonical_aliases WHERE doc_id = ?", (doc_id,))
        row = cur.fetchone()
        conn.close()
        return row[0] if row else None

    def aliases_for(self, canonical_id: str) -> List[str]:
        import sqlite3
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT doc_id FROM canonical_aliases WHERE canonical_id = ?", (canonical_id,))
        rows = cur.fetchall()
        conn.close()
        return [r[0] for r in rows]
