"""
LOCUS RAG normalization layer.

Per spec §21:
  1. Unicode normalization (NFKC)
  2. Whitespace normalization
  3. Encoding repair
  4. Script-aware normalization
  5. Safe punctuation normalization
  6. Number normalization (raw vs parsed, preserving ambiguity)
  7. Date normalization
  8. Currency normalization (NPR, USD, "Rs.", lakh/crore)
  9. Locale normalization

Critical rule:
  - ALWAYS preserve raw source representation
  - NEVER assume "100,000 = NPR" unless context establishes it
  - Store: raw_value, parsed_numeric_value, unit, currency, locale,
    format_style, source_text, provenance
"""

import re
import logging
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ─── Enums ──────────────────────────────────────────────────────────────────

class NumberFormat(Enum):
    """Locale-specific number format styles."""
    WESTERN_GROUPED = "western_grouped"   # 1,234,567.89
    INDIAN_GROUPED = "indian_grouped"     # 12,34,567.89 (lakh/crore)
    PLAIN = "plain"                        # 1234567.89
    SCIENTIFIC = "scientific"              # 1.23e6


class DateStyle(Enum):
    ISO = "iso"                # 2024-01-15
    US = "us"                  # 01/15/2024
    UK = "uk"                  # 15/01/2024
    LONG = "long"              # 15 January 2024
    WITH_TIME = "with_time"    # 2024-01-15T10:30:00Z
    NEPALI = "nepali"          # भाद्र १५, २०८१ (B.S.)


@dataclass
class NormalizedNumber:
    """Normalized numeric value with full provenance (spec §21)."""
    raw_value: str
    parsed_numeric_value: Optional[float] = None
    unit: Optional[str] = None
    currency: Optional[str] = None
    locale: Optional[str] = None
    format_style: Optional[str] = None
    source_text: Optional[str] = None
    provenance: Optional[str] = None


@dataclass
class NormalizedDate:
    """Normalized date with style + provenance."""
    raw_value: str
    parsed_date: Optional[date] = None
    date_style: Optional[str] = None
    calendar: Optional[str] = "gregorian"  # gregorian | bikram_sambat
    provenance: Optional[str] = None


# ─── Number normalization ─────────────────────────────────────────────────────

_NUMBER_CURRENCY_MAP = {
    "rs": "NPR",
    "npr": "NPR",
    "रू": "NPR",
    "रु": "NPR",
    "usd": "USD",
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
    "aed": "AED",
    "inr": "INR",
}

_NEPALI_DIGITS = {
    "०": "0", "१": "1", "२": "2", "३": "3", "४": "4",
    "५": "5", "६": "6", "७": "7", "८": "8", "९": "9",
}

_LARGE_UNITS = {
    "thousand": 1_000,
    "hundred thousand": 100_000,
    "million": 1_000_000,
    "lakh": 100_000,
    "crore": 10_000_000,
    "hajar": 1_000,
    "lakhs": 100_000,
    "crores": 10_000_000,
}


def normalize_devanagari_digits(text: str) -> str:
    """Convert Devanagari numerals (१२३...) to ASCII (123...)."""
    return "".join(_NEPALI_DIGITS.get(ch, ch) for ch in text)


def parse_number(
    raw: str,
    locale: Optional[str] = None,
    currency_hint: Optional[str] = None,
) -> NormalizedNumber:
    """
    Parse a number from raw text, preserving raw source.

    Handles:
      - "100,000" (western grouping)
      - "1,00,000" (Indian grouping)
      - "Rs. 100000" / "NPR 100,000"
      - "NPR 1 lakh" / "1 crore"
      - Devanagari digits "५०,०००"
      - "50%" and "USD 1.2m"
    """
    original = raw
    raw = raw.strip()

    # Extract currency prefix/suffix
    currency = None
    lower = raw.lower()
    for symbol, cur in _NUMBER_CURRENCY_MAP.items():
        if symbol in lower or (symbol in raw):
            currency = cur
            break

    # Remove currency symbols for parsing
    parsed_raw = re.sub(r"(NPR|Rs\.?|रू|रु|\$|USD|€|£|AED|INR)\s*", "", raw, flags=re.I)

    # Handle "X lakh / X crore" style
    unit = None
    text_part = re.search(r"(thousand|hundred thousand|million|lakh|lakhs|crore|crores|hajar)\b", parsed_raw, re.I)
    if text_part:
        unit = text_part.group(1).lower()
        parsed_raw = parsed_raw[: text_part.start()].strip()

    # Convert Devanagari digits
    parsed_raw = normalize_devanagari_digits(parsed_raw)

    # Remove remaining non-numeric except . , - %
    cleaned = re.sub(r"[^\d.,%\-\s]", "", parsed_raw).strip()

    # Detect format style
    format_style = None
    if "," in cleaned and re.search(r"\d", cleaned):
        digits_only = cleaned.replace(",", "")
        ndigits = len(digits_only)
        ncommas = cleaned.count(",")
        # Indian grouping has groups of 3 (last) then {3,2} preceding groups.
        # Western grouping: all groups except the last are exactly 3 digits.
        groups = [g for g in cleaned.split(",") if g]
        n_last = len(groups[-1]) if groups else 0
        groups_before = groups[:-1]
        if n_last == 3 and all(len(g) == 3 for g in groups_before):
            format_style = NumberFormat.WESTERN_GROUPED.value
        elif n_last == 3:
            format_style = NumberFormat.INDIAN_GROUPED.value

    # Strip commas/percent
    numeric_str = cleaned.replace("%", "").replace(",", "")
    try:
        number = float(numeric_str)
    except ValueError:
        number = None

    # Apply unit multiplier
    if number is not None and unit in _LARGE_UNITS:
        number *= _LARGE_UNITS[unit]

    if currency_hint and currency is None:
        currency = currency_hint

    return NormalizedNumber(
        raw_value=original,
        parsed_numeric_value=number,
        unit=unit,
        currency=currency,
        locale=locale,
        format_style=format_style,
        source_text=original,
    )


def is_probably_currency(row: Dict[str, Any]) -> bool:
    """Heuristic: does a spreadsheet row look like it holds currency amounts?"""
    text = " ".join(str(v) for v in row.values() if v is not None)
    text = text.lower()
    return bool(
        re.search(r"(rs\.?|npr|रू|रु|\$|usd|lakh|crore)", text)
    )


# ─── Date normalization ───────────────────────────────────────────────────────

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12, "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}

_NEPALI_MONTHS = {
    "बैशाख": 1, "जेठ": 2, "असार": 3, "साउन": 4, "भदौ": 5, "असोज": 6,
    "कात्तिक": 7, "मंसिर": 8, "पुष": 9, "माघ": 10, "फागुन": 11, "चैत": 12,
    "baishakh": 1, "jestha": 2, "ashar": 3, "shrawan": 4, "bhadra": 5,
    "ashoj": 6, "kartik": 7, "mangsir": 8, "poush": 9, "magh": 10,
    "falgun": 11, "chaitra": 12,
}


def parse_date(
    raw: str,
    locale: Optional[str] = None,
) -> NormalizedDate:
    """Parse a date string, preserving raw + detecting style."""
    original = raw
    raw = raw.strip()

    # ISO / with-time
    date_obj = None
    style = None

    # ISO 2024-01-15
    m = re.match(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$", raw)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            date_obj = date(y, mo, d)
            style = DateStyle.ISO.value
        except ValueError:
            date_obj = None

    # US 01/15/2024 or UK 15/01/2024
    if not date_obj:
        m = re.match(r"^(\d{1,2})[/.](\d{1,2})[/.](\d{2,4})$", raw)
        if m:
            a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if y < 100:
                y += 2000
            # Try US (mm/dd): month = a
            try:
                date_obj = date(y, a, b)
                style = DateStyle.US.value
            except ValueError:
                # Try UK (dd/mm): month = b
                try:
                    date_obj = date(y, b, a)
                    style = DateStyle.UK.value
                except ValueError:
                    date_obj = None

    # Long form: "15 January 2024"
    if not date_obj:
        m = re.match(r"^(\d{1,2})\s+([A-Za-z]+)[,\s]+(\d{4})$", raw)
        if m:
            d, mon, y = int(m.group(1)), m.group(2).lower(), int(m.group(3))
            if mon in _MONTHS:
                try:
                    date_obj = date(y, _MONTHS[mon], d)
                    style = DateStyle.LONG.value
                except ValueError:
                    date_obj = None

    # Month day, year: "January 15, 2024"
    if not date_obj:
        m = re.match(r"^([A-Za-z]+)\s+(\d{1,2})[,\s]+(\d{4})$", raw)
        if m:
            mon, d, y = m.group(1).lower(), int(m.group(2)), int(m.group(3))
            if mon in _MONTHS:
                try:
                    date_obj = date(y, _MONTHS[mon], d)
                    style = DateStyle.LONG.value
                except ValueError:
                    date_obj = None

    # With time
    if not date_obj:
        m = re.match(r"^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}:\d{2})", raw)
        if m:
            try:
                date_obj = date(
                    int(m.group(1)), int(m.group(2)), int(m.group(3))
                )
                style = DateStyle.WITH_TIME.value
            except ValueError:
                date_obj = None

    return NormalizedDate(
        raw_value=original,
        parsed_date=date_obj,
        date_style=style,
        provenance=None,
    )


# ─── Text normalization ───────────────────────────────────────────────────────

def normalize_text(
    text: str,
    lower: bool = True,
    collapse_whitespace: bool = True,
    strip_punctuation_variants: bool = True,
) -> str:
    """
    Normalize text for retrieval while preserving source meaning.

    - Unicode NFKC (compat + canonical)
    - Optional lowercase
    - Collapse whitespace
    - Fold smart quotes/dashes to ASCII
    """
    if not text:
        return text

    # Unicode normalization
    text = unicodedata.normalize("NFKC", text)

    # Smart quotes / dashes → ASCII
    if strip_punctuation_variants:
        text = text.replace("’", "'").replace("‘", "'")  # curly apostrophes
        text = text.replace("“", '"').replace("”", '"')   # curly double
        text = text.replace("–", "-").replace("—", "-")   # en/em dash
        text = text.replace(" ", " ")                          # nbsp

    if collapse_whitespace:
        text = re.sub(r"\s+", " ", text).strip()
    if lower:
        text = text.lower()

    return text


def is_mixed_script(text: str) -> bool:
    """Detect if text contains both Devanagari and Latin script."""
    devanagari = re.search(r"[ऀ-ॿ]", text)
    latin = re.search(r"[A-Za-z]", text)
    return bool(devanagari and latin)


# ─── Normalizer facade ────────────────────────────────────────────────────────

class Normalizer:
    """Top-level normalizer producing a NormalizedDocument."""

    def normalize(self, raw_document: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize an extracted document.

        Input: ExtractionResult.to_dict() or similar.
        Output: NormalizedDocument with:
          - normalized full_text
          - per-block normalized text
          - parsed numbers/dates/currencies discovered
        """
        full_text = raw_document.get("full_text", "")

        normalized = normalize_text(full_text, lower=False)  # preserve case for display
        normalized_lower = normalize_text(full_text, lower=True)

        extracted_numbers = self.extract_numbers(full_text)
        extracted_dates = self.extract_dates(full_text)

        return {
            "doc_id": raw_document.get("doc_id"),
            "raw_full_text": full_text,
            "normalized_full_text": normalized,
            "normalized_lower": normalized_lower,
            "extracted_numbers": [n.__dict__ for n in extracted_numbers],
            "extracted_dates": [d.__dict__ for d in extracted_dates],
            "metadata": raw_document.get("metadata", {}),
            "provenance": raw_document.get("provenance", {}),
        }

    def extract_numbers(self, text: str) -> List[NormalizedNumber]:
        """Find and parse all numeric mentions in text."""
        results = []
        # Currency + unit patterns are high-precision
        patterns = [
            r"(NPR|Rs\.?|रू|रु|\$|USD|€|£|AED|INR)\s*[\d,]+(?:\.\d+)?(?: (?:lakh|crore|thousand|million|hundred thousand))?",
            r"\b\d[\d,]*(?:\.\d+)?\s*(?:%|(?:lakh|crore|thousand|million|hundred thousand))\b",
            r"\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\b",          # 1,000 / 1,00,000 (grouped)
            r"\b\d{4,}(?:\.\d+)?\b",                       # 50000, 100000 (plain ≥4 digits)
        ]
        matches = []  # (start, end, raw) — collect candidates first
        for pat in patterns:
            for m in re.finditer(pat, text):
                raw = m.group(0)
                if re.fullmatch(r"\d{4}", raw) and 1900 <= int(raw) <= 2099:
                    continue  # bare year, not an amount
                matches.append((m.start(), m.end(), raw))

        # Earliest start, and among overlaps keep the longest (so "Rs. 50,000"
        # wins over "50,000"). Sort by start, then by -length, then dedup.
        matches.sort(key=lambda x: (x[0], -len(x[2])))
        prev_end = -1
        for start, end, raw in matches:
            if start < prev_end:
                continue  # overlapped by an earlier, longer match
            prev_end = end
            num = parse_number(raw)
            if num.parsed_numeric_value is not None or num.currency:
                results.append(num)
        return results[:50]

    def extract_dates(self, text: str) -> List[NormalizedDate]:
        """Find and parse all date mentions in text."""
        results = []
        patterns = [
            r"\b\d{4}[-/.]\d{1,2}[-/.]\d{1,2}\b",
            r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",
            r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?[,\s]+\d{4}\b",
            r"\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*[,\s]+\d{4}\b",
            r"[०-९]+\s+[A-Za-zऀ-ॿ]+\s+[०-९]{4}",  # Nepali BS
        ]
        seen = set()
        for pat in patterns:
            for m in re.finditer(pat, text):
                raw = m.group(0)
                if raw in seen:
                    continue
                seen.add(raw)
                parsed = parse_date(raw)
                if parsed.parsed_date or parsed.date_style:
                    results.append(parsed)
        return results[:50]

    def batch(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [self.normalize(d) for d in documents]