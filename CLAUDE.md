# call-your-rep

## Overview

Shared repo for US legislator contact data. Python scrapers produce JSON data published as two npm packages: `call-your-rep` (rep contact info) and `call-your-rep-boundaries` (district GeoJSON).

## Commands

- `python -m scrapers --state SC` — scrape all SC data
- `python -m scrapers --state SC --state-only` — state legislators only
- `python -m scrapers --state SC --local-only` — local councils only
- `python -m scrapers --state SC --boundaries-only` — boundaries only
- `python -m scrapers --dry-run` — preview without scraping
- `python validate.py` — validate all data files

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

## Adding a New State

1. Add state block to `registry.json` under `states.XX`
2. Add email rules to `scrapers/state_email_rules.py`
3. Run `python -m scrapers --state XX`
4. Add local adapters as needed in `scrapers/adapters/`

## Adding a Local Adapter

1. Create `scrapers/adapters/my_jurisdiction.py` extending `BaseAdapter`
2. Register it in `scrapers/__main__.py` ADAPTERS dict
3. Add jurisdiction entry to `registry.json` under the state's `jurisdictions` array
4. Run `python -m scrapers --jurisdiction county:my-jurisdiction`
