# Dorchester SCAC Vacancy Fix — Design

## Problem

A fresh `scac`-adapter scrape of Dorchester County (`county:dorchester`) fails the
`test_seat_overrides_districted[county:dorchester]` gate, which blocked the weekly
data-update auto-merge (PR #45, ci-issue #46). Two defects:

1. **Vacant-seat placeholder ingested as a member.** The SCAC directory
   (`https://www.sccounties.org/county/dorchester-county/directory`) includes the row
   `<td>DorchesterCouncil Vacant</td>` — a placeholder for an unfilled seat. The `scac`
   adapter has no vacancy handling, so it emits a member literally named
   "DorchesterCouncil Vacant".
2. **Stale override roster.** Frankie Staropoli — a real sitting council member — is
   missing from `scrapers/seat_overrides.py` and the test's EXPECTED map.

## Verified roster (2026-06-09)

Dorchester County Council = 7 single-member districts, all currently filled:

| District | Member | Role |
|---|---|---|
| 1 | Peter Smith | |
| 2 | C. David Chinnis | Chairman |
| 3 | Rita May Ranck | Vice Chair |
| 4 | S. Todd Friddle | |
| 5 | Edward Crosby | |
| **6** | **Frankie Staropoli** | (new) |
| 7 | James Byars | |

District 6: Frankie Staropoli won the March/May 2026 special election to replace
**Bill Hearn**, who left D6 to become the **county attorney** — corroborated by the same
SCAC directory now listing "William Hearn, Attorney". No current vacancy; the SCAC
"Vacant" row is stale leftover from before Staropoli was seated.
Sources: Post & Courier, Live 5 News, ABC News 4, Ballotpedia.

## Approach

1. **`scac.py` — skip vacant-seat rows (general).** In `parse()`, skip any row whose
   name matches a vacancy pattern (case-insensitive "vacant"). Chosen over emitting a
   `vacant: true` record (YAGNI: a vacancy carries no person, contact, or seat to track,
   and a synthetic vacant record would complicate the override + normalization path).
   Benefits every SCAC-sourced county, not just Dorchester.
2. **`seat_overrides.py` — add D6.** Add `("county:dorchester", "Frankie Staropoli")` →
   numbered / district / "6". Replace the stale "District 6 currently vacant" comment
   with the verified replacement story + sources.
3. **`test_seat_overrides_districted.py` — extend EXPECTED.** Add
   `"Frankie Staropoli": ("numbered", "district", "6")` to the Dorchester map.
4. **Regression test + snapshot.** Save the live SCAC Dorchester HTML under
   `tests/fixtures/snapshots/` and add a test asserting the adapter (a) skips the
   "Vacant" row and (b) returns the 7 real members.
5. **Refresh `data/sc/local/county-dorchester.json`** to the corrected 7-member roster.

## Testing

- New `scac` vacancy-skip test against the saved snapshot.
- Extended districted-override coverage test (Staropoli, district 6).
- Full `pytest tests/unit/` + `python validate.py` green.

## Out of scope (filed as follow-ups)

- #47 — automated discrepancy-verification tooling (detect override/scrape drift, verify
  against authoritative sources, propose fixes).
- #48 — granular updates so one bad jurisdiction can't block the whole weekly refresh.
