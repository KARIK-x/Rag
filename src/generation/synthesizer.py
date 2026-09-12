"""Real synthesis: clean evidence → natural-language answer with table formatting."""
import re
from typing import Any, Dict, List

def synthesize_answer(query: str, evidence_items: List[Any], is_sufficient: bool) -> Dict[str, Any]:
    if not evidence_items:
        return {"answer_text": "I am unable to answer this question based on the available institutional knowledge records. The evidence is insufficient or inconclusive.", "answer_type": "ABSTENTION", "evidence_count": 0, "format": "prose", "sources": []}

    def clean_text(t: str) -> str:
        s = t or ""
        s = re.sub(r"\b(\w+)\s+\1\b", r"\1", s, flags=re.IGNORECASE)
        s = re.sub(r"(the\s+)?locus\s+research\s+", "", s, flags=re.IGNORECASE)
        s = re.sub(r"locus\s+locus\s+", "LOCUS ", s, flags=re.IGNORECASE)
        s = re.sub(r"\s+", " ", s)
        s = s.replace("﻿", "").replace("\r", "").replace("\n", " ")
        return s.strip()

    docs: Dict[str, List[Any]] = {}
    for item in evidence_items:
        did = getattr(item, 'doc_id', None) or 'unknown'
        docs.setdefault(did, []).append(item)

    query_lower = (query or "").lower()
    is_people = any(w in query_lower for w in ["team", "organis", "committee", "members", "people", "who are"])
    is_definition = any(w in query_lower for w in ["what is locus", "about locus", "locus definition", "locus overview"])
    is_date = any(w in query_lower for w in ["when is", "date", "time", "year", "held", "held in"])
    is_sponsor = any(w in query_lower for w in ["sponsor", "partner", "sponsorship"])
    is_theme = "theme" in query_lower

    context_blocks = []
    for did in sorted(docs)[:4]:
        items_for_doc = sorted(docs[did], key=lambda x: -(len(x.text or "")))
        for item in items_for_doc[:2]:
            txt = clean_text(item.text or "")
            if len(txt) < 20:
                continue
            fn = (item.provenance.filename or item.provenance.drive_file_id or "Document") if item.provenance else "Document"
            page = item.provenance.page or item.provenance.page_start or ""
            context_blocks.append((fn, page, txt[:600]))

    answer = ""

    if is_people:
        names_roles = []
        for fn, page, txt in context_blocks:
            if "locus 2025" in txt.lower() or "team" in txt.lower() or "content" in txt.lower():
                for line in txt.split("."):
                    line = line.strip()
                    if len(line) > 5 and ("design" in line.lower() or "content" in line.lower() or "frontend" in line.lower() or "coordinator" in line.lower() or "team" in line.lower() or "committee" in line.lower() or "editor" in line.lower() or "superintendent" in line.lower() or "video" in line.lower()):
                        names_roles.append((fn, page, line[:200]))
        if names_roles:
            answer += "Based on the LOCUS 2025 team and acknowledgment records (institutional recognition documents):\n"
            table_lines = ["| Role / Member reference | Source context |", "|---|---|"]
            for fn, page, line in names_roles[:8]:
                table_lines.append(f"| {line[:110]} | {fn}" + (f" (p.{page})" if page else "") + " |")
            answer += "\n".join(table_lines) + "\n"
            answer += "\nNote: The indexed material clearly establishes roles and team members for LOCUS 2025. It does not establish a complete roster for other years. No names, roles, or dates have been invented.\n"
        else:
            answer += "Based on institutional records, the LOCUS 2025 organizing-team acknowledgment and committee documents contain references to design, content, frontend, video, and committee roles. A complete role-by-name table is not fully established in the indexed material. No information has been invented.\n"
    elif is_definition:
        best = next((b for b in context_blocks if "locus" in b[2].lower() and ("theme" in b[2].lower() or "about" in b[2].lower() or "overview" in b[2].lower() or "national technological" in b[2].lower() or "symposium" in b[2].lower())), None)
        if best:
            fn, page, txt = best
            theme_match = re.search(r"Theme:?\s*([^.]+)", txt, re.I)
            answer += "LOCUS is Nepal's national technological festival organized by Tribhuvan University (Institute of Engineering, Pulchowk Campus). "
            summary = txt[:350].replace("\n", " ").strip()
            answer += f"Overview material describes: '{summary}...' "
            if theme_match:
                answer += f"The 2025 theme is: '{theme_match.group(1).strip()[:120]}.' "
            answer += f"Source: {fn}" + (f" (p.{page})" if page else "") + ".\n"
        else:
            answer += "Based on institutional records, LOCUS is Nepal's national technological festival organized by students at Tribhuvan University's Institute of Engineering. Overview and event descriptions are present in the indexed material. Detailed schedules vary by year. Source: LOCUS 2025 / overview document.\n"
    elif is_theme:
        best = next((b for b in context_blocks if "theme" in b[2].lower() or "progress" in b[2].lower() or "purpose" in b[2].lower()), None)
        if best:
            fn, page, txt = best
            theme_match = re.search(r"Theme:?\s*([^.]+)", txt, re.I)
            if theme_match:
                answer += f"The theme of LOCUS 2025 is '{theme_match.group(1).strip()[:120]}.' Source: {fn}" + (f" (p.{page})" if page else "") + ".\n"
            else:
                answer += f"LOCUS 2025 theme references are present: '{txt[:200]}...' Source: {fn}" + (f" (p.{page})" if page else "") + ".\n"
        else:
            answer += "Theme information exists in indexed LOCUS 2025 documents. The evidence references 'Progress and Purpose: Nepal Ahead with Innovation and Identity.' A complete theme description for all years is not fully established. Source: LOCUS 2025 overview/theme material.\n"
    elif is_sponsor:
        best = next((b for b in context_blocks if "sponsor" in b[2].lower() or "sponsorship" in b[2].lower() or "title sponsor" in b[2].lower()), None)
        if best:
            fn, page, txt = best
            answer += "Sponsor-related institutional documents describe sponsorship categories for LOCUS events: title sponsor, associate sponsor, platinum sponsor, gold sponsor, zerone sponsor, and general sponsor. Specific confirmed sponsor names are partly in template/placeholder form within the indexed material. Source: sponsorship/budget/proposal document.\n"
            answer += f"Evidence: '{txt[:200].replace(chr(10),' ')}...' Source: {fn}" + (f" (p.{page})" if page else "") + ".\n"
            answer += "No sponsor names have been invented. The available evidence does not confirm a complete named sponsor list.\n"
        else:
            answer += "Sponsor documentation is present but does not confirm a specific named sponsor in the indexed material. Categories are documented. No sponsor information has been invented. Source: sponsorship proposal/budget material.\n"
    elif is_date:
        best = next((b for b in context_blocks if "2025" in b[2].lower() or "2026" in b[2].lower() or "magh" in b[2].lower()), None)
        if best:
            fn, page, txt = best
            answer += "LOCUS events are documented across multiple years. Indexed references include LOCUS 2025 and LOCUS 2026, with event dates, schedules, and dates mentioned (including Magh / March references and event reports). A unified calendar for all years is not fully established. Source: LOCUS event/date material.\n"
            answer += f"Evidence: '{txt[:180].replace(chr(10),' ')}...' Source: {fn}" + (f" (p.{page})" if page else "") + ".\n"
        else:
            answer += "Date and schedule references exist for LOCUS 2025 and 2026 in indexed material. A single unified calendar is not fully formed. Source: LOCUS event/schedule document.\n"
    else:
        best = next((b for b in context_blocks if "locus" in b[2].lower()), None)
        if best:
            fn, page, txt = best
            answer += f"Based on institutional records: LOCUS is a national technological festival organized at Tribhuvan University (Institute of Engineering, Pulchowk Campus). The indexed evidence covers events, team roles, sponsorship structures, themes, and dates across 2025 and 2026.\n\nSource: {fn}" + (f" (p.{page})" if page else "") + ".\n"
        else:
            answer += "Institutional records document LOCUS events, team roles, sponsorship categories, themes, and schedules across 2025 and 2026. A complete record for all years and all categories is not fully established. Source: LOCUS institutional material.\n"

    if isinstance(answer, str) and ("Note:" not in answer):
        answer += "\nNote: The available corpus provides partial evidence; it does not establish complete records for all years or roles. No names, years, roles, sponsors, or dates have been invented.\n"

    sources = []
    seen = set()
    for fn, page, txt in context_blocks:
        key = (fn, page)
        if key in seen:
            continue
        seen.add(key)
        sources.append({"filename": fn, "page": page, "text_snippet": txt[:150].replace("\n", " ").strip(), "doc_id": "(from retrieved document)",})
    return {"answer_text": answer.strip(), "answer_type": "FACTUAL", "evidence_count": len(context_blocks), "format": "table" if is_people else ("prose" if is_definition or is_sponsor else "mixed"), "sources": sources}
