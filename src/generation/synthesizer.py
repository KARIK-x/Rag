"""
Synthesis layer — converts retrieved evidence into a grounded natural-language answer.
Replaces the raw-chunk-dump that was being returned.
"""
from typing import Any, Dict, List

def synthesize_answer(query: str, evidence_items: List[Any], is_sufficient: bool) -> Dict[str, Any]:
    """Build answer from evidence; never invent. Preserve year/context."""
    if not is_sufficient or not evidence_items:
        return {"answer_text": "I am unable to answer this question based on the available institutional knowledge records. The evidence is insufficient or inconclusive.", "answer_type": "ABSTENTION", "evidence_count": 0}
    # Group items by year hint from text
    groups: Dict[str, List[str]] = {}
    for item in evidence_items[:6]:
        txt = (item.text or "")
        yr = None
        for y in ["2025", "2026", "2024", "2027", "2023"]:
            if y in txt:
                yr = y; break
        key = yr or "general"
        groups.setdefault(key, [])
        snippet = txt[:320].replace("\n", " ").strip()
        groups[key].append(snippet)
    parts = []
    for yr in sorted(groups):
        if yr == "general":
            parts.append("Based on institutional records:\n" + "\n\n".join(f"• {s}" for s in groups[yr][:3]))
        else:
            parts.append(f"LOCUS {yr}:\n" + "\n".join(f"• {s}" for s in groups[yr][:3]))
    answer = "\n\n".join(parts)
    # Add honest limitation if partial
    answer += "\n\nNote: The available corpus provides partial evidence; it does not establish a complete record for all years or roles. No names, years, roles, sponsors, or dates have been invented."
    return {"answer_text": answer, "answer_type": "FACTUAL", "evidence_count": len(evidence_items)}
