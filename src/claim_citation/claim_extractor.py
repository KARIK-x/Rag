"""Claim extraction that treats sentences as claims, not fragments."""
import re
from typing import List, Dict, Any

class ClaimExtractor:
    def extract(self, answer_text: str) -> List[Dict[str, Any]]:
        claims = []
        # Split into sentences; treat each sentence (not each phrase split by commas) as a claim
        sentences = re.split(r"(?<=[.!?])\s+", answer_text)
        for s in sentences:
            s = s.strip()
            if len(s) < 15:  # ignore very short fragments (likely headings/bullet fragments)
                continue
            # Skip pure headings like "LOCUS 2025:" followed only by bullet points
            # But keep natural-language sentences
            clean = re.sub(r"\[[^\]]+\]", "", s).strip()
            # Avoid splitting by comma/and for basic claim extraction; split only by sentence
            # Split compound sentences by ';' if present, but not by commas
            parts = [p.strip() for p in clean.split(";") if p.strip()]
            # If no semicolon split produces more than 4 parts, keep original sentence
            if len(parts) > 4:
                parts = [clean]
            for part in parts:
                # Filter out bullet markers at start and pure headings
                part = re.sub(r"^•\s*", "", part)
                part = re.sub(r"^\s*[-–—]\s*", "", part)
                # Skip pure labels (e.g., just "Theme:", "Event Title", "Introduction")
                if re.fullmatch(r"[A-Z][\w\s:]*", part) and len(part) < 30:
                    continue
                # Skip very short pieces that are just headings
                words = [w for w in part.split() if w.lower() not in ("and","with","which","where","of","the","a","an","to","in","for","as","on","at","from")]
                if len(words) < 3 and len(part.split()) < 6:
                    # Could be heading; skip unless it clearly states a fact (contains year/name/number)
                    if not (any(ch.isdigit() for ch in part) or "locus" in part.lower() or "sponsor" in part.lower() or "team" in part.lower() or "theme" in part.lower()):
                        continue
                # Deduplicate very similar claims
                key = part.lower()[:100]
                # Check for duplicates in current list
                if any(c.get("key") == key for c in claims):
                    continue
                claims.append({
                    "claim_text": part,
                    "raw_text": s,
                    "verified": False,
                    "evidence_ids": [],
                    "citation_locator": None,
                    "status": "PENDING",
                    "key": key,
                })
        return claims
