"""Centralized normalization of seat semantics into structured fields.

Called from both BaseAdapter.normalize() (locals) and scrapers/state.py
(state legislators and executive) so the same logic produces the same
structured fields regardless of source.

See docs/plans/2026-05-16-data-model-normalization-design.md for the
schema definition and the four-stage precedence model.
"""

import re
from dataclasses import dataclass
from typing import Literal, Optional


@dataclass
class NormalizationContext:
    """Context passed into normalize_member from the caller."""
    level: Literal["state", "local"]
    chamber: Optional[Literal["senate", "house", "executive"]] = None
    jurisdiction_type: Optional[Literal["county", "place"]] = None
    jurisdiction_id: Optional[str] = None
    registry_hints: Optional[dict] = None  # e.g. {"seatClass": "at-large", "partisan": False}


# Stage 2: title parsing patterns
_WORD_NUMS = {
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
    "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
    "eleven": "11", "twelve": "12", "thirteen": "13", "fourteen": "14",
    "fifteen": "15", "sixteen": "16", "seventeen": "17", "eighteen": "18",
    "nineteen": "19", "twenty": "20",
}

_WORD_SEAT_RE = re.compile(
    r"\b(District|Ward|Seat)\s+(" + "|".join(_WORD_NUMS.keys()) + r")\b",
    re.IGNORECASE,
)

_NUMERIC_SEAT_RE = re.compile(
    r"\b(District|Ward|Seat)\s+(?:Number\s+)?(\d+)\b",
    re.IGNORECASE,
)
_PREFIX_DISTRICT_RE = re.compile(
    r"^District\s+(?:Number\s+)?(\d+)\b",
    re.IGNORECASE,
)
_AT_LARGE_RE = re.compile(r"\bAt[\s-]?Large\b", re.IGNORECASE)
_MAYOR_PRO_TEM_RE = re.compile(r"^Mayor\s+Pro[\s-]?Tem\b", re.IGNORECASE)
_MAYOR_RE = re.compile(r"^Mayor\b", re.IGNORECASE)


def _parse_title(title: str) -> dict:
    """Extract structured seat fields from a free-text title.

    Returns a dict of fields the title could determine. Does not set
    seatSource — the caller decides that based on whether the title
    parse actually contributed.
    """
    out = {}
    if not title:
        return out

    # Mayor Pro Tem must beat Mayor (more specific prefix wins)
    if _MAYOR_PRO_TEM_RE.match(title):
        out["office"] = "council-member"
        out["leadership"] = "mayor-pro-tem"
        # Continue parsing for embedded seat (e.g., "Mayor Pro Tem, District 2")
    elif _MAYOR_RE.match(title):
        out["office"] = "mayor"
        out["leadership"] = None
        out["seatClass"] = "at-large"
        out["seatLabel"] = None
        out["seatId"] = None
        return out

    # At-large beats incidental numeric matches (e.g. "Council Member 1, At-Large")
    if _AT_LARGE_RE.search(title):
        out["seatClass"] = "at-large"
        out["seatLabel"] = None
        out["seatId"] = None
        return out

    # Prefix form: "District Number 3 - Councilman"
    m = _PREFIX_DISTRICT_RE.match(title)
    if m:
        out["seatClass"] = "numbered"
        out["seatLabel"] = "district"
        out["seatId"] = m.group(1)
        return out

    # Embedded form: "Council Member, District 17" / "Ward 3" / "Seat 5"
    m = _NUMERIC_SEAT_RE.search(title)
    if m:
        out["seatClass"] = "numbered"
        out["seatLabel"] = m.group(1).lower()
        out["seatId"] = m.group(2)
        return out

    # Word-form: "District One" / "Ward Four" / "District Twelve"
    m = _WORD_SEAT_RE.search(title)
    if m:
        out["seatClass"] = "numbered"
        out["seatLabel"] = m.group(1).lower()
        out["seatId"] = _WORD_NUMS[m.group(2).lower()]
        return out

    return out


def normalize_member(record: dict, ctx: NormalizationContext) -> dict:
    """Fill missing structured seat fields on a member record.

    Four-stage precedence (see design doc §"Layered precedence"):
        1. Explicit source fields (gap-fill, highest non-override)
        2. Title parsing (gap-fill)
        3. Registry defaults (gap-fill, only for unknown seatClass)
        4. Manual overrides (override-anything)

    Returns the same dict, mutated in place.
    """
    title = record.get("title", "") or ""

    # Stage 2: title parsing fills any structured fields not already set
    parsed = _parse_title(title)
    filled_from_parse = False
    for field in ("office", "leadership", "seatClass", "seatLabel", "seatId"):
        if field not in record and field in parsed:
            record[field] = parsed[field]
            filled_from_parse = True

    if filled_from_parse and "seatSource" not in record:
        record["seatSource"] = "parsed-title"

    return record
