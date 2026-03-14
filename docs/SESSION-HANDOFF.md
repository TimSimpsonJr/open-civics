# Session Handoff — call-your-rep

## What Was Done

Extracted scraper infrastructure and SC legislator data from `deflocksc-website` into this standalone repo. Everything is committed and pushed to GitHub (https://github.com/TimSimpsonJr/call-your-rep).

### Repo Contents
- Python scrapers with adapter pattern (CivicPlus, Greenville County, Greenville City)
- SC state legislators (46 senators, 124 house reps) with email backfill
- 96 per-jurisdiction local council files
- 50 boundary GeoJSON files
- GitHub Actions: weekly/monthly scraping, PR validation with auto-merge, weekly npm publish
- Two npm packages: `call-your-rep` (rep data) and `call-your-rep-boundaries` (district GeoJSON)

### Key Fixes Applied (from code review)
- Charleston bad data cleared (admin staff, not council members) — adapter set to `manual`
- Email backfill wired into `state.py` from `state_email_rules.py`
- Publish workflow version sync between both package.json files
- Weekly vs monthly scope differentiation via `github.event.schedule`
- SC-specific phone backfill guard

## What's Next

### Immediate (this repo)
1. **Local adapter audit** — plan at `docs/local-adapter-audit.md`. Audit all CivicPlus-scraped jurisdictions for data quality.
2. **Minor code review items** (not yet filed as issues):
   - Pin versions in `requirements.txt`
   - Normalize phone formats in `state.py` (strip parens, dashes → consistent format)
   - Add title-based data quality validation (detect admin staff vs elected officials)

### Separate Session (deflocksc-website)
3. **Phase 4: Consume npm packages** — Update deflocksc-website to install `call-your-rep` and `call-your-rep-boundaries`, update imports in `ActionModal.astro` and `district-matcher.ts`, remove extracted files, add build-time boundary copy script.

### Manual Steps (user)
4. **NPM account** — Create npmjs.org account, add `NPM_TOKEN` secret to this repo's GitHub settings for the publish workflow.
5. **Submit sitemap** — After deflocksc-website merge + deploy, submit `/sitemap-index.xml` in Google Search Console.

## Reference Docs
- `docs/2026-03-13-shared-repo-design.md` — Architecture decisions and rationale
- `docs/2026-03-13-shared-repo-implementation.md` — Full implementation plan (15 tasks)
- `docs/local-adapter-audit.md` — Next planned work
