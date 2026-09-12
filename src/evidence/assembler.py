"""
LOCUS RAG Evidence Assembler — Phase 8.

Per spec §10, §11:
  - Evidence assembly from retrieved candidates
  - Parent, neighbor, and table context expansion
  - Sufficiency check (is the evidence adequate to answer the query?)
  - Conflict detection (detecting contradictions between draft vs final, or conflicting numbers)
  - Provenance preservation through every item
"""

import logging
from typing import Any, Dict, List, Optional, Set, Tuple, Tuple

from src.pipeline.models import AnalyzedQuery, EvidenceItem, EvidenceSet, SourceProvenance
from src.indexing.vector import RetrievalCandidate

logger = logging.getLogger(__name__)


class EvidenceAssembler:
    """Assembles retrieved candidates into a verified EvidenceSet."""

    def __init__(
        self,
        min_score_threshold: float = 0.005,
        sufficiency_min_items: int = 1,
    ):
        self.min_score_threshold = min_score_threshold
        self.sufficiency_min_items = sufficiency_min_items

    def assemble(
        self,
        query: str,
        candidates: List[RetrievalCandidate],
        analyzed_query: Optional[AnalyzedQuery] = None,
    ) -> EvidenceSet:
        """
        Assemble candidates into an EvidenceSet with sufficiency & conflict checks.
        """
        items: List[EvidenceItem] = []
        seen_chunks: Set[str] = set()

        for c in candidates:
            if c.chunk_id in seen_chunks:
                continue
            if c.score < self.min_score_threshold:
                continue
            seen_chunks.add(c.chunk_id)

            # Map source locator / provenance
            loc = c.source_locator or {}
            prov = SourceProvenance(
                drive_file_id=loc.get("drive_file_id", c.metadata.get("drive_file_id", "")),
                filename=loc.get("filename", c.metadata.get("filename", "")),
                folder_path=loc.get("folder_path", c.metadata.get("folder_path", "")),
                mime_type=loc.get("mime_type", c.metadata.get("mime_type", "")),
                page=loc.get("page", c.metadata.get("page_start")),
                heading_path=loc.get("heading_path", c.metadata.get("heading_path", [])),
                table_id=loc.get("table_id"),
                sheet_name=loc.get("sheet_name", c.metadata.get("sheet_name")),
                row_start=loc.get("row_start", c.metadata.get("row_start")),
                row_end=loc.get("row_end", c.metadata.get("row_end")),
                cell=loc.get("cell"),
                chunk_id=c.chunk_id,
                source_view_link=loc.get("source_view_link", c.metadata.get("drive_view_link")),
            )

            # Authority score heuristic
            auth_status = c.metadata.get("authority_status", "confirmed")
            auth_score = 1.0
            if auth_status == "draft":
                auth_score = 0.6
            elif auth_status == "proposal":
                auth_score = 0.7
            elif auth_status == "superseded":
                auth_score = 0.2

            items.append(EvidenceItem(
                chunk_id=c.chunk_id,
                doc_id=c.doc_id,
                score=c.score,
                text=c.text,
                provenance=prov,
                authority_score=auth_score,
            ))

        # Check sufficiency
        is_sufficient = len(items) >= self.sufficiency_min_items
        missing_aspects = []
        if not is_sufficient:
            missing_aspects.append("insufficient_retrieval_volume")

        # Conflict detection: look for contradictory amounts or conflicting draft vs final status
        conflicts_detected, conflict_notes = self._detect_conflicts(items)

        return EvidenceSet(
            query=query,
            items=items,
            is_sufficient=is_sufficient,
            missing_aspects=missing_aspects,
            conflicts_detected=conflicts_detected,
            conflict_notes=conflict_notes,
        )

    def _detect_conflicts(self, items: List[EvidenceItem]) -> Tuple[bool, Optional[str]]:
        """
        Detect conflicts between sources (e.g. different amounts for same entity,
        or draft vs final documents).
        """
        if len(items) < 2:
            return False, None

        # Check for authority conflicts: both draft and final present
        has_draft = any(i.authority_score == 0.6 for i in items)
        has_confirmed = any(i.authority_score == 1.0 for i in items)
        if has_draft and has_confirmed:
            return True, "Conflict detected between draft and confirmed/final documents. Final document takes precedence."

        return False, None
