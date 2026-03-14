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
│   ├── state.py                   # OpenStates CSV download + phone backfill + executive scraping
│   ├── boundaries.py              # Census TIGER/Line + ArcGIS boundary downloader/simplifier
│   ├── state_email_rules.py       # Per-state email format conventions for backfill
│   └── adapters/                  # Per-site scraper adapters (~68 files)
│       ├── base.py                # Abstract base: fetch → parse → normalize → validate + get_contact()
│       ├── civicplus.py           # Config-driven CivicPlus staff directory scraper (14 jurisdictions)
│       ├── revize.py              # Marker-based parser for Revize CMS freeform pages (3 jurisdictions)
│       ├── generic_mailto.py      # Extends RevizeAdapter for any mailto-heavy page (6 jurisdictions)
│       ├── table_adapter.py       # Auto-detects table columns by header text (4 jurisdictions)
│       ├── drupal_views.py        # Shared adapter for Drupal Views module sites (3 jurisdictions)
│       ├── rock_hill.py            # CivicPlus profile-page scraper with urllib (WAF bypass)
│       ├── aiken_city.py          # Divi theme member cards with tel: links
│       ├── kershaw_county.py      # Staff directory table with Name/Title/Phone/Email columns
│       ├── masc.py                # Municipal Association of SC directory fallback (3 cities)
│       ├── scac.py                # SC Association of Counties directory fallback (2 counties)
│       ├── greenville_county.py   # Custom two-page scraper with JS email deobfuscation
│       ├── greenville_city.py     # CivicPlus headless CMS JSON API with JWT auth
│       ├── bamberg_city.py        # CivicLive/ConnectSuite JSON API directory widget
│       └── [50+ site-specific]    # One-off adapters for unique site structures
│
├── data/
│   └── sc/                        # South Carolina (only state so far)
│       ├── state.json             # State legislators (senate + house + executive), keyed by district
│       ├── local/                 # Per-jurisdiction council member JSON (96 files)
│       │   ├── county-*.json      # County councils (46 counties)
│       │   └── place-*.json       # City/town councils (50 municipalities)
│       └── boundaries/            # Simplified GeoJSON district boundaries
│           ├── sldu.json          # State Senate districts (TIGER/Line)
│           ├── sldl.json          # State House districts (TIGER/Line)
│           ├── county-*.json      # County council districts (46 counties)
│           └── place-*.json       # City council districts (2 cities)
│
├── scripts/                       # CI/CD helper scripts
│   ├── diff_summary.py            # Git diff → human-readable PR body summary
│   ├── stale_check.py             # Detect jurisdictions with unchanged data >90 days
│   ├── quality_report.py          # Data coverage dashboard: email/phone/executive/contact per jurisdiction
│   └── refresh_snapshots.py       # Re-download real site HTML for integration test snapshots
│
├── tests/                         # Test suite (pytest)
│   ├── conftest.py                # Shared helpers: load_fixture, make_adapter
│   ├── unit/                      # Unit tests for utilities, adapters, scripts, validation
│   ├── integration/               # Integration smoke tests with real HTML snapshots
│   └── fixtures/
│       ├── html/                  # Hand-crafted HTML test fixtures
│       └── snapshots/             # Saved real site HTML for integration tests
│
├── requirements-dev.txt           # Dev/test dependencies (pytest, responses, etc.)
├── pytest.ini                     # Pytest configuration
│
├── .github/workflows/
│   ├── scrape.yml                 # Weekly/monthly scraper run → data-update/* PR + reporting
│   ├── validate.yml               # PR check on data/** changes + auto-merge for data-update/* PRs
│   └── publish.yml                # Weekly npm publish (both packages) if data changed since last tag
│
└── docs/                          # Documentation, audits, and plans
```

## Key Relationships

- `scrapers/__main__.py` reads `registry.json` to discover states, jurisdictions, and adapter configs
- `registry.json` jurisdiction entries map `"adapter"` field → adapter class in `__main__.py` ADAPTERS dict
- Adapter hierarchy: `BaseAdapter` → `RevizeAdapter` → `GenericMailtoAdapter` (marker-based parsing chain)
- `DrupalViewsAdapter` handles two Drupal patterns: `views-row` divs and `person-item` articles
- `TableAdapter` auto-detects column roles from header text (name, title, email, phone, district, department)
- `scrape.yml` runs scrapers with `--report`, then `diff_summary.py`, `stale_check.py`, and `quality_report.py` enrich the PR body
- `validate.yml` auto-merges `data-update/*` PRs after validation passes
- `publish.yml` publishes both npm packages from the same repo using `package.json` and `boundaries-package.json`
- `dataHash` and `dataLastChanged` in local JSON meta blocks track actual data changes vs re-scrapes
- All three workflows create GitHub Issues on failure (label: `ci-failure`)
- `tests/unit/` tests mirror `scrapers/adapters/` structure (e.g., `test_revize_parse.py` tests `revize.py`)
- `tests/integration/` uses snapshots from `scripts/refresh_snapshots.py` to smoke-test adapters against real HTML
- `state.py` uses `state_email_rules.py` to fill missing emails from name-based conventions
- `boundaries.py` reads boundary source configs from `registry.json` (both `stateBoundaries` and per-jurisdiction `boundary` blocks)
- `base.py` provides `deobfuscate_cf_email()` and `normalize_phone()` utilities used across adapters
- `MascAdapter` and `ScacAdapter` provide fallback data for WAF-blocked municipal/county sites
- Dead-end adapters override `get_contact()` to provide city hall phone as `meta.contact` fallback
- `state.py` `scrape_executive()` adds Governor + Lt. Gov to `state.json` after legislature scrape
- Coverage: 96/96 SC jurisdictions automated (100%), 88/96 with executive (91%), 70 email / 71 phone
