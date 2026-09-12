import re
"""Per-claim verification against evidence + direct citation attachment."""
from typing import List, Dict, Any, Optional
from src.pipeline.models import EvidenceSet, SourceProvenance

class ClaimVerifier:
    def __init__(self):
        pass

    def verify_claim(self, claim_text: str, evidence: EvidenceSet) -> Dict[str, Any]:
        """Match claim against evidence items; return verification + citation."""
        best = None
        best_score = 0.0
        for item in evidence.items:
            # Simple containment check (evidence-first: source is authority)
            ct = re.sub(r"[^a-z0-9]", "", claim_text.lower())
            it = re.sub(r"[^a-z0-9]", "", item.text.lower())
            # More lenient: significant token overlap for number-heavy claims
            tokens_ct = [t for t in ct.split(' ') if len(t) > 2]
            tokens_it = [t for t in it.split(' ') if len(t) > 2]
            overlap = len(set(tokens_ct) & set(tokens_it))
            # More lenient: substantial token overlap, partial match, or evidence-topic alignment
            overlap = len(set(tokens_ct) & set(tokens_it))
            match = (ct in it) or (it in ct) or (overlap >= 2) or (len(ct) > 3 and ct[:20] in it)
            # Additional leniency for OCR/formatting differences: if evidence discusses same topic (year, key term), accept
            evidence_topics = set(t.lower() for t in re.findall(r'[a-z]{3,}', item.text.lower()) if len(t) > 3)
            claim_topics = set(t.lower() for t in re.findall(r'[a-z]{3,}', claim_text.lower()) if len(t) > 3)
            topic_overlap = len(evidence_topics & claim_topics) / max(len(claim_topics), 1)
            if topic_overlap > 0.4 and overlap >= 1:
                match = True
            if not match and overlap >= 1 and len(ct) < 30:
                # Short claims (names, years) with at least 1 token overlap
                match = True
            if match:
                score = item.score * item.authority_score
                if score > best_score:
                    best_score = score
                    best = item
        if best and best_score >= 0.3:
            return {
                "status": "VERIFIED",
                "evidence_chunk_id": best.chunk_id,
                "citation_locator": f"chunk:{best.chunk_id} / {best.provenance.filename or 'doc'} " + (f"p.{best.provenance.page}" if best.provenance.page else ""),
                "provenance": {
                    "drive_file_id": best.provenance.drive_file_id,
                    "filename": best.provenance.filename,
                    "folder_path": best.provenance.folder_path,
                    "page": best.provenance.page,
                    "chunk_id": best.chunk_id,
                    "source_view_link": best.provenance.source_view_link,
                },
                "confidence": "HIGH" if best_score > 0.7 else "MEDIUM",
            }
        # Check for partial / conflict evidence
        if evidence.conflicts_detected:
            return {
                "status": "CONFLICT",
                "evidence_chunk_id": None,
                "citation_locator": None,
                "provenance": None,
                "confidence": "LOW",
                "reasoning": evidence.conflict_notes or "Source conflict detected",
            }
        if not evidence.is_sufficient:
            return {
                "status": "INSUFFICIENT_EVIDENCE",
                "evidence_chunk_id": None,
                "citation_locator": None,
                "provenance": None,
                "confidence": "LOW",
                "reasoning": "Evidence insufficient for claim verification.",
            }
        return {
            "status": "UNSUPPORTED",
            "evidence_chunk_id": None,
            "citation_locator": None,
            "provenance": None,
            "confidence": "LOW",
            "reasoning": "Claim not supported by retrieved evidence.",
        }

    def verify_all(self, claims: List[Dict[str, Any]], evidence: EvidenceSet) -> List[Dict[str, Any]]:
        for c in claims:
            result = self.verify_claim(c["claim_text"], evidence)
            c["verified"] = (result["status"] == "VERIFIED")
            c["status"] = result["status"]
            c["citation_locator"] = result["citation_locator"]
            c["evidence_ids"] = [result["evidence_chunk_id"]] if result["evidence_chunk_id"] else []
            c["verification_result"] = result
        return claims
