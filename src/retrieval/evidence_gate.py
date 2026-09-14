"""Query-understanding + evidence-gate for LOCUS retrieval correctness.
Extracts intent, entities, years, roles; requires exact-entity evidence for
named-entity questions; suppresses benefit/fee docs for 'who' sponsor queries."""
import re
from typing import List, Dict, Any

ENTITY_MAP = {
    "roboevent": ["roboevent","robowarz","robo warz","robo-event","robo event"],
    "electro tech week": ["electro tech week","electro tech","electrotech","electro-tech"],
    "locust event": ["locust exhibition","locust fest","locust festival","locust event","locust 2025"],
    "magazine": ["zerone","the zerone","magazine","locust magazine"],
    "mou": ["memorandum of understanding","mou","memorandum","signed memorandum"],
}

def extract_query_plan(query: str) -> Dict[str, Any]:
    q = query.lower()
    # Intent from answer-type keywords
    intent = "general"
    if any(x in q for x in ["who is","who was","who were","president","sponsor","organizer","team","members"]):
        intent = "who"
    elif any(x in q for x in ["what is","what was","define","explain","description"]):
        intent = "what"
    elif any(x in q for x in ["when","date","held","year","2025","2023","2024"]):
        intent = "when"
    elif any(x in q for x in ["list","20","100","all","names","items","table"]):
        intent = "list"
    elif any(x in q for x in ["how much","cost","price","fee","investment","rs","amount"]):
        intent = "how_much"
    # Named entities
    entities = []
    for key, aliases in ENTITY_MAP.items():
        for alias in aliases:
            if alias in q:
                entities.append(key)
                break
    # Year extraction
    years = [y for y in ["2025","2023","2024","2026","2022","2012"] if y in q]
    return {"intent": intent, "entities": entities, "years": years, "raw": q}

def evidence_gate(candidate_text: str, plan: Dict[str, Any]) -> bool:
    """Pass only if chunk actually supports the requested answer."""
    text = (candidate_text or "").lower()
    # Entity questions: must contain the named entity; suppress benefit/fee-only for sponsor 'who'
    if plan["intent"] == "who" and "sponsor" in plan["raw"]:
        # Must have company/identity signals; reject pure benefit/price docs
        has_company = any(w in text for w in ["company","corporation","ltd","pvt","group","bank","tech","engineering","limited","industrial"])
        has_fee_only = any(w in text for w in ["price","fee","cost","investment","rs ","starting sponsorship","benefit","privilege","privileges"]) and not has_company
        if has_fee_only and not has_company:
            return False  # benefit-only chunk for "who was sponsor" — reject
    # Named entity: must contain at least one named entity from plan
    if plan["entities"]:
        for ent in plan["entities"]:
            ent_text = ENTITIES.get(ent, [ent])
            # Check aliases
            if any(a in text for a in ent_text):
                return True
        return False  # no named entity present → reject for named-entity query
    # General LOCUS + year/role check
    if not ("locus" in text or "tribhuvan" in text or "pulchowk" in text):
        return False
    return True

ENTITIES = ENTITY_MAP
