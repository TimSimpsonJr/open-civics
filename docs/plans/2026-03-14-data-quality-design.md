# Data Quality Improvement Design

## Goal

Fill contact info gaps across all 96 SC jurisdictions and add executive representatives (Governor, Lt. Governor, mayors). Establish an ongoing quality report to track coverage.

## Scope

Five workstreams, all independent:

1. Adapter upgrades (6 sites with recoverable missing data)
2. General contact fallback (12+ sites with no individual contact info)
3. Missing mayors (10 cities)
4. Governor + Lt. Governor in state.json
5. Quality report script

## 1. Adapter Upgrades

Six sites have contact info on their websites that our scrapers aren't capturing.

**New adapters replacing MASC fallback:**

- **Rock Hill** -- new bespoke adapter, scrape member profile sub-pages at `/government/city-council/members/{slug}` for email + phone
- **Aiken** -- new bespoke adapter, scrape main council page for individual phone numbers

**Existing adapter fixes:**

- **Kershaw County** -- pull emails from staff directory table on `/our-county`
- **Beaufort County** -- follow member profile sub-page links for phone numbers
- **Richland County** -- capture phone numbers (already on the same page as email)
- **Columbia** -- follow profile links on `citycouncil.columbiasc.gov` subdomain for phones

Each is an independent adapter change with no shared dependencies.

## 2. General Contact Fallback

For jurisdictions where individual contact info doesn't exist, add a `contact` field to the `meta` block:

```json
{
  "meta": {
    "contact": {
      "phone": "803-259-3266",
      "email": "",
      "note": "City Hall - no individual council member contact info published"
    }
  }
}
```

Adapters scrape city hall phone from the page footer / contact page. The `note` field explains why individual info is missing.

**Affected sites:** Barnwell, Dillon, Edgefield, Marion (city), McCormick, St. George, St. Matthews, Bishopville, and other zero-contact jurisdictions.

**Schema:** `validate.py` recognizes `meta.contact` but does not require it.

## 3. Missing Mayors

10 cities don't include their mayor in the member list:
Abbeville, Camden, Charleston, Columbia, Mount Pleasant, Myrtle Beach, Newberry, North Charleston, Ridgeland, Walterboro.

Two categories:
- **Mayor on page but not captured** -- adapter parses council section only, mayor listed separately. Fix: widen the selector.
- **Mayor on a different page** -- e.g., `/mayor` vs `/city-council`. Fix: fetch second URL and merge results.

Mayor added as a regular member with `"title": "Mayor"`. No schema change (40 cities already do this).

## 4. Governor + Lt. Governor

Add an `executive` array to `state.json`:

```json
{
  "executive": [
    {
      "name": "Henry McMaster",
      "title": "Governor",
      "email": "governor@gov.sc.gov",
      "phone": "803-734-2100"
    },
    {
      "name": "Pamela Evette",
      "title": "Lieutenant Governor",
      "email": "ltgovernor@ltgov.sc.gov",
      "phone": "803-734-2080"
    }
  ]
}
```

**Source:** `governor.sc.gov` and `ltgov.sc.gov`.

**Implementation:** Add `scrape_executive()` in `scrapers/state.py`. Validation updated to check the `executive` key.

## 5. Quality Report Script

`scripts/quality_report.py` scans all data files and produces a coverage dashboard.

**Checks per jurisdiction:**
- Has email? (any member with non-empty email)
- Has phone? (any member with non-empty phone)
- Has executive? (mayor for cities, chairman for counties)
- Has general contact? (`meta.contact` present)
- Member count (flags if 0)

**Output:** Markdown table to stdout, `--json` for machine-readable.

**Integration:** `scrape.yml` runs this after scraping and appends summary stats to the PR body. Full report uploaded as workflow artifact.

## Research Findings

### Zero-contact sites (genuinely no individual data available)

| Site | General Phone | Notes |
|------|--------------|-------|
| Barnwell | 803-259-3266 | City Hall |
| Dillon | 843-774-0040 | Footer; clerk email available |
| Edgefield | 803-637-4014 | Town email also available |
| Marion (city) | 843-423-5961 | All members share city hall number |
| McCormick | 864-852-2225 | Footer |
| St. George | 843-563-3032 | Header |
| St. Matthews | 803-874-2405 | Footer |
| Bishopville | 803-484-5948 | Contact forms only, no direct emails |

### Partial-contact sites (missing field not available on site)

Phone-only (no emails on site): Berkeley, Clarendon, Dorchester, Lee, Marlboro, Orangeburg, York counties; Bamberg, Hampton, Kingstree cities.

Email-only (no phones on site): Florence County; Georgetown city, Myrtle Beach, Sumter, Walterboro, Ridgeland cities.

### Sites currently down

Camden (redirects to tourism site), Calhoun County, Saluda County, Allendale, Bamberg (SSL), Hampton, Gaffney (domain expired), Conway (404s).
