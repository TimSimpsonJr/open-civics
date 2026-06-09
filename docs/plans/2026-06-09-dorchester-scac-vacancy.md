# Dorchester SCAC Vacancy Fix — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the `scac` adapter skip vacant-seat placeholder rows and add verified District 6 member Frankie Staropoli, so Dorchester scrapes pass the gate and auto-merge.

**Architecture:** General skip-vacant fix in `scac.py` `parse()`; Dorchester roster completed in `seat_overrides.py` + the override-coverage test; snapshot regression test; data file regenerated via `refresh_from_snapshot.py`.

**Tech Stack:** Python 3.12, BeautifulSoup4, pytest.

---

### Task 1: Save + register the SCAC Dorchester snapshot

**Files:**
- Create: `tests/fixtures/snapshots/scac_dorchester.html`
- Modify: `tests/fixtures/snapshots/snapshots.json`

**Step 1:** Fetch + save the live SCAC directory:
```bash
python -c "import requests; open('tests/fixtures/snapshots/scac_dorchester.html','w',encoding='utf-8').write(requests.get('https://www.sccounties.org/county/dorchester-county/directory', headers={'User-Agent':'OpenCivics/1.0 (+https://github.com/TimSimpsonJr/open-civics)'}, timeout=30).text)"
```

**Step 2:** Append to the `snapshots` array in `snapshots.json`:
```json
{
  "file": "scac_dorchester.html",
  "url": "https://www.sccounties.org/county/dorchester-county/directory",
  "adapter": "scac",
  "adapter_module": "scrapers.adapters.scac",
  "adapter_class": "ScacAdapter",
  "entry": {"id": "county:dorchester", "url": "https://www.dorchestercountysc.gov/government/county-council/council-members"},
  "min_members": 7
}
```

**Step 3:** Commit (`test(scac): add Dorchester SCAC directory snapshot`).

---

### Task 2: scac adapter skips vacant-seat rows (TDD)

**Files:**
- Create: `tests/unit/test_scac_vacancy.py`
- Modify: `scrapers/adapters/scac.py` (`parse()`)

**Step 1 — RED:** write `tests/unit/test_scac_vacancy.py`:
```python
import os
import pytest

SNAPSHOT = os.path.join(os.path.dirname(__file__), "..", "fixtures",
                        "snapshots", "scac_dorchester.html")
EXPECTED_NAMES = {
    "Peter Smith", "C. David Chinnis", "Rita May Ranck", "S. Todd Friddle",
    "Edward Crosby", "Frankie Staropoli", "James Byars",
}


@pytest.fixture
def html():
    with open(SNAPSHOT, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def adapter():
    from scrapers.adapters.scac import ScacAdapter
    return ScacAdapter({"id": "county:dorchester",
                        "url": "https://www.dorchestercountysc.gov/government/county-council/council-members"})


class TestScacVacancy:
    def test_skips_vacant_placeholder_row(self, adapter, html):
        names = {m["name"] for m in adapter.parse(html)}
        assert not any("vacant" in n.lower() for n in names)

    def test_returns_seven_real_members(self, adapter, html):
        assert {m["name"] for m in adapter.parse(html)} == EXPECTED_NAMES
```

**Step 2:** Run `python -m pytest tests/unit/test_scac_vacancy.py -v` → expect FAIL ("DorchesterCouncil Vacant" present).

**Step 3 — GREEN:** in `scrapers/adapters/scac.py` `parse()`, immediately after the `if not name or not position: continue` guard, add:
```python
            # Skip vacant-seat placeholder rows: SCAC lists an unfilled seat as
            # a "<County>Council Vacant" name with no real person behind it.
            if "vacant" in name.lower():
                continue
```

**Step 4:** Run the test again → expect PASS.

**Step 5:** Commit (`fix(scac): skip vacant-seat placeholder rows`).

---

### Task 3: Add Staropoli (District 6) to override + EXPECTED

**Files:**
- Modify: `scrapers/seat_overrides.py`
- Modify: `tests/unit/test_seat_overrides_districted.py`

**Step 1:** In `seat_overrides.py`, after the `James Byars` Dorchester entry add:
```python
    ("county:dorchester", "Frankie Staropoli"): {
        "seatClass": "numbered", "seatLabel": "district", "seatId": "6",
    },
```
Update the block comment: District 6 is no longer vacant — filled by Frankie Staropoli (won the 2026 special election to replace Bill Hearn, who left D6 to become county attorney). Cite Post & Courier / Ballotpedia; note SCAC corroboration ("William Hearn, Attorney" in same directory).

**Step 2:** In `test_seat_overrides_districted.py`, add to the `county:dorchester` EXPECTED map:
```python
        "Frankie Staropoli": ("numbered", "district", "6"),
```

**Step 3:** Commit (`data(dorchester): add District 6 member Frankie Staropoli`).

---

### Task 4: Regenerate the Dorchester data file

**Files:** Modify `data/sc/local/county-dorchester.json`

**Step 1:** `python scripts/refresh_from_snapshot.py county:dorchester tests/fixtures/snapshots/scac_dorchester.html`
→ Expect `Wrote .../county-dorchester.json`.

**Step 2:** Verify: `python -c "import json; d=json.load(open('data/sc/local/county-dorchester.json',encoding='utf-8')); print(len(d['members'])); print(sorted(m['name'] for m in d['members']))"`
→ Expect 7 members, includes `Frankie Staropoli`, no `Vacant`, seats 1-7 all assigned.

**Step 3:** Commit (`data(dorchester): refresh roster to 7 members (Staropoli D6)`).

---

### Task 5: Full verification + PR

**Step 1:** `python -m pytest tests/unit/ -q && python validate.py`
→ Expect all green, including `test_seat_overrides_districted[county:dorchester]`; validate.py clean (only the pre-existing abbeville phone warning).

**Step 2:** Push + open PR against `master` (validation gate runs; merge when green). Note in the body that this resolves the Dorchester block behind PR #45 / ci-issue #46.
