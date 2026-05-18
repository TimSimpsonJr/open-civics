# Migrating to open-civics

Instructions for replacing existing scraper infrastructure in DeflockSC and Call Y'all with the `open-civics` npm packages.

## What open-civics provides

Two npm packages, updated weekly via automated scrapers:

- **`open-civics`** — contact data for SC state legislators (senate + house + governor + lt-governor), 96 local jurisdictions (county and city councils), and federal representatives (US senators + US house members for SC)
- **`open-civics-boundaries`** — GeoJSON district boundaries for client-side point-in-polygon matching (state legislative + county council + congressional + state outline)

Starting in v0.2, every state-level and local-level member record carries structured seat fields (`office`, `seatClass`, `seatLabel`, `seatId`, `vacant`, etc.) so consumers don't need to parse free-text titles to find a constituent's representative. Federal records use a different shape (see below).

## Install

```bash
npm install open-civics open-civics-boundaries
```

## Data shapes

### State legislators (`open-civics/sc/state.json`)

```ts
{
  meta: { state: "SC", level: "state", lastUpdated: "2026-03-14", source: "openstates" },
  senate: {
    [districtNumber: string]: StateMember
  },
  house: {
    [districtNumber: string]: StateMember
  },
  executive: ExecutiveMember[]   // governor, lt-governor
}

interface StateMember {
  // identity + display
  name: string;
  title: string;                 // synthesized — e.g. "State Senator, District 25"
  district: string;              // legacy alias of seatId, kept for v0.1 consumers

  // structured seat (v0.2+)
  office: "state-senator" | "state-representative";
  leadership: null;              // state legislators don't carry leadership overlays in this dataset
  seatClass: "numbered";
  seatLabel: "district";
  seatId: string;                // matches the dict key

  // state
  vacant: boolean;               // always false for legislators (vacancies don't get scraped into here)
  seatSource: "source";          // structured from OpenStates CSV
  partisan: true;
  party: "R" | "D" | "I";

  // contact
  email: string;
  emailVerified?: boolean;       // false when backfilled from name-based convention
  phone: string;
  photoUrl?: string;
  website?: string;

  // provenance
  source: "openstates";
  lastUpdated: string;
}

interface ExecutiveMember {
  name: string;
  title: string;                 // e.g. "Governor", "Lieutenant Governor"
  office: "governor" | "lt-governor";
  leadership: null;
  seatClass: "at-large";
  seatLabel: null;
  seatId: null;
  vacant: boolean;
  seatSource: "source";
  partisan: true;
  email?: string;
  phone?: string;
  website?: string;
  source: string;
  lastUpdated: string;
}
```

### Local councils (`open-civics/sc/local/county-greenville.json`)

```ts
{
  meta: {
    state: "SC",
    level: "local",
    jurisdiction: "county:greenville",  // or "place:greenville"
    label: "Greenville County Council",
    lastUpdated: "2026-03-14",
    adapter: "greenville_county",
    dataHash: "...",
    dataLastChanged: "...",
    contact?: {                  // optional — when the council publishes no per-member contact
      phone?: string,
      email?: string,
      note?: string
    }
  },
  members: LocalMember[]
}

interface LocalMember {
  // identity + display
  name: string;
  title: string;                 // raw scraped string — e.g. "Council Member, District 17"

  // structured seat (v0.2+)
  office: "council-member" | "mayor";
  leadership: "chair" | "vice-chair" | "mayor-pro-tem" | null;
  seatClass: "numbered" | "at-large" | "unknown";
  seatLabel: "district" | "ward" | "seat" | null;
  seatId: string | null;

  // state
  vacant: boolean;
  seatSource: "source" | "parsed-title" | "inferred-registry" | "manual";
  partisan: boolean;             // false for most SC local offices

  // contact
  email?: string;
  phone?: string;

  // provenance
  source: string;
  lastUpdated: string;
}
```

Jurisdiction naming: `county-{slug}.json` for counties, `place-{slug}.json` for cities/towns.

### Federal legislators (`open-civics/sc/federal.json`)

Different shape from state/local — these come from the `unitedstates/congress-legislators` dataset rather than the normalized open-civics scrapers, so they do NOT carry the v0.2 structured seat fields:

```ts
{
  meta: { state: "SC", level: "federal", lastUpdated: "...", source: "unitedstates/congress-legislators" },
  senate: {
    [seatClass: "1" | "2" | "3"]: FederalSenator   // keyed by senate class (staggered terms)
  },
  house: {
    [districtNumber: string]: FederalRep
  }
}

interface FederalSenator {
  name: string;
  party: "R" | "D";
  phone: string;
  website: string;
  contactForm: string;
  office: string;                // physical office address — NOT the v0.2 office enum
  seatClass: "1" | "2" | "3";    // US Senate class (NOT the v0.2 seatClass enum)
  stateRank: "senior" | "junior";
  bioguideId: string;
  source: string;
  lastUpdated: string;
}

interface FederalRep {
  name: string;
  party: "R" | "D";
  phone: string;
  website: string;
  contactForm: string;
  office: string;                // physical office address
  district: string;
  bioguideId: string;
  source: string;
  lastUpdated: string;
}
```

⚠ **Name collision warning:** federal records use `office` for the physical office building string ("211 Russell Senate Office Building") and `seatClass` for the US Senate class number ("1" / "2" / "3"). These are NOT the same fields as the v0.2 normalized enums on state/local records. If your code reads federal data, treat it as its own schema — don't try to share validators or display logic between federal and state/local without disambiguation.

### Boundaries (`open-civics-boundaries/sc/boundaries/*.json`)

Standard GeoJSON FeatureCollections. Each feature has `properties.district` matching the district keys in contact data.

- `sldu.json` — state senate districts (46 features)
- `sldl.json` — state house districts (124 features)
- `cd.json` — US congressional districts (7 features, SC only)
- `state-outline.json` — SC state outline (1 feature, used for US senate matching)
- `county-{name}.json` — county council districts
- `place-{name}.json` — city council districts (where available)

## Structured seat fields (v0.2+)

The state/local member shape lifts seat semantics out of free-text `title` into typed fields. Consumers should prefer these for any logic that needs to find or filter by seat.

- **`office`** — what office this person holds. Enum: `state-senator | state-representative | governor | lt-governor | mayor | council-member`. Leadership overlays (chair, vice-chair, mayor pro tem) are NOT offices — they're captured separately.
- **`leadership`** — leadership role on top of the office, or `null`. Enum: `chair | vice-chair | mayor-pro-tem | null`. A "Chairman of County Council, District 8" is a `council-member` with `leadership: chair` and a seat at `seatId: "8"`.
- **`seatClass`** — structural class of the seat. `numbered` (specific identifiable seat — District 5, Ward 2, Seat 3), `at-large` (no geographic subdivision), or `unknown` (source didn't publish enough to distinguish).
- **`seatLabel`** — literal label the jurisdiction uses for numbered seats: `district`, `ward`, or `seat`. `null` for at-large and unknown. Use this for display when you want to render "Ward 3" vs "District 3" correctly.
- **`seatId`** — the seat's identifier as a string, or `null` for at-large and unknown. For state legislators this equals the dict key (`senate["25"].seatId === "25"`).
- **`vacant`** — boolean. `true` when the seat exists but is unfilled. Filter on this rather than `name === "Vacant"` — vacancies sometimes include the seat number in the name (e.g., `"Vacant District 5"`).
- **`seatSource`** — provenance of the structured seat data. `source` = structured upstream field; `parsed-title` = extracted from free-text title; `inferred-registry` = jurisdiction-wide hint applied; `manual` = hand-curated override. Useful for understanding data confidence.
- **`partisan`** — whether the office is partisan. `true` for state legislators, governor, lt-governor. `false` for most SC local offices (council seats are nonpartisan). `null` for unknown. Distinguishes "no party info" from "no parties at this level".

## Import examples

```js
// State legislators
import scState from 'open-civics/sc/state.json';
const senator = scState.senate["1"];
const rep = scState.house["42"];
const governor = scState.executive.find(m => m.office === "governor");

// All senators as array
const allSenators = Object.values(scState.senate);

// Local councils
import greenvilleCounty from 'open-civics/sc/local/county-greenville.json';
const members = greenvilleCounty.members;

// Find the member representing a specific district seat
const district17Member = members.find(
  m => m.seatClass === "numbered" && m.seatId === "17"
);

// Filter out vacancies before showing reps
const filledSeats = members.filter(m => !m.vacant);

// Federal
import scFederal from 'open-civics/sc/federal.json';
const seniorSenator = Object.values(scFederal.senate).find(s => s.stateRank === "senior");

// Boundaries for point-in-polygon lookup
import senateBoundaries from 'open-civics-boundaries/sc/boundaries/sldu.json';
import houseBoundaries from 'open-civics-boundaries/sc/boundaries/sldl.json';
import countyBoundaries from 'open-civics-boundaries/sc/boundaries/county-greenville.json';
```

## Dynamic loading (if you need all jurisdictions)

```js
// Load all local council files dynamically
const localFiles = [
  'county-greenville', 'county-spartanburg', 'place-greenville',
  // ... full list at: https://github.com/TimSimpsonJr/open-civics/tree/master/data/sc/local
];

const councils = await Promise.all(
  localFiles.map(f => import(`open-civics/sc/local/${f}.json`))
);
```

## Point-in-polygon lookup (finding a user's reps by address)

Use any geocoding service to get lat/lng from an address, then use Turf.js (or similar) to find which districts contain that point:

```js
import * as turf from '@turf/turf';
import senateBoundaries from 'open-civics-boundaries/sc/boundaries/sldu.json';
import scState from 'open-civics/sc/state.json';

function findSenator(lat, lng) {
  const point = turf.point([lng, lat]);
  const district = senateBoundaries.features.find(f =>
    turf.booleanPointInPolygon(point, f)
  );
  if (!district) return null;
  return scState.senate[district.properties.district];
}
```

To find the local council member for a county-council district:

```js
import countyBoundaries from 'open-civics-boundaries/sc/boundaries/county-greenville.json';
import greenvilleCounty from 'open-civics/sc/local/county-greenville.json';

function findCouncilMember(lat, lng) {
  const point = turf.point([lng, lat]);
  const districtFeature = countyBoundaries.features.find(f =>
    turf.booleanPointInPolygon(point, f)
  );
  if (!districtFeature) return null;
  const seatId = districtFeature.properties.district;
  return greenvilleCounty.members.find(
    m => m.seatClass === "numbered" && m.seatId === seatId && !m.vacant
  );
}
```

## Migration checklist

### 1. Remove existing scraper code
- Delete any scraper scripts, cron jobs, or serverless functions that fetch legislator data
- Delete any local JSON/DB storage of legislator contact info
- Delete any boundary/district data files you maintain

### 2. Replace data access
- Install packages: `npm install open-civics open-civics-boundaries`
- Replace all data reads with imports from the packages (see examples above)
- State legislators: `import scState from 'open-civics/sc/state.json'`
- Local councils: `import data from 'open-civics/sc/local/{jurisdiction}.json'`
- Federal: `import scFederal from 'open-civics/sc/federal.json'`
- Boundaries: `import geo from 'open-civics-boundaries/sc/boundaries/{file}.json'`

### 3. Adapt to the data shape
- State data is keyed by district number, not an array — use `Object.values()` if you need arrays
- Local members are in a `members` array
- Prefer `seatClass`/`seatId` over parsing `title` for seat lookup (`title` is human-readable but variable; the structured fields are normalized)
- Filter vacancies via `member.vacant === true`, NOT `name === "Vacant"` (vacancies sometimes carry the seat in the name)
- Render display labels with `seatLabel`: a Ward town like Camden should read "Ward 3" not "District 3"
- Federal records have their OWN `office` and `seatClass` fields with different semantics (office address; senate class number) — don't share types with state/local
- Party info is on state legislators, governor/lt-governor, and federal — local offices are nonpartisan (`partisan: false`) and won't carry `party`

### 4. Update any district lookup logic
- Replace any server-side geocoding/district lookup with client-side point-in-polygon using the boundary GeoJSON
- Or keep server-side if you prefer — just import the boundary files there instead
- Match members to boundary features via `member.seatId === feature.properties.district`

## Staying up to date

### Option A: Dependabot (recommended)

Add to `.github/dependabot.yml`:

```yaml
version: 2
updates:
  - package-ecosystem: "npm"
    directory: "/"
    schedule:
      interval: "weekly"
    allow:
      - dependency-name: "open-civics"
      - dependency-name: "open-civics-boundaries"
```

This opens a PR whenever new data is published (weekly). Merge it to get fresh data.

### Option B: Pin to latest in CI

In your deploy/build pipeline:

```bash
npm update open-civics open-civics-boundaries
```

This pulls the latest version on every deploy.

### Option C: Use `*` or `>=` version range

In `package.json`:

```json
{
  "dependencies": {
    "open-civics": "*",
    "open-civics-boundaries": "*"
  }
}
```

Every `npm install` gets the latest. Less reproducible but always fresh.

### Recommended approach

Use Dependabot (Option A). It gives you visibility into what changed, lets you review before merging, and keeps your lockfile deterministic.

## Update cadence

- **Contact data**: scraped and published weekly (Mondays). State legislators change rarely; local councils change when elections happen or members resign.
- **Boundary data**: rebuilt monthly (1st of month). Boundaries only change after redistricting (every 10 years for state, occasionally for local).
- **npm publish**: every Friday if data changed since last release.

## Available jurisdictions

96 local jurisdictions are covered — every SC county and incorporated municipality. Full list of files:

https://github.com/TimSimpsonJr/open-civics/tree/master/data/sc/local

## Questions?

Source repo: https://github.com/TimSimpsonJr/open-civics
