---
codex_plan_review_status: approved
codex_plan_review_approved_hash: fd4114e2e0d4fee4220f6abd0b0ef9d2fbdda4d329419eaf5cd59e12bc79a4f9
codex_thread_id: 019e311a-c877-7453-9cd1-f72a038f3c99
---

# Districted Scraper Bug Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close the district-info coverage gap for 7 SC jurisdictions identified in `docs/plans/2026-05-16-followup-districted-scraper-bugs.md` so their members carry `seatClass: numbered` with populated `seatLabel` / `seatId` instead of `seatClass: unknown`.

**Architecture:** Per-jurisdiction triage in three buckets. (a) Source publishes district info but the current adapter misses it — extend the adapter and prove with a saved-HTML snapshot test. (b) Primary source is unreachable / has no district info — populate `scrapers/seat_overrides.py` with hand-researched name→district mappings. (c) A new validator check guarantees the gap stays closed: warn whenever a registry-districted jurisdiction has all-unknown member seats.

**Tech Stack:** Python 3.12, `requests`, `beautifulsoup4`, `pytest`. All edits are in-repo; no new dependencies.

**Environment notes for the executing agent:**

- Data files live under **`data/sc/`** (lowercase — matches what `scrapers/__main__.py` writes; the case matters on Linux CI even though Windows is case-insensitive).
- All shell snippets in this plan are intended for the Bash tool (Git Bash on Windows, native bash on Linux). Avoid `/tmp/` as a destination — write fetched HTML directly into `tests/fixtures/snapshots/` so it survives across turns and is portable. The plan never assumes `/tmp/` files persist.
- The validator function is **`validate_local_file(data, filepath)`** in [validate.py](validate.py) — not `validate_local_json`. It's called from `main()` at [validate.py:520](validate.py:520).

---

## Rollout

- **PR 1 — "Districted scraper fixes" (Tasks 0–4).** Adds the validator gate plus the four scraper-side fixes. One commit per task. Autonomous-safe.
- **PR 2 — "Districted manual overrides" (Tasks 5–7 + Task 8).** Adds the three `seat_overrides.py` entries (one commit per jurisdiction, each citing its research source) and the closeout edit to the followup design doc. Autonomous-safe.

Each task below ends with its own commit. The PR break happens between Task 4 and Task 5.

---

## Affected jurisdictions and chosen strategy

| # | Jurisdiction | Current adapter | Strategy | Why |
|---|---|---|---|---|
| 1 | `place:north-charleston` | `generic_mailto` | **A — extend adapter** | Source has `<li>District N</li>` immediately above each member block. Structural fix. |
| 2 | `place:aiken` | `aiken_city` | **A — verify + deterministic refresh** | Adapter already parses `et_pb_member_position` ("District N"). Data file is stale (was last scraped under `masc`). |
| 3 | `county:berkeley` | `scac` (fallback) | **A — write bespoke adapter** | Primary site IS reachable with OpenCivics UA. `<figcaption>` contains `District N<br>Name`. |
| 4 | `county:aiken` | `civicplus` | **A — extend adapter** | Council-members page at `sc-aikencounty.civicplus.com/529/Council-Members` groups members under "District N" headings (the staff-directory page used today doesn't). |
| 5 | `county:dorchester` | `scac` (fallback) | **B — manual overrides** | Primary site is Akamai-blocked (even via curl + browser UA). |
| 6 | `county:kershaw` | `kershaw_county` | **B — manual overrides** | Primary site is Akamai-blocked. The bespoke adapter exists but cannot reach the source. |
| 7 | `county:jasper` | `table` | **B — manual overrides** | Source is reachable but contains no district info anywhere on the council page. |

---

## Task 0: Validator check — flag all-unknown seatClass on districted jurisdictions

**Why first:** Without this gate, every later task's "done" is opinion. With it, every later task has a one-line proof (the warning disappears).

**Files:**
- Modify: `validate.py` — extend `validate_local_file` to accept `jurisdiction_entry=None`; add an in-function coverage check; update `main()` to look up the matching jurisdiction in the registry and pass it through.
- Modify: `tests/unit/test_validate.py` — add a new test class.

**Step 1: Re-read the validator**

Read [validate.py](validate.py) end-to-end, focusing on `validate_local_file()` at line 270 and the `main()` loop that calls it around line 520. Note that `main()` already loads the registry (used for boundary validation) — the registry lookup just needs to be hoisted up to the local-files loop.

**Step 2: Write the failing test**

Append to `tests/unit/test_validate.py`:

```python
class TestLocalSeatCoverage:
    """A jurisdiction registry-marked as districted (atLarge: false, no
    councilDefaults override) should not have every member at seatClass: unknown.
    The check warns rather than errors — a single overrides patch can fix it,
    but a regression should be loud."""

    def _data(self, members):
        return {
            "meta": {"state": "SC", "level": "local", "jurisdiction": "county:test",
                     "label": "Test", "lastUpdated": "2026-05-20", "adapter": "test"},
            "members": members,
        }

    def _member(self, name, seat_class="unknown", seat_label=None, seat_id=None,
                leadership=None, office="council-member"):
        return {
            "name": name, "title": "Council Member", "office": office,
            "leadership": leadership, "seatClass": seat_class,
            "seatLabel": seat_label, "seatId": seat_id,
            "seatSource": "parsed-title", "vacant": False, "partisan": False,
        }

    def test_warns_when_districted_jurisdiction_has_all_unknown_seats(self):
        from validate import validate_local_file, warnings as warn_list
        warn_list.clear()
        entry = {"id": "county:test", "type": "county", "atLarge": False}
        data = self._data([self._member("A"), self._member("B")])
        validate_local_file(data, "test.json", jurisdiction_entry=entry)
        assert any("districted but all members have seatClass: unknown" in w
                   for w in warn_list)

    def test_no_warning_when_at_large(self):
        from validate import validate_local_file, warnings as warn_list
        warn_list.clear()
        entry = {"id": "place:test", "type": "place", "atLarge": True,
                 "councilDefaults": {"seatClass": "at-large", "partisan": False}}
        data = self._data([self._member("A", seat_class="at-large")])
        validate_local_file(data, "test.json", jurisdiction_entry=entry)
        assert not any("seatClass: unknown" in w for w in warn_list)

    def test_no_warning_when_at_least_one_seat_populated(self):
        from validate import validate_local_file, warnings as warn_list
        warn_list.clear()
        entry = {"id": "county:test", "type": "county", "atLarge": False}
        data = self._data([
            self._member("A", seat_class="numbered", seat_label="district", seat_id="1"),
            self._member("B"),
        ])
        validate_local_file(data, "test.json", jurisdiction_entry=entry)
        assert not any("seatClass: unknown" in w for w in warn_list)

    def test_no_warning_when_jurisdiction_entry_missing(self):
        # Defensive: if the lookup fails, don't warn (avoids noise on jurisdictions
        # that were dropped from registry but still have a data file).
        from validate import validate_local_file, warnings as warn_list
        warn_list.clear()
        data = self._data([self._member("A"), self._member("B")])
        validate_local_file(data, "test.json", jurisdiction_entry=None)
        assert not any("seatClass: unknown" in w for w in warn_list)
```

**Step 3: Run the test to verify it fails**

Run: `pytest tests/unit/test_validate.py::TestLocalSeatCoverage -v`

Expected: TypeError on the new `jurisdiction_entry` keyword (since the parameter doesn't exist yet) — that's the failing state. If you get assertion failures instead, that's fine too; the contract is "not yet wired up."

**Step 4: Implement the validator check**

In `validate.py`, change the signature of `validate_local_file`:

```python
def validate_local_file(data, filepath, jurisdiction_entry=None):
```

At the bottom of the function (after the per-member loop), add:

```python
    _check_districted_seat_coverage(label, members, jurisdiction_entry)
```

Add the helper near the other validators:

```python
def _check_districted_seat_coverage(label, members, jurisdiction_entry):
    """Warn when a registry-districted jurisdiction has all-unknown member seats.

    A jurisdiction is "districted" when registry has atLarge: false AND
    councilDefaults does not pin seatClass to at-large. If every member's
    seatClass is "unknown" in that case, the source publishes no district info
    OR the adapter is missing it — either way, a regression worth flagging.
    """
    if not jurisdiction_entry or not isinstance(members, list):
        return
    if jurisdiction_entry.get("atLarge", False):
        return
    council_defaults = jurisdiction_entry.get("councilDefaults") or {}
    if council_defaults.get("seatClass") == "at-large":
        return
    council_members = [m for m in members
                       if m.get("office") == "council-member"
                       and m.get("leadership") not in ("chair", "vice-chair")]
    if not council_members:
        return
    if all(m.get("seatClass") == "unknown" for m in council_members):
        warn(label, "jurisdiction is districted but all members have seatClass: unknown")
```

Then update `main()` to pass the entry. Around line 510–521 in the local-files loop:

```python
            # Build a quick lookup of jurisdictions from the registry
            jurisdictions_by_id = {}
            if registry is not None:
                state_block = registry.get("states", {}).get(state_upper, {})
                for j in state_block.get("jurisdictions", []):
                    if j.get("id"):
                        jurisdictions_by_id[j["id"]] = j

            # Validate local council files
            local_dir = os.path.join(state_dir, "local")
            if os.path.isdir(local_dir):
                for local_file in sorted(os.listdir(local_dir)):
                    if not local_file.endswith(".json"):
                        continue
                    local_path = os.path.join(local_dir, local_file)
                    local_label = f"data/{state_code}/local/{local_file}"
                    local_data = load_json(local_path, local_label)
                    if local_data is not None:
                        jid = (local_data.get("meta") or {}).get("jurisdiction", "")
                        entry = jurisdictions_by_id.get(jid)
                        validate_local_file(local_data, local_label,
                                            jurisdiction_entry=entry)
                print(f"  Checked data/{state_code}/local/ ({len(os.listdir(local_dir))} files)")
```

**Step 5: Run the tests to verify they pass**

Run: `pytest tests/unit/test_validate.py -v`

Expected: all PASS, including the existing tests (the new keyword argument has a default so the API is backwards-compatible).

**Step 6: Run the full validator and capture the regression baseline inline**

Run:

```bash
python validate.py 2>&1 | grep "districted but all"
```

Read the warnings off stdout — no file written. Expected: warnings for at least the 7 affected jurisdictions. Copy the list into the PR description as the regression baseline that each later task shrinks; do NOT commit a baseline log file.

**Step 7: Commit**

```bash
git add validate.py tests/unit/test_validate.py
git commit -m "feat(validate): warn on districted jurisdictions with all-unknown seats"
```

---

## Task 1: `place:north-charleston` — extend `generic_mailto` to attach district headings

**Strategy:** The source page wraps each member in a `<div class="rz-business-block">` that contains a `<ul class="category-list"><li>District N</li></ul>` and an `<h2>` with the member's name. The current `GenericMailtoAdapter` (extending `RevizeAdapter`) pairs name+mailto but ignores the preceding category list. Add a post-processing pass that builds a `{member_name: 'District N'}` map from the page and rewrites each member's title before returning.

**Files:**
- Create: `tests/fixtures/snapshots/generic_mailto_north_charleston.html` (saved HTML, fetched directly into the snapshots dir)
- Modify: `tests/fixtures/snapshots/snapshots.json`
- Modify: `scrapers/adapters/generic_mailto.py` (add `_extract_district_map_from_rz_blocks()` and apply it after `super().parse()`)
- Create: `tests/unit/test_generic_mailto_north_charleston.py`

**Step 1: Save the HTML snapshot directly into the fixture dir**

```bash
curl -s -A "OpenCivics/1.0 (+https://github.com/TimSimpsonJr/open-civics)" -L \
  --compressed \
  "https://www.northcharleston.org/government/city_council/city_council_members_and_districts.php" \
  -o tests/fixtures/snapshots/generic_mailto_north_charleston.html
```

Sanity-check the file:

```bash
wc -c tests/fixtures/snapshots/generic_mailto_north_charleston.html  # expect > 100KB
grep -c "rz-business-block" tests/fixtures/snapshots/generic_mailto_north_charleston.html  # expect >= 10
grep -c "District [0-9]" tests/fixtures/snapshots/generic_mailto_north_charleston.html | head -1
```

**Step 2: Add snapshot manifest entry**

Append to `tests/fixtures/snapshots/snapshots.json`'s `snapshots` array:

```json
{
  "file": "generic_mailto_north_charleston.html",
  "url": "https://www.northcharleston.org/government/city_council/city_council_members_and_districts.php",
  "adapter": "generic_mailto",
  "adapter_module": "scrapers.adapters.generic_mailto",
  "adapter_class": "GenericMailtoAdapter",
  "entry": {
    "id": "place:north-charleston",
    "url": "https://www.northcharleston.org/government/city_council/city_council_members_and_districts.php",
    "adapterConfig": {"mayorUrl": "https://www.northcharleston.org/government/office_of_the_mayor/index.php"}
  },
  "min_members": 10
}
```

**Step 3: Write the failing unit test**

Create `tests/unit/test_generic_mailto_north_charleston.py`:

```python
"""Tests for GenericMailtoAdapter against the North Charleston snapshot.

This jurisdiction has district info as <li>District N</li> inside a
<ul class="category-list"> sitting above each member's <h2> name.
The adapter must attach those districts to each member's title so the
normalizer's stage-2 title parser produces seatClass: numbered.
"""

import os
import re

import pytest

from scrapers.adapters.generic_mailto import GenericMailtoAdapter
from scrapers.normalize import normalize_member, NormalizationContext

SNAPSHOT = os.path.join(os.path.dirname(__file__), "..", "fixtures",
                        "snapshots", "generic_mailto_north_charleston.html")


@pytest.fixture
def html():
    with open(SNAPSHOT, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def adapter():
    return GenericMailtoAdapter({
        "id": "place:north-charleston",
        "url": "",
        "adapterConfig": {},
    })


class TestNorthCharlestonDistricts:

    def test_parse_yields_ten_members(self, adapter, html):
        members = adapter.parse(html)
        # 10 districts; mayor not necessarily on this page (fetched separately
        # via mayorUrl); assert lower bound on the district members.
        district_members = [m for m in members if "District" in m.get("title", "")]
        assert len(district_members) >= 10

    def test_district_titles_format(self, adapter, html):
        members = adapter.parse(html)
        ids = sorted(int(re.search(r"District\s+(\d+)", m["title"]).group(1))
                     for m in members if "District" in m.get("title", ""))
        assert ids == list(range(1, 11))

    def test_full_pipeline_produces_numbered_seats(self, adapter, html):
        """parse → normalize → every council member has seatClass: numbered."""
        raw = adapter.parse(html)
        ctx = NormalizationContext(
            level="local", jurisdiction_type="place",
            jurisdiction_id="place:north-charleston",
        )
        for r in raw:
            normalize_member(r, ctx)
        district_members = [m for m in raw if "District" in m.get("title", "")]
        for m in district_members:
            assert m["seatClass"] == "numbered", m
            assert m["seatLabel"] == "district", m
            assert m["seatId"] is not None, m
```

Run: `pytest tests/unit/test_generic_mailto_north_charleston.py -v`

Expected: tests FAIL because the current adapter outputs `"Council Member"` without district info.

**Step 4: Implement the attachment**

In `scrapers/adapters/generic_mailto.py`, refactor `parse()` to apply a post-processing district map. Keep all existing logic (the RevizeAdapter delegation, mayor fetch, etc.) — just add a new step at the end:

```python
def parse(self, html: str) -> list[dict]:
    # ... existing logic that produces `members` ...
    name_to_district = self._extract_district_map_from_rz_blocks(html)
    if name_to_district:
        for m in members:
            if m.get("title", "").startswith("Mayor"):
                continue
            district = name_to_district.get(m["name"])
            if district:
                m["title"] = f"Council Member, {district}"
    return members

@staticmethod
def _extract_district_map_from_rz_blocks(html: str) -> dict[str, str]:
    """For Revize-style sites that wrap each member in a div.rz-business-block
    with <ul class="category-list"><li>District N</li></ul>, return
    {member_name: 'District N'}. No-op on sites without this structure."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    mapping: dict[str, str] = {}
    for block in soup.find_all("div", class_="rz-business-block"):
        li = block.select_one("ul.category-list li")
        h2 = block.find("h2")
        if not li or not h2:
            continue
        li_text = li.get_text(strip=True)
        if li_text.lower().startswith("district"):
            mapping[h2.get_text(strip=True)] = li_text
    return mapping
```

The map is defensive — empty when no `rz-business-block` divs exist, so other GenericMailto sites are unaffected.

**Step 5: Verify the new tests pass**

Run: `pytest tests/unit/test_generic_mailto_north_charleston.py -v` → PASS.

**Step 6: Verify no regression**

Run: `pytest tests/unit/test_generic_mailto.py tests/integration/test_real_snapshots.py -v` → all PASS.

**Step 7: Commit**

```bash
git add scrapers/adapters/generic_mailto.py \
        tests/unit/test_generic_mailto_north_charleston.py \
        tests/fixtures/snapshots/generic_mailto_north_charleston.html \
        tests/fixtures/snapshots/snapshots.json
git commit -m "feat(scrapers): attach district headings to North Charleston members"
```

---

## Task 2: `place:aiken` — verify adapter + deterministic data refresh

**Strategy:** Snapshot inspection confirms the adapter already produces `"Council Member District N"` titles from `p.et_pb_member_position`. The shipped `data/sc/local/place-aiken.json` is stale (last scraped under `masc`). Pin the behavior with a unit test, then refresh the data file. If the live re-scrape is blocked locally by Cloudflare, generate the JSON deterministically from the saved snapshot (no "wait for CI" handwave).

**Files:**
- Create: `tests/fixtures/snapshots/aiken_city.html`
- Modify: `tests/fixtures/snapshots/snapshots.json`
- Create: `tests/unit/test_aiken_city.py`
- Modify: `data/sc/local/place-aiken.json` (refreshed from snapshot OR live scrape)

**Step 1: Save the snapshot**

```bash
curl -s -A "OpenCivics/1.0 (+https://github.com/TimSimpsonJr/open-civics)" -L \
  --compressed \
  "https://www.cityofaikensc.gov/government/city-council/" \
  -o tests/fixtures/snapshots/aiken_city.html
```

If the response is < 5KB or contains "Just a moment..." (Cloudflare challenge), abort the fetch and ask the user to provide the snapshot from a non-Cloudflare-blocked source. Don't proceed with a junk snapshot.

**Step 2: Add to manifest**

```json
{
  "file": "aiken_city.html",
  "url": "https://www.cityofaikensc.gov/government/city-council/",
  "adapter": "aiken_city",
  "adapter_module": "scrapers.adapters.aiken_city",
  "adapter_class": "AikenCityAdapter",
  "entry": {"id": "place:aiken", "url": "https://www.cityofaikensc.gov/government/city-council/"},
  "min_members": 7
}
```

**Step 3: Write the failing test**

Create `tests/unit/test_aiken_city.py`:

```python
import os
import re
import pytest
from scrapers.adapters.aiken_city import AikenCityAdapter
from scrapers.normalize import normalize_member, NormalizationContext

SNAPSHOT = os.path.join(os.path.dirname(__file__), "..", "fixtures",
                        "snapshots", "aiken_city.html")


@pytest.fixture
def adapter():
    return AikenCityAdapter({"id": "place:aiken", "url": "", "adapterConfig": {}})


@pytest.fixture
def html():
    with open(SNAPSHOT, "r", encoding="utf-8") as f:
        return f.read()


class TestAikenCity:

    def test_extracts_mayor_and_six_districts(self, adapter, html):
        members = adapter.parse(html)
        mayors = [m for m in members if m["title"] == "Mayor"]
        districts = [m for m in members if "District" in m["title"]]
        assert len(mayors) == 1
        assert len(districts) == 6

    def test_districts_are_1_through_6(self, adapter, html):
        members = adapter.parse(html)
        ids = sorted(int(re.search(r"District\s+(\d+)", m["title"]).group(1))
                     for m in members if "District" in m["title"])
        assert ids == [1, 2, 3, 4, 5, 6]

    def test_full_pipeline_produces_numbered_seats(self, adapter, html):
        raw = adapter.parse(html)
        ctx = NormalizationContext(level="local", jurisdiction_type="place",
                                   jurisdiction_id="place:aiken")
        for r in raw:
            normalize_member(r, ctx)
        for m in raw:
            if m.get("office") == "mayor":
                continue
            assert m["seatClass"] == "numbered", m
            assert m["seatLabel"] == "district", m
```

Run: `pytest tests/unit/test_aiken_city.py -v` — expected to PASS without adapter changes; this task is verification.

**Step 4: Refresh `data/sc/local/place-aiken.json`**

Try the live path first:

```bash
python -m scrapers --state SC --jurisdiction place:aiken
```

If the command exits clean and the file's `meta.adapter` is `"aiken_city"`, you're done. If Cloudflare blocks the request (the command errors with 403 or `cityofaikensc.gov` doesn't respond), use the deterministic fallback: generate the data file from the saved snapshot.

**Deterministic fallback:** write a one-off helper script `scripts/refresh_from_snapshot.py` (or run inline via `python -c`) that loads `tests/fixtures/snapshots/aiken_city.html`, runs the adapter's `parse()` + `normalize()` + the meta block from `scrapers/__main__.py:286-318`, and writes the result to `data/sc/local/place-aiken.json`. The helper is generic — name it so it can be reused for any task that needs the same fallback (Task 3 may too).

Skeleton:

```python
# scripts/refresh_from_snapshot.py
"""Regenerate a local-council data file from a saved HTML snapshot.

Usage:
  python scripts/refresh_from_snapshot.py <jurisdiction_id> <snapshot_path>

Used as a fallback when live scraping is blocked (Cloudflare, Akamai, etc.)
but a saved snapshot exists in tests/fixtures/snapshots/.
"""
import hashlib, json, os, sys
from datetime import date

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from scrapers.__main__ import ADAPTERS, load_registry

def main(jid: str, snapshot_path: str) -> None:
    registry = load_registry()
    entry = next(
        (j for state in registry["states"].values()
         for j in state.get("jurisdictions", [])
         if j["id"] == jid),
        None,
    )
    if entry is None:
        sys.exit(f"jurisdiction {jid!r} not found in registry")
    adapter_cls = ADAPTERS[entry["adapter"]]
    adapter = adapter_cls(entry)
    with open(snapshot_path, "r", encoding="utf-8") as f:
        html = f.read()
    raw = adapter.parse(html)
    members = adapter.normalize(raw)
    adapter.validate(members)
    members_json = json.dumps(members, sort_keys=True, ensure_ascii=False)
    data_hash = hashlib.sha256(members_json.encode()).hexdigest()[:16]
    today = date.today().isoformat()
    state_code = "SC"  # extend if multistate
    data = {
        "meta": {
            "state": state_code, "level": "local", "jurisdiction": jid,
            "label": entry["name"], "lastUpdated": today,
            "adapter": entry["adapter"], "dataHash": data_hash,
            "dataLastChanged": today,
        },
        "members": members,
    }
    out = os.path.join(PROJECT_ROOT, "data", state_code.lower(), "local",
                       f"{jid.replace(':', '-')}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"Wrote {out}")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
```

Run it:

```bash
python scripts/refresh_from_snapshot.py place:aiken tests/fixtures/snapshots/aiken_city.html
```

**Step 5: Verify**

```bash
python validate.py 2>&1 | grep "place:aiken"
```

Expected: no district-coverage warning for `place:aiken`.

**Step 6: Commit**

```bash
git add tests/unit/test_aiken_city.py \
        tests/fixtures/snapshots/aiken_city.html \
        tests/fixtures/snapshots/snapshots.json \
        scripts/refresh_from_snapshot.py \
        data/sc/local/place-aiken.json
git commit -m "feat(scrapers): pin aiken_city behavior with snapshot, refresh data"
```

---

## Task 3: `county:berkeley` — write bespoke `berkeley_county` adapter

**Strategy:** `https://berkeleycountysc.gov/dept/council/elected-officials/` returns ~120KB of WordPress HTML when fetched with the OpenCivics UA + gzip (which `requests` does automatically). Each member sits in a `<figure class="wp-block-image">` whose `<figcaption>` contains `District N` and the member's name as text. The page also lists a "Supervisor" entry — Johnny Cribb — outside the District 1..N grid (Berkeley uses Supervisor-Council form). Phone and email are on per-member detail pages.

**Important constraints from review:**

- Keep `parse(html)` **pure** on the index HTML. The snapshot-test harness in [tests/integration/test_real_snapshots.py:33](tests/integration/test_real_snapshots.py:33) calls `adapter.parse(html)` with no network. Any HTTP from inside `parse()` makes the test non-hermetic.
- Do not hard-code the district count. The saved snapshot may show 7 or 8 districts depending on when it was captured (Berkeley redistricted recently and the registry says `districts: 7` while the live site I inspected during planning showed 1–8). Derive expected count from the snapshot, and emit a clear warning if the snapshot disagrees with `registry.districts` so the registry can be updated in a follow-up commit.

**Files:**
- Create: `scrapers/adapters/berkeley_county.py`
- Modify: `scrapers/__main__.py` (register `BerkeleyCountyAdapter`)
- Modify: `registry.json` (change `county:berkeley` `adapter` from `"scac"` to `"berkeley_county"`, and update `districts` to whatever the snapshot shows)
- Create: `tests/fixtures/snapshots/berkeley_county.html`
- Modify: `tests/fixtures/snapshots/snapshots.json`
- Create: `tests/unit/test_berkeley_county.py`

**Step 1: Save the HTML snapshot**

```bash
curl -s -A "OpenCivics/1.0 (+https://github.com/TimSimpsonJr/open-civics)" -L \
  --compressed \
  "https://berkeleycountysc.gov/dept/council/elected-officials/" \
  -o tests/fixtures/snapshots/berkeley_county.html
```

Confirm: `wc -c tests/fixtures/snapshots/berkeley_county.html` > 50KB and `grep -c "wp-block-image" tests/fixtures/snapshots/berkeley_county.html` >= 8.

**Step 2: Determine the actual district count and roster from the snapshot**

```bash
grep -oE 'District [0-9]+' tests/fixtures/snapshots/berkeley_county.html | sort -u
grep -oE 'Supervisor' tests/fixtures/snapshots/berkeley_county.html | head -1
```

Record the result (e.g., `1..8` plus one Supervisor). Use this as the source of truth — neither the registry nor any external doc overrides the snapshot.

**Step 3: Write the failing test**

Create `tests/unit/test_berkeley_county.py`. Parameterize on the count derived in step 2; if the snapshot shows N districts, assert exactly N members carry numbered districts contiguous from 1, plus one Supervisor (chairman-equivalent):

```python
import os
import re
import pytest

# Import lazily so the test still reports a useful failure when the adapter
# file doesn't exist yet (rather than collection-time ImportError).

SNAPSHOT = os.path.join(os.path.dirname(__file__), "..", "fixtures",
                        "snapshots", "berkeley_county.html")


@pytest.fixture
def html():
    with open(SNAPSHOT, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def adapter():
    from scrapers.adapters.berkeley_county import BerkeleyCountyAdapter
    return BerkeleyCountyAdapter({
        "id": "county:berkeley",
        "url": "https://berkeleycountysc.gov/dept/council/elected-officials/",
        "adapterConfig": {},
    })


def _expected_district_ids(html: str) -> list[int]:
    """Discover the set of district numbers present in the snapshot."""
    ids = sorted({int(m.group(1))
                  for m in re.finditer(r"District\s+(\d+)", html)})
    assert ids and ids[0] == 1, "snapshot district numbering changed unexpectedly"
    # Must be contiguous from 1
    assert ids == list(range(1, ids[-1] + 1))
    return ids


class TestBerkeleyCountyParse:

    def test_district_count_matches_snapshot(self, adapter, html):
        expected = _expected_district_ids(html)
        members = adapter.parse(html)
        district_members = [m for m in members if "District" in m.get("title", "")]
        assert len(district_members) == len(expected)

    def test_district_ids_match_snapshot(self, adapter, html):
        expected = _expected_district_ids(html)
        members = adapter.parse(html)
        ids = sorted(int(re.search(r"District\s+(\d+)", m["title"]).group(1))
                     for m in members if "District" in m.get("title", ""))
        assert ids == expected

    def test_supervisor_present(self, adapter, html):
        members = adapter.parse(html)
        # Supervisor parses as Chairman-equivalent (chair leadership).
        assert any("Supervisor" in m.get("title", "") or m.get("title") == "Chairman"
                   for m in members)

    def test_full_pipeline_produces_numbered_seats(self, adapter, html):
        from scrapers.normalize import normalize_member, NormalizationContext
        raw = adapter.parse(html)
        ctx = NormalizationContext(level="local", jurisdiction_type="county",
                                   jurisdiction_id="county:berkeley")
        for r in raw:
            normalize_member(r, ctx)
        district_members = [m for m in raw if "District" in m.get("title", "")]
        for m in district_members:
            assert m["seatClass"] == "numbered"
            assert m["seatLabel"] == "district"
```

Run: `pytest tests/unit/test_berkeley_county.py -v` → ImportError on `berkeley_county`. That's the failing state.

**Step 4: Implement the adapter (pure parse, network only in `fetch()`)**

Create `scrapers/adapters/berkeley_county.py`:

```python
"""Adapter for Berkeley County Council elected officials.

The primary site is a WordPress page where each member appears in a
<figure class="wp-block-image"> whose <figcaption class="wp-element-caption">
contains text like 'District N' and the member's name, sometimes split
across multiple anchor elements joined by <br>. The county uses
Supervisor-Council form, so the Supervisor is an at-large position
separate from district seats.

Phone and email live on per-member detail pages linked by figcaption hrefs.
v1 of this adapter does NOT visit those pages — name + district is the
priority (it's what closes the validator warning). A future enhancement
can add detail-page enrichment via a separate `scrape()` override that
runs after parse() returns the index members.
"""

import re
import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter

USER_AGENT = "OpenCivics/1.0 (+https://github.com/TimSimpsonJr/open-civics)"

_DISTRICT_RE = re.compile(r"District\s+(\d+)", re.IGNORECASE)
_SUPERVISOR_RE = re.compile(r"\bSupervisor\b", re.IGNORECASE)


class BerkeleyCountyAdapter(BaseAdapter):

    def fetch(self) -> str:
        resp = requests.get(
            self.url, headers={"User-Agent": USER_AGENT}, timeout=30,
            allow_redirects=True,
        )
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []
        for fig in soup.find_all("figure", class_="wp-block-image"):
            cap = fig.find("figcaption")
            if not cap:
                continue
            text = cap.get_text(separator="\n", strip=True)
            lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
            if not lines:
                continue

            district_match = _DISTRICT_RE.search(text)
            is_supervisor = _SUPERVISOR_RE.search(text)

            # Member name is the line in the caption that is NOT a label
            label_predicates = (_DISTRICT_RE, _SUPERVISOR_RE,
                                re.compile(r"^Chair(?:man|woman)?$", re.IGNORECASE),
                                re.compile(r"^Vice", re.IGNORECASE))
            name = next(
                (ln for ln in lines
                 if not any(p.search(ln) for p in label_predicates)),
                "",
            )
            if not name:
                continue

            if district_match:
                title = f"Council Member, District {district_match.group(1)}"
            elif is_supervisor:
                title = "Chairman"  # Supervisor-Council form: supervisor IS the chair-equivalent
            else:
                # Non-district, non-supervisor figure — likely a banner image.
                continue

            members.append({
                "name": name,
                "title": title,
                "email": "",
                "phone": "",
            })

        members.sort(key=self._sort_key)
        return members

    @staticmethod
    def _sort_key(m: dict) -> tuple:
        title = m["title"]
        if title == "Chairman":
            return (0, 0)
        match = _DISTRICT_RE.search(title)
        if match:
            return (1, int(match.group(1)))
        return (2, 0)
```

**Step 5: Register the adapter and update the registry**

In `scrapers/__main__.py`:
- Add import: `from .adapters.berkeley_county import BerkeleyCountyAdapter`
- Add to `ADAPTERS` dict: `"berkeley_county": BerkeleyCountyAdapter,`

In `registry.json` for `county:berkeley`:
- Change `"adapter": "scac"` to `"adapter": "berkeley_county"`
- Change `url` to `"https://berkeleycountysc.gov/dept/council/elected-officials/"`
- Update `"districts": 7` to match what the snapshot shows (likely 8 per planning research; verify against step 2 output)

**Step 6: Run unit tests**

```bash
pytest tests/unit/test_berkeley_county.py -v
```

Expected: all PASS.

**Step 7: Add to snapshot manifest**

```json
{
  "file": "berkeley_county.html",
  "url": "https://berkeleycountysc.gov/dept/council/elected-officials/",
  "adapter": "berkeley_county",
  "adapter_module": "scrapers.adapters.berkeley_county",
  "adapter_class": "BerkeleyCountyAdapter",
  "entry": {"id": "county:berkeley", "url": "https://berkeleycountysc.gov/dept/council/elected-officials/"},
  "min_members": 7
}
```

(Use `7` as the floor regardless of whether snapshot shows 7 or 8 — both satisfy.)

Run: `pytest tests/integration/test_real_snapshots.py -v -k berkeley` → PASS.

**Step 8: Refresh the data file**

```bash
python -m scrapers --state SC --jurisdiction county:berkeley
```

If the live fetch fails, use `scripts/refresh_from_snapshot.py county:berkeley tests/fixtures/snapshots/berkeley_county.html` (created in Task 2).

**Step 9: Verify**

```bash
python validate.py 2>&1 | grep "county:berkeley"
```

Expected: no district-coverage warning.

**Step 10: Commit**

```bash
git add scrapers/adapters/berkeley_county.py scrapers/__main__.py registry.json \
        tests/unit/test_berkeley_county.py \
        tests/fixtures/snapshots/berkeley_county.html \
        tests/fixtures/snapshots/snapshots.json \
        data/sc/local/county-berkeley.json
git commit -m "feat(scrapers): bespoke Berkeley County adapter parses elected-officials page"
```

---

## Task 4: `county:aiken` — extend `civicplus` with a council-page supplement

**Strategy:** The CivicPlus directory at `/directory.aspx?did=117` lists members with bare "Council Member" titles. But the council-members landing page at `https://sc-aikencounty.civicplus.com/529/Council-Members` groups members under "District N" section headings. Add an OPT-IN supplementary fetch step in `CivicPlusAdapter.scrape()` (not `parse()`) so the per-HTML parse stays hermetic.

**Important constraint from review:** Per Task 3's reasoning, `parse(html)` must remain pure. Override `scrape()` on the adapter instead — `scrape()` orchestrates `fetch + parse + enrich + normalize + validate`, so it's the right place for a second HTTP call.

**Files:**
- Modify: `scrapers/adapters/civicplus.py` — add `_extract_district_map_from_council_page()`, `_apply_district_map()`, and override `scrape()` when `councilMembersUrl` is set
- Modify: `registry.json` — add `adapterConfig.councilMembersUrl` for `county:aiken`
- Create: `tests/fixtures/snapshots/civicplus_aiken_directory.html` (the directory page used by the existing CivicPlus `parse()`)
- Create: `tests/fixtures/snapshots/civicplus_aiken_council_members.html` (the supplementary page that carries district headings)
- Modify: `scripts/refresh_from_snapshot.py` (from Task 2) — add `--civicplus-supplement <path>` flag
- Create: `tests/unit/test_civicplus_aiken_districts.py`

**Step 1: Save BOTH snapshots**

The CivicPlus adapter normally uses TWO HTTP fetches: the staff directory page (consumed by `parse()`) and the new supplementary council-members page (consumed by the `scrape()` override added in step 3). We need both saved so the deterministic fallback in step 6 can regenerate the data file without any network access.

```bash
# Primary: the staff directory the existing parse() handles
curl -s -A "OpenCivics/1.0 (+https://github.com/TimSimpsonJr/open-civics)" -L \
  --compressed \
  "https://www.aikencountysc.gov/directory.aspx?did=117" \
  -o tests/fixtures/snapshots/civicplus_aiken_directory.html

# Supplementary: the council-members page with District N headings
curl -s -A "OpenCivics/1.0 (+https://github.com/TimSimpsonJr/open-civics)" -L \
  --compressed \
  "https://sc-aikencounty.civicplus.com/529/Council-Members" \
  -o tests/fixtures/snapshots/civicplus_aiken_council_members.html
```

Inspect the supplementary structure to confirm the parser approach:

```bash
grep -oE 'District [0-9]+' tests/fixtures/snapshots/civicplus_aiken_council_members.html | sort -u
grep -i 'Honorable' tests/fixtures/snapshots/civicplus_aiken_council_members.html | head -10
```

The snapshot drives the parser — record the actual tag containing "District N" headings (`<h3>` or `<h2>` or `<strong>`) and adjust the implementation below to match.

**Step 2: Write failing tests for the two new helpers**

Create `tests/unit/test_civicplus_aiken_districts.py`:

```python
import os
import pytest
from scrapers.adapters.civicplus import CivicPlusAdapter


SNAPSHOT = os.path.join(os.path.dirname(__file__), "..", "fixtures",
                        "snapshots", "civicplus_aiken_council_members.html")


def test_council_members_page_yields_district_map():
    with open(SNAPSHOT, "r", encoding="utf-8") as f:
        html = f.read()
    mapping = CivicPlusAdapter._extract_district_map_from_council_page(html)
    assert len(mapping) == 8  # Aiken County has 8 single-member districts
    for district_num, name in mapping.items():
        assert 1 <= district_num <= 8
        assert isinstance(name, str) and name


def test_apply_district_map_updates_titles():
    members = [
        {"name": "Honorable Ron Felder", "title": "Council Member"},
        {"name": "Honorable Mike Kellems", "title": "Council Member"},
        {"name": "Honorable Gary Bunker", "title": "Chairman"},
    ]
    mapping = {1: "Honorable Ron Felder", 2: "Honorable Mike Kellems"}
    CivicPlusAdapter._apply_district_map(members, mapping)
    by_name = {m["name"]: m["title"] for m in members}
    assert by_name["Honorable Ron Felder"] == "Council Member, District 1"
    assert by_name["Honorable Mike Kellems"] == "Council Member, District 2"
    assert by_name["Honorable Gary Bunker"] == "Chairman"


def test_apply_district_map_tolerates_honorable_prefix_variance():
    """Directory may have 'Ron Felder' while the council page has 'Honorable Ron Felder',
    or vice versa. Match should still succeed."""
    members = [{"name": "Ron Felder", "title": "Council Member"}]
    mapping = {1: "Honorable Ron Felder"}
    CivicPlusAdapter._apply_district_map(members, mapping)
    assert members[0]["title"] == "Council Member, District 1"


def test_aiken_directory_plus_supplement_end_to_end():
    """End-to-end on the real Aiken snapshots: parse the directory, apply the
    supplement map, normalize. All 8 non-chair council members must end up
    seatClass=numbered with a populated seatLabel/seatId. This is the test
    that catches partial name-match failures — the validator's all-unknown
    check would let 6-of-8 coverage slip through."""
    from scrapers.normalize import normalize_member, NormalizationContext

    here = os.path.dirname(__file__)
    snaps = os.path.join(here, "..", "fixtures", "snapshots")
    with open(os.path.join(snaps, "civicplus_aiken_directory.html"),
              "r", encoding="utf-8") as f:
        directory_html = f.read()
    with open(os.path.join(snaps, "civicplus_aiken_council_members.html"),
              "r", encoding="utf-8") as f:
        supplement_html = f.read()

    adapter = CivicPlusAdapter({
        "id": "county:aiken",
        "url": "https://www.aikencountysc.gov/528/County-Council",
        "adapterConfig": {
            "baseUrl": "https://www.aikencountysc.gov",
            "councilPageId": "528",
            "directoryDeptId": "117",
            "councilMembersUrl": "https://sc-aikencounty.civicplus.com/529/Council-Members",
        },
    })
    members = adapter.parse(directory_html)
    mapping = CivicPlusAdapter._extract_district_map_from_council_page(supplement_html)
    CivicPlusAdapter._apply_district_map(members, mapping)

    ctx = NormalizationContext(level="local", jurisdiction_type="county",
                               jurisdiction_id="county:aiken")
    for m in members:
        normalize_member(m, ctx)

    district_members = [m for m in members
                        if m.get("office") == "council-member"
                        and m.get("leadership") not in ("chair", "vice-chair")]
    assert len(district_members) == 8, \
        f"Expected 8 district council members, got {len(district_members)}: " \
        f"{[m['name'] for m in district_members]}"
    for m in district_members:
        assert m["seatClass"] == "numbered", \
            f"{m['name']!r} got seatClass={m['seatClass']!r} (title={m['title']!r}) — " \
            f"likely a name-match failure between directory and supplement"
        assert m["seatLabel"] == "district", m
        assert m["seatId"] is not None, m
    # All 8 district IDs should be present, no duplicates
    ids = sorted(int(m["seatId"]) for m in district_members)
    assert ids == [1, 2, 3, 4, 5, 6, 7, 8], f"district ids = {ids}"
```

Run: `pytest tests/unit/test_civicplus_aiken_districts.py -v` → FAIL (helpers don't exist, end-to-end test fails because of helper failures).

**Step 3: Implement the helpers and `scrape()` override**

In `scrapers/adapters/civicplus.py`, add at the bottom of the class:

```python
@staticmethod
def _extract_district_map_from_council_page(html: str) -> dict[int, str]:
    """Parse a CivicPlus council-members page that groups members under
    District N headings. Returns {district_number: member_name}.

    Walks the document, tracking the most-recent District N heading; assigns
    the next person-looking line ("Honorable <name>") to that district.
    """
    soup = BeautifulSoup(html, "html.parser")
    mapping: dict[int, str] = {}
    current_district: int | None = None
    for el in soup.find_all(True):
        if el.name not in ("h1", "h2", "h3", "h4", "h5", "p", "strong"):
            continue
        text = el.get_text(strip=True)
        if not text:
            continue
        m = re.match(r"^District\s+(\d+)\s*$", text, re.IGNORECASE)
        if m:
            current_district = int(m.group(1))
            continue
        if current_district is not None and re.match(r"^Honorable\s+\S+", text):
            name = re.sub(r",\s*Council\s+Member\s*$", "", text).strip()
            if current_district not in mapping:
                mapping[current_district] = name
                current_district = None  # consume
    return mapping

@staticmethod
def _apply_district_map(members: list[dict], mapping: dict[int, str]) -> None:
    """Mutate member titles: 'Council Member' → 'Council Member, District N'.

    Tolerates 'Honorable' prefix variance and minor surname-only fallback."""
    def _strip_hon(name: str) -> str:
        return re.sub(r"^Honorable\s+", "", name).strip()

    name_to_district = {_strip_hon(name): dist for dist, name in mapping.items()}
    surname_to_district: dict[str, int] = {}
    for dist, name in mapping.items():
        bare = _strip_hon(name).split()
        if bare:
            surname_to_district.setdefault(bare[-1].lower(), dist)

    for m in members:
        if m.get("title") != "Council Member":
            continue
        bare = _strip_hon(m["name"])
        district = name_to_district.get(bare) \
                or surname_to_district.get(bare.split()[-1].lower() if bare else "")
        if district is not None:
            m["title"] = f"Council Member, District {district}"
```

Then override `scrape()` in the same class:

```python
def scrape(self) -> list[dict]:
    """Index-page scrape + optional supplementary council-members page.

    Network calls live here (not in parse) so parse(html) remains hermetic
    for snapshot tests. When adapterConfig.councilMembersUrl is set, this
    fetches the supplementary page and applies its district map to the
    directory members.
    """
    html = self.fetch()
    self._html = html
    members = self.parse(html)

    supp_url = self.config.get("councilMembersUrl")
    if supp_url:
        try:
            resp = requests.get(supp_url,
                                headers={"User-Agent": USER_AGENT},
                                timeout=30, allow_redirects=True)
            resp.raise_for_status()
            mapping = self._extract_district_map_from_council_page(resp.text)
            if mapping:
                self._apply_district_map(members, mapping)
            else:
                self.warnings.append(
                    f"councilMembersUrl returned empty district map for {self.id}")
        except requests.RequestException as e:
            self.warnings.append(
                f"councilMembersUrl fetch failed for {self.id}: {e}")

    normalized = self.normalize(members)
    return self.validate(normalized)
```

**Step 4: Update the registry**

In `registry.json` for `county:aiken`, add to `adapterConfig`:

```json
"councilMembersUrl": "https://sc-aikencounty.civicplus.com/529/Council-Members"
```

**Step 5: Add the directory snapshot to the integration manifest**

So the directory page is exercised by `tests/integration/test_real_snapshots.py` like the other adapters (a structural regression-detection net), append to `tests/fixtures/snapshots/snapshots.json`'s `snapshots` array:

```json
{
  "file": "civicplus_aiken_directory.html",
  "url": "https://www.aikencountysc.gov/directory.aspx?did=117",
  "adapter": "civicplus",
  "adapter_module": "scrapers.adapters.civicplus",
  "adapter_class": "CivicPlusAdapter",
  "entry": {
    "id": "county:aiken",
    "url": "https://www.aikencountysc.gov/528/County-Council",
    "adapterConfig": {
      "baseUrl": "https://www.aikencountysc.gov",
      "councilPageId": "528",
      "directoryDeptId": "117"
    }
  },
  "min_members": 8
}
```

(The supplementary `civicplus_aiken_council_members.html` stays helper-only — it's only consumed by `_extract_district_map_from_council_page` via the unit tests in step 2, not by `parse()`, so it doesn't belong in the integration manifest.)

**Step 6: Run the new tests, existing civicplus tests, AND the integration harness**

```bash
pytest tests/unit/test_civicplus_aiken_districts.py \
       tests/unit/test_civicplus_parse.py \
       tests/integration/test_real_snapshots.py -v -k 'civicplus or aiken'
```

Expected: all PASS. The existing civicplus tests are unaffected (they exercise `parse()` directly and the new logic lives in `scrape()`). The integration harness now also exercises `CivicPlusAdapter.parse()` against the saved Aiken directory snapshot, guarding against future regressions when CivicPlus changes its directory page structure.

**Step 7: Extend `refresh_from_snapshot.py` to handle the supplement, then refresh**

Before refreshing, extend the helper from Task 2 to accept an optional supplementary-snapshot path so the offline path mirrors the live `scrape()` flow.

Edit `scripts/refresh_from_snapshot.py`. Add a `--civicplus-supplement <path>` argument and, after `adapter.parse(html)`, apply the CivicPlus supplement when the flag is set:

```python
# Patch into scripts/refresh_from_snapshot.py
import argparse

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("jurisdiction_id")
    ap.add_argument("snapshot_path")
    ap.add_argument("--civicplus-supplement",
                    help="Path to a saved CivicPlus council-members page; "
                         "applies _extract_district_map_from_council_page + "
                         "_apply_district_map after parse() to mirror scrape().")
    args = ap.parse_args()

    # ... existing registry lookup + adapter construction ...

    with open(args.snapshot_path, "r", encoding="utf-8") as f:
        members = adapter.parse(f.read())

    if args.civicplus_supplement:
        from scrapers.adapters.civicplus import CivicPlusAdapter
        if not isinstance(adapter, CivicPlusAdapter):
            sys.exit("--civicplus-supplement only applies to CivicPlusAdapter jurisdictions")
        with open(args.civicplus_supplement, "r", encoding="utf-8") as f:
            mapping = CivicPlusAdapter._extract_district_map_from_council_page(f.read())
        CivicPlusAdapter._apply_district_map(members, mapping)

    members = adapter.normalize(members)
    adapter.validate(members)
    # ... existing meta + write logic ...
```

(The skeleton in Task 2 takes positional args; this step replaces the `if __name__ == "__main__":` body with the argparse-based `main()`. Update the call in Task 2 accordingly — `python scripts/refresh_from_snapshot.py place:aiken tests/fixtures/snapshots/aiken_city.html` still works because both args are positional.)

Then try the live refresh first:

```bash
python -m scrapers --state SC --jurisdiction county:aiken
```

If the live command succeeds and writes `data/sc/local/county-aiken.json` with district info, you're done. If it fails (CivicPlus blocks the request, supplementary URL times out, etc.), fall back to the deterministic snapshot path:

```bash
python scripts/refresh_from_snapshot.py county:aiken \
  tests/fixtures/snapshots/civicplus_aiken_directory.html \
  --civicplus-supplement tests/fixtures/snapshots/civicplus_aiken_council_members.html
```

This produces an identical-shape data file using only the saved snapshots — no network calls.

**Step 8: Verify**

```bash
python validate.py 2>&1 | grep "county:aiken"
```

Expected: no district-coverage warning (only the at-large chairman might still trip an unknown — that's a separate issue; the 8 district members are what the gate cares about).

**Step 9: Commit**

```bash
git add scrapers/adapters/civicplus.py registry.json \
        scripts/refresh_from_snapshot.py \
        tests/fixtures/snapshots/snapshots.json \
        tests/unit/test_civicplus_aiken_districts.py \
        tests/fixtures/snapshots/civicplus_aiken_directory.html \
        tests/fixtures/snapshots/civicplus_aiken_council_members.html \
        data/sc/local/county-aiken.json
git commit -m "feat(scrapers): civicplus supplements district info from council-members page"
```

**End of PR 1.** Open PR 1 here:

```bash
gh pr create --title "Districted scraper fixes (validator + 4 jurisdictions)" \
  --body "Closes coverage gap for place:north-charleston, place:aiken, county:berkeley, county:aiken. Adds validator warning for any future regressions. See docs/plans/2026-05-16-followup-districted-scraper-bugs-plan.md tasks 0–4."
```

---

## Tasks 5–7: Manual overrides for Akamai-blocked / district-less sources

These three jurisdictions can't be scraped for district info — Dorchester and Kershaw primary sites are Akamai-protected (HTTP 403 even via WebFetch and curl with a browser UA), and Jasper publishes no district data on its council page. Each task adds `SEAT_OVERRIDES` entries after a brief research step.

**Shared pattern (apply to each of Tasks 5, 6, 7):**

**Step 1 — Research:** Web-search for the canonical member→district mapping. Trustworthy sources, roughly in order:
- The county's redistricting / boundary GIS portal (often public-facing maps with elected-rep tooltips)
- South Carolina Election Commission certified election results (`scvotes.sc.gov`)
- Recent county council meeting minutes hosted on the county site (the PDF can usually be downloaded even when the index pages are blocked)
- Local newspaper coverage of the most recent county council election (Post and Courier, Index-Journal, etc.)

Cite the URL + retrieval date in a comment block above the new entries.

**Step 2 — Confirm against current data:** Cross-check the names against the current `data/sc/local/county-{jurisdiction}.json` to ensure the mapping covers exactly the scraped members. If a name doesn't match (e.g., abbreviation differences, recent resignation), update the live data via the underlying scraper first — overrides only work when keyed on exact `(jurisdiction_id, name)` pairs.

**Step 3 — Write the failing test:** Add a test class to a new `tests/unit/test_seat_overrides_districted.py`:

```python
import json
import os
import pytest

from scrapers.normalize import normalize_member, NormalizationContext

DATA = os.path.join(os.path.dirname(__file__), "..", "..", "data", "sc", "local")


def _load(jid: str) -> list[dict]:
    path = os.path.join(DATA, f"{jid.replace(':', '-')}.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)["members"]


@pytest.mark.parametrize("jurisdiction", [
    "county:dorchester",
    "county:kershaw",
    "county:jasper",
])
def test_all_council_members_numbered_via_manual_override(jurisdiction):
    """After normalization, every council member (excluding chair/vice-chair)
    should carry seatClass: numbered with seatSource: manual."""
    ctx = NormalizationContext(level="local", jurisdiction_type="county",
                               jurisdiction_id=jurisdiction)
    raw_members = _load(jurisdiction)
    for raw in raw_members:
        # Reset normalized fields to test the override stage cleanly
        for k in ("seatClass", "seatLabel", "seatId", "seatSource"):
            raw.pop(k, None)
        normalize_member(raw, ctx)
    for m in raw_members:
        if m.get("office") == "council-member" \
                and m.get("leadership") not in ("chair", "vice-chair"):
            assert m["seatClass"] == "numbered", \
                f"{jurisdiction}: {m['name']} not numbered"
            assert m["seatSource"] == "manual", \
                f"{jurisdiction}: {m['name']} not from manual override"
```

**Step 4 — Populate overrides:** Add entries to `scrapers/seat_overrides.py`. Example structure (research fills names/districts):

```python
# Dorchester County — 7 single-member districts. Primary site Akamai-blocked.
# Verified against {SOURCE_URL} on 2026-05-20.
("county:dorchester", "Edward Crosby"): {
    "seatClass": "numbered", "seatLabel": "district", "seatId": "1",
},
("county:dorchester", "Rita May Ranck"): {
    "seatClass": "numbered", "seatLabel": "district", "seatId": "2",
},
# ... repeat for all districted members ...
```

Per-jurisdiction comment header citing the research source and date is mandatory — future you needs to know whether the mapping is still valid.

**Step 5 — Run the test:** `pytest tests/unit/test_seat_overrides_districted.py::test_all_council_members_numbered_via_manual_override -v -k <jurisdiction>` should PASS.

**Step 6 — Run `python validate.py`:** Confirm no more "districted but all members have seatClass: unknown" warnings for the patched jurisdiction.

**Step 7 — Commit per jurisdiction:**

```bash
git add scrapers/seat_overrides.py tests/unit/test_seat_overrides_districted.py
git commit -m "feat(scrapers): seat overrides for {jurisdiction} (primary source blocked)"
```

One commit per jurisdiction keeps the research provenance reviewable. Tasks 5, 6, 7 share PR 2.

---

## Task 8: Close out the followup design doc

**Step 1: Run the full validator**

```bash
python validate.py 2>&1 | grep "districted but all" || echo "(no districted-coverage warnings — gap closed)"
```

Expected: the 7 affected jurisdictions are gone from the warning list. If any remain, return to that task before continuing.

**Step 2: Run the full test suite**

```bash
pytest -v
```

Expected: all PASS.

**Step 3: Update the followup design doc**

In `docs/plans/2026-05-16-followup-districted-scraper-bugs.md`, append:

```markdown
## Resolution

All 7 jurisdictions fixed via `docs/plans/2026-05-16-followup-districted-scraper-bugs-plan.md`:

- 4 scraper-side fixes (PR 1): north-charleston, aiken-city, berkeley-county, aiken-county
- 3 manual overrides (PR 2): dorchester-county, kershaw-county, jasper-county

The 14 "District count unverified" jurisdictions remain as a separate triage item.
```

**Step 4: Commit and finalize PR 2**

```bash
git add docs/plans/2026-05-16-followup-districted-scraper-bugs.md
git commit -m "docs: mark districted-scraper-bug followup as resolved"
gh pr create --title "Districted manual overrides (3 jurisdictions)" \
  --body "Closes coverage gap for county:dorchester, county:kershaw, county:jasper via seat_overrides.py. Closes out docs/plans/2026-05-16-followup-districted-scraper-bugs.md. See tasks 5–8 of the implementation plan."
```

---

## Remember

- **TDD per task:** failing test → minimal code → passing test → commit
- **Two PRs only:** Task 0–4 ship together; Task 5–8 ship together. No umbrella PR closing both.
- **Save HTML snapshots** for every adapter touched — they prevent silent regressions when the source page restructures.
- **`parse(html)` must stay pure** (no HTTP). Network calls live in `fetch()` or in a `scrape()` override.
- **`data/sc/`** (lowercase) is the actual data path. Don't write to `data/SC/`.
- **The validator function is `validate_local_file`**, not `validate_local_json`.
- **Cite sources** in `seat_overrides.py` comments — verified date + URL — so the entries can be re-validated next year.
- **Keep the validator warning** — it's the regression alarm. Don't silence it; fix the underlying gap.
