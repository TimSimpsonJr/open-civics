# Local Adapter Audit: Automate All SC Jurisdictions

## Context

This is a handoff document for a Claude instance with unrestricted network
access. The goal is to audit all 81 manually-entered local jurisdictions in
deflocksc-website and build a plan to automate every one of them.

**Related documents (in this same `docs/` directory):**
- `scraper-changes.md` — Recent changes to the state legislator scraper
  (email backfill logic)
- `shared-repo-plan.md` — Architecture plan for extracting scrapers into a
  shared repo covering all US levels (federal, state, local)

## The problem

We have 96 local jurisdictions in `src/data/registry.json`. Only 15 are
scraped automatically. The other 81 use `"adapter": "manual"`, meaning their
data was entered by hand and goes stale silently when council members change.

**We want zero manual jurisdictions.** Every jurisdiction should have a
working scraper that runs on a schedule.

## Current automated adapters

| Adapter | File | Jurisdictions | How it works |
|---------|------|---------------|-------------|
| `civicplus` | `scripts/scrape_reps/adapters/civicplus.py` | 13 | Config-driven. Scrapes CivicPlus staff directory pages. Handles JS email deobfuscation (`var w`/`var x`). Needs `baseUrl` and `councilPageId` in registry config. |
| `greenville_county` | `scripts/scrape_reps/adapters/greenville_county.py` | 1 | Custom. Scrapes two pages (listing + contacts), merges by district. JS email deobfuscation (`var email`/`var emailHost`). |
| `greenville_city` | `scripts/scrape_reps/adapters/greenville_city.py` | 1 | Custom. Uses CivicPlus headless CMS JSON API with JWT auth and pagination. |

All adapters inherit from `scripts/scrape_reps/adapters/base.py` which
provides the `fetch → parse → normalize → validate` pipeline.

## Your task

### Phase 1: Platform identification

For each of the 60 manual jurisdictions that have URLs (listed below), fetch
the page and identify:

1. **What CMS/platform** the site runs on
2. **Whether council member emails are visible** on the page
3. **Whether emails are JS-obfuscated** (look for `document.write`, inline
   `<script>` tags with email variables, etc.)
4. **The HTML structure** of the member listing (table, cards, divs, etc.)

**Platform detection hints:**
- **CivicPlus**: `civicplus` in CSS/JS paths, `/directory.aspx`, `cpCMS`,
  "CivicPlus" in footer, `civicengage` references
- **Revize**: `revize.com` in source, `revize` in CSS/JS paths
- **Granicus**: `granicus.com` references, `govoffice` in paths
- **Municode**: `municode.com` references
- **WordPress**: `wp-content/`, `wp-includes/` in source
- **SC.gov Palmetto SiteBuilder**: `palmetto` references, `.sc.gov` domain
  with state-standard template
- **Squarespace/Wix**: characteristic script tags and meta content

### Phase 2: Group by platform and assess

Produce a summary table like:

```
| Platform        | Count | Existing adapter? | Effort to cover |
|-----------------|-------|-------------------|-----------------|
| CivicPlus       | N     | Yes               | Config only     |
| Revize          | N     | No                | New adapter     |
| WordPress       | N     | No                | New adapter     |
| ...             | ...   | ...               | ...             |
```

For each platform group, pick one representative site and document:
- The URL structure for the council member page
- How member data is structured in the HTML (table rows, cards, etc.)
- Where name, title/district, email, and phone appear
- Whether the pattern is consistent across all sites in that group

### Phase 3: Identify missing URLs

These jurisdictions have no URL in the registry. Find their official
council/government page:

- `county:allendale` — Allendale County Council
- `place:allendale` — Town of Allendale
- `place:moncks-corner` — Town of Moncks Corner
- `place:st-matthews` — Town of St. Matthews
- `place:manning` — City of Manning
- `place:st-george` — Town of St. George
- `place:edgefield` — Town of Edgefield
- `place:winnsboro` — Town of Winnsboro
- `place:ridgeland` — Town of Ridgeland
- `place:camden` — City of Camden
- `place:bennettsville` — City of Bennettsville
- `place:walhalla` — City of Walhalla
- `county:union` — Union County Council
- `place:union` — City of Union
- `county:williamsburg` — Williamsburg County Council
- `place:kingstree` — Town of Kingstree

### Phase 4: Write a report

Produce a final document with:

1. **Complete platform breakdown** — every jurisdiction categorized
2. **Recommended adapter strategy** — which new adapters to build, in what
   order, and how many jurisdictions each would cover
3. **CivicPlus quick wins** — which manual jurisdictions are actually
   CivicPlus sites and can be automated immediately by adding config to the
   existing adapter
4. **Jurisdictions that will need one-off adapters** — flag these so we know
   the true tail of custom work
5. **Missing URL jurisdictions** — found URLs or confirmation that no
   official page exists

## Manual jurisdictions to audit (60 with URLs)

```
place:spartanburg         https://www.cityofspartanburg.org/city-council
county:anderson           https://andersoncountysc.org/county-council
place:anderson            https://www.cityofandersonsc.com/city-council
county:pickens            https://www.co.pickens.sc.us/county_council/index.php
county:laurens            https://www.laurenscountysc.gov/government/county-council
county:charleston         https://www.charlestoncounty.org/departments/county-council/index.php
place:north-charleston    https://www.northcharleston.org/government/city_council/city_council_members_and_districts.php
county:richland           https://www.richlandcountysc.gov/Government/Elected-Offices/County-Council
place:columbia            https://citycouncil.columbiasc.gov/
county:lexington          https://lex-co.sc.gov/county-council
county:horry              https://www.horrycountysc.gov/county-council
place:myrtle-beach        https://www.cityofmyrtlebeach.com/government/mayor___city_council/index.php
place:conway              https://www.conwaysc.gov/city_council/
county:york               https://www.yorkcountygov.com/375/County-Council
place:rock-hill           https://www.cityofrockhill.com/government/city-council
county:beaufort           https://www.beaufortcountysc.gov/council/index.html
place:hilton-head         https://hiltonheadislandsc.gov/government/town_council/index.php
county:abbeville          https://abbevillecountysc.com/county-council/
place:abbeville           https://www.abbevillecitysc.com/189/City-Council
place:aiken               https://www.cityofaikensc.gov/government/city-council/
county:bamberg            https://www.bambergcounty.sc.gov/county-council
place:bamberg             https://www.cityofbambergsc.gov/citycouncilofficials
place:barnwell            https://www.cityofbarnwell.com/government
county:berkeley           https://berkeleycountysc.gov/dept/council/
place:goose-creek         https://www.goosecreeksc.gov/government/mayor-and-city-council
county:calhoun            https://calhouncounty.sc.gov/officials
county:cherokee           https://cherokeecountysc.gov/county-council-administration/
place:gaffney             https://www.cityofgaffney-sc.gov/184/City-Council
county:chester            https://chestercountysc.gov/government/chester-county-council/
place:chester             https://www.chestersc.org/
county:chesterfield       https://www.chesterfieldcountysc.com/countycouncil
county:clarendon          https://www.clarendoncountysc.gov/our-government/council/
county:colleton           https://www.colletoncounty.org/county-council
place:walterboro          https://www.walterborosc.org/city-council
county:darlington         https://www.darcosc.com/government/county_council/index.php
place:darlington          https://www.cityofdarlington.com/mayor-council/
county:dillon             https://dilloncounty.sc.gov/administrator/county-council
place:dillon              https://cityofdillonsc.gov/citycouncil
county:dorchester         https://www.dorchestercountysc.gov/government/county-council
county:edgefield          https://edgefieldcounty.sc.gov/county-council/
county:fairfield          https://www.fairfieldsc.com/departments/county-council
county:florence           https://www.florenceco.org/council/
place:florence            https://www.cityofflorencesc.gov/city-council
place:georgetown          https://www.georgetownsc.gov/governmental_services/city_council.php
county:greenwood          https://www.greenwoodcounty-sc.gov/county-council
place:greenwood           https://www.cityofgreenwoodsc.com/government/city_council.php
place:hampton             https://www.hamptonsc.gov/mayor-council
county:jasper             https://www.jaspercountysc.gov/government/council/
county:kershaw            https://www.kershaw.sc.gov/county-council/council-members
county:lee                https://www.leecountysc.org/council/members/
county:marion             https://www.marionsc.org/government/county_council/index.php
place:marion              https://marionsc.gov/city-council-marion-sc/
county:marlboro           https://marlborocounty.sc.gov/government_/council.php
county:mccormick          https://www.mccormickcountysc.org/
place:mccormick           https://www.townofmccormicksc.com/government/town-officials-staff/
county:newberry           https://www.newberrycounty.gov/county-council
place:newberry            https://www.cityofnewberry.com/government/city_council.php
county:oconee             https://oconeesc.com/council-home/council-information
place:orangeburg          https://www.orangeburg.sc.us/city-council
county:saluda             https://saludacounty.sc.gov/county-council
place:saluda              https://www.townofsaluda.com/town-council
county:sumter             https://www.sumtercountysc.gov/our_council/council_information/council_frequently_asked_questions.php
place:sumter              https://www.sumtersc.gov/city-council
place:bishopville         https://cityofbishopvillesc.com/
place:darlington          https://www.cityofdarlington.com/mayor-council/
place:dillon              https://cityofdillonsc.gov/citycouncil
```

## Key files to reference

- `scripts/scrape_reps/adapters/base.py` — Base adapter class (65 lines)
- `scripts/scrape_reps/adapters/civicplus.py` — CivicPlus adapter (~294 lines)
- `scripts/scrape_reps/adapters/greenville_county.py` — Custom adapter example (~191 lines)
- `scripts/scrape_reps/adapters/greenville_city.py` — API-based adapter example (~291 lines)
- `scripts/scrape_reps/__main__.py` — Scraper orchestrator
- `src/data/registry.json` — Jurisdiction configuration
- `src/data/local-councils.json` — Current local council data (output)
- `scripts/validate-data.py` — Data validation script

## Output format

The existing adapter output schema for local councils is:

```json
{
  "name": "John Smith",
  "title": "Council Member District 3",
  "email": "jsmith@county.gov",
  "phone": "(864) 555-1234",
  "source": "civicplus",
  "lastUpdated": "2026-03-13"
}
```

All adapters must produce records with at minimum `name` and `title`.
`email` and `phone` are strongly preferred but the validator only warns
(doesn't fail) if missing.
