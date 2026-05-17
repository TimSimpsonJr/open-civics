---
codex_thread_id: 019e311a-c877-7453-9cd1-f72a038f3c99
codex_plan_review_status: approved
codex_plan_review_approved_hash: 527168a1ca18f72726405981bdf30a3bc03a1235c444c4c418b7fb79b4b2ec37
codex_plan_review_rounds: 4
---

# Data Model Normalization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Promote seat semantics (office, leadership, seatClass, seatLabel, seatId, vacant, seatSource, partisan) from buried free-text titles to structured fields across every member record in open-civics, and remove the consumer's runtime title-parsing in deflocksc-website. Additive migration — keep all existing fields.

**Architecture:** New shared `scrapers/normalize.py` module called from both `BaseAdapter.normalize()` (locals) and `scrapers/state.py` (state legislators + executive). Per-record overrides in `scrapers/seat_overrides.py`. Jurisdiction-wide defaults in `registry.json`'s new `councilDefaults` block. One-shot `scripts/backfill_normalized_fields.py` regenerates existing data without re-scraping. NPM minor bump to 0.2.0. Coordinated dual-repo PRs with explicit publish-trigger gate.

**Tech Stack:** Python 3.12+ (open-civics), TypeScript/Astro (deflocksc-website), pytest, GitHub Actions, npm.

**Design doc:** [`docs/plans/2026-05-16-data-model-normalization-design.md`](2026-05-16-data-model-normalization-design.md) — read this first for full context, rationale, and the adversarial review history.

**Total tasks:** 26 — Phase A (17) in open-civics, Phase B (3) coordination, Phase C (6) in deflocksc-website.

---

## Phase A — open-civics PR

All Phase A work happens in the `open-civics` repo on a new branch `data-model-normalization`. Do not merge to master until every Phase A task is complete and the design's success criteria pass.

```bash
cd C:/Users/tim/OneDrive/Documents/Projects/open-civics
git checkout -b data-model-normalization
```

### Task A1: Skeleton normalize module

**Files:**
- Create: `scrapers/normalize.py`
- Create: `tests/unit/test_normalize.py`

**Step 1: Write the failing test**

In `tests/unit/test_normalize.py`:

```python
"""Unit tests for scrapers.normalize."""

from scrapers.normalize import normalize_member, NormalizationContext


def test_normalize_member_idempotent_when_fields_already_set():
    record = {
        "name": "Joey Russo",
        "title": "Council Member, District 17",
        "office": "council-member",
        "leadership": None,
        "seatClass": "numbered",
        "seatLabel": "district",
        "seatId": "17",
        "vacant": False,
        "seatSource": "source",
        "partisan": False,
    }
    ctx = NormalizationContext(level="local", jurisdiction_type="county",
                               jurisdiction_id="county:greenville")
    out = normalize_member(record, ctx)
    # Idempotent: pre-set structured fields preserved exactly
    assert out["office"] == "council-member"
    assert out["seatId"] == "17"
    assert out["seatSource"] == "source"
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/unit/test_normalize.py -v
```
Expected: `ImportError: cannot import name 'normalize_member' from 'scrapers.normalize'`.

**Step 3: Write minimal implementation**

In `scrapers/normalize.py`:

```python
"""Centralized normalization of seat semantics into structured fields.

Called from both BaseAdapter.normalize() (locals) and scrapers/state.py
(state legislators and executive) so the same logic produces the same
structured fields regardless of source.

See docs/plans/2026-05-16-data-model-normalization-design.md for the
schema definition and the four-stage precedence model.
"""

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


def normalize_member(record: dict, ctx: NormalizationContext) -> dict:
    """Fill missing structured seat fields on a member record.

    Four-stage precedence (see design doc §"Layered precedence"):
        1. Explicit source fields (gap-fill, highest non-override)
        2. Title parsing (gap-fill)
        3. Registry defaults (gap-fill, only for unknown seatClass)
        4. Manual overrides (override-anything)

    Returns the same dict, mutated in place.
    """
    # Stage 1: explicit source fields are already on the record. Nothing to do.
    # Stages 2-4 are implemented in subsequent tasks.
    return record
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/unit/test_normalize.py -v
```
Expected: PASS.

**Step 5: Commit**

```bash
git add scrapers/normalize.py tests/unit/test_normalize.py
git commit -m "feat: add normalize module skeleton with NormalizationContext"
```

---

### Task A2: Title parsing — numeric districts

**Files:**
- Modify: `scrapers/normalize.py`
- Modify: `tests/unit/test_normalize.py`

**Step 1: Write the failing tests**

Append to `tests/unit/test_normalize.py`:

```python
import pytest


@pytest.mark.parametrize("title, expected_class, expected_label, expected_id", [
    ("Council Member, District 17", "numbered", "district", "17"),
    ("Council Member, Ward 3", "numbered", "ward", "3"),
    ("Council Member, Seat 5", "numbered", "seat", "5"),
    ("District Number 3 - Councilman", "numbered", "district", "3"),
    ("Council Member, District 10", "numbered", "district", "10"),
])
def test_title_parsing_numeric_districts(title, expected_class, expected_label, expected_id):
    record = {"name": "Test", "title": title}
    ctx = NormalizationContext(level="local", jurisdiction_type="place",
                               jurisdiction_id="place:test")
    out = normalize_member(record, ctx)
    assert out["seatClass"] == expected_class
    assert out["seatLabel"] == expected_label
    assert out["seatId"] == expected_id
    assert out["seatSource"] == "parsed-title"
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_normalize.py::test_title_parsing_numeric_districts -v
```
Expected: 5 failures, all KeyError on `seatClass`.

**Step 3: Implement title parsing**

In `scrapers/normalize.py`, add:

```python
import re

# Stage 2: title parsing patterns
_NUMERIC_SEAT_RE = re.compile(
    r"\b(District|Ward|Seat)\s+(?:Number\s+)?(\d+)\b",
    re.IGNORECASE,
)
_PREFIX_DISTRICT_RE = re.compile(
    r"^District\s+(?:Number\s+)?(\d+)\b",
    re.IGNORECASE,
)


def _parse_title(title: str) -> dict:
    """Extract structured seat fields from a free-text title.

    Returns a dict of fields the title could determine. Does not set
    seatSource — the caller decides that based on whether the title
    parse actually contributed.
    """
    out = {}
    if not title:
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

    return out
```

Update `normalize_member` to call it (stage 2):

```python
def normalize_member(record: dict, ctx: NormalizationContext) -> dict:
    title = record.get("title", "") or ""

    # Stage 2: title parsing fills any structured fields not already set
    parsed = _parse_title(title)
    filled_from_parse = False
    for field in ("seatClass", "seatLabel", "seatId"):
        if field not in record and field in parsed:
            record[field] = parsed[field]
            filled_from_parse = True

    if filled_from_parse and "seatSource" not in record:
        record["seatSource"] = "parsed-title"

    return record
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/unit/test_normalize.py -v
```
Expected: all PASS.

**Step 5: Commit**

```bash
git add scrapers/normalize.py tests/unit/test_normalize.py
git commit -m "feat: parse numeric district/ward/seat from titles"
```

---

### Task A3: Title parsing — word-form numbers

**Files:** same as A2.

**Step 1: Write the failing tests**

Append:

```python
@pytest.mark.parametrize("title, expected_id", [
    ("Council Member, District One", "1"),
    ("Council Member, District Two", "2"),
    ("Council Member, District Three", "3"),
    ("Council Member, Ward Four", "4"),
    ("Council Member, District Twelve", "12"),
])
def test_title_parsing_word_form_numbers(title, expected_id):
    record = {"name": "Test", "title": title}
    ctx = NormalizationContext(level="local", jurisdiction_type="place",
                               jurisdiction_id="place:test")
    out = normalize_member(record, ctx)
    assert out["seatClass"] == "numbered"
    assert out["seatId"] == expected_id
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_normalize.py::test_title_parsing_word_form_numbers -v
```
Expected: 5 failures.

**Step 3: Implement word-form support**

In `scrapers/normalize.py`, add above the regex:

```python
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
```

In `_parse_title`, after the embedded numeric match attempt, add:

```python
    # Word-form: "District One" / "Ward Four" / "District Twelve"
    m = _WORD_SEAT_RE.search(title)
    if m:
        out["seatClass"] = "numbered"
        out["seatLabel"] = m.group(1).lower()
        out["seatId"] = _WORD_NUMS[m.group(2).lower()]
        return out
```

**Step 4: Verify**

```bash
pytest tests/unit/test_normalize.py -v
```
Expected: all PASS.

**Step 5: Commit**

```bash
git add scrapers/normalize.py tests/unit/test_normalize.py
git commit -m "feat: parse word-form district numbers (One through Twenty)"
```

---

### Task A4: Title parsing — at-large variants

**Files:** same as A2.

**Step 1: Write the failing tests**

```python
@pytest.mark.parametrize("title", [
    "Council Member, At Large",
    "Council Member, At-Large",
    "Vice Chair, At-Large",
    "Mayor Pro Tem, At Large",
])
def test_title_parsing_at_large(title):
    record = {"name": "Test", "title": title}
    ctx = NormalizationContext(level="local", jurisdiction_type="place",
                               jurisdiction_id="place:test")
    out = normalize_member(record, ctx)
    assert out["seatClass"] == "at-large"
    assert out["seatLabel"] is None
    assert out["seatId"] is None
```

**Step 2: Run tests to verify they fail**

Expected: 4 failures.

**Step 3: Implement**

In `scrapers/normalize.py`, add regex:

```python
_AT_LARGE_RE = re.compile(r"\bAt[\s-]?Large\b", re.IGNORECASE)
```

In `_parse_title`, BEFORE the numeric checks (so at-large beats incidental "1" matches), add:

```python
    if _AT_LARGE_RE.search(title):
        out["seatClass"] = "at-large"
        out["seatLabel"] = None
        out["seatId"] = None
        return out
```

Update the gap-fill loop in `normalize_member` to handle null values:

```python
    for field in ("seatClass", "seatLabel", "seatId"):
        if field not in record and field in parsed:
            record[field] = parsed[field]
            filled_from_parse = True
```

(Already correct — `field in parsed` is True even when value is None.)

**Step 4: Verify**

```bash
pytest tests/unit/test_normalize.py -v
```

**Step 5: Commit**

```bash
git commit -am "feat: parse at-large variants in titles"
```

---

### Task A5: Title parsing — Mayor and Mayor Pro Tem

**Files:** same as A2.

**Step 1: Write the failing tests**

```python
def test_title_parsing_mayor():
    record = {"name": "Knox White", "title": "Mayor"}
    ctx = NormalizationContext(level="local", jurisdiction_type="place",
                               jurisdiction_id="place:greenville")
    out = normalize_member(record, ctx)
    assert out["office"] == "mayor"
    assert out["leadership"] is None
    assert out["seatClass"] == "at-large"
    assert out["seatLabel"] is None
    assert out["seatId"] is None


@pytest.mark.parametrize("title, expected_seat_id", [
    ("Mayor Pro Tem", None),
    ("Mayor Pro-Tem", None),
    ("Mayor Pro Tem, District 2", "2"),
])
def test_title_parsing_mayor_pro_tem(title, expected_seat_id):
    record = {"name": "Test", "title": title}
    ctx = NormalizationContext(level="local", jurisdiction_type="place",
                               jurisdiction_id="place:test")
    out = normalize_member(record, ctx)
    assert out["office"] == "council-member"
    assert out["leadership"] == "mayor-pro-tem"
    assert out["seatId"] == expected_seat_id
```

**Step 2: Run tests to verify they fail**

Expected: 4 failures.

**Step 3: Implement**

In `scrapers/normalize.py`:

```python
_MAYOR_PRO_TEM_RE = re.compile(r"^Mayor\s+Pro[\s-]?Tem\b", re.IGNORECASE)
_MAYOR_RE = re.compile(r"^Mayor\b", re.IGNORECASE)
```

In `_parse_title`, BEFORE the at-large check, add:

```python
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
```

(Mayor Pro Tem falls through so the at-large / numeric / word checks below can fill seat fields.)

Update gap-fill loop to handle `office` and `leadership`:

```python
    for field in ("office", "leadership", "seatClass", "seatLabel", "seatId"):
        if field not in record and field in parsed:
            record[field] = parsed[field]
            filled_from_parse = True
```

**Step 4: Verify**

```bash
pytest tests/unit/test_normalize.py -v
```

**Step 5: Commit**

```bash
git commit -am "feat: parse Mayor and Mayor Pro Tem from titles"
```

**Note on bare "Mayor Pro Tem" / "Mayor Pro-Tem" cases:** The plan originally listed these in the A5 parametrize test, but they require A7's leadership-only fallback to populate seat fields with `seatClass: unknown`. They have been moved to A7's test set. The A5 commit only covers the "with embedded district" case.

---

### Task A6: Title parsing — Chairman and Vice Chairman

**Files:** same as A2.

**Step 1: Write the failing tests**

```python
@pytest.mark.parametrize("title, expected_leadership, expected_seat_id", [
    ("Chairman, District 4", "chair", "4"),
    ("Vice Chairman, District 3", "vice-chair", "3"),
])
def test_title_parsing_leadership(title, expected_leadership, expected_seat_id):
    record = {"name": "Test", "title": title}
    ctx = NormalizationContext(level="local", jurisdiction_type="county",
                               jurisdiction_id="county:test")
    out = normalize_member(record, ctx)
    assert out["office"] == "council-member"
    assert out["leadership"] == expected_leadership
    assert out["seatId"] == expected_seat_id
```

**Step 2: Run tests to verify they fail**

Expected: 2 failures.

**Step 3: Implement**

In `_parse_title`, AFTER the Mayor Pro Tem block, add:

```python
    # Vice Chair must beat Chair (more specific prefix wins)
    if re.search(r"\bVice[\s-]?Chair(?:man)?\b", title, re.IGNORECASE):
        out["office"] = "council-member"
        out["leadership"] = "vice-chair"
        # Fall through for embedded seat
    elif re.search(r"\bChair(?:man)?\b", title, re.IGNORECASE):
        out["office"] = "council-member"
        out["leadership"] = "chair"
        # Fall through for embedded seat
```

**Step 4: Verify**

```bash
pytest tests/unit/test_normalize.py -v
```

**Step 5: Commit**

```bash
git commit -am "feat: parse Chair / Vice Chair leadership from titles"
```

**Note on bare leadership-only cases:** The plan originally listed "Chairman", "Chair", "Vice Chairman", "Vice Chair" (no embedded district) in A6's parametrize, but they require A7's leadership-only fallback to populate seat fields with `seatClass: unknown`. They have been moved to A7's `test_leadership_only_titles_get_unknown_seat_class` parametrize. The A6 commit only covers the "with embedded district" cases.

---

### Task A7: Title parsing — plain council member and leadership-only fallback

**Files:** same as A2.

This task closes the **chair-seatclass-gap** found in plan review: when a title is just "Chairman" or "Vice Chairman" with no embedded seat, Task A6 only sets `office`/`leadership` and leaves `seatClass` unset, which the validator (A16) requires. The fallback below also handles plain "Council Member" titles.

**Step 1: Write the failing tests**

```python
@pytest.mark.parametrize("title", [
    "Council Member",
    "Councilman",
    "Town Council Member",
    "",
])
def test_title_parsing_plain_council_member(title):
    record = {"name": "Test", "title": title}
    ctx = NormalizationContext(level="local", jurisdiction_type="place",
                               jurisdiction_id="place:test")
    out = normalize_member(record, ctx)
    assert out["office"] == "council-member"
    assert out["leadership"] is None
    assert out["seatClass"] == "unknown"
    assert out["seatLabel"] is None
    assert out["seatId"] is None


@pytest.mark.parametrize("title, expected_leadership", [
    ("Chairman", "chair"),
    ("Chair", "chair"),
    ("Vice Chairman", "vice-chair"),
    ("Vice Chair", "vice-chair"),
    ("Mayor Pro Tem", "mayor-pro-tem"),
    ("Mayor Pro-Tem", "mayor-pro-tem"),
])
def test_leadership_only_titles_get_unknown_seat_class(title, expected_leadership):
    """Chairman / Vice Chairman / Mayor Pro Tem with no embedded seat: leadership set, seat unknown."""
    record = {"name": "Test", "title": title}
    ctx = NormalizationContext(level="local", jurisdiction_type="county",
                               jurisdiction_id="county:test")
    out = normalize_member(record, ctx)
    assert out["office"] == "council-member"
    assert out["leadership"] == expected_leadership
    assert out["seatClass"] == "unknown"
    assert out["seatLabel"] is None
    assert out["seatId"] is None
```

**Step 2: Run tests to verify they fail**

Expected: 10 failures (6 leadership-only + 4 plain-council-member).

**Step 3: Implement**

In `_parse_title`, AFTER all other patterns, add the final fallback. The condition is broader than "out is empty" — it must also catch the case where A6 set office/leadership but no seat fields:

```python
    # Default seat fields when title yielded an office but no seat info.
    # This catches "Chairman" / "Vice Chairman" / "Mayor Pro Tem" with no
    # embedded district, and the plain "Council Member" case below.
    if "seatClass" not in out:
        if "office" not in out:
            # Title is empty, plain "Council Member", or otherwise unrecognized.
            # Default to council-member with unknown seat.
            if re.search(r"council(?:man)?", title, re.IGNORECASE) or not title:
                out["office"] = "council-member"
                out["leadership"] = None
        # Whether office was set above or by A6, fill seat fields as unknown.
        if "office" in out:
            out["seatClass"] = "unknown"
            out["seatLabel"] = None
            out["seatId"] = None
```

Also ensure `leadership` is set when office is set:

```python
    # If we set office but no leadership, leadership defaults to None
    if "office" in out and "leadership" not in out:
        out["leadership"] = None
```

**Step 4: Verify**

```bash
pytest tests/unit/test_normalize.py -v
```
Expected: all PASS, including the new `test_leadership_only_titles_get_unknown_seat_class`.

**Step 5: Commit**

```bash
git commit -am "feat: default seatClass=unknown for leadership-only titles"
```

---

### Task A8: Vacancy detection from name

**Files:** same as A2.

**Step 1: Write the failing tests**

```python
@pytest.mark.parametrize("name, expected_vacant, expected_seat_id", [
    ("Vacant", True, None),
    ("Vacant District 5", True, "5"),
    ("vacant district 7", True, "7"),
    ("Joey Russo", False, None),
])
def test_vacancy_detection(name, expected_vacant, expected_seat_id):
    record = {"name": name, "title": "Council Member"}
    ctx = NormalizationContext(level="local", jurisdiction_type="place",
                               jurisdiction_id="place:test")
    out = normalize_member(record, ctx)
    assert out["vacant"] == expected_vacant
    if expected_seat_id is not None:
        assert out["seatId"] == expected_seat_id
```

**Step 2: Run tests to verify they fail**

Expected: 4 failures.

**Step 3: Implement**

In `scrapers/normalize.py`:

```python
_VACANT_RE = re.compile(r"^Vacant\b\s*(.*)$", re.IGNORECASE)
```

In `normalize_member`, BEFORE the title-parse stage, add:

```python
    # Vacancy detection: if name starts with "Vacant", set vacant=True and
    # parse the rest of the name as a synthetic title for seat extraction.
    name = record.get("name", "") or ""
    m = _VACANT_RE.match(name)
    if m:
        record["vacant"] = True
        remainder = m.group(1).strip()
        if remainder and not record.get("title"):
            # If no real title, treat the name remainder as the title
            title = remainder
        elif remainder and (record.get("title", "").strip() in ("", "Council Member")):
            # Title is empty or generic — let the name remainder fill seat fields
            title = remainder
        else:
            title = record.get("title", "") or ""
    else:
        record.setdefault("vacant", False)
        title = record.get("title", "") or ""
```

Replace the `title = record.get("title", "") or ""` line at the top of the function with this block.

**Step 4: Verify**

```bash
pytest tests/unit/test_normalize.py -v
```

**Step 5: Commit**

```bash
git commit -am "feat: detect vacancies from name prefix"
```

---

### Task A9: Registry defaults (stage 3 precedence)

**Files:** same as A2.

**Step 1: Write the failing tests**

```python
def test_registry_defaults_promote_unknown_to_at_large():
    record = {"name": "Teddy W. Milner", "title": "Council Member"}
    ctx = NormalizationContext(
        level="local",
        jurisdiction_type="place",
        jurisdiction_id="place:aiken",
        registry_hints={"seatClass": "at-large", "partisan": False},
    )
    out = normalize_member(record, ctx)
    assert out["seatClass"] == "at-large"
    assert out["seatLabel"] is None
    assert out["seatId"] is None
    assert out["seatSource"] == "inferred-registry"
    assert out["partisan"] is False


def test_registry_defaults_do_not_overwrite_numbered_seat():
    """Registry hint of at-large should NOT swallow a member whose title says District N."""
    record = {"name": "Test", "title": "Council Member, District 3"}
    ctx = NormalizationContext(
        level="local",
        jurisdiction_type="place",
        jurisdiction_id="place:somewhere",
        registry_hints={"seatClass": "at-large"},
    )
    out = normalize_member(record, ctx)
    assert out["seatClass"] == "numbered"
    assert out["seatId"] == "3"
    assert out["seatSource"] == "parsed-title"
```

**Step 2: Run tests to verify they fail**

Expected: 2 failures.

**Step 3: Implement stage 3**

In `normalize_member`, AFTER the title-parse stage and BEFORE returning, add:

```python
    # Stage 3: registry defaults fill remaining unknown fields only
    hints = ctx.registry_hints or {}
    promoted_from_registry = False

    if record.get("seatClass") == "unknown" and hints.get("seatClass"):
        record["seatClass"] = hints["seatClass"]
        if hints["seatClass"] == "at-large":
            record["seatLabel"] = None
            record["seatId"] = None
        promoted_from_registry = True

    if "partisan" not in record and "partisan" in hints:
        record["partisan"] = hints["partisan"]

    if promoted_from_registry:
        record["seatSource"] = "inferred-registry"
```

**Step 4: Verify**

```bash
pytest tests/unit/test_normalize.py -v
```

**Step 5: Commit**

```bash
git commit -am "feat: apply registry councilDefaults to fill unknown seats"
```

---

### Task A10: Manual overrides (stage 4 precedence)

**Files:**
- Create: `scrapers/seat_overrides.py`
- Modify: `scrapers/normalize.py`
- Modify: `tests/unit/test_normalize.py`

**Step 1: Write the failing tests**

```python
def test_manual_override_replaces_parsed_value():
    # Adapter set seatClass: unknown from parsed title; manual override fixes it
    record = {"name": "Alex Saitta", "title": "Chairman"}
    ctx = NormalizationContext(
        level="local",
        jurisdiction_type="county",
        jurisdiction_id="county:pickens",
    )
    out = normalize_member(record, ctx)
    # With the override in place, the chairman gets their actual district
    assert out["seatClass"] == "numbered"
    assert out["seatLabel"] == "district"
    assert out["seatId"] == "1"
    assert out["seatSource"] == "manual"
```

**Step 2: Run test to verify it fails**

Expected: 1 failure.

**Step 3: Create overrides table**

In `scrapers/seat_overrides.py`:

```python
"""Per-record manual overrides for seat fields.

Keyed by (jurisdiction_id, member_name). Use this when:
- The source publishes wrong or missing structured data
- Title parsing produces a wrong value the registry hint can't fix
- A specific record needs a hand-curated patch

This is the only stage of the normalization precedence chain that
OVERWRITES existing structured values. Every entry should be reviewed
periodically; if a source becomes parseable, remove the override.

Schema: dict[(jurisdiction_id, name)] = {field: value, ...}
The normalizer applies these last and sets seatSource: "manual".
"""

SEAT_OVERRIDES: dict[tuple[str, str], dict] = {
    # Example: a Pickens County chairman whose title overwrites their district seat.
    # Add real entries here as they're discovered during regen.
    # ("county:pickens", "Alex Saitta"): {
    #     "seatClass": "numbered",
    #     "seatLabel": "district",
    #     "seatId": "1",
    # },
}
```

(Leave the example commented for now — the test will add it.)

**Step 4: Wire stage 4 into normalize_member**

In `scrapers/normalize.py`, add at top:

```python
from .seat_overrides import SEAT_OVERRIDES
```

In `normalize_member`, AFTER stage 3 and BEFORE returning, add:

```python
    # Stage 4: manual overrides — the ONLY stage that overwrites existing values
    if ctx.jurisdiction_id:
        key = (ctx.jurisdiction_id, record.get("name", ""))
        override = SEAT_OVERRIDES.get(key)
        if override:
            for field, value in override.items():
                record[field] = value
            record["seatSource"] = "manual"
```

**Step 5: Add the actual override for the test**

In `scrapers/seat_overrides.py`, uncomment the Pickens entry:

```python
SEAT_OVERRIDES: dict[tuple[str, str], dict] = {
    ("county:pickens", "Alex Saitta"): {
        "seatClass": "numbered",
        "seatLabel": "district",
        "seatId": "1",
    },
}
```

(NOTE to executor: verify Saitta's actual district by reading the Pickens County council page before committing. Don't ship a fictional override. If district unknown, use a different real example or remove the test.)

**Step 6: Verify**

```bash
pytest tests/unit/test_normalize.py -v
```

**Step 7: Commit**

```bash
git add scrapers/normalize.py scrapers/seat_overrides.py tests/unit/test_normalize.py
git commit -m "feat: add seat_overrides.py with stage-4 override semantics"
```

---

### Task A11: Default partisan + leadership defaults

**Files:** same as A2.

**Step 1: Write the failing tests**

```python
def test_partisan_default_state():
    record = {"name": "Shane Massey", "title": "State Senator, District 25",
              "office": "state-senator"}
    ctx = NormalizationContext(level="state", chamber="senate")
    out = normalize_member(record, ctx)
    assert out["partisan"] is True


def test_partisan_default_local():
    record = {"name": "Joey Russo", "title": "Council Member, District 17"}
    ctx = NormalizationContext(level="local", jurisdiction_type="county",
                               jurisdiction_id="county:greenville")
    out = normalize_member(record, ctx)
    assert out["partisan"] is False


def test_leadership_defaults_to_null():
    record = {"name": "Test", "title": "Council Member, District 1"}
    ctx = NormalizationContext(level="local", jurisdiction_type="place",
                               jurisdiction_id="place:test")
    out = normalize_member(record, ctx)
    assert out["leadership"] is None
```

**Step 2: Run tests to verify they fail**

Expected: 3 failures (partisan unset).

**Step 3: Implement defaults**

In `normalize_member`, AFTER stage 4 and BEFORE returning, add final defaults:

```python
    # Final defaults: ensure all required fields are set
    record.setdefault("leadership", None)
    record.setdefault("vacant", False)
    if "partisan" not in record:
        record["partisan"] = True if ctx.level == "state" else False
    # office must be set somewhere — if not, infer from level/chamber
    if "office" not in record:
        if ctx.level == "state":
            if ctx.chamber == "senate":
                record["office"] = "state-senator"
            elif ctx.chamber == "house":
                record["office"] = "state-representative"
        # local default already filled by title parse fallback
    # seatSource fallback if nothing set it
    record.setdefault("seatSource", "source")
```

**Step 4: Verify**

```bash
pytest tests/unit/test_normalize.py -v
```

**Step 5: Commit**

```bash
git commit -am "feat: add final defaults for leadership, vacant, partisan, office"
```

---

### Task A12: Wire normalizer into BaseAdapter

**Files:**
- Modify: `scrapers/adapters/base.py`
- Modify: `tests/unit/test_base_adapter.py`

**Step 1: Read the current BaseAdapter.normalize()**

Read lines 60–75 of `scrapers/adapters/base.py` to see the existing implementation. Cross-platform:

```bash
python -c "print(''.join(open('scrapers/adapters/base.py').readlines()[59:75]))"
```

Currently:
```python
def normalize(self, raw: list[dict]) -> list[dict]:
    today = date.today().isoformat()
    for record in raw:
        record.setdefault("source", self.adapter_name())
        record.setdefault("lastUpdated", today)
        if record.get("phone"):
            record["phone"] = normalize_phone(record["phone"])
    return raw
```

**Step 2: Write failing test in `tests/unit/test_base_adapter.py`**

Append:

```python
def test_base_adapter_normalize_calls_normalize_member():
    """BaseAdapter.normalize should populate structured seat fields."""
    from scrapers.adapters.base import BaseAdapter

    class DummyAdapter(BaseAdapter):
        def fetch(self): return ""
        def parse(self, html): return []

    adapter = DummyAdapter({"id": "place:test", "url": "http://example.com",
                            "type": "place"})
    raw = [{"name": "Joey Russo", "title": "Council Member, District 17",
            "email": "x@y.com", "phone": "8645551234"}]
    out = adapter.normalize(raw)
    assert out[0]["office"] == "council-member"
    assert out[0]["seatClass"] == "numbered"
    assert out[0]["seatId"] == "17"
    assert out[0]["vacant"] is False
    assert out[0]["partisan"] is False
```

**Step 3: Run test to verify it fails**

Expected: KeyError on `office`.

**Step 4: Wire normalizer**

Modify `scrapers/adapters/base.py` `normalize` method:

```python
from ..normalize import normalize_member, NormalizationContext

def normalize(self, raw: list[dict]) -> list[dict]:
    today = date.today().isoformat()
    jid = self.entry.get("id", "")
    jtype = "county" if jid.startswith("county:") else "place" if jid.startswith("place:") else None
    hints = self.entry.get("councilDefaults")
    ctx = NormalizationContext(
        level="local",
        jurisdiction_type=jtype,
        jurisdiction_id=jid,
        registry_hints=hints,
    )
    for record in raw:
        record.setdefault("source", self.adapter_name())
        record.setdefault("lastUpdated", today)
        if record.get("phone"):
            record["phone"] = normalize_phone(record["phone"])
        normalize_member(record, ctx)
    return raw
```

**Step 5: Verify**

```bash
pytest tests/unit/test_base_adapter.py tests/unit/test_normalize.py -v
```

**Step 6: Commit**

```bash
git commit -am "feat: wire normalize_member into BaseAdapter.normalize"
```

---

### Task A13: Wire normalizer into scrapers/state.py

**Files:**
- Modify: `scrapers/state.py`
- Modify: `tests/unit/test_state_helpers.py`

**Step 1: Write failing tests**

Append to `tests/unit/test_state_helpers.py`:

```python
from scrapers.state import normalize_row


def test_normalize_row_synthesizes_title_for_senate():
    row = {
        "name": "Shane Massey",
        "current_district": "25",
        "current_chamber": "upper",
        "current_party": "Republican",
        "capitol_voice": "803-212-6330",
    }
    rec = normalize_row(row, chamber="upper")
    assert rec["title"] == "State Senator, District 25"
    assert rec["office"] == "state-senator"
    assert rec["seatClass"] == "numbered"
    assert rec["seatLabel"] == "district"
    assert rec["seatId"] == "25"
    assert rec["partisan"] is True
    assert rec["vacant"] is False


def test_normalize_row_synthesizes_title_for_house():
    row = {
        "name": "Bill Hager",
        "current_district": "122",
        "current_chamber": "lower",
        "current_party": "Republican",
        "capitol_voice": "",
    }
    rec = normalize_row(row, chamber="lower")
    assert rec["title"] == "State Representative, District 122"
    assert rec["office"] == "state-representative"
```

**Step 2: Run tests to verify they fail**

Expected: failures — `normalize_row` doesn't accept `chamber` and doesn't set `title`/`office`.

**Step 3: Modify normalize_row**

This task closes the **state-source-provenance** gap from plan review: state legislators have a structured `current_district` column in the OpenStates CSV, so `seatClass`/`seatLabel`/`seatId` should be set from that column directly as stage-1 source data — not re-parsed from the synthesized title (which would tag them `parsed-title` instead of `source`).

In `scrapers/state.py`, modify `normalize_row`:

```python
from .normalize import normalize_member, NormalizationContext


def normalize_row(row: dict, chamber: str = "") -> dict:
    """Convert an OpenStates CSV row to our unified schema."""
    district = row.get("current_district", "").strip()
    office_map = {"upper": "state-senator", "lower": "state-representative"}
    office = office_map.get(chamber, "")
    title_map = {
        "upper": f"State Senator, District {district}",
        "lower": f"State Representative, District {district}",
    }
    record = {
        "name": row.get("name", "").strip(),
        "title": title_map.get(chamber, ""),
        "office": office,
        "district": district,                  # legacy alias of seatId
        # Stage-1 structured seat fields from the OpenStates CSV column.
        # Tagging seatSource: "source" tells the normalizer not to re-derive.
        "seatClass": "numbered" if district else "unknown",
        "seatLabel": "district" if district else None,
        "seatId": district if district else None,
        "seatSource": "source",
        "leadership": None,
        "vacant": False,
        "partisan": True,
        "party": _abbreviate_party(row.get("current_party", "")),
        "email": row.get("email", "").strip(),
        "phone": normalize_phone(row.get("capitol_voice", "")),
        "photoUrl": row.get("image", "").strip(),
        "website": _first_link(row.get("links", "")),
        "source": "openstates",
        "lastUpdated": date.today().isoformat(),
    }

    # Optional social media fields
    if row.get("twitter", "").strip():
        record["twitter"] = row["twitter"].strip()
    if row.get("facebook", "").strip():
        record["facebook"] = row["facebook"].strip()

    # Apply normalization. With all stage-1 fields already set, normalize_member
    # is effectively a no-op on the seat fields here — it just applies any
    # final defaults the dict didn't pre-populate.
    chamber_norm = {"upper": "senate", "lower": "house"}.get(chamber)
    ctx = NormalizationContext(level="state", chamber=chamber_norm)
    normalize_member(record, ctx)
    return record
```

Update the test in Step 1 to verify `seatSource == "source"` rather than `"parsed-title"`:

```python
def test_normalize_row_uses_structured_csv_columns_as_source():
    row = {
        "name": "Shane Massey",
        "current_district": "25",
        "current_chamber": "upper",
        "current_party": "Republican",
        "capitol_voice": "803-212-6330",
    }
    rec = normalize_row(row, chamber="upper")
    assert rec["seatSource"] == "source"  # stage-1 provenance
    assert rec["seatClass"] == "numbered"
    assert rec["seatId"] == "25"
```

Update the caller in `update_state_legislators` to pass `chamber`:

```python
# Find the existing call to normalize_row in scrapers/state.py and change:
#   record = normalize_row(row)
# to:
#   record = normalize_row(row, chamber=row.get("current_chamber", ""))
```

**Step 4: Wire normalize into executive**

In `scrapers/state.py` `scrape_executive()`, after building each executive dict, populate stage-1 seat fields and then normalize. This closes the **executive-normalize-drift** finding from plan review round 2: live scrape output must produce the same structured fields as the backfill path in Task A15 (which already pre-populates these).

```python
def scrape_executive(state_code: str) -> list[dict]:
    if state_code != "SC":
        print(f"  Executive scraping not implemented for {state_code}")
        return []

    def _preset_executive_fields(rec: dict, office: str):
        """Stage-1 seat field population for executive officers.

        Executive officers (Governor, Lt Governor) are categorically
        at-large statewide and partisan. Tagging seatSource: "source"
        because the structure is known from the office definition,
        not parsed from a title.
        """
        rec["office"] = office
        rec.setdefault("seatClass", "at-large")
        rec.setdefault("seatLabel", None)
        rec.setdefault("seatId", None)
        rec.setdefault("seatSource", "source")
        rec.setdefault("leadership", None)
        rec.setdefault("vacant", False)
        rec.setdefault("partisan", True)

    ctx = NormalizationContext(level="state", chamber="executive")
    executives = []
    gov = _scrape_sc_governor()
    if gov:
        _preset_executive_fields(gov, "governor")
        normalize_member(gov, ctx)
        executives.append(gov)
    lt_gov = _scrape_sc_lt_governor()
    if lt_gov:
        _preset_executive_fields(lt_gov, "lt-governor")
        normalize_member(lt_gov, ctx)
        executives.append(lt_gov)
    return executives
```

The `_preset_executive_fields` helper here mirrors the inline pre-population in Task A15's backfill script — both paths produce identical executive records.

**Step 5: Verify**

```bash
pytest tests/unit/test_state_helpers.py tests/unit/test_normalize.py -v
```

**Step 6: Commit**

```bash
git commit -am "feat: wire normalize_member into state.py for legislators and executive"
```

---

### Task A14: Add councilDefaults to registry.json (verified at-large only)

**Files:**
- Modify: `registry.json`

This task adds `councilDefaults: {seatClass: "at-large", partisan: false}` ONLY to jurisdictions whose own registry metadata confirms they are all-at-large.

**CRITICAL caveat from plan review:** the audit identified 28 jurisdictions where no member record had district info, but several of those entries (Aiken County, Berkeley, Kershaw, Jasper, place-aiken) are *districted per the registry's own `notes` field* — they appear without districts only because the fallback scraper (`scac` / `masc`) doesn't capture the source's district information. Flagging those as `at-large` would permanently hide a real scraper bug behind a config override. Do not include them.

**Step 1: Filter the seed list against registry metadata**

For each candidate jurisdiction from the audit, read its current entry in `registry.json`. If the `notes` field (or equivalent) describes single-member districts, wards, or seats, **exclude** it from this task. Add a follow-up issue to fix the scraper instead.

Run:

```bash
python -c "
import json
data = json.load(open('registry.json'))
audit = ['county:aiken','county:berkeley','county:dorchester','county:hampton',
         'county:jasper','county:kershaw','place:aiken','place:allendale',
         'place:beaufort','place:bishopville','place:camden','place:conway',
         'place:edgefield','place:georgetown','place:goose-creek','place:hampton',
         'place:lexington','place:manning','place:moncks-corner','place:mount-pleasant',
         'place:myrtle-beach','place:north-charleston','place:ridgeland','place:saluda',
         'place:st-matthews','place:union','place:walhalla','place:walterboro']
for j in data['states']['SC']['jurisdictions']:
    if j['id'] in audit:
        notes = j.get('notes', '')
        print(f'{j[\"id\"]:30} {notes[:80]}')
"
```

Manually classify each row:

- **DISTRICTED (exclude):** any entry whose `notes` mentions "single-member districts", "wards", "seats", "elected by district", or similar. File a follow-up issue: "Scraper drops district info for `<jid>` — `notes` says districted but data shows none."
- **AT-LARGE (include):** any entry whose `notes` explicitly says "elected at-large" or "no districts" or is silent and the jurisdiction is a small town where verifying the council's own website confirms at-large elections.
- **UNCLEAR (exclude, file investigation issue):** anything in between. Leave `seatClass: unknown` flowing through; the validator emits warnings, not errors, for unknowns.

**Step 2: Edit registry.json**

For each VERIFIED at-large jurisdiction in the `jurisdictions` array, add the block:

```json
{
  "id": "place:allendale",
  "name": "Allendale",
  "type": "place",
  ...,
  "councilDefaults": {
    "seatClass": "at-large",
    "partisan": false
  }
}
```

Do NOT mass-add this list. Add one jurisdiction at a time and verify against the registry `notes` before committing.

**Step 3: File a follow-up issue for districted-but-empty jurisdictions**

For each entry classified as DISTRICTED in Step 1, create one tracking issue:

```bash
gh issue create \
  --title "[scraper] Districted jurisdictions missing seat info in scraped data" \
  --body "$(cat <<'EOF'
The following jurisdictions' registry notes describe single-member districts, but the current adapter / fallback scraper does not capture district info into member records:

- county:aiken (registry: 8 single-member districts + chairman at-large)
- county:berkeley (registry: 7 single-member districts + county supervisor)
- county:jasper (registry: township districts)
- county:kershaw (registry: 6 single-member districts + chairman at-large)
- place:aiken (verify against registry)

Out of scope for the schema migration; tracked separately. After fix, members will have `seatClass: numbered` via normal title parsing without needing `councilDefaults`.
EOF
)" \
  --label "autonomous-safe"
```

**Step 4: Verify**

```bash
python -c "import json; data = json.load(open('registry.json')); print(sum(1 for j in data['states']['SC']['jurisdictions'] if 'councilDefaults' in j), 'jurisdictions with councilDefaults')"
```
Expected: matches the verified at-large count from Step 1 (typically smaller than 28).

**Step 5: Commit**

```bash
git add registry.json
git commit -m "feat: add councilDefaults to verified at-large jurisdictions in registry"
```

---

### Task A15: Write backfill script

**Files:**
- Create: `scripts/backfill_normalized_fields.py`

**Step 1: Write the script**

This script applies two plan-review fixes:
- **state-source-provenance**: state records pre-set `seatClass`/`seatLabel`/`seatId`/`seatSource: "source"` from the existing `district` field before calling `normalize_member`, so they're tagged as structured source data rather than re-parsed from the synthesized title.
- **backfill-metadata**: local files recompute `meta.dataHash` and update `meta.dataLastChanged` consistent with the existing scraper pipeline (see [`scrapers/__main__.py:294-314`](../../scrapers/__main__.py)). Adding the new structured fields IS a content change to the published JSON.

```python
"""One-shot script: backfill normalized seat fields into existing data files.

Walks data/{state}/state.json and data/{state}/local/*.json, applies
scrapers.normalize.normalize_member() to every record, and writes the
files back. Idempotent — safe to run repeatedly.

Run before npm publish so the published data has the new fields without
requiring a full re-scrape.

Usage:
    python scripts/backfill_normalized_fields.py
"""

import hashlib
import json
import os
import sys
from datetime import date

# Make scrapers importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapers.normalize import normalize_member, NormalizationContext


def load_registry():
    with open("registry.json", encoding="utf-8") as f:
        return json.load(f)


def _preset_state_seat_fields(rec: dict, office: str, chamber_label: str):
    """Pre-populate stage-1 seat fields from the existing structured district.

    Tagged seatSource: "source" because the district came from OpenStates'
    structured column originally (preserved across re-runs via record state).
    """
    district = (rec.get("district") or "").strip()
    rec.setdefault("title",
                   f"{chamber_label}, District {district}" if district else chamber_label)
    rec.setdefault("office", office)
    rec.setdefault("seatClass", "numbered" if district else "unknown")
    rec.setdefault("seatLabel", "district" if district else None)
    rec.setdefault("seatId", district if district else None)
    rec.setdefault("seatSource", "source")
    rec.setdefault("leadership", None)
    rec.setdefault("vacant", False)
    rec.setdefault("partisan", True)


def backfill_state(state_code: str):
    path = f"data/{state_code.lower()}/state.json"
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    # Senate
    ctx_senate = NormalizationContext(level="state", chamber="senate")
    for _district, rec in data.get("senate", {}).items():
        _preset_state_seat_fields(rec, "state-senator", "State Senator")
        normalize_member(rec, ctx_senate)

    # House
    ctx_house = NormalizationContext(level="state", chamber="house")
    for _district, rec in data.get("house", {}).items():
        _preset_state_seat_fields(rec, "state-representative", "State Representative")
        normalize_member(rec, ctx_house)

    # Executive — office inferred from existing title; partisan stays True
    ctx_exec = NormalizationContext(level="state", chamber="executive")
    for rec in data.get("executive", []):
        existing_title = rec.get("title", "").lower()
        if "lieutenant governor" in existing_title or "lt. gov" in existing_title:
            rec.setdefault("office", "lt-governor")
        elif "governor" in existing_title:
            rec.setdefault("office", "governor")
        rec.setdefault("seatClass", "at-large")
        rec.setdefault("seatLabel", None)
        rec.setdefault("seatId", None)
        rec.setdefault("seatSource", "source")
        rec.setdefault("leadership", None)
        rec.setdefault("vacant", False)
        rec.setdefault("partisan", True)
        normalize_member(rec, ctx_exec)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"  Backfilled {path}")


def backfill_local(state_code: str, registry: dict):
    local_dir = f"data/{state_code.lower()}/local"
    if not os.path.isdir(local_dir):
        return

    # Index registry by jurisdiction id for councilDefaults lookup
    state_data = registry.get("states", {}).get(state_code.upper(), {})
    j_index = {j["id"]: j for j in state_data.get("jurisdictions", [])}
    today = date.today().isoformat()

    for fname in sorted(os.listdir(local_dir)):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(local_dir, fname)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        jid = data.get("meta", {}).get("jurisdiction", "")
        jtype = "county" if jid.startswith("county:") else "place" if jid.startswith("place:") else None
        hints = j_index.get(jid, {}).get("councilDefaults")
        ctx = NormalizationContext(
            level="local",
            jurisdiction_type=jtype,
            jurisdiction_id=jid,
            registry_hints=hints,
        )
        for rec in data.get("members", []):
            normalize_member(rec, ctx)

        # Recompute dataHash; if it changed, bump dataLastChanged to today.
        # Mirrors the production scraper pipeline (scrapers/__main__.py:294-314).
        members = data.get("members", [])
        members_json = json.dumps(members, sort_keys=True, ensure_ascii=False)
        new_hash = hashlib.sha256(members_json.encode()).hexdigest()[:16]
        meta = data.setdefault("meta", {})
        prev_hash = meta.get("dataHash", "")
        if prev_hash != new_hash:
            meta["dataHash"] = new_hash
            meta["dataLastChanged"] = today

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"  Backfilled {path}")


def main():
    registry = load_registry()
    for state_code in sorted(registry.get("states", {}).keys()):
        print(f"Backfilling {state_code}...")
        backfill_state(state_code)
        backfill_local(state_code, registry)
    print("Done.")


if __name__ == "__main__":
    main()
```

**Step 2: Run the script**

```bash
python scripts/backfill_normalized_fields.py
```

Expected output: `Backfilling SC...` followed by `Backfilled data/sc/...` for state.json and all 96 local files.

**Step 3: Spot-check the output**

```bash
python -c "import json; d = json.load(open('data/sc/local/county-greenville.json')); m = d['members'][0]; print(m.get('office'), m.get('seatClass'), m.get('seatLabel'), m.get('seatId'), m.get('partisan'), m.get('seatSource'))"
```
Expected: `council-member numbered district 17 False parsed-title` (or similar).

```bash
python -c "import json; d = json.load(open('data/sc/state.json')); m = d['senate']['25']; print(m.get('office'), m.get('title'), m.get('seatId'), m.get('partisan'))"
```
Expected: `state-senator State Senator, District 25 25 True`.

**Step 4: Commit the regenerated data**

```bash
git add data/ scripts/backfill_normalized_fields.py
git commit -m "chore: backfill normalized seat fields into all data files"
```

---

### Task A16: Update validator

**Files:**
- Modify: `validate.py`
- Modify: `tests/unit/test_validate.py`

**Step 1: Write the failing tests**

Append to `tests/unit/test_validate.py`:

```python
def test_validate_requires_new_fields_on_local_member(tmp_path):
    """A local member missing office should produce an error."""
    # Build a minimal local file and verify the validator catches missing office
    # (Use the validator's existing test helpers; adapt to existing patterns.)
    ...  # Pattern-match against the existing test file structure


def test_validate_enforces_seat_invariants():
    """seatClass: numbered must have seatLabel and seatId."""
    ...
```

(NOTE to executor: read `tests/unit/test_validate.py` first to match its existing pytest style, then write tests that match. The patterns above are placeholders.)

**Step 2: Extend the validator**

In `validate.py`, in `validate_state_json` and `validate_local_file`, add new field checks AFTER the existing `name`/`title`/`email`/`phone` checks:

```python
VALID_OFFICES = {"state-senator", "state-representative", "governor",
                 "lt-governor", "mayor", "council-member"}
VALID_LEADERSHIP = {"chair", "vice-chair", "mayor-pro-tem", None}
VALID_SEAT_CLASS = {"numbered", "at-large", "unknown"}
VALID_SEAT_LABEL = {"district", "ward", "seat", None}
VALID_SEAT_SOURCE = {"source", "parsed-title", "inferred-registry", "manual"}


def _validate_normalized_fields(label, prefix, member):
    """Validate the new normalized seat fields and cross-field invariants."""
    office = member.get("office")
    if office not in VALID_OFFICES:
        error(label, f"{prefix}: office '{office}' not in {VALID_OFFICES}")

    leadership = member.get("leadership", "MISSING")
    if leadership == "MISSING":
        error(label, f"{prefix}: missing 'leadership' (must be null or enum)")
    elif leadership not in VALID_LEADERSHIP:
        error(label, f"{prefix}: leadership '{leadership}' not valid")

    seat_class = member.get("seatClass")
    if seat_class not in VALID_SEAT_CLASS:
        error(label, f"{prefix}: seatClass '{seat_class}' not valid")

    seat_label = member.get("seatLabel", "MISSING")
    if seat_label == "MISSING":
        error(label, f"{prefix}: missing 'seatLabel'")
    elif seat_label not in VALID_SEAT_LABEL:
        error(label, f"{prefix}: seatLabel '{seat_label}' not valid")

    seat_id = member.get("seatId", "MISSING")
    if seat_id == "MISSING":
        error(label, f"{prefix}: missing 'seatId'")

    seat_source = member.get("seatSource")
    if seat_source not in VALID_SEAT_SOURCE:
        error(label, f"{prefix}: seatSource '{seat_source}' not valid")

    if not isinstance(member.get("vacant"), bool):
        error(label, f"{prefix}: vacant must be boolean")

    if "partisan" not in member:
        error(label, f"{prefix}: missing 'partisan'")

    # Cross-field invariants
    if seat_class == "at-large":
        if seat_label is not None or seat_id is not None:
            error(label, f"{prefix}: at-large must have null seatLabel and seatId")
    elif seat_class == "numbered":
        if seat_label is None or seat_id is None:
            error(label, f"{prefix}: numbered must have seatLabel and seatId set")
    if leadership == "mayor-pro-tem" and office != "council-member":
        error(label, f"{prefix}: mayor-pro-tem leadership requires council-member office")
    if office == "mayor" and seat_class != "at-large":
        error(label, f"{prefix}: mayor office requires at-large seatClass")
```

Call it from both `validate_state_json` (after the existing senate/house/executive member loops) and `validate_local_file` (after the existing member loop).

**Step 3: Run the validator on real data**

```bash
python validate.py
```
Expected: 0 errors. Warnings about phone format are still acceptable.

**Step 4: Run validator tests**

```bash
pytest tests/unit/test_validate.py -v
```
Expected: all PASS.

**Step 5: Commit**

```bash
git commit -am "feat: validate normalized seat fields and cross-field invariants"
```

---

### Task A17: Cleanup, docs, version bump

**Files:**
- Delete: `scripts/backfill_normalized_fields.py`
- Modify: `package.json`, `boundaries-package.json`
- Modify: `CLAUDE.md`
- Regenerate: `MANIFEST.md`

**Step 1: Delete the backfill script**

```bash
git rm scripts/backfill_normalized_fields.py
```

The script was one-shot; future scrapes apply normalization inline via the wired-in normalizer.

**Step 2: Bump version**

In `package.json`, change:
```json
"version": "0.1.x"
```
to:
```json
"version": "0.2.0"
```

Same for `boundaries-package.json` if applicable.

**Step 3: Update CLAUDE.md**

Append a new section under "Conventions":

```markdown
## Schema (v0.2+)

All member records — state legislators, executive, and local council members — share the same shape with structured seat fields:

- `office`: enum of `state-senator | state-representative | governor | lt-governor | mayor | council-member`
- `leadership`: `chair | vice-chair | mayor-pro-tem | null`
- `seatClass`: `numbered | at-large | unknown`
- `seatLabel`: `district | ward | seat | null`
- `seatId`: string or null
- `vacant`: boolean
- `seatSource`: `source | parsed-title | inferred-registry | manual`
- `partisan`: boolean (true for state offices, false for most local SC offices)

Normalization runs in `scrapers/normalize.py` and is called from both `BaseAdapter.normalize()` (locals) and `scrapers/state.py` (state legislators and executive). Per-record patches go in `scrapers/seat_overrides.py`. Jurisdiction-wide hints (e.g., a council being all-at-large) go in `registry.json` under each jurisdiction's `councilDefaults` block.

See `docs/plans/2026-05-16-data-model-normalization-design.md` for the rationale.
```

**Step 4: Regenerate MANIFEST.md**

Update the Structure section to mention the new files:

```
├── scrapers/
│   ├── normalize.py              # Seat-field normalization (NEW v0.2)
│   ├── seat_overrides.py         # Per-record manual overrides (NEW v0.2)
│   ...
```

Update Key Relationships to mention the normalizer is called from both BaseAdapter and state.py.

**Step 5: Verify nothing broke**

```bash
python validate.py
pytest -v
```
Both should pass.

**Step 6: Commit**

```bash
git add -A
git commit -m "chore: bump to 0.2.0, update docs, remove backfill script"
```

**Step 7: Push and open PR**

```bash
git push -u origin data-model-normalization
gh pr create --title "Normalize data model: structured seat fields across all member records" \
  --body "$(cat <<'EOF'
## Summary

Promotes seat semantics (office, leadership, seatClass, seatLabel, seatId, vacant, seatSource, partisan) from buried free-text titles to structured fields. Additive migration: all existing fields preserved.

See `docs/plans/2026-05-16-data-model-normalization-design.md` for design and `docs/plans/2026-05-16-data-model-normalization-plan.md` for the executed plan.

## Post-merge gate

This PR's merge does NOT auto-publish. After merging, manually trigger:

```sh
gh workflow run publish.yml -R TimSimpsonJr/open-civics
```

Only after publish completes (and v0.2.0 lands on npm) can the deflocksc-website PR be opened.

## Test plan

- [ ] `python validate.py` exits 0
- [ ] `pytest -v` passes
- [ ] Spot-check a member in `data/sc/local/county-greenville.json` has the new fields
- [ ] Spot-check a state senator in `data/sc/state.json` has synthesized title + office

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Phase B — Coordination

These tasks are NOT code changes. They are manual coordination steps the human maintainer runs.

### Task B1: Merge open-civics PR

After Phase A is reviewed and approved:

```bash
gh pr merge --merge --repo TimSimpsonJr/open-civics <PR_NUMBER>
```

(Per the global CLAUDE.md, prefer merge commits over squash for multi-commit branches.)

### Task B2: Manually trigger npm publish

```bash
gh workflow run publish.yml -R TimSimpsonJr/open-civics
```

Watch the workflow:

```bash
gh run watch -R TimSimpsonJr/open-civics
```

Expected: workflow tags `v0.2.0`, publishes `open-civics@0.2.0` and `open-civics-boundaries@0.2.0` to npm.

### Task B3: Verify npm publish

```bash
npm view open-civics@0.2.0
```

Expected: version 0.2.0 is listed, with the published date matching today.

---

## Phase C — deflocksc-website PR

All Phase C work happens in the `deflocksc-website` repo, on a new branch `open-civics-0.2.0`. Phase C can only START after Phase B is complete.

```bash
cd C:/Users/tim/OneDrive/Documents/Projects/deflocksc-website
git checkout -b open-civics-0.2.0
```

### Task C1: Bump open-civics dependency

**Files:**
- Modify: `package.json`
- Modify: `package-lock.json`

```bash
npm install open-civics@^0.2.0
npm run sync-data
```

Verify that the new structured fields are present. The package's `exports` map (`"./*": "./data/*"` in [package.json](../../package.json)) means the import path is `open-civics/sc/local/...`, NOT `open-civics/data/sc/local/...`:

```bash
node -e "const d = require('open-civics/sc/local/county-greenville.json'); console.log(d.members[0])"
```

Expected: output includes `office`, `seatClass`, `seatLabel`, `seatId`, `vacant`, `seatSource`, `partisan`.

**Commit:**

```bash
git add package.json package-lock.json src/data/local-councils.json
git commit -m "chore: bump open-civics to 0.2.0"
```

### Task C2: Update TypeScript types

**Files:**
- Modify: `src/scripts/action-modal/types.ts` (or wherever the member type is defined)

**Step 1: Locate the existing type**

```bash
rg -n "title:" src/scripts/action-modal/types.ts
```

**Step 2: Add new optional fields to the local member type**

Append to the existing member shape:

```typescript
interface LocalCouncilMember {
  name: string;
  title: string;
  email: string;
  phone: string;
  source: string;
  lastUpdated: string;
  // NEW v0.2 normalized fields
  office?: 'council-member' | 'mayor';
  leadership?: 'chair' | 'vice-chair' | 'mayor-pro-tem' | null;
  seatClass?: 'numbered' | 'at-large' | 'unknown';
  seatLabel?: 'district' | 'ward' | 'seat' | null;
  seatId?: string | null;
  vacant?: boolean;
  seatSource?: 'source' | 'parsed-title' | 'inferred-registry' | 'manual';
  partisan?: boolean;
}
```

(Optional fields because TS may already infer them from open-civics' own type exports; verify whether the package ships types or not.)

**Step 3: Commit**

```bash
git commit -am "feat: add normalized seat fields to LocalCouncilMember type"
```

### Task C3: Refactor results-renderer.ts

**Files:**
- Modify: `src/scripts/action-modal/results-renderer.ts`

**Step 1: Find the title regex usages**

```bash
rg -n "title\.match" src/scripts/action-modal/results-renderer.ts
```

Expected: lines 381 and 399 (or nearby — exact line numbers may have shifted).

**Step 2: Replace line 381 (wrong-district dropdown options)**

Currently:
```typescript
const titleMatch = council.members[di].title.match(/(?:District|Seat) (\d+)/);
if (titleMatch && !seen.has(titleMatch[1])) {
  seen.add(titleMatch[1]);
  const opt = document.createElement('option');
  opt.value = titleMatch[1];
  opt.textContent = 'District ' + titleMatch[1];
  ...
}
```

Replace with:
```typescript
const m = council.members[di];
if (m.seatClass === 'numbered' && m.seatId && !seen.has(m.seatId)) {
  seen.add(m.seatId);
  const opt = document.createElement('option');
  opt.value = m.seatId;
  const labelWord = m.seatLabel ? m.seatLabel.charAt(0).toUpperCase() + m.seatLabel.slice(1) : 'District';
  opt.textContent = `${labelWord} ${m.seatId}`;
  if (m.seatId === String(wdGroup.matchedDistrict)) opt.selected = true;
  sel.appendChild(opt);
}
```

**Step 3: Replace line 399 (matched-district rep update)**

Currently:
```typescript
const repDistMatch = repTitle.match(/(?:District|Seat) (\d+)/);
wdGroup.reps[r].isMatchedDistrict = !!(repDistMatch && repDistMatch[1] === newDistrict);
```

Replace with — but note this works against `rep.office` (a string), not against a member. The rep was already constructed from the member by `group-builder.ts`. The cleanest fix is to propagate `seatId` from the member to the rep when buildGroups runs. Defer this until Task C4 fixes group-builder; for now use a more permissive regex that includes `Ward`:

```typescript
const repDistMatch = repTitle.match(/(?:District|Seat|Ward)\s+(\d+)/);
wdGroup.reps[r].isMatchedDistrict = !!(repDistMatch && repDistMatch[1] === newDistrict);
```

(A proper fix is added in Task C4 by carrying `seatId` on the rep object directly.)

**Step 4: Verify build**

```bash
npm run build
```
Expected: clean build.

**Step 5: Commit**

```bash
git commit -am "refactor: read structured seatClass/seatId/seatLabel in results-renderer"
```

### Task C4: Refactor group-builder.ts

**Files:**
- Modify: `src/scripts/action-modal/group-builder.ts`
- Modify: `src/scripts/action-modal/types.ts` (add `seatId` to `Rep`)

**Step 1: Find the title parsing**

```bash
rg -n "title\.indexOf|needleD|needleS" src/scripts/action-modal/group-builder.ts
```

**Step 2: Replace `findMatchedMember`**

Currently lines 21-32:
```typescript
function findMatchedMember(council: Council | undefined, districtNum: string | null) {
  if (!council || !council.members || !districtNum) return null;
  const needleD = 'District ' + districtNum;
  const needleS = 'Seat ' + districtNum;
  for (let i = 0; i < council.members.length; i++) {
    const title = council.members[i].title || '';
    if (title.indexOf(needleD) !== -1 || title.indexOf(needleS) !== -1) {
      return council.members[i];
    }
  }
  return null;
}
```

Replace with:
```typescript
function findMatchedMember(council: Council | undefined, districtNum: string | null) {
  if (!council || !council.members || !districtNum) return null;
  for (let i = 0; i < council.members.length; i++) {
    const m = council.members[i];
    if (m.seatClass === 'numbered' && m.seatId === districtNum) {
      return m;
    }
  }
  return null;
}
```

**Step 3: Find the Vacant filter**

```bash
rg -n "Vacant" src/scripts/action-modal/group-builder.ts
```

Expected: around line 91.

**Step 4: Replace exact-string "Vacant" with `vacant: true`**

Currently:
```typescript
if (matchedCountyMember && matchedCountyMember.name && matchedCountyMember.name !== 'Vacant') {
```

Replace with:
```typescript
if (matchedCountyMember && matchedCountyMember.name && !matchedCountyMember.vacant) {
```

Apply the same change to any other `name !== 'Vacant'` checks in the file.

**Step 5: Propagate seatId into Rep object**

When constructing local matched reps (around the same area), add `seatId`:

```typescript
localMatchedReps.push({
  name: matchedCountyMember.name,
  office: matchedCountyMember.title + ' — ' + countyCouncil!.label,
  seatId: matchedCountyMember.seatId || null,
  email: matchedCountyMember.email || '',
  phone: matchedCountyMember.phone || ''
});
```

Add `seatId?: string | null` to the `Rep` type in `types.ts`.

**Step 6: Update results-renderer to use rep.seatId**

Back in `results-renderer.ts`, replace the Task C3 step-3 temporary regex with:

```typescript
wdGroup.reps[r].isMatchedDistrict = wdGroup.reps[r].seatId === newDistrict;
```

**Step 7: Verify build and test**

```bash
npm run build && npm run test
```
Expected: clean build, passing tests.

**Step 8: Verify the rg success criterion**

```bash
rg -n "title\.(match|indexOf|includes|search)" src/scripts/action-modal/
```
Expected: no hits related to seat extraction. (Hits on `divisionPattern.indexOf` are fine — those aren't title parsing.)

**Step 9: Commit**

```bash
git add src/scripts/action-modal/
git commit -m "refactor: read structured seatClass/seatId in group-builder, drop title parsing"
```

### Task C5: Render seatLabel for display

**Files:**
- Modify: `src/scripts/action-modal/results-renderer.ts`

**Step 1: Find places that hardcode "District"**

```bash
rg -n "'District '" src/scripts/action-modal/results-renderer.ts
```

**Step 2: Replace hardcoded "District" with the seat's seatLabel**

For each occurrence, derive the display word from `member.seatLabel`:

```typescript
const labelWord = m.seatLabel
  ? m.seatLabel.charAt(0).toUpperCase() + m.seatLabel.slice(1)
  : 'District';
opt.textContent = `${labelWord} ${m.seatId}`;
```

**Step 3: Commit**

```bash
git commit -am "feat: render seatLabel for Ward / Seat / District display"
```

### Task C6: Final sync, verify, push

**Step 1: Run prebuild sync to refresh local-councils.json**

```bash
npm run sync-data
```

**Step 2: Run the full build and test suite**

```bash
npm run build && npm run test
```

**Step 3: Verify success criteria**

```bash
# (a) No runtime title parsing for seat extraction
rg -n "title\.(match|indexOf|includes|search)" src/scripts/action-modal/

# (b) Ward seats appear in dropdown — open the action modal manually for
# Camden, Darlington, Lancaster, or Newberry and verify "Ward N" options.
# (For automated verification: a Vitest unit test that builds a council
# with Ward members and asserts the dropdown options include them.)

# (c) Vacancy filter works (note: path uses package exports map, not raw data/ path)
node -e "const d = require('open-civics/sc/local/place-lancaster.json'); console.log(d.members.filter(m => m.vacant).map(m => m.name))"
# Expected: ["Vacant District 5"]
```

**Step 4: Commit any final fixes**

```bash
git add src/data/local-councils.json
git commit -m "chore: sync data and verify schema migration"
```

**Step 5: Push and open PR**

```bash
git push -u origin open-civics-0.2.0
gh pr create --title "Adopt open-civics 0.2.0: structured seat fields, drop title parsing" \
  --body "$(cat <<'EOF'
## Summary

Adopts `open-civics@0.2.0`'s structured seat fields (`seatClass`, `seatLabel`, `seatId`, `vacant`) across the action modal. Removes runtime title regex parsing in `results-renderer.ts` and `group-builder.ts`. Adds Ward / Seat label rendering, fixes Lancaster's "Vacant District 5" filter, fixes the wrong-district dropdown for Ward-based towns (Camden, Darlington, Lancaster, Newberry).

Depends on open-civics PR <link>. Must merge AFTER `open-civics@0.2.0` is published to npm.

## Test plan

- [ ] `npm run build` succeeds
- [ ] `npm run test` passes
- [ ] Action modal "wrong district" dropdown shows Ward N for Darlington
- [ ] Lancaster's vacant seat is filtered out of matched reps
- [ ] No `title.match(...)` or `title.indexOf('District'...)` remains in `src/scripts/action-modal/`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Final verification (after both PRs merged)

```bash
# In open-civics:
python validate.py    # exits 0
pytest -v             # all pass

# In deflocksc-website:
npm run test          # all pass
npm run build         # clean build

# Production deploy (Netlify auto-deploys on merge to main):
# - Check that the deployed site's action modal works
# - Check that Camden/Darlington/Lancaster/Newberry Ward seats appear
# - Check that Lancaster's vacant District 5 doesn't appear
```

The design's success criteria all map to verifications above. If any check fails, file a follow-up issue with label `autonomous-safe` (the schema work itself is done; remaining bugs are code-only follow-ups).
