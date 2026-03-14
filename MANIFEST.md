# MANIFEST — call-your-rep

## Stack

- **Language:** Python 3.12+ (scrapers, validation), JSON (data, config)
- **Dependencies:** requests, beautifulsoup4, geopandas, shapely
- **Publish:** Two npm packages (`call-your-rep`, `call-your-rep-boundaries`) via GitHub Actions

## Structure

```
call-your-rep/
├── registry.json                  # Master config: states, jurisdictions, boundary sources, adapter configs
├── package.json                   # npm package def for call-your-rep (rep contact data)
├── boundaries-package.json        # npm package def for call-your-rep-boundaries (district GeoJSON)
├── requirements.txt               # Python dependencies (pinned versions)
├── validate.py                    # Data validation: schema checks, member count sanity, coordinate bounds
│
├── scrapers/                      # Python package — scraper orchestration + adapters
│   ├── __init__.py
│   ├── __main__.py                # CLI entry point + ADAPTERS dict mapping adapter names to classes
│   ├── state.py                   # OpenStates CSV download + scstatehouse.gov phone backfill
│   ├── boundaries.py              # Census TIGER/Line + ArcGIS boundary downloader/simplifier
│   ├── state_email_rules.py       # Per-state email format conventions for backfill
│   └── adapters/                  # Per-site scraper adapters (~43 adapters)
│       ├── base.py                # Abstract base: fetch → parse → normalize → validate pipeline
│       ├── civicplus.py           # Config-driven CivicPlus staff directory scraper (14 jurisdictions)
│       ├── revize.py              # Marker-based parser for Revize CMS freeform pages (3 jurisdictions)
│       ├── generic_mailto.py      # Extends RevizeAdapter for any mailto-heavy page (6 jurisdictions)
│       ├── table_adapter.py       # Auto-detects table columns by header text (4 jurisdictions)
│       ├── drupal_views.py        # Shared adapter for Drupal Views module sites (3 jurisdictions)
│       ├── greenville_county.py   # Custom two-page scraper with JS email deobfuscation
│       ├── greenville_city.py     # CivicPlus headless CMS JSON API with JWT auth
│       └── [30+ site-specific]    # One-off adapters for unique site structures
│
├── data/
│   └── sc/                        # South Carolina (only state so far)
│       ├── state.json             # State legislators (senate + house), keyed by district
│       ├── local/                 # Per-jurisdiction council member JSON (96 files)
│       │   ├── county-*.json      # County councils (46 counties)
│       │   └── place-*.json       # City/town councils (50 municipalities)
│       └── boundaries/            # Simplified GeoJSON district boundaries
│           ├── sldu.json          # State Senate districts (TIGER/Line)
│           ├── sldl.json          # State House districts (TIGER/Line)
│           ├── county-*.json      # County council districts (46 counties)
│           └── place-*.json       # City council districts (2 cities)
│
├── .github/workflows/
│   ├── scrape.yml                 # Weekly/monthly scraper run → data-update/* PR
│   ├── validate.yml               # PR check on data/** changes + auto-merge for data-update/* PRs
│   └── publish.yml                # Weekly npm publish (both packages) if data changed since last tag
│
└── docs/                          # Documentation and audits
```

## Key Relationships

- `scrapers/__main__.py` reads `registry.json` to discover states, jurisdictions, and adapter configs
- `registry.json` jurisdiction entries map `"adapter"` field → adapter class in `__main__.py` ADAPTERS dict
- Adapter hierarchy: `BaseAdapter` → `RevizeAdapter` → `GenericMailtoAdapter` (marker-based parsing chain)
- `DrupalViewsAdapter` handles two Drupal patterns: `views-row` divs and `person-item` articles
- `TableAdapter` auto-detects column roles from header text (name, title, email, phone, district, department)
- `scrape.yml` runs scrapers, then `validate.py`, then opens PR to `data-update/*` branch
- `validate.yml` auto-merges `data-update/*` PRs after validation passes
- `publish.yml` publishes both npm packages from the same repo using `package.json` and `boundaries-package.json`
- `state.py` uses `state_email_rules.py` to fill missing emails from name-based conventions
- `boundaries.py` reads boundary source configs from `registry.json` (both `stateBoundaries` and per-jurisdiction `boundary` blocks)
- `base.py` provides `deobfuscate_cf_email()` and `normalize_phone()` utilities used across adapters
- Coverage: 64/96 SC jurisdictions automated (67%), 13 inaccessible (403/blocked), 19 remaining manual
