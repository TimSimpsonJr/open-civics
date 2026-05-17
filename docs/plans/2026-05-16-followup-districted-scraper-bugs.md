# Followup: Districted jurisdictions missing seat info in scraped data

The following SC jurisdictions' registry notes describe single-member districts, wards, or seats — but the current adapter / fallback scraper does not capture that structural info into member records. The data-model-normalization audit (Task A14) found that **no** member record for these jurisdictions carries district info, even though the registry's own `notes` field documents the jurisdiction as districted.

These cannot be patched with `councilDefaults: { seatClass: "at-large" }` because that would permanently hide the real scraper bug: a districted council whose members all come through as `seatClass: unknown` is a coverage gap, not an at-large council.

## Affected jurisdictions

Districted per registry notes, but no district info in scraped members:

- **county:aiken** — "8 single-member districts + chairman elected at-large. CivicPlus website. Boundary from SC Revenue & Fiscal Affairs statewide county council districts shapefile."
- **county:berkeley** — "7 single-member districts + county supervisor. Supervisor-Council form of government. Boundary from SC Revenue & Fiscal Affairs statewide county council districts shapefile."
- **county:dorchester** — "7 single-member districts, 4-year terms. Council-Administrator form. Boundary from SC Revenue & Fiscal Affairs statewide county council districts shapefile."
- **county:jasper** — "5 council members elected by township districts. Boundary from SC Revenue & Fiscal Affairs statewide county council districts shapefile."
- **county:kershaw** — "6 single-member districts + chairman elected at-large. Boundary from SC Revenue & Fiscal Affairs statewide county council districts shapefile."
- **place:aiken** — "6-1 plan: Mayor at-large + 6 single-member districts. Cloudflare-protected site."
- **place:north-charleston** — "10 single-member districts + mayor elected at-large"

## Scope

Out of scope for the schema migration (PR `data-model-normalization`); the gap predates this work. The migration intentionally added `councilDefaults` only to councils whose registry notes explicitly confirm all-at-large composition.

## Fix path

After the underlying scraper / adapter is fixed for each jurisdiction (most likely by extending the relevant adapter to capture title fields like "District 3" or by parsing structured columns on the source page), members will have `seatClass: numbered` via the normal title parsing pipeline (stage 2) without needing `councilDefaults` overrides. `seatId` and `seatLabel` will populate from the parsed title.

Until then, these members will continue to carry `seatClass: unknown`, which correctly signals the gap rather than silently misclassifying them.

## Also flagged

The audit also surfaced 14 jurisdictions whose registry notes only say "District count unverified" — composition is ambiguous and could be either at-large or districted. Investigate these on a per-jurisdiction basis to verify with official sources before adding `councilDefaults` or filing a districted-scraper-gap fix:

- place:allendale, place:bishopville, place:camden, place:edgefield, place:georgetown, place:hampton, place:manning, place:moncks-corner, place:ridgeland, place:saluda, place:st-matthews, place:union, place:walhalla, place:walterboro

Suggested label: `autonomous-safe`
