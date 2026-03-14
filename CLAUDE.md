# call-your-rep

## Overview

Shared repo for US legislator contact data. Python scrapers produce JSON data published as two npm packages: `call-your-rep` (rep contact info) and `call-your-rep-boundaries` (district GeoJSON).

## Commands

- `python -m scrapers --state SC` — scrape all SC data
- `python -m scrapers --state SC --state-only` — state legislators only
- `python -m scrapers --state SC --local-only` — local councils only
- `python -m scrapers --state SC --boundaries-only` — boundaries only
- `python -m scrapers --state SC --skip-boundaries` — state + local, skip boundaries
- `python -m scrapers --dry-run` — preview without scraping
- `python validate.py` — validate all data files
- `pytest tests/unit/ -v` — run unit tests (fast)
- `pytest -v` — run all tests including integration
- `python scripts/refresh_snapshots.py` — refresh integration test HTML snapshots

## Architecture

- **Scrapers** (`scrapers/`): Python package with adapter pattern for local council sites
  - `state.py` — OpenStates CSV download + phone backfill from scstatehouse.gov
  - `boundaries.py` — Census TIGER + ArcGIS boundary builder
  - `state_email_rules.py` — per-state email format conventions
  - `adapters/` — per-site scrapers (CivicPlus, Greenville County, Greenville City)
  - `adapters/base.py` — abstract base: fetch -> parse -> normalize -> validate pipeline
- **Registry** (`registry.json`): nested by state code, contains source URLs, adapter configs, boundary sources
- **Data** (`data/{state}/`): state.json, local/*.json, boundaries/*.json
- **Validation** (`validate.py`): schema checks, sanity checks (>50% member drop detection), boundary coordinate validation

## Conventions

- Data files include a `meta` block with `state`, `level`, `lastUpdated`, `source`
- Local council files are per-jurisdiction (one file per council, not one big monolith)
- User-Agent: `CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)`
- Python 3.12+
- Adapters extend `BaseAdapter` and implement `fetch()` and `parse()`

## Safety Gate

Scrapers never commit directly to main. The workflow:
1. Scraper commits to `data-update/*` branch and opens PR
2. Validation runs as PR check
3. Auto-merge if validation passes
4. npm publish runs weekly from main

## npm Publishing Setup

Two secrets must be configured in GitHub repo settings:

1. **NPM_TOKEN** — npm automation token for publishing
   - Go to https://www.npmjs.com → Access Tokens → Generate New Token → Automation
   - Copy the token
   - Go to GitHub repo → Settings → Secrets and variables → Actions → New repository secret
   - Name: `NPM_TOKEN`, Value: the token

The `GITHUB_TOKEN` is auto-provided by GitHub Actions (no setup needed).

## Adding a New State

1. Add state block to `registry.json` under `states.XX`
2. Add email rules to `scrapers/state_email_rules.py`
3. Run `python -m scrapers --state XX`
4. Add local adapters as needed in `scrapers/adapters/`

## Adding a Local Adapter

Before writing a bespoke adapter, check these in order:

1. **Check for JSON APIs first** — probe the site for structured data endpoints:
   - CivicLive/ConnectSuite: `GET {origin}/sys/api/directory` (see `bamberg_city.py`)
   - WordPress REST API: `GET {origin}/wp-json/wp/v2/` — look for custom post types like `people` or `team`
   - CivicPlus headless CMS: check page source for `civicplus-headless` tokens (see `greenville_city.py`)
   - Drupal JSON:API: `GET {origin}/jsonapi` (usually locked down, but worth checking)
2. **Try shared adapters** — check if the site matches an existing pattern:
   - `civicplus` — CivicPlus staff directory pages with `directoryDeptId` config
   - `revize` / `generic_mailto` — Revize CMS freeform pages with mailto links
   - `table` — any page with an HTML table containing name/email/phone columns
   - `drupal_views` — Drupal sites with `views-row` or `person-item` patterns
3. **Fall back to MASC/SCAC** if the primary site is WAF-blocked (403):
   - Cities/towns: `masc` adapter pulls from `https://www.masc.sc/municipality/{slug}` (names + titles only)
   - Counties: `scac` adapter pulls from `https://www.sccounties.org/county/{slug}/directory` (names + titles + phones)
4. **Write a bespoke adapter** only if none of the above work:
   - Create `scrapers/adapters/my_jurisdiction.py` extending `BaseAdapter`
   - Register it in `scrapers/__main__.py` ADAPTERS dict
   - Add jurisdiction entry to `registry.json` under the state's `jurisdictions` array
   - Run `python -m scrapers --jurisdiction county:my-jurisdiction`
