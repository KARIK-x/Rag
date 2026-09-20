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

        # Build provenance from evidence (preserve for sources display)
        provenance_records = []
        for item in evidence.items[:5]:
            provenance_records.append({
                "drive_file_id": item.provenance.drive_file_id,
                "filename": item.provenance.filename,
                "folder_path": item.provenance.folder_path,
                "page": item.provenance.page,
                "row": item.provenance.row_start,
                "chunk_id": item.chunk_id,
                "source_view_link": item.provenance.source_view_link,
            })

        # Synthesize answer text from evidence items — natural language, not chunk dump
        from src.generation.synthesizer import synthesize as synthesize_answer
        synth = synthesize_answer(query=evidence.query or "", evidence_items=evidence.items, is_sufficient=verification.confidence_level != "ABSTAIN" and evidence.is_sufficient)
        synthesized_text = synth.get("answer_text") or synth.get("text", "")
        # Fallback: if synthesis returns empty due to intent mismatch, use bounded quick synthesis
        if not synthesized_text or len(str(synthesized_text).strip()) < 10:
            from src.generation.synthesizer import quick_synth
            synthesized_text = quick_synth(query=evidence.query or "", evidence_items=evidence.items)
        # Preserve grounded citations in answer: add numbered refs matching provenance
        citation_refs = ""
        for idx, item in enumerate(evidence.items[:5], 1):
            fn = (item.provenance.filename or item.provenance.drive_file_id or "source") if item.provenance else "source"
            citation_refs += f" [{idx}:{fn}]"
        if synthesized_text and citation_refs and "[" not in synthesized_text:
            synthesized_text = synthesized_text.rstrip(".") + citation_refs + "."

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
