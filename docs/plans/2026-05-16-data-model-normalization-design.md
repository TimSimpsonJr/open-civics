---
codex_thread_id: 019e311a-c877-7453-9cd1-f72a038f3c99
---

# Data Model Normalization Design

## Goal

Unify the data model across state legislators, executive officials, and local councils so that consumers can read structured seat information without parsing free-text titles. Coordinated rollout with the only current consumer (`deflocksc-website`).

## Background

An audit of the open-civics repo found three different record shapes for what is fundamentally the same kind of entity (an elected official with contact info):

| | State senate/house | State executive | Local councils |
|---|---|---|---|
| Container | `{senate: {"25": {...}}}` (district-keyed dict) | array under `executive` | `{members: [...]}` (array) |
| Identity | `district` (field) | `title` (free text) | `title` (free text) |
| Party | `party` | — | — |
| Photo | `photoUrl` | — | — |
| Website | `website` | `website` | — |

The consumer site (`deflocksc-website`) compensates with runtime regex parsing of `title` to extract district numbers ([results-renderer.ts:381](../../../../deflocksc-website/src/scripts/action-modal/results-renderer.ts)) and brittle exact-string `"Vacant"` filtering ([group-builder.ts:91](../../../../deflocksc-website/src/scripts/action-modal/group-builder.ts)) that misses `"Vacant District 5"` in [place-lancaster.json](../../data/sc/local/place-lancaster.json).

Extraction analysis of the 676 local members:
- 64% have a clearly extractable numeric district
- 7% are mayors (categorically at-large)
- 2% are explicit "At-Large"
- 27% have no district info in source — split between genuinely all-at-large small towns and scraper inconsistencies where county chairman titles overwrite the district seat

## Non-goals

- **No container churn.** State stays dict-keyed by district. Local stays an array of members. Executive stays an array. Dict-by-district lookup is genuinely useful for the consumer; converting to arrays adds re-indexing work downstream with no offsetting benefit.
- **No removal of existing fields in this release.** Legacy `district` on state members and free-text `title` everywhere stay. They become documented sources for backward compatibility while new structured fields take over the read path.
- **No `role` enum collapsing office, seat, and leadership.** That ambiguity is the bug we're fixing, not a model to perpetuate.
- **No `term` field.** It would rot faster than almost anything else in the model without a maintained source of truth.

## Target schema (per-member)

Every member record in `state.json` (`senate`, `house`, `executive`) and every member in local council files conforms to the same shape:

```jsonc
{
  // identity + display
  "name": "Joey Russo",
  "title": "Council Member, District 17",   // required everywhere, display-only;
                                            // synthesized for state legislators
                                            // (e.g., "State Senator, District 25")

  // structural seat (NEW)
  "office": "council-member",               // enum, required
  "leadership": null,                       // enum or null, required
  "seatClass": "numbered",                  // enum, required
  "seatLabel": "district",                  // enum or null, required
  "seatId": "17",                           // string or null, required
  "vacant": false,                          // boolean, required (NEW)
  "seatSource": "parsed-title",             // enum, required (NEW)

  // partisan info
  "partisan": false,                        // boolean or null, required (NEW)
  "party": null,                            // existing — kept for state members

  // contact (existing)
  "email": "JRusso@greenvillecounty.org",
  "phone": "(864) 483-0689",
  "emailVerified": true,                    // OPTIONAL — only on backfilled state emails today
  "photoUrl": "...",                        // OPTIONAL — currently state-only
  "website": "...",                         // OPTIONAL — state + executive today

  // provenance (existing)
  "source": "greenvillecounty",
  "lastUpdated": "2026-05-16"
}
```

**Enum style.** All multi-word enum values use `kebab-case` for JSON serialization (e.g., `state-senator`, `at-large`, `parsed-title`, `mayor-pro-tem`). Existing snake_case fields like `meta.adapter` are unaffected — kebab-case applies only to the new enum values introduced by this design.

**`title` for state legislators.** State senate/house records do not have `title` today. They get one synthesized during normalization: `"State Senator, District 25"` / `"State Representative, District 122"`. Same for executive: governor and lt-governor already have `title`. This makes `title` a required field across every record so consumers always have a display string, even though for state legislators it's derived rather than scraped.

### Enums

**`office`** — what office this person holds:
- `state-senator`
- `state-representative`
- `governor`
- `lt-governor`
- `mayor`
- `council-member`

Note: `chair`, `vice-chair`, and `mayor-pro-tem` are NOT offices. A "Chairman of County Council, District 8" is a `council-member` with a leadership overlay.

**`leadership`** — leadership role within the office's body, or null:
- `chair`
- `vice-chair`
- `mayor-pro-tem`
- `null`

**`seatClass`** — the structural class of seat:
- `numbered` — a specific identifiable seat (District 5, Ward 2, Seat 3, etc.)
- `at-large` — explicitly elected at-large, no geographic subdivision
- `unknown` — source data did not publish enough to distinguish (rare; see Aiken council)

**`seatLabel`** — the literal label the jurisdiction uses for the seat, or null:
- `district` — most counties and cities
- `ward` — Camden, Darlington, Lancaster, Newberry (a handful)
- `seat` — Colleton County
- `null` — for `at-large` and `unknown` seats

`seatLabel` is preserved separately from `seatClass` because the UI cares about the literal phrasing ("Ward 3" vs "District 3") even though the matcher only cares that it's numbered.

**`seatSource`** — provenance of the structured seat data, used to indicate evidence strength:
- `source` — the source site published a structured district field directly (e.g., OpenStates CSV column)
- `parsed-title` — extracted from the free-text title via the central normalizer
- `inferred-registry` — derived from registry knowledge (e.g., the registry knows Aiken council is at-large)
- `manual` — overridden by hand in a per-jurisdiction patch table

**`partisan`** — whether the office is a partisan election:
- `true` — partisan office; `party` will be populated when known. Applies to state senators, state representatives, governor, lt-governor, and any local office where partisan affiliation is on the ballot.
- `false` — nonpartisan office (most local SC offices: city council, town council, mayor in nonpartisan jurisdictions).
- `null` — unknown.

This distinguishes "we don't know their party" (`partisan: true, party: null`) from "this office doesn't have parties" (`partisan: false, party: null`). The current consumer rendering branches on `rep.party`; this gives it the right signal for nonpartisan races.

### Legacy fields

- **`district`** on state senate/house members is RETAINED as a documented legacy alias of `seatId`. Not deprecated. Removed only if a future maintenance cycle has a reason (second consumer, real friction). NOT mirrored onto local members — that would recreate the old ambiguity under a new name.
- **`title`** stays everywhere as the display string. Consumers should prefer structured fields for logic and use `title` only for display.

## Normalization module

A new module `scrapers/normalize.py` exposes a single function used by every code path that produces member records:

```python
def normalize_member(record: dict, context: NormalizationContext) -> dict:
    """
    Fill missing structured fields on a member record by parsing its title
    and consulting registry-level knowledge. Idempotent: if structured
    fields are already set, they win.
    """
```

`context` carries:
- `level`: `state` | `local`
- `chamber`: `senate` | `house` | `executive` (for `level: state`; None for local)
- `jurisdiction_type`: `county` | `place` (for `level: local`; None for state)
- `jurisdiction_id`: e.g., `place:aiken` (for local)
- Optional `registry_hints`: e.g., `seatClass: at-large` if the registry pre-declares the council is at-large

### Call sites

The normalizer is called from two places (not just `BaseAdapter.normalize()` — state legislators don't go through `BaseAdapter`):

1. **`BaseAdapter.normalize()`** in [scrapers/adapters/base.py:60](../../scrapers/adapters/base.py) — for every local member produced by an adapter.
2. **`scrapers/state.py`** `normalize_row()` and `scrape_executive()` paths — for every state legislator and executive official.

This shared placement is important. The previous audit found state and local diverged precisely because there was no shared normalization path.

### Layered precedence

The normalizer applies four stages in strict order. Three are gap-fillers; the fourth (manual) is an audited escape hatch that may overwrite earlier structured values:

1. **Explicit source fields (gap-fill).** If the adapter set `seatClass`/`seatId`/`leadership` explicitly — for example, from a structured column in the OpenStates CSV — keep those and set `seatSource: source`. These are the highest-confidence structured signals.
2. **Title parsing (gap-fill).** Parse the free-text title. If a confident match yields structured fields not already set by stage 1, fill them and set `seatSource: parsed-title`. Title parsing never overrides fields already set in stage 1.
3. **Registry defaults (gap-fill).** If the jurisdiction's registry entry has a `councilDefaults` block (e.g., "Aiken council is at-large"), apply it to any field still unset after stages 1–2 and set `seatSource: inferred-registry`. Registry defaults never overwrite a `seatClass: numbered` produced by title parsing — they only fill `unknown`.
4. **Manual overrides (override).** Per-record entries in `scrapers/seat_overrides.py`, keyed by `(jurisdiction_id, member_name)`, are applied last and **may overwrite any earlier structured value** (including stage-1 source fields). Manual overrides exist precisely for cases where the source is known to be wrong — for example, county chairman records where the title overwrites the district seat. Each manual override records `seatSource: manual` on the affected record.

The contradiction between "fill gaps only" and "manual is last": stages 1–3 are pure gap-fill; stage 4 is the explicit, audited override path. The override budget lives in `seat_overrides.py` so that every exception is reviewable in one file.

### Title parsing rules

The base title parser handles:

- `"District N"` / `"Ward N"` / `"Seat N"` / `"Township N"` — `seatClass: numbered`, `seatLabel` set, `seatId: "N"`
  - `township` was added in [`2026-05-16-followup-districted-scraper-bugs-plan.md`](2026-05-16-followup-districted-scraper-bugs-plan.md) Task 7 for SC counties (e.g., Jasper) that subdivide by named townships rather than numbered districts. `seatId` carries the township name (`"Hardeeville"`, `"Pocotaligo"`) when the source uses names.
- `"District One"` etc. (word-form numbers, one through twenty) — same as above
- `"District Number N - X"` (Berkeley-style prefix) — same as above
- `"At Large"` / `"At-Large"` — `seatClass: at-large`, `seatLabel: null`, `seatId: null`
- Title starts with `"Mayor"` (and not `"Mayor Pro Tem"`) — `office: mayor`, `seatClass: at-large`, `leadership: null`
- Title starts with `"Mayor Pro Tem"` / `"Mayor Pro-Tem"` — `office: council-member`, `leadership: mayor-pro-tem`, plus any embedded seat
- Title contains `"Chairman"` / `"Chair"` — `leadership: chair`
- Title contains `"Vice Chair"` / `"Vice Chairman"` — `leadership: vice-chair`
- Title is plain `"Council Member"` / `"Councilman"` / `"Town Council Member"` with no seat info — `office: council-member`, `seatClass: unknown` (overridable to `at-large` via registry hint)

### Vacancy detection

The normalizer also detects vacant seats. If `name` starts with `"Vacant"` (case-insensitive), set `vacant: true`. The remainder of the name (e.g., `"District 5"` in `"Vacant District 5"`) is parsed as if it were the title to extract `seatId` and `seatLabel`. The actual `name` field is preserved as-is for display ("Vacant District 5" reads better than "Vacant").

## Registry changes

Add an optional `councilDefaults` block per jurisdiction entry in `registry.json`:

```json
{
  "id": "place:aiken",
  "name": "Aiken",
  "type": "place",
  "councilDefaults": {
    "seatClass": "at-large",
    "partisan": false
  }
}
```

When the normalizer encounters a member with `seatClass: unknown` after title parsing, the registry hint promotes it to `at-large`. For the 28 small-town councils that publish no district info, a single registry entry resolves all members.

`councilDefaults` is intentionally narrow: it carries only **jurisdiction-wide** defaults like the council being all-at-large or all-nonpartisan. Per-member exceptions belong in `seat_overrides.py`, not here. This keeps the registry from becoming a dumping ground for record-specific patches.

`partisan` defaults: `true` for state senate/house and for governor/lt-governor (all SC state offices are partisan); `false` for `level: local` unless the local jurisdiction's `councilDefaults.partisan` says otherwise.

## Validator updates

`validate.py` extensions:

1. Require new fields on every member: `office`, `leadership`, `seatClass`, `seatLabel`, `seatId`, `vacant`, `seatSource`, `partisan`.
2. Validate enums for `office`, `leadership`, `seatClass`, `seatLabel`, `seatSource`.
3. Cross-field invariants:
   - `seatClass: at-large` ⇒ `seatLabel === null && seatId === null`
   - `seatClass: numbered` ⇒ `seatLabel !== null && seatId !== null`
   - `seatClass: unknown` ⇒ `seatId === null` (label may be null too)
   - `leadership: mayor-pro-tem` ⇒ `office === council-member`
   - `office: mayor` ⇒ `seatClass: at-large`
4. Per-member `source` and `lastUpdated` already exist; no change.
5. Adapter-mismatch warning: if `meta.adapter` doesn't match `registry.json` for the jurisdiction, warn. (Catches the `place:aiken`/`county:kershaw` drift.)

The validator's `partisan === false` records don't require `party`.

## Migration strategy

### open-civics PR (one PR)

**Commits (in order, in the same PR):**

1. **`feat: add seat normalization module`** — new `scrapers/normalize.py` + `scrapers/seat_overrides.py`, unit tests covering every title pattern in the audit, no data changes yet.
2. **`feat: wire normalizer into adapters and state scraper`** — call site changes in `BaseAdapter.normalize()` and `state.py`. Includes a one-off `scripts/backfill_normalized_fields.py` so the regenerated JSON is mechanical, not requiring a full re-scrape.
3. **`chore: regenerate all data files with normalized fields`** — runs the backfill script; the diff is data-only.
4. **`feat: update validator for normalized schema`** — schema invariants enforced; CI now fails if a future scrape produces malformed records.
5. **`chore: remove backfill script and bump to 0.2.0`** — `scripts/backfill_normalized_fields.py` is one-shot and deleted before merge (the wired-in normalizer makes it obsolete from this PR onward). npm minor bump (additive change, no removals). MANIFEST.md regenerated. CLAUDE.md updated with the new schema convention.

Splitting code/tests first, data second keeps the PR reviewable: reviewers can read the logic without scrolling past 96 regenerated JSON files. Five commits, not six — docs and version bump fold into the final commit since they're trivial.

### deflocksc-website PR (one PR, lands same day)

**Commits:**

1. **`chore: bump open-civics to 0.2.0`** — package.json + lockfile.
2. **`refactor: read structured seat fields in results-renderer`** — removes the `title.match(/(?:District|Seat) (\d+)/)` regex at [results-renderer.ts:381](../../../../deflocksc-website/src/scripts/action-modal/results-renderer.ts) and [results-renderer.ts:399](../../../../deflocksc-website/src/scripts/action-modal/results-renderer.ts), replaces with reads from `member.seatClass`, `member.seatId`, `member.seatLabel`.
3. **`refactor: read structured seat fields in group-builder`** — removes the matched-rep title parsing in [group-builder.ts:21](../../../../deflocksc-website/src/scripts/action-modal/group-builder.ts), replaces with `seatClass === "numbered" && seatId === <matched>`.
4. **`refactor: use vacant field for filtering`** — replaces the exact-string `"Vacant"` check in [group-builder.ts:91](../../../../deflocksc-website/src/scripts/action-modal/group-builder.ts) with `member.vacant === true`. This correctly handles `"Vacant District 5"` in Lancaster.
5. **`refactor: render seatLabel for display`** — UI shows "Ward 3" or "Seat 5" using the literal label instead of hardcoding "District".
6. **`chore: sync data and verify`** — runs prebuild sync, commits the regenerated `src/data/local-councils.json`.

**No compatibility shim.** The site builds via `npm install` so the resolved schema is deterministic once both repos are aligned. A scattered shim across two files would be more complexity than it saves; a single helper isn't worth the abstraction for a coordinated cutover. Clean break.

### Coordination

The site consumes raw JSON files from `node_modules/open-civics/data/...`, so site code referencing `member.seatClass` only works once `open-civics@0.2.0` is **published to npm**. The current [publish.yml](../../.github/workflows/publish.yml) runs on a weekly cron (Friday 6pm ET) OR `workflow_dispatch`. To avoid a multi-day window where the site PR can't be authored, the open-civics PR's merge MUST be followed by a manual publish trigger before the site PR can begin.

**Strict ordering:**

1. open-civics PR is reviewed and merged to master (with `package.json` bumped to `0.2.0` and all data regenerated)
2. Maintainer runs `gh workflow run publish.yml -R TimSimpsonJr/open-civics` to manually trigger the publish workflow. This is the explicit gate — without it, the next publish is up to a week away.
3. Workflow publishes `open-civics@0.2.0` to npm and tags `v0.2.0`
4. Site PR is opened with `package.json` referencing `^0.2.0`; `npm install` resolves to the just-published version
5. Site PR is reviewed and merged

This sequence holds for both production and dev. A developer pulling site main between steps 1 and 4 would have a broken `npm install` (no 0.2.0 available yet) — but the site PR itself can't be opened against an unpublished version, so the site PR's existence implies step 3 has completed.

The open-civics PR description must include the manual trigger as an explicit post-merge step, not buried in the implementation plan. Same with the site PR: it should reference the open-civics version it depends on so reviewers can verify the publish has happened.

### Open-civics PR post-merge step (explicit)

After the open-civics PR merges, the maintainer runs:

```sh
gh workflow run publish.yml -R TimSimpsonJr/open-civics
```

Then waits for the workflow to complete (publishes both packages, tags v0.2.0, pushes the bump commit). Only then is the site PR cleared to open.

## Out of scope (for this design)

- The handful of county chairman records where the title overwrites the district seat. These get a `seat_overrides.py` entry case-by-case; the design above accommodates them but doesn't enumerate them. Adapter fixes are tracked separately.
- The `place:aiken`/`county:kershaw` adapter-mismatch issue from the audit. Resolves naturally when the regen runs the primary adapters.
- State `dataHash`/`dataLastChanged` parity with local files. Worth doing but unrelated to schema unification.
- Multi-state expansion. The model is state-agnostic; nothing here is SC-specific other than the data being scraped today.

## Success criteria

1. Every member record across `state.json` and `local/*.json` validates against the new schema; `python validate.py` exits 0.
2. `pytest` passes in `open-civics`, including new unit tests for `scrapers/normalize.py` covering every title pattern in the audit.
3. `deflocksc-website` builds successfully against `open-civics@0.2.0` with no runtime title parsing anywhere in `src/scripts/action-modal/`. Verified two ways: (a) `grep -rE "title\.(match|indexOf|includes|search)" src/scripts/action-modal/` returns no hits for seat extraction; (b) no member's `title` field is read as input to seat-selection logic in either `results-renderer.ts` or `group-builder.ts` (title may still be read for display).
4. `npm run test` in `deflocksc-website` passes.
5. The "wrong district" dropdown in the site action modal includes Ward-based seats (currently broken for Camden / Darlington / Lancaster / Newberry).
6. `"Vacant District 5"` in Lancaster surfaces as `vacant: true` in data and is filtered correctly by the site.
