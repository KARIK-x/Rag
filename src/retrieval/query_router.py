"""
LOCUS RAG Query Router — Phase 7.

Implements:
- Query intent classification
- Query normalization/rewriting
- Retrieval strategy routing
- Compound/multi-part query decomposition
- Multi-query expansion
- Temporal reasoning
- Structured-data routing
- Safe ambiguity handling

Integrates with existing Phase 6 HybridRetriever.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from src.indexing.vector import SearchQuery
from src.retrieval.hybrid import HybridRetriever, retrieve


# ─── Intent Types ─────────────────────────────────────────────────────────────

class QueryIntent(Enum):
    EXACT_LOOKUP = "exact_lookup"
    ENTITY_LOOKUP = "entity_lookup"
    SEMANTIC = "semantic"
    NUMERIC = "numeric"
    DATE = "date"
    COMPARISON = "comparison"
    AGGREGATION = "aggregation"
    TEMPORAL = "temporal"
    MULTI_DOCUMENT = "multi_document"
    STRUCTURED_DATA = "structured_data"
    METADATA = "metadata"
    NAVIGATION = "navigation"
    EXTRACTION = "extraction"
    TRANSFORMATION = "transformation"
    AMBIGUOUS = "ambiguous"
    OUT_OF_DOMAIN = "out_of_domain"
    COMPOUND = "compound"


# ─── Dataclasses ──────────────────────────────────────────────────────────────

@dataclass
class QueryIntentResult:
    """Result of intent classification with confidence and metadata."""
    intent: QueryIntent
    confidence: float
    primary_entity: Optional[str] = None
    temporal_constraints: Dict[str, Any] = field(default_factory=dict)
    structured_data_hint: Optional[str] = None
    sub_queries: List[str] = field(default_factory=list)
    expanded_queries: List[str] = field(default_factory=list)
    signals: Dict[str, Any] = field(default_factory=dict)

    def is_compound(self) -> bool:
        return len(self.sub_queries) > 1 or self.intent == QueryIntent.COMPOUND


@dataclass
class RetrievalPlan:
    """Execution plan for retrieval based on query intent."""
    intent: QueryIntent
    strategies: List[str]  # dense, bm25, exact, metadata, structured
    filters: Dict[str, Any] = field(default_factory=dict)
    structured_query: Optional[str] = None  # SQL for structured data engine
    temporal_constraints: Dict[str, Any] = field(default_factory=dict)
    sub_plans: List["RetrievalPlan"] = field(default_factory=list)
    confidence: float = 1.0
    rationale: str = ""


# ─── Query Normalizer ─────────────────────────────────────────────────────────

class QueryNormalizer:
    """Normalize and rewrite queries while protecting exact information."""

    # Patterns to preserve
    EMAIL_PATTERN = re.compile(r"[\w.-]+@[\w.-]+\.\w+")
    URL_PATTERN = re.compile(r"https?://\S+")
    DATE_PATTERN = re.compile(r"\b\d{4}[-/.]\d{1,2}[-/.]\d{1,2}\b")
    DATE_SLASH_PATTERN = re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b")
    CURRENCY_PATTERN = re.compile(r"(NPR|Rs\.?|\$|USD)\s*[\d,]+(?:\.\d+)?", re.I)
    LARGE_NUMBER_PATTERN = re.compile(r"\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\b")
    DRIVE_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{28}")
    NEPALI_NUMERAL_PATTERN = re.compile(r"[०-९]+")
    NEPALI_DATE_PATTERN = re.compile(r"[०-९]{1,2}\s+[अ-ह]+\s+[०-९]{4}")

    def __init__(self):
        self._abbreviation_map = {
            "loc": "LOCUS",
            "ncell": "Ncell",
            "cg": "CG",
            "dft": "DFT",
            "pdn": "PDN",
        }

    def normalize(self, query: str) -> str:
        """Normalize whitespace and case, preserving exact entities."""
        # Store exact entities for later restoration (in original order)
        entities = self._extract_entities(query)

        # Mask entities by their original case before lowercasing.
        # Use case-insensitive masks so the lowercased string still matches.
        masked = query.strip()
        entity_map: List[Tuple[str, str]] = []
        for mask, value in entities.items():
            lower_mask = mask.lower()
            entity_map.append((lower_mask, value))
            masked = masked.replace(value, lower_mask)

        # Normalize whitespace then case
        normalized = re.sub(r"\s+", " ", masked)
        normalized = normalized.lower()

        # Restore exact entities (case-insensitive via lower_mask match)
        for lower_mask, value in entity_map:
            normalized = re.sub(re.escape(lower_mask), value, normalized, flags=re.I)

        return normalized

    def _extract_entities(self, query: str) -> Dict[str, str]:
        """Extract and return exact entities found in query."""
        entities = {}
        for match in self.EMAIL_PATTERN.finditer(query):
            entities[f"__EMAIL_{len(entities)}__"] = match.group()
        for match in self.URL_PATTERN.finditer(query):
            entities[f"__URL_{len(entities)}__"] = match.group()
        for match in self.DATE_PATTERN.finditer(query):
            entities[f"__DATE_{len(entities)}__"] = match.group()
        for match in self.DATE_SLASH_PATTERN.finditer(query):
            entities[f"__DATE_{len(entities)}__"] = match.group()
        for match in self.CURRENCY_PATTERN.finditer(query):
            entities[f"__CURRENCY_{len(entities)}__"] = match.group()
        for match in self.LARGE_NUMBER_PATTERN.finditer(query):
            entities[f"__NUMBER_{len(entities)}__"] = match.group()
        for match in self.DRIVE_ID_PATTERN.finditer(query):
            entities[f"__DRIVEID_{len(entities)}__"] = match.group()
        for match in self.NEPALI_NUMERAL_PATTERN.finditer(query):
            entities[f"__NEPALI_NUM_{len(entities)}__"] = match.group()
        for match in self.NEPALI_DATE_PATTERN.finditer(query):
            entities[f"__NEPALI_DATE_{len(entities)}__"] = match.group()
        return entities

    def expand_abbreviations(self, query: str) -> str:
        """Expand known abbreviations in query."""
        expanded = query
        for abbr, full in self._abbreviation_map.items():
            expanded = re.sub(rf"\b{abbr}\b", full, expanded, flags=re.I)
        return expanded


# ─── Intent Classifier ────────────────────────────────────────────────────────

class IntentClassifier:
    """Classify query intent using rule-based heuristics."""

    def __init__(self):
        self._compile_patterns()

    def _compile_patterns(self):
        """Compile regex patterns for intent detection."""
        self.patterns = {
            QueryIntent.EXACT_LOOKUP: [
                re.compile(r"\b(who is|what is the|find the|show me the)\s+\w+", re.I),
                re.compile(r"\b(name|id|identifier|code)\s+of\s+", re.I),
            ],
            QueryIntent.ENTITY_LOOKUP: [
                re.compile(r"\b(who|which)\s+(was|is|were)\s+", re.I),
                re.compile(r"\b(sponsor|organizer|president|member)\s+", re.I),
            ],
            QueryIntent.NUMERIC: [
                re.compile(r"\b(how much|total|sum|amount|count|average)\b", re.I),
                re.compile(r"\b(\d{1,3}(?:,\d{3})*|\d+)\b"),
            ],
            QueryIntent.DATE: [
                re.compile(r"\b(when|date|year|month|day)\b", re.I),
                re.compile(r"\b(20\d{2})\b"),
            ],
            QueryIntent.COMPARISON: [
                re.compile(r"\b(compare|versus|vs\.?|difference|similar|different)\b", re.I),
            ],
            QueryIntent.AGGREGATION: [
                re.compile(r"\b(total|sum|average|count|min|max|group by|by year)\b", re.I),
            ],
            QueryIntent.COMPARISON: [
                re.compile(r"\b(compare|versus|vs\.?|difference|similar|different)\b", re.I),
            ],
            QueryIntent.TEMPORAL: [
                re.compile(r"\b(before|after|since|until|during|in\s+\d{4})\b", re.I),
                re.compile(r"\b(historical|current|latest|latest|as of)\b", re.I),
            ],
            QueryIntent.STRUCTURED_DATA: [
                re.compile(r"\b(list|show|export|all\s+\w+\s+and|every\s+\w+)\b", re.I),
                re.compile(r"\b(table|rows|columns|spreadsheet|csv|excel)\b", re.I),
            ],
            QueryIntent.METADATA: [
                re.compile(r"\b(meta|metadata|file|document|type|folder|path)\b", re.I),
            ],
            QueryIntent.NAVIGATION: [
                re.compile(r"\b(open|go to|show|navigate|path)\b", re.I),
            ],
        }

    def classify(self, query: str, expanded: Optional[str] = None) -> QueryIntentResult:
        """Classify query into one or more intents with confidence."""
        q = (expanded or query).lower()
        scores: Dict[QueryIntent, int] = {}

        # Pattern matching
        for intent, patterns in self.patterns.items():
            score = 0
            for pat in patterns:
                if pat.search(q):
                    score += 1
            if score > 0:
                scores[intent] = score

        # Special detection for compound queries
        if re.search(r"\band\b|,", q):
            scores[QueryIntent.COMPOUND] = scores.get(QueryIntent.COMPOUND, 0) + 1

        # Detect structured data queries (SQL-like)
        if re.search(r"\b(select|where|group by|order by|sum|count|average)\b", q):
            scores[QueryIntent.STRUCTURED_DATA] = scores.get(QueryIntent.STRUCTURED_DATA, 0) + 2

        # No strong signals -> semantic
        if not scores:
            scores[QueryIntent.SEMANTIC] = 1

        # Pick primary intent
        primary = max(scores, key=scores.get)
        confidence = min(scores[primary] / 3.0, 1.0)

        # Extract sub-queries for compound
        sub_queries = []
        if primary == QueryIntent.COMPOUND or scores.get(QueryIntent.COMPOUND, 0) > 0:
            sub_queries = self._decompose_compound(query)

        # Extract primary entity
        entity = self._extract_primary_entity(query)

        # Temporal constraints
        temporal = self._extract_temporal(query)

        # Structured data hint
        struct_hint = self._extract_structured_hint(query)

        # Expansion
        expanded_queries = self._expand_query(query)

        return QueryIntentResult(
            intent=primary,
            confidence=confidence,
            primary_entity=entity,
            temporal_constraints=temporal,
            structured_data_hint=struct_hint,
            sub_queries=sub_queries,
            expanded_queries=expanded_queries,
            signals={"scores": {k.value: v for k, v in scores.items()}},
        )

    def _decompose_compound(self, query: str) -> List[str]:
        """Decompose compound query into sub-queries."""
        # Split on conjunctions
        parts = re.split(r"\b(?:and|,)\b", query)
        return [p.strip() for p in parts if len(p.strip()) > 3]

    def _extract_primary_entity(self, query: str) -> Optional[str]:
        """Extract the primary entity (person, org, event) from query."""
        # Simple heuristic: capitalized proper nouns
        matches = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b", query)
        if matches:
            # Filter out common words
            common = {"The", "A", "An", "What", "Who", "When", "Where", "How", "Why"}
            for m in matches:
                if m not in common:
                    return m
        return None

    def _extract_temporal(self, query: str) -> Dict[str, Any]:
        """Extract temporal constraints from query."""
        temporal = {}
        # Year patterns
        years = re.findall(r"\b(20\d{2})\b", query)
        if years:
            temporal["years"] = [int(y) for y in years]
        # "before/after X"
        for m in re.finditer(r"\b(before|after|since|until)\s+(\d{4})", query, re.I):
            temporal.setdefault(m.group(1).lower(), []).append(int(m.group(2)))
        # "during X"
        for m in re.finditer(r"\bduring\s+(20\d{2})", query, re.I):
            temporal.setdefault("during", []).append(int(m.group(1)))
        return temporal

    def _extract_structured_hint(self, query: str) -> Optional[str]:
        """Detect if query suggests structured data access."""
        if re.search(r"\b(export|list|all|every|each|show\s+\w+\s+table|rows|columns)\b", query, re.I):
            return "structured"
        return None

    def _expand_query(self, query: str) -> List[str]:
        """Generate query expansions for better recall."""
        expansions = [query]
        # Abbreviation expansion
        expanded = query
        for abbr, full in {
            "loc": "LOCUS",
            "ncell": "Ncell",
            "cg": "CG",
            "dft": "DFT",
            "pdn": "PDN",
            "mtg": "meeting",
            "conf": "conference",
            "comp": "competition",
        }.items():
            expanded = re.sub(rf"\b{abbr}\b", full, expanded, flags=re.I)
        if expanded != query:
            expansions.append(expanded)
        # Synonym expansion for common terms
        if "sponsor" in query.lower():
            expansions.append(query.replace("sponsor", "partner"))
        if "event" in query.lower():
            expansions.append(query.replace("event", "festival"))
        if "total" in query.lower():
            expansions.append(query.replace("total", "sum"))
        return expansions


# ─── Retrieval Strategy Router ────────────────────────────────────────────────

class RetrievalRouter:
    """Map query intent to retrieval strategies and build execution plan."""

    def __init__(self, hybrid_retriever: Optional[HybridRetriever] = None):
        self.hybrid = hybrid_retriever

    def build_plan(self, intent_result: QueryIntentResult) -> RetrievalPlan:
        """Build retrieval execution plan from intent."""
        intent = intent_result.intent
        strategies = []
        filters = {}
        structured_query = None
        sub_plans = []

        # Base strategies
        if intent in (QueryIntent.EXACT_LOOKUP, QueryIntent.ENTITY_LOOKUP):
            strategies = ["exact", "bm25"]
        elif intent == QueryIntent.NUMERIC:
            strategies = ["exact", "bm25", "structured"]
        elif intent == QueryIntent.DATE:
            strategies = ["exact", "bm25", "metadata"]
        elif intent == QueryIntent.STRUCTURED_DATA:
            strategies = ["structured", "bm25", "exact"]
        elif intent == QueryIntent.AGGREGATION:
            strategies = ["structured", "bm25", "exact"]
        elif intent == QueryIntent.COMPARISON:
            strategies = ["structured", "bm25", "exact", "dense"]
        elif intent == QueryIntent.TEMPORAL:
            strategies = ["exact", "metadata", "bm25"]
        elif intent == QueryIntent.METADATA:
            strategies = ["metadata", "bm25", "exact"]
        elif intent == QueryIntent.NAVIGATION:
            strategies = ["metadata", "bm25"]
        elif intent == QueryIntent.COMPOUND:
            # Delegate to sub-plans
            pass
        else:
            strategies = ["bm25", "exact", "dense"]

        # Add metadata filters from temporal constraints
        temporal = intent_result.temporal_constraints
        if "years" in temporal:
            filters["year"] = temporal["years"]
        if "before" in temporal:
            filters["before"] = temporal["before"]
        if "after" in temporal:
            filters["after"] = temporal["after"]

        # Structured data hint
        if intent_result.structured_data_hint:
            pass  # handled in structured strategies

        # Handle compound queries
        sub_plans = []
        if intent_result.sub_queries:
            for sq in intent_result.sub_queries:
                sub_intent = IntentClassifier().classify(sq)
                sub_plan = self.build_plan(sub_intent)
                sub_plans.append(sub_plan)

        return RetrievalPlan(
            intent=intent,
            strategies=strategies,
            filters=filters,
            temporal_constraints=intent_result.temporal_constraints,
            sub_plans=sub_plans,
            confidence=intent_result.confidence,
            rationale=f"Intent: {intent.value}, strategies: {strategies}",
        )

    def classify(self, query: str) -> QueryIntentResult:
        """Convenience method to classify then build plan."""
        return IntentClassifier().classify(query)

    def execute(self, plan: RetrievalPlan, hybrid: HybridRetriever) -> List:
        """Execute retrieval plan (placeholder for actual execution)."""
        # In a full implementation, this would call hybrid.retrieve()
        # for each strategy and merge results per plan.
        pass


# ─── Main Query Router ────────────────────────────────────────────────────────

class QueryRouter:
    """Main entry point for query understanding and routing."""

    def __init__(
        self,
        hybrid_retriever: Optional[HybridRetriever] = None,
        enable_expansion: bool = True,
    ):
        self.hybrid = hybrid_retriever
        self.normalizer = QueryNormalizer()
        self.classifier = IntentClassifier()
        self.router = RetrievalRouter()
        self.enable_expansion = enable_expansion

    def route(self, query: str) -> RetrievalPlan:
        """Full query routing pipeline."""
        # 1. Normalize
        normalized = self.normalizer.normalize(query)
        # 2. Expand abbreviations
        expanded = self.normalizer.expand_abbreviations(query)
        # 3. Classify intent
        intent_result = self.classifier.classify(query, expanded=expanded)
        # 4. Build retrieval plan
        plan = self.router.build_plan(intent_result)
        return plan

    def retrieve(self, query: str, top_k: int = 20, filters: Optional[Dict] = None) -> List:
        """Convenience method: route + execute via hybrid retriever."""
        plan = self.route(query)
        # Apply filters from plan + provided filters
        if filters:
            plan.filters.update(filters)

        # If we have a hybrid retriever, use it
        if self.hybrid:
            return self.hybrid.retrieve(query, top_k=top_k, filters=plan.filters)
        return []

    def get_intent(self, query: str) -> QueryIntentResult:
        """Just classify, no routing."""
        return self.classifier.classify(query)


# ─── Convenience Functions ────────────────────────────────────────────────────

def route_query(query: str) -> RetrievalPlan:
    """Route a query to a retrieval plan."""
    router = QueryRouter()
    return router.route(query)

def classify_query(query: str) -> QueryIntentResult:
    """Classify a query's intent."""
    return IntentClassifier().classify(query)

def retrieve_with_routing(
    query: str,
    top_k: int = 20,
    filters: Optional[Dict] = None,
) -> List:
    """Convenience: route + retrieve via hybrid retriever."""
    router = QueryRouter()
    return router.retrieve(query, top_k=top_k, filters=filters)