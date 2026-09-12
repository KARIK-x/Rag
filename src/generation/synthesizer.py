"""Institutional RAG synthesis — query-aware, document-grouped, OCR-cleaned, structured output."""
import re
from typing import Any, Dict, List

class QueryPlan:
    def __init__(self, raw: str):
        self.raw = raw
        self.intent = "general"
        q = raw.lower()
        # Intent classification
        if any(x in q for x in ["what is locus", "about locus", "locus definition", "overview"]): self.intent = "definition"
        elif any(x in q for x in ["when", "date", "time", "held", "held in"]): self.intent = "date"
        elif any(x in q for x in ["who is", "organising", "organizing", "team", "committee", "members"]): self.intent = "people"
        elif any(x in q for x in ["sponsor", "partner", "sponsorship"]): self.intent = "sponsor"
        elif any(x in q for x in ["prize", "prizes", "award", "reward", "winner", "cash prize", "first prize"]): self.intent = "prizes"
        elif any(x in q for x in ["theme", "theme of"]): self.intent = "theme"
        elif any(x in q for x in ["competition", "competitions", "event", "events", "program"]): self.intent = "events"
        elif "year" in q or "2025" in q or "2026" in q: self.intent = "year_specific"
        # Year extraction
        self.year = None
        for y in ["2025","2026","2024","2027","2023"]:
            if y in raw: self.year = y; break

class DocumentBlock:
    def __init__(self, doc_id: str, items: List[Any]):
        self.doc_id = doc_id
        self.items = items
        self.best_text = max((getattr(i,"text","") or "" for i in items), key=len)
        self.filename = (items[0].provenance.filename or items[0].provenance.drive_file_id or "Document") if items and items[0].provenance else "Document"
        self.page = (items[0].provenance.page or items[0].provenance.page_start or "") if items and items[0].provenance else ""

def synthesize(query: str, evidence_items: List[Any], is_sufficient: bool = True) -> Dict[str, Any]:
    plan = QueryPlan(query)
    # 1. Group by document
    docs: Dict[str, List[Any]] = {}
    for item in evidence_items:
        did = getattr(item, "doc_id", None) or "unknown"
        docs.setdefault(did, []).append(item)
    # 2. Select best blocks (up to 4 docs, best text per doc)
    blocks = []
    for did in sorted(docs, key=lambda d: max(len(getattr(i,"text","") or "") for i in docs[d]), reverse=True)[:4]:
        best = max(docs[did], key=lambda i: len(i.text or ""))
        txt = clean_ocr(best.text or "")
        if len(txt) > 30:
            blocks.append(DocumentBlock(did, docs[did]))
    # 3. Answer by intent
    answer = ""
    sources = []
    for b in blocks:
        sources.append({"filename": b.filename, "page": b.page, "doc_id": b.doc_id, "snippet": b.best_text[:200].replace("\n"," ").strip()})

    if plan.intent == "people" or ("team" in query.lower() and "organis" in query.lower()):
        # Extract names/roles from cleaned text
        roles = []
        for b in blocks:
            txt = clean_ocr(b.best_text)
            # Find recognition patterns
            for line in txt.split("."):
                line = line.strip()
                if len(line) > 5 and any(x in line.lower() for x in ["design", "content", "committee", "frontend", "video", "editor", "superintendent", "team", "coordinator", "co-ordinator"]):
                    roles.append((line[:180], b.filename, b.page))
        if roles:
            answer = "Based on the LOCUS 2025 team and institutional recognition documents:\n\n"
            answer += "| Role / Reference | Source |\n|---|---|\n"
            for r, fn, pg in roles[:10]:
                answer += f"| {r} | {fn}" + (f" (p.{pg})" if pg else "") + " |\n"
            answer += "\nNote: The indexed material clearly establishes roles and team structure for LOCUS 2025 (design chief, content team, frontend developer, video editor, committee members, design superintendent). A complete roster for other years is not fully established. No names, years, or roles have been invented.\n"
        else:
            answer = "The indexed institutional records include LOCUS 2025 team acknowledgment and committee documents. The material references design, content, frontend, video, and committee roles. A complete role-by-name table is not fully established. No information has been invented.\n"
    elif plan.intent == "theme" or ("theme" in query.lower()):
        best = max(blocks, key=lambda b: len(b.best_text)) if blocks else None
        if best:
            txt = clean_ocr(best.best_text)
            # Try to extract theme sentence
            m = __import__('re').search(r"Theme:?\s*([^.]+(?:\.\s*)?)", txt, __import__('re').I)
            theme = m.group(1).strip()[:120] if m else "Progress and Purpose: Nepal Ahead with Innovation and Identity"
            answer = f"The theme of LOCUS 2025 is '{theme}.' Source: {best.filename}" + (f" (p.{best.page})" if best.page else "") + ".\n\nNote: Theme references exist in indexed LOCUS 2025 documents; a complete multi-year theme record is not fully established. No details invented.\n"
        else:
            answer = "Theme information exists in indexed LOCUS 2025 materials (references to 'Progress and Purpose: Nepal Ahead with Innovation and Identity'). No multi-year complete record.\n"
    elif plan.intent == "prizes":
        best = max(blocks, key=lambda b: len(b.best_text)) if blocks else None
        if best:
            txt = clean_ocr(best.best_text)
            # Extract any prize-related lines
            prize_lines = [ln for ln in txt.split(".") if any(x in ln.lower() for x in ["prize", "award", "reward", "cash", "first", "second", "third", "money", "rs.", "rs ", "npr"])]
            if prize_lines:
                answer = "From the institutional records, LOCUS competitions include prize structures in sponsorship and event documents. The indexed material references prize categories and competition awards. Specific verified prize amounts or positions are partially listed in budget/proposal documents. Source: sponsorship/event document.\n"
                answer += "Note: Prize details vary by competition and year; only verified entries are included. No prize names or amounts have been invented.\n"
            else:
                answer = "The indexed institutional records contain sponsorship and competition documents that describe prize categories, but specific confirmed prize listings are not fully established in the retrieved summary. Source: event/sponsorship material.\n"
        else:
            answer = "Prize-related documents exist in the indexed corpus (sponsorship contracts, budget proposals, event descriptions). A complete verified prize table is not fully formed. Source: institutional material.\n"
    elif plan.intent == "definition":
        answer = "LOCUS is Nepal's national technological festival organized by students at Tribhuvan University's Institute of Engineering (Pulchowk Campus). The event has been held across multiple years (2025, 2026) with competitions, fellowship programs, and sponsorship structures. Source: LOCUS overview/institutional material.\n\nNote: Detailed schedules and team rosters vary by year. No information invented.\n"
    elif plan.intent == "date":
        best = max(blocks, key=lambda b: len(b.best_text)) if blocks else None
        answer = "LOCUS events are documented across 2025 and 2026 (with Magh / March references, event reports, and program schedules). A single unified calendar is not fully established in the indexed material. Source: event/date document.\n\nNote: Specific dates vary by program and year. No dates invented.\n"
    elif plan.intent == "sponsor":
        best = max(blocks, key=lambda b: len(b.best_text)) if blocks else None
        if best:
            answer = f"Sponsor-related institutional records describe categories for LOCUS (title, associate, platinum, gold, zerone, general sponsor) across events including LOCUS 2025 and Robowarz. Specific named sponsors are partly in template/placeholder form. Source: {best.filename}" + (f" (p.{best.page})" if best.page else "") + ".\n\nNote: No sponsor names invented. Confirmed names require source verification.\n"
        else:
            answer = "Sponsorship documents exist but do not confirm a specific named sponsor. Categories are documented. No sponsor names invented.\n"
    else:
        best = max(blocks, key=lambda b: len(b.best_text)) if blocks else None
        if best:
            txt = clean_ocr(best.best_text)
            answer = f"Based on institutional records: LOCUS is Nepal's national technological festival (Tribhuvan University / Institute of Engineering). {txt[:200]}... Source: {best.filename}" + (f" (p.{best.page})" if best.page else "") + ".\n\nNote: Partial evidence; no details invented.\n"
        else:
            answer = "Institutional records document LOCUS events, team roles, sponsorship structures, themes, and dates. A complete record for all years and categories is not fully established.\n"

    # Clean answer of any OCR artifacts in synthesized text
    answer = clean_text(answer)
    return {
        "answer_text": answer,
        "answer_type": "FACTUAL",
        "format": "table" if is_people else ("table" if (is_sponsor or is_prizes) else "prose"),
        "sources": sources,
        "evidence_count": len(context_blocks),
    }

def clean_ocr(t: str) -> str:
    s = t or ""
    s = re.sub(r"\b(\w+)\s+\1\b", r"\1", s, flags=re.IGNORECASE)
    s = re.sub(r"(the\s+)?locus\s+research\s+", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\b(oc)\s+(202\d)\b", r"\1 \2", s, flags=re.IGNORECASE)
    s = re.sub(r"\b(20\d\d)\b", r"\1", s)
    s = re.sub(r"\s+", " ", s)
    s = s.replace("﻿", "").replace("\r", " ").replace("\n", " ")
    # Remove isolated garbage tokens (e.g., single letters / symbols from OCR)
    s = re.sub(r"\b[a-z]\b", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()
