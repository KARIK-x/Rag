"""Atomic claim extraction — splits compound sentences into individual factual assertions."""
import re
from typing import List, Dict, Any

class ClaimExtractor:
    def extract(self, answer_text: str) -> List[Dict[str, Any]]:
        claims = []
        # Split on sentence terminators
        sentences = re.split(r"(?<=[.!?])\s+", answer_text)
        for s in sentences:
            s = s.strip()
            if len(s) < 10:
                continue
            # Split compound sentences by common joiners into atomic claims
            parts = re.split(r"\s+and\s+|\s+with\s+|\s+which\s+|\s+where\s+|,\s*", s)
            for part in parts:
                part = part.strip()
                # Clean citation markers
                clean = re.sub(r"\[[^\]]+\]", "", part).strip()
                if len(clean) < 8:
                    continue
                # Remove duplicate whitespace
                clean = re.sub(r"\s+", " ", clean)
                claims.append({
                    "claim_text": clean,
                    "raw_text": s,
                    "verified": False,
                    "evidence_ids": [],
                    "citation_locator": None,
                    "status": "PENDING",
                })
        # Deduplicate very similar claims
        seen = set()
        deduped = []
        for c in claims:
            key = c["claim_text"].lower()[:80]
            if key not in seen:
                seen.add(key)
                deduped.append(c)
        return deduped
