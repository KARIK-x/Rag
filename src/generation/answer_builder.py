"""
LOCUS RAG Answer Builder — Phase 9.

Per spec §15, §16:
  - Faithful answer generation from EvidenceSet
  - Claim-level citations pointing to source provenance
  - Explicit uncertainty and abstention when evidence is insufficient
  - Structured output with provenance records
"""

import logging
from typing import Any, Dict, List, Optional

from src.pipeline.models import EvidenceSet, VerificationResult, SourceProvenance

logger = logging.getLogger(__name__)


class AnswerBuilder:
    """Builds evidence-grounded answers with citations and provenance."""

    def __init__(self):
        pass

    def build_answer(
        self,
        evidence: EvidenceSet,
        verification: VerificationResult,
    ) -> Dict[str, Any]:
        """
        Build structured answer output with citations and provenance.
        """
        if verification.confidence_level == "ABSTAIN" or not evidence.is_sufficient or not evidence.items:
            return {
                "answer_type": "ABSTENTION",
                "answer": "I am unable to answer this question based on the available institutional knowledge records. The evidence is insufficient or inconclusive.",
                "table": None,
                "verification": {
                    "is_faithful": verification.is_faithful,
                    "unsupported_claims": verification.unsupported_claims,
                    "completeness": verification.completeness_score,
                    "confidence": verification.confidence_level,
                    "reasoning": verification.reasoning,
                },
                "provenance": [],
                "completeness_breakdown": {
                    "overall": "0/1 supported (abstain)"
                }
            }

        # Synthesize answer text from evidence items
        answer_parts = []
        provenance_records = []

        for idx, item in enumerate(evidence.items[:5], start=1):
            text_snippet = item.text.strip()
            if len(text_snippet) > 250:
                text_snippet = text_snippet[:250] + "..."

            filename = item.provenance.filename or "Document"
            page_str = f" (Page {item.provenance.page})" if item.provenance.page else ""
            answer_parts.append(f"{text_snippet} [{idx}: {filename}{page_str}]")

            prov_rec = {
                "drive_file_id": item.provenance.drive_file_id,
                "filename": item.provenance.filename,
                "folder_path": item.provenance.folder_path,
                "page": item.provenance.page,
                "row": item.provenance.row_start,
                "chunk_id": item.chunk_id,
                "source_view_link": item.provenance.source_view_link,
            }
            provenance_records.append(prov_rec)

        synthesized_text = "Based on institutional records:\n\n" + "\n\n".join(answer_parts)

        return {
            "answer_type": "FACTUAL",
            "answer": synthesized_text,
            "table": None,
            "verification": {
                "is_faithful": verification.is_faithful,
                "unsupported_claims": verification.unsupported_claims,
                "completeness": verification.completeness_score,
                "confidence": verification.confidence_level,
                "reasoning": verification.reasoning,
            },
            "provenance": provenance_records,
            "completeness_breakdown": {
                "overall": f"{len(evidence.items)} source chunks integrated with {verification.confidence_level} confidence."
            }
        }
