# Test Suite Design

**Goal:** Add unit and integration tests covering utility functions, shared adapter parsing, CI scripts, and data validation.

**Approach:** Grouped by layer — `tests/unit/` for fast pure-function and minimal-HTML tests, `tests/integration/` for real-snapshot smoke tests, `tests/fixtures/` for HTML files.

## Structure

```
tests/
├── conftest.py                    # Shared fixtures (adapter factory, tmp data dirs)
├── unit/
│   ├── test_normalize_phone.py    # normalize_phone() parametrized table
│   ├── test_deobfuscate_email.py  # deobfuscate_cf_email() parametrized table
│   ├── test_state_helpers.py      # _abbreviate_party(), _first_link()
│   ├── test_base_adapter.py       # normalize(), validate(), get_contact() contract
│   ├── test_revize_parse.py       # RevizeAdapter.parse() with minimal HTML
│   ├── test_civicplus_parse.py    # CivicPlusAdapter.parse() with minimal HTML
│   ├── test_table_adapter.py      # TableAdapter.parse() with minimal HTML
│   ├── test_drupal_views.py       # DrupalViewsAdapter.parse() (both patterns)
│   ├── test_generic_mailto.py     # GenericMailtoAdapter.parse() with minimal HTML
│   ├── test_quality_report.py     # check_executive(), check_contact(), format_summary()
│   ├── test_stale_check.py        # Stale detection logic against temp data files
│   └── test_validate.py           # validate_local_file(), validate_state_json()
├── integration/
│   └── test_real_snapshots.py     # Real HTML snapshots → parse() smoke tests
└── fixtures/
    ├── html/                      # Hand-crafted minimal HTML for unit tests
    │   ├── revize_basic.html
    │   ├── civicplus_directory.html
    │   ├── table_basic.html
    │   ├── drupal_views_row.html
    │   ├── drupal_person_item.html
    │   └── generic_mailto.html
    └── snapshots/                 # Real site HTML for integration tests
        ├── README.md              # How to refresh snapshots
        └── snapshots.json         # Manifest: file → adapter, config, min members
```

## Test Runner

- `pytest>=8.0,<9` in `requirements-dev.txt`
- `pytest tests/unit/ -v` for fast feedback (sub-second)
- `pytest` for everything including integration
- Integration tests marked with `@pytest.mark.integration`

## Unit Tests: Utility Functions

### test_normalize_phone.py (~15 cases)

Parametrized table covering:
- Standard formats: `803-212-6016`, `803.212.6016`, `(803) 212-6016`, `8032126016` → all normalize to `(803) 212-6016`
- Already normalized → unchanged
- Empty/whitespace → `""`
- Partial (7 digits like `378-0488`) → passthrough as-is
- Leading/trailing whitespace → trimmed

### test_deobfuscate_email.py (~6 cases)

- Known encoded/decoded pair from XOR algorithm
- Empty string → `""`
- Invalid hex → `""`
- Odd-length string → `""`

### test_state_helpers.py (~10 cases)

- `_abbreviate_party()`: "Democratic" → "D", "Republican" → "R", "Independent" → "I", "" → "", "Libertarian" → "L"
- `_first_link()`: semicolon-separated → first URL, empty → `""`, single URL → that URL

### test_base_adapter.py

Concrete subclass stub for testing the abstract base:
- `validate()` raises `ValueError` on empty list
- `validate()` adds warnings for missing name/title/email+phone
- `normalize()` calls `normalize_phone()` on phone fields, sets `source`/`lastUpdated`
- `get_contact()` returns `None` by default
- `_html` initialized to `None`, set after `scrape()`

## Unit Tests: Shared Adapter Parsing

Each adapter gets a test file with hand-crafted minimal HTML fixtures. Tests call `parse()` directly — no HTTP, no `fetch()`.

### test_revize_parse.py

- Basic: 3 members with bold name → mailto → phone. Assert names, emails, phones.
- Mayor detection: `<strong>Mayor John Smith</strong>` + mailto → title "Mayor"
- Mayor Pro Tem suffix: `"Jane Doe, Mayor Pro Tem"` → name stripped, title set
- Cloudflare obfuscation: `data-cfemail` → email decoded
- Separator: `<hr>` prevents cross-pairing
- Generic email filtering: `info@city.gov` skipped
- Member exclusion: "Clerk" title filtered

### test_civicplus_parse.py

- JS-obfuscated email: `var w = "john"; var x = "city.gov"` → `john@city.gov`
- `_flip_name()`: "Smith, John" → "John Smith", passthrough without comma
- `_normalize_title()`: "District 3 Representative" → "Council Member, District 3", "County Council Chairman" → "Chairman"
- `_should_exclude()`: "Clerk to Council" excluded
- `_discover_directory_id()`: finds `did=42` from link

### test_table_adapter.py

- Column auto-detection from `<th>` text
- Mailto in name cell → email extracted, name cleaned
- "Last, First" reversal
- Department filtering
- District column → "Council Member, District 5"

### test_drupal_views.py

- `views-row` pattern: field extraction from CSS classes
- `person-item` pattern: article-based extraction
- `_normalize_title()`: "Chairman" + district "3" → "Chairman, District 3", "Seat #4" → "Council Member, Seat 4"

### test_generic_mailto.py

- Wider content area detection: various CMS container classes
- Custom `contentSelector` respected
- Falls through to `<body>` as last resort

## Unit Tests: Scripts & Validation

### test_quality_report.py

Tests pure functions with synthetic data:
- `check_executive()`: "Mayor" found, "Vice Chairman" skipped, "Chairman" for county, empty list → `None`
- `check_contact()`: valid contact → string, empty → `None`, missing key → `None`
- `_has_title_match()`: vice prefix filtering
- `format_summary()`: known inputs → correct counts/percentages
- `analyze_local_file()`: temp JSON → correct result dict

### test_stale_check.py

Uses `tmp_path`:
- 3 temp files: 100 days old, 50 days old, today → only 100-day flagged at threshold=90
- `dataLastChanged` missing → falls back to `lastUpdated`
- Invalid date → skipped silently

### test_validate.py

Tests validator functions directly (clear module-level `errors`/`warnings` between tests):
- `validate_local_file()`: valid → no errors, missing meta → error, missing members → error, admin title → warning
- `validate_state_json()`: valid → no errors, >50% drop → error, bad email → warning, valid executive → no errors
- `meta.contact` validation: valid → no errors, bad phone → warning

### diff_summary.py — Not tested

Shells out to `git diff` — testing would require mocking subprocess for minimal value. Real validation happens in CI.

## Integration Tests: Real Snapshots

### test_real_snapshots.py

- Loads saved HTML from `tests/fixtures/snapshots/`
- `snapshots.json` manifest maps file → adapter class, config, minimum member count
- Assertions: non-empty members, every member has a name, count ≥ floor
- Marked `@pytest.mark.integration`

### Initial snapshots (one per shared adapter):

- `revize_walterboro.html` — Revize pattern
- `civicplus_spartanburg.html` — CivicPlus directory table
- `table_florence_county.html` — HTML table
- `drupal_newberry.html` — views-row pattern
- `drupal_orangeburg.html` — person-item pattern
- `generic_mailto_camden.html` — GenericMailto

### Snapshot refresh

`scripts/refresh_snapshots.py` fetches each URL from the manifest, saves HTML. Run manually when adapters change.
