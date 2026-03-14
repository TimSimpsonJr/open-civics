# Local Adapter Audit Results

## Platform Breakdown (all 82 manual jurisdictions)

| Platform | Count | Existing adapter? | Effort |
|----------|------:|-------------------|--------|
| Revize | 14 | No | New adapter (config-driven, similar to CivicPlus) |
| CivicPlus | 6 | **Yes** | Config only |
| WordPress | 13 | No | New adapter (varied themes, moderate effort) |
| Drupal | 12 | No | New adapter (varied themes, moderate effort) |
| Granicus | 4 | No | New adapter |
| Govstack | 2 | No | New adapter |
| Wix | 3 | No | Difficult (JS-rendered, Thunderbolt framework) |
| Custom/Other | 10 | No | One-off adapters |
| Squarespace | 1 | No | Difficult (403 to automated fetches) |
| Joomla | 1 | No | New adapter (single site) |
| Munibit | 1 | No | API-based (`/api/public/mwjsPeople`) |
| Unknown/Down | 3 | No | Manual investigation needed |
| No URL (found) | 12 | No | URLs discovered, need platform audit |

## Detailed Audit by Jurisdiction

### Batch 1 (17 sites)

| ID | Platform | Emails? | Obfuscated? | HTML Structure | Notes |
|----|----------|---------|-------------|----------------|-------|
| place:spartanburg | CivicPlus | Yes (mailto) | No | Card divs | URL should be /316/City-Council |
| county:anderson | WordPress | Yes (plain) | No | Cards with modals | Smush lazy-load |
| place:anderson | WordPress | Unknown | Unknown | Unknown | SSL error, needs manual check |
| county:pickens | Revize | Yes (mailto) | No | Divs (strong+img+p) | cms5.revize.com |
| county:laurens | Revize | Yes (mailto) | No | Business directory module | URL should be /departments/county_council/ |
| county:charleston | Custom | Yes (sub-page) | No | Div profile sections | .org redirects to .gov |
| place:charleston | CivicPlus | No | N/A | UL/LI with links | Emails on individual profile pages |
| place:north-charleston | Revize | Yes | **Yes (Cloudflare)** | Accordion + cards | Cloudflare email protection |
| county:richland | Granicus | Yes (mailto) | No | Cards (150x150 imgs) | 11 members |
| place:columbia | WordPress | No | N/A | Card/image blocks | Salient/Nectar theme, emails on subpages |
| county:lexington | Drupal | Yes (mailto) | No | Div sections, h3 headings | Landing page links to /council-members |
| county:horry | Granicus | Yes (mailto) | Partial (Base64 on info@) | Card grid | 11 members |
| place:myrtle-beach | Revize | Yes (mailto) | No | Divs + hr separators | cms6.revize.com |
| place:conway | Revize | Yes (mailto) | No | Unstructured text + br/strong | cms1.revize.com |
| county:york | CivicPlus | No | N/A | Card divs | Emails on /401/District-5 style subpages |
| place:rock-hill | CivicPlus (likely) | Unknown | Unknown | Unknown | WAF blocks automated fetches |
| county:beaufort | Custom (Tyler Tech) | No | N/A | Inline text links | tylertech.com references |

### Batch 2 (17 sites)

| ID | Platform | Emails? | Obfuscated? | HTML Structure | Notes |
|----|----------|---------|-------------|----------------|-------|
| place:hilton-head | Revize | Yes | No | Div cards (photo+contact) | Footer credits Revize |
| county:abbeville | WordPress (Enfold) | No (info@ only) | No | Div sections per member | No individual emails |
| place:abbeville | CivicPlus | Partial (2/8) | No | Div containers per member | Most members lack contact info |
| place:aiken | Unknown | Unknown | Unknown | Unknown | 403 to automated fetches |
| county:bamberg | Drupal (VC3) | No | N/A | UL/LI nav to district subpages | Individual district pages |
| place:bamberg | SchoolInsites/Najla | No | Yes (server-side dialog) | Bootstrap card grid | Emails behind JS dialog popups |
| place:barnwell | Drupal | No | N/A | Plain text | Very minimal, names + districts only |
| county:berkeley | WordPress | Unknown | Unknown | Unknown | 403 on council page |
| place:goose-creek | Drupal | No | Yes (Cloudflare) | H4/H5 headings + links | Member subpages at /staff/* |
| county:calhoun | Drupal (Palmetto) | Yes | No | **Table** | Clean table layout |
| county:cherokee | WordPress (Elementor) | No | Unknown | Unknown | Landing page only |
| place:gaffney | CivicPlus | Yes (all 7) | No | UL/LI + mailto | Clean plaintext emails |
| county:chester | WordPress | Yes (subpage) | Yes (Cloudflare) | Div cards | Members at /county-council-members |
| place:chester | CivicPlus | No | N/A | N/A | Homepage only, no council page found |
| county:chesterfield | Wix | No | Unknown | Wix mesh/grid | No member data visible |
| place:chesterfield | Wix | No | Unknown | Wix components | Landing page only |
| county:clarendon | Govstack | No | N/A | Div blocks (photo+h6) | Phones visible, no emails |

### Batch 3 (17 sites)

| ID | Platform | Emails? | Obfuscated? | HTML Structure | Notes |
|----|----------|---------|-------------|----------------|-------|
| county:colleton | Drupal | Yes | No | Div cards | Plaintext mailto links |
| place:walterboro | Drupal (Panopoly) | Yes | No | Div cards | VC3-hosted |
| county:darlington | Revize | Yes | No | Divs (profile+contact) | UserWay accessibility |
| place:darlington | WordPress | Yes | No | Essential Grid (li elements) | citygov theme |
| county:dillon | Unknown | N/A | N/A | N/A | **Site down** (ECONNREFUSED) |
| place:dillon | Munibit | Limited | No | Web components (`<mwjspeople-obj>`) | API at /api/public/mwjsPeople |
| county:dorchester | Granicus | Yes (subpage) | No | Widget divs + table | Members on /council-members subpage |
| county:edgefield | WordPress (Divi) | Yes | No | Divi sections per district | |
| county:fairfield | Custom (DuBose Web) | Yes | No | Semantic HTML sections | |
| county:florence | Custom (Mobirise) | Yes | No | Card layout | Assets on AWS S3 |
| place:florence | Drupal | No | N/A | Div cards | Emails on individual profile pages |
| place:georgetown | Revize | Yes | No | Divs + hr + bio paragraphs | |
| county:greenwood | Wix | Yes | No | Wix dynamic content | Emails in page source |
| place:greenwood | Revize | Yes | No | Definition list (dt/dd) | |
| place:hampton | Drupal | No | N/A | HTML table | No council member emails |
| county:jasper | Govstack | Yes | No | HTML table + photo cards | Recite Me widget |
| county:kershaw | Granicus | Yes | No | Widget divs | 7 members |

### Batch 4 (15 sites)

| ID | Platform | Emails? | Obfuscated? | HTML Structure | Notes |
|----|----------|---------|-------------|----------------|-------|
| county:lee | Revize | No (staff only) | No | UL with images + text | 7 members, no council emails |
| place:bishopville | WordPress (Breakdance) | Partial | Yes (CleanTalk) | Contact form popups | |
| county:marion | Revize | No (empty email col) | N/A | HTML table | Email column exists but empty |
| place:marion | WordPress (Wonder Blocks) | No | N/A | Unknown | JS-rendered, no static content |
| county:marlboro | Revize | No (clerk only) | No | h4 + img + text | 8 members with phones |
| county:mccormick | Revize | Yes (some personal) | No | FAQ/accordion divs | Non-standard email domains |
| place:mccormick | WordPress (Divi) | No | N/A | Unknown | JS-rendered content |
| county:newberry | Drupal | Yes | No | Div cards + headshots | Plain email text |
| place:newberry | Revize | Yes | No | Revize business_directory | ArcGIS map linked |
| county:oconee | Joomla | Yes | Partial (info@ obfuscated) | Div cards + modals | district1-5@oconeesc.com |
| place:orangeburg | Drupal | Yes | No | Div cards + images | 7 members |
| county:saluda | Drupal | Yes | No | Plain text + strong + mailto | 5 members |
| place:saluda | Squarespace | Unknown | Unknown | Unknown | 403 to automated fetches |
| county:sumter | Revize | No (generic council@) | No | Plain text in FAQ block | This is FAQ page, not member directory |
| place:sumter | Drupal | Yes | Yes (Cloudflare) | Div cards + headshots | |

### Missing URLs (16 jurisdictions -- all found)

| ID | URL Found | Has Contact Info | Platform |
|----|-----------|-----------------|----------|
| county:allendale | allendalecounty.com/.../city_council_members.php | Yes (full) | Revize |
| place:allendale | townofallendale.sc.gov/.../allendale-town-council | Yes (emails) | Drupal |
| place:moncks-corner | monckscornersc.gov/government/elected-officials | Yes (emails) | WordPress (Elementor) |
| place:st-matthews | stmatthews.sc.gov/town-leaders | Names only | Drupal |
| place:manning | cityofmanning.org/city-council | Yes (directory) | Unknown (403) |
| place:st-george | saintgeorgesc.org/administration | Names only | GoDaddy Builder |
| place:edgefield | exploreedgefield.com/community-resources.html | Names only | Custom (MGM Design) |
| place:winnsboro | townofwinnsboro.com/town-council | Yes (emails) | WordPress |
| place:ridgeland | ridgelandsc.gov/town-council | Yes (emails) | Custom (Hazel Digital) |
| place:camden | experiencecamdensc.com/.../mayor-and-city-council/ | Likely yes | WordPress (Divi) |
| place:bennettsville | bennettsvillesc.com/city-council | Yes (phone+email) | Drupal |
| place:walhalla | cityofwalhalla.com/government/mayor/ | Yes (mayor) | WordPress (Jupiter) |
| county:union | gearupunionsc.com/.../union-county-council/ | Yes (full) | WordPress |
| place:union | cityofunion.net/.../Union-City-Council | Unclear (404s) | Apptegy/Vue.js |
| county:williamsburg | williamsburgcounty.sc.gov/184/County-Council | Yes (directory) | CivicPlus |
| place:kingstree | kingstree.org/government/mayor-town-council/ | Yes (bios) | WordPress (Elementor) |

---

## Recommended Adapter Strategy

### Priority 1: CivicPlus quick wins (config only)

These are CivicPlus sites that can be automated by adding config to the existing adapter:

1. **place:spartanburg** -- URL: /316/City-Council
2. **place:charleston** -- URL: /180/Members-Districts (may need profile page crawl)
3. **county:york** -- URL: /375/County-Council (may need subpage crawl)
4. **place:gaffney** -- already has clean mailto links
5. **place:abbeville** -- partial contact info
6. **place:rock-hill** -- needs manual URL verification (WAF blocks)
7. **county:williamsburg** -- from missing URLs list

**Estimated coverage: 7 jurisdictions with zero new code.**

### Priority 2: Revize adapter (new, config-driven)

14 Revize sites with very similar structure. Build one config-driven adapter like CivicPlus:

county:pickens, county:laurens, place:north-charleston, place:hilton-head, place:myrtle-beach, place:conway, county:darlington, place:georgetown, place:greenwood, county:lee, county:marion, county:marlboro, county:mccormick, place:newberry, county:allendale, county:sumter, place:newberry

Key patterns:
- Business directory module common
- Most have plain mailto links
- North Charleston has Cloudflare email protection (needs deobfuscation)
- Some have no council member emails at all

**Estimated coverage: ~14 jurisdictions with one new adapter.**

### Priority 3: Drupal adapter (new)

12 Drupal sites. More varied themes but common patterns (VC3-hosted, Panopoly, Palmetto):

county:lexington, county:bamberg, place:barnwell, place:goose-creek, county:calhoun, county:colleton, place:walterboro, place:florence, place:hampton, county:newberry, place:orangeburg, county:saluda, place:allendale, place:bennettsville, place:st-matthews, place:sumter

**Estimated coverage: ~12 jurisdictions with one new adapter (may need subclass variants).**

### Priority 4: Granicus adapter (new)

4 Granicus (OpenCities) sites with widget-based layouts:

county:richland, county:horry, county:dorchester, county:kershaw

**Estimated coverage: 4 jurisdictions with one new adapter.**

### Priority 5: WordPress adapter (new, most complex)

13 WordPress sites with many different themes (Divi, Elementor, Enfold, Salient, etc.). May need per-theme subclasses:

county:anderson, place:anderson, place:columbia, county:abbeville, county:berkeley, county:cherokee, county:chester, place:darlington, county:edgefield, place:moncks-corner, place:winnsboro, place:camden, place:walhalla, county:union, place:kingstree, place:bishopville, place:marion, place:mccormick

**Estimated coverage: ~13 jurisdictions, but high variance between themes.**

### Priority 6: One-offs and difficult cases

| ID | Platform | Difficulty | Notes |
|----|----------|-----------|-------|
| county:charleston | Custom | Medium | Profile sections on sub-page |
| county:beaufort | Tyler Tech | Medium | Member links to profiles |
| county:fairfield | Custom (DuBose) | Low | Semantic HTML |
| county:florence | Custom (Mobirise) | Low | Card layout |
| county:greenwood | Wix | Hard | JS-rendered |
| county:chesterfield | Wix | Hard | No member data visible |
| place:chesterfield | Wix | Hard | No member data visible |
| place:bamberg | SchoolInsites | Hard | Email behind JS dialog |
| county:dillon | Unknown | Blocked | Site down |
| place:dillon | Munibit | Medium | Has JSON API |
| county:oconee | Joomla | Medium | SP Page Builder |
| place:saluda | Squarespace | Hard | 403 to automated fetches |
| county:clarendon | Govstack | Medium | No emails |
| county:jasper | Govstack | Low | Table + cards |
| place:aiken | Unknown | Blocked | 403 |
| place:chester | CivicPlus | Blocked | No council page found |
| place:st-george | GoDaddy Builder | Hard | Names only |
| place:edgefield | Custom | Hard | Names only |
| place:ridgeland | Custom (Hazel) | Medium | Has emails |
| place:manning | Unknown | Blocked | 403 |
| place:union | Apptegy/Vue | Hard | 404s on fetch |

## Cloudflare Email Deobfuscation

4 sites use Cloudflare email protection:
- place:north-charleston (Revize)
- place:goose-creek (Drupal)
- county:chester (WordPress)
- place:sumter (Drupal)

The existing CivicPlus adapter already handles JS email deobfuscation (`var w`/`var x` pattern). Cloudflare uses a different scheme (hex-encoded XOR with a key byte from `/cdn-cgi/l/email-protection#`). This should be a shared utility in `base.py`.

## Summary

| Category | Count | New code needed |
|----------|------:|----------------|
| CivicPlus config-only | 7 | None |
| Revize adapter | 14 | 1 new adapter |
| Drupal adapter | 12 | 1 new adapter |
| Granicus adapter | 4 | 1 new adapter |
| WordPress adapter | 13 | 1 adapter + theme variants |
| Govstack adapter | 2 | 1 new adapter |
| One-off / custom | 14 | Individual adapters |
| Blocked / down | 6 | Manual investigation |
| **Total** | **72** | |

Remaining 10 jurisdictions from the missing-URL list that weren't platform-audited above need a follow-up audit pass once their URLs are added to the registry.
