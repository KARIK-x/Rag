"""
LOCUS RAG document classification.

Per spec §22, §23:
  - Metadata classification (document type / domain)
  - Temporal classification (content dates, event periods, reporting periods)
  - Authority scoring (draft/final/proposal/signed/superseded)

A document may be classified into multiple types (a sponsorship proposal is
both a "proposal" authority and "sponsorship" domain).
"""

import re
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from src.normalization.text import parse_date, parse_number, normalize_text

logger = logging.getLogger(__name__)


# ─── Enums ──────────────────────────────────────────────────────────────────

class DocDomain(Enum):
    """Semantic domain of a document."""
    EVENT = "event"
    SPONSORSHIP = "sponsorship"
    BUDGET_FINANCE = "budget_finance"
    MEETING = "meeting"
    MEMBER_CV = "member_cv"
    REPORT = "report"
    PROPOSAL = "proposal"
    TECHNICAL = "technical"
    DESIGN = "design"
    FORM_RESPONSES = "form_responses"
    GENERAL = "general"
    UNKNOWN = "unknown"


class AuthorityStatus(Enum):
    """Source authority signal (spec §23)."""
    DRAFT = "draft"
    FINAL = "final"
    PROPOSAL = "proposal"
    CONFIRMED = "confirmed"
    SIGNED = "signed"
    SUPERSEDED = "superseded"
    CURRENT = "current"
    UNKNOWN = "unknown"


# ─── Domain keyword heuristics ──────────────────────────────────────────────

_DOMAIN_PATTERNS: List[Tuple[DocDomain, List[str]]] = [
    (DocDomain.SPONSORSHIP, [
        r"sponsor", r"sponsorship", r"sponsors", r"contribution",
        r"partnership", r"patron", r"tier", r"gold sponsor", r"silver sponsor",
    ]),
    (DocDomain.BUDGET_FINANCE, [
        r"\bbudget\b", r"\bexpense\b", r"\brevenue\b", r"financial",
        r"\bcash\b", r"expenditure", r"\bincome\b", r"cost",
    ]),
    (DocDomain.EVENT, [
        r"\bevent\b", r"\bfestival\b", r"\blocus 20\d\d\b", r"tech fest",
        r"national technological", r"\bworkshop\b", r"\bbootcamp\b",
        r"hackathon", r"seminar", r"expo",
    ]),
    (DocDomain.MEETING, [
        r"\bmeeting\b", r"\bminutes\b", r"\bagenda\b", r"attendees",
    ]),
    (DocDomain.MEMBER_CV, [
        r"\bcurriculum vitae\b", r"\bresume\b", r"\bcv\b",
        r"work experience", r"\bcertificate\b", r"achievement",
    ]),
    (DocDomain.REPORT, [
        r"\breport\b", r"annual report", r"\bsummary\b", r"highlights",
    ]),
    (DocDomain.PROPOSAL, [
        r"\bproposal\b", r"\binvitation\b", r"letter of intent",
        r"\bquery\b", r"call for",
    ]),
    (DocDomain.TECHNICAL, [
        r"technical", r"\bcode\b", r"programming", r"\bsoftware\b",
        r"engineering", r"\bapi\b", r"\bserver\b",
    ]),
    (DocDomain.DESIGN, [
        r"\bdesign\b", r"\bui\b", r"\bux\b", r"\bgraphic\b",
        r"photoshop", r"\bposter\b", r"\bbanner\b",
    ]),
]


# ─── Authority heuristics ───────────────────────────────────────────────────

_AUTHORITY_PATTERNS: List[Tuple[AuthorityStatus, List[str]]] = [
    (AuthorityStatus.DRAFT, [
        r"\bdraft\b", r"working copy", r"v\d+\s*draft",
    ]),
    (AuthorityStatus.PROPOSAL, [
        r"\bproposal\b", r"proposed", r"invitation to", r"letter of intent",
    ]),
    (AuthorityStatus.FINAL, [
        r"\bfinal\b", r"finalized", r"final version",
        r"\breport\b", r"\bapproved\b",
    ]),
    (AuthorityStatus.SIGNED, [
        r"\bsigned\b", r"\bsignature\b", r"\baccepted\b", r"\bagreed\b",
        r"memorandum of understanding", r"\bmou\b",
    ]),
    (AuthorityStatus.CONFIRMED, [
        r"\bconfirmed\b", r"official", r"\bverified\b",
    ]),
    (AuthorityStatus.SUPERSEDED, [
        r"\bsuperseded\b", r"\bobsolete\b", r"replaced by", r"\barchive\b",
    ]),
]


# ─── Dataclasses ────────────────────────────────────────────────────────────

@dataclass
class Classification:
    """Classification result for a document."""
    doc_id: str
    domains: List[str]
    primary_domain: Optional[str]
    authority_status: str
    content_dates: List[str]           # normalized ISO dates found
    event_period_start: Optional[str]
    event_period_end: Optional[str]
    reporting_period_start: Optional[str]
    reporting_period_end: Optional[str]
    confidence: float
    signals: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "domains": self.domains,
            "primary_domain": self.primary_domain,
            "authority_status": self.authority_status,
            "content_dates": self.content_dates,
            "event_period_start": self.event_period_start,
            "event_period_end": self.event_period_end,
            "reporting_period_start": self.reporting_period_start,
            "reporting_period_end": self.reporting_period_end,
            "confidence": self.confidence,
            "signals": self.signals,
        }


class DocumentClassifier:
    """Classify documents by domain, authority, and temporal content."""

    def __init__(self):
        self._domain_compiled = [
            (dom, [re.compile(p, re.I) for p in pats])
            for dom, pats in _DOMAIN_PATTERNS
        ]
        self._authority_compiled = [
            (auth, [re.compile(p, re.I) for p in pats])
            for auth, pats in _AUTHORITY_PATTERNS
        ]

    def classify(
        self,
        doc: Dict[str, Any],
        text: Optional[str] = None,
    ) -> Classification:
        """
        Classify a document.

        `doc` is an extraction/normalized doc (doc_id, metadata, provenance,
        full_text). `text` overrides the source text (e.g. filename + text).
        """
        doc_id = doc.get("doc_id", "?")
        filename = doc.get("metadata", {}).get("title", "") or doc.get("provenance", {}).get("filename", "")
        source_text = text or doc.get("full_text", "") or doc.get("normalized_full_text", "")
        search_text = f"{filename} {source_text}"

        # Domain classification
        domain_scores: Dict[str, int] = {}
        for dom, pats in self._domain_compiled:
            score = 0
            for p in pats:
                score += len(p.findall(search_text))
            if score > 0:
                domain_scores[dom.value] = score

        domains = sorted(domain_scores, key=domain_scores.get, reverse=True)
        primary = domains[0] if domains else DocDomain.UNKNOWN.value

        # Authority
        authority = AuthorityStatus.UNKNOWN.value
        auth_score = 0
        for auth, pats in self._authority_compiled:
            score = sum(len(p.findall(search_text)) for p in pats)
            if score > auth_score and score > 0:
                auth_score = score
                authority = auth.value

        # Temporal
        content_dates = self._extract_dates(search_text)
        event_period = self._detect_period(search_text, ["event", "festival"], content_dates)
        reporting_period = self._detect_period(search_text, ["report", "annual"], content_dates)

        # Confidence: based on domain signal strength + primary domain known
        confidence = min(1.0, 0.4 + 0.1 * sum(domain_scores.values())) if domain_scores else 0.2
        if primary == DocDomain.UNKNOWN.value:
            confidence = 0.2

        return Classification(
            doc_id=doc_id,
            domains=domains,
            primary_domain=primary,
            authority_status=authority,
            content_dates=sorted(set(content_dates)),
            event_period_start=event_period[0] if event_period else None,
            event_period_end=event_period[1] if event_period else None,
            reporting_period_start=reporting_period[0] if reporting_period else None,
            reporting_period_end=reporting_period[1] if reporting_period else None,
            confidence=confidence,
            signals={
                "filename": filename,
                "domain_scores": domain_scores,
                "authority_score": auth_score,
            },
        )

    # ─── Temporal helpers ──────────────────────────────────────────────────

    def _extract_dates(self, text: str) -> List[str]:
        """Extract date mentions and return ISO-normalized."""
        dates = []
        patterns = [
            r"\b\d{4}[-/.]\d{1,2}[-/.]\d{1,2}\b",
            r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",
            r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+\d{1,2}[a-z]*[,\s]+\d{4}\b",
            r"\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*[,\s]+\d{4}\b",
        ]
        seen = set()
        for pat in patterns:
            for m in re.finditer(pat, text):
                raw = m.group(0)
                parsed = parse_date(raw)
                if parsed.parsed_date:
                    iso = parsed.parsed_date.isoformat()
                    if iso not in seen:
                        seen.add(iso)
                        dates.append(iso)
        return dates

    def _detect_period(
        self,
        text: str,
        keywords: List[str],
        dates: List[str],
    ) -> Optional[Tuple[str, str]]:
        """Find a start/end date pair near a keyword (spec §22)."""
        # Look for "period: <date> to <date>" or "<date> - <date>"
        pattern = re.compile(
            r"(?:period|from|between)\s+"
            r"(\d{1,2}[/.]\d{1,2}[/.]\d{2,4}|\d{4}[-/.]\d{1,2}[-/.]\d{1,2})"
            r".{0,10}(?:to|[-–]|until|and)\s+"
            r"(\d{1,2}[/.]\d{1,2}[/.]\d{2,4}|\d{4}[-/.]\d{1,2}[-/.]\d{1,2})",
            re.I,
        )
        for kw in keywords:
            # Search in the region around the keyword
            idx = text.lower().find(kw)
            if idx < 0:
                continue
            region = text[max(0, idx - 200): idx + 500]
            m = pattern.search(region)
            if m:
                d1 = parse_date(m.group(1)).parsed_date
                d2 = parse_date(m.group(2)).parsed_date
                if d1 and d2:
                    return d1.isoformat(), d2.isoformat()
        return None