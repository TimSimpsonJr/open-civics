# Data Quality Improvement Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fill contact info gaps across all 96 SC jurisdictions, add executives (Governor, Lt. Gov, missing mayors), and create a quality report script.

**Architecture:** Five independent workstreams: (1) upgrade 6 adapters to capture missing contact data, (2) add `meta.contact` fallback to ~12 dead-end sites, (3) add missing mayors to 10 city adapters, (4) add Governor + Lt. Gov to `scrapers/state.py`, (5) create `scripts/quality_report.py` and wire it into `scrape.yml`.

**Tech Stack:** Python 3.12, requests, BeautifulSoup4, existing BaseAdapter pattern.

---

## Task 1: Quality Report Script

This goes first so we can measure our baseline before making changes.

**Files:**
- Create: `scripts/quality_report.py`

**Step 1: Write `scripts/quality_report.py`**

```python
"""Data quality report for all jurisdiction data files.

Scans data/{state}/local/*.json and data/{state}/state.json to produce
a coverage dashboard showing which jurisdictions have email, phone,
executive (mayor/chair), and general contact info.

Usage:
    python scripts/quality_report.py                # markdown table
    python scripts/quality_report.py --json          # machine-readable
    python scripts/quality_report.py --summary-only  # just the totals
"""

import argparse
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.join(SCRIPT_DIR, "..")
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

EXECUTIVE_TITLES = {
    "place": ["mayor"],
    "county": ["chairman", "chairwoman", "chair", "county supervisor"],
}


def check_jurisdiction(filepath: str) -> dict:
    """Check a single local JSON file for data quality."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    meta = data.get("meta", {})
    members = data.get("members", [])
    jid = meta.get("jurisdiction", os.path.basename(filepath))
    jtype = jid.split(":")[0] if ":" in jid else "place"

    has_email = any(m.get("email") for m in members)
    has_phone = any(m.get("phone") for m in members)
    has_contact = bool(meta.get("contact", {}).get("phone") or meta.get("contact", {}).get("email"))

    # Check for executive title
    exec_titles = EXECUTIVE_TITLES.get(jtype, EXECUTIVE_TITLES["place"])
    executive = ""
    for m in members:
        title_lower = m.get("title", "").lower()
        for et in exec_titles:
            if et in title_lower:
                executive = m.get("title", "").split(",")[0].strip()
                break
        if executive:
            break

    return {
        "id": jid,
        "label": meta.get("label", jid),
        "members": len(members),
        "has_email": has_email,
        "has_phone": has_phone,
        "has_executive": bool(executive),
        "executive_title": executive,
        "has_contact": has_contact,
        "contact_phone": meta.get("contact", {}).get("phone", ""),
    }


def check_state(filepath: str) -> dict:
    """Check state.json for executive data."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    has_executive = "executive" in data and len(data.get("executive", [])) > 0
    senate_count = len(data.get("senate", {}))
    house_count = len(data.get("house", {}))
    exec_count = len(data.get("executive", []))

    return {
        "has_executive": has_executive,
        "senate": senate_count,
        "house": house_count,
        "executive": exec_count,
    }


def main():
    parser = argparse.ArgumentParser(description="Data quality report")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--summary-only", action="store_true", help="Summary stats only")
    args = parser.parse_args()

    results = []
    state_results = {}

    for state_code in sorted(os.listdir(DATA_DIR)):
        state_dir = os.path.join(DATA_DIR, state_code)
        if not os.path.isdir(state_dir):
            continue

        # Check state.json
        state_path = os.path.join(state_dir, "state.json")
        if os.path.exists(state_path):
            state_results[state_code] = check_state(state_path)

        # Check local files
        local_dir = os.path.join(state_dir, "local")
        if not os.path.isdir(local_dir):
            continue
        for fname in sorted(os.listdir(local_dir)):
            if not fname.endswith(".json"):
                continue
            results.append(check_jurisdiction(os.path.join(local_dir, fname)))

    # Compute summary
    total = len(results)
    with_email = sum(1 for r in results if r["has_email"])
    with_phone = sum(1 for r in results if r["has_phone"])
    with_exec = sum(1 for r in results if r["has_executive"])
    with_contact = sum(1 for r in results if r["has_contact"])
    with_any_contact = sum(1 for r in results if r["has_email"] or r["has_phone"] or r["has_contact"])

    summary = {
        "total": total,
        "with_email": with_email,
        "with_phone": with_phone,
        "with_executive": with_exec,
        "with_general_contact": with_contact,
        "with_any_contact": with_any_contact,
    }

    if args.json:
        output = {"jurisdictions": results, "state": state_results, "summary": summary}
        json.dump(output, sys.stdout, indent=2)
        print()
        return

    if not args.summary_only:
        # Markdown table
        print("## Data Quality Report\n")
        print("| Jurisdiction | Members | Email | Phone | Executive | Contact |")
        print("|---|---|---|---|---|---|")
        for r in results:
            email = "yes" if r["has_email"] else "no"
            phone = "yes" if r["has_phone"] else "no"
            exc = r["executive_title"] if r["has_executive"] else "no"
            contact = f'City Hall {r["contact_phone"]}' if r["has_contact"] else "-"
            print(f'| {r["label"]} | {r["members"]} | {email} | {phone} | {exc} | {contact} |')
        print()

    # State info
    for sc, sr in state_results.items():
        state_exec = "yes" if sr["has_executive"] else "NO"
        print(f"**{sc.upper()}:** Senate {sr['senate']}, House {sr['house']}, Executive: {state_exec}")

    print(f"\n**Coverage:** {total} jurisdictions, {with_email} with email, {with_phone} with phone, {with_exec} with executive, {with_contact} with general contact")


if __name__ == "__main__":
    main()
```

**Step 2: Run it to get the baseline**

Run: `python scripts/quality_report.py --summary-only`

Expected output showing current gaps (roughly):
- ~80 with email, ~70 with phone, ~86 with executive, 0 with general contact, state executive: NO

**Step 3: Commit**

```bash
git add scripts/quality_report.py
git commit -m "feat: add data quality report script"
```

---

## Task 2: Add `meta.contact` fallback to dead-end adapters

For jurisdictions where no individual contact info exists, scrape the city hall phone from the page footer/contact section and add it to `meta.contact`. This requires changes in two places: the adapters (to return contact info) and `__main__.py` (to write it into the meta block).

**Files:**
- Modify: `scrapers/adapters/base.py` — add `get_contact()` method to BaseAdapter
- Modify: `scrapers/__main__.py:261-275` — write `meta.contact` if adapter provides it
- Modify: `validate.py:134-137` — recognize optional `meta.contact`
- Modify each dead-end adapter to implement `get_contact()`

**Step 1: Add `get_contact()` to BaseAdapter**

In `scrapers/adapters/base.py`, add after the `scrape()` method:

```python
def get_contact(self) -> dict | None:
    """Return general contact info for the jurisdiction, if available.

    Override in subclasses for jurisdictions where individual member
    contact info is not published. Returns a dict with keys:
        phone: str - general office phone
        email: str - general office email
        note: str - explanation of why individual contact is unavailable

    Returns None if not applicable (i.e., members have their own contact info).
    """
    return None
```

**Step 2: Update `__main__.py` to write `meta.contact`**

In `scrapers/__main__.py`, after the line `data["meta"]["dataLastChanged"] = data_last_changed` (~line 297), add:

```python
# Add general contact info if adapter provides it
contact = adapter.get_contact()
if contact:
    data["meta"]["contact"] = contact
```

**Step 3: Update `validate.py` to recognize `meta.contact`**

In `validate.py`, inside `validate_local_file()`, after the meta field checks (~line 137), add:

```python
contact = meta.get("contact")
if contact is not None:
    if not isinstance(contact, dict):
        error(label, "meta.contact must be an object")
    else:
        phone = contact.get("phone", "")
        if phone and not PHONE_RE.match(phone):
            warn(label, f"meta.contact.phone: unexpected format '{phone}'")
        email = contact.get("email", "")
        if email and not EMAIL_RE.match(email):
            warn(label, f"meta.contact.email: invalid format '{email}'")
```

**Step 4: Implement `get_contact()` on each dead-end adapter**

Each adapter already fetches the page HTML. Override `get_contact()` to parse the city hall phone from the footer or contact section. The adapter's `fetch()` result isn't cached, so we store it during `scrape()`. Add a `_html` attribute in BaseAdapter's `scrape()` method:

In `base.py`, modify `scrape()`:

```python
def scrape(self) -> list[dict]:
    """Full pipeline: fetch -> parse -> normalize -> validate."""
    html = self.fetch()
    self._html = html  # Cache for get_contact()
    raw = self.parse(html)
    normalized = self.normalize(raw)
    return self.validate(normalized)
```

Then each dead-end adapter implements `get_contact()` by parsing `self._html`. Example for `barnwell_city.py`:

```python
def get_contact(self) -> dict | None:
    """Return City Hall phone from the page."""
    if not hasattr(self, "_html"):
        return None
    soup = BeautifulSoup(self._html, "html.parser")
    # Look for phone in page text
    text = soup.get_text()
    match = re.search(r"\(?\d{3}\)?[\s.\-]*\d{3}[\s.\-]*\d{4}", text)
    phone = normalize_phone(match.group(0)) if match else ""
    return {
        "phone": phone,
        "email": "",
        "note": "City Hall - no individual council member contact info published",
    }
```

Adapters to update (each follows the same pattern — find the general phone on the page):
- `scrapers/adapters/barnwell_city.py` — phone: (803) 259-3266
- `scrapers/adapters/dillon_city.py` — phone: (843) 774-0040, email: clerk
- `scrapers/adapters/edgefield_town.py` — phone: (803) 637-4014, email: townofedgefield@exploreedgefield.com
- `scrapers/adapters/marion_city.py` — phone: (843) 423-5961
- `scrapers/adapters/mccormick_town.py` — phone: (864) 852-2225
- `scrapers/adapters/st_george.py` — phone: (843) 563-3032
- `scrapers/adapters/st_matthews.py` — phone: (803) 874-2405
- `scrapers/adapters/bishopville_city.py` — phone: (803) 484-5948
- `scrapers/adapters/chesterfield_county.py` — check if phone available on page
- `scrapers/adapters/masc.py` — MASC pages don't have local phone; skip this adapter (contact comes from the primary site's adapter if available)

For MASC-sourced jurisdictions (Rock Hill, Aiken, Manning, Saluda, Union) — Rock Hill and Aiken get upgraded in Task 3. Manning, Saluda, and Union stay on MASC; add a `get_contact()` that fetches the primary site's contact page for the city hall phone. Use the `url` from the registry entry.

**Step 5: Run scrapers for affected jurisdictions and validate**

Run: `python -m scrapers --jurisdiction place:barnwell` (and each affected jurisdiction)
Run: `python validate.py`
Run: `python scripts/quality_report.py --summary-only`

Expected: `meta.contact` populated, validation passes, quality report shows improved contact coverage.

**Step 6: Commit**

```bash
git add scrapers/adapters/base.py scrapers/__main__.py validate.py scrapers/adapters/*.py
git commit -m "feat: add general contact fallback to dead-end adapters"
```

---

## Task 3: Upgrade Rock Hill and Aiken adapters

Replace MASC fallback with real adapters that capture individual contact info.

**Files:**
- Create: `scrapers/adapters/rock_hill.py`
- Create: `scrapers/adapters/aiken_city.py`
- Modify: `scrapers/__main__.py` — add imports and ADAPTERS entries
- Modify: `registry.json` — change adapter from "masc" to "rock_hill" / "aiken_city"

### Task 3a: Rock Hill adapter

**Step 1: Write `scrapers/adapters/rock_hill.py`**

Rock Hill has a CivicPlus/Revize-style site. The council page links to individual member profile pages at `/government/city-council/members/{slug}` with email, phone, and mailing address.

```python
"""Adapter for City of Rock Hill council members.

Scrapes the Rock Hill city website. The council page lists members as
links to individual profile pages. Each profile page contains email
(mailto link) and phone (tel link or text).
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter, normalize_phone

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"
LISTING_URL = "https://www.cityofrockhill.com/government/city-council"
BASE_URL = "https://www.cityofrockhill.com"


class RockHillAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("url", LISTING_URL)
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []

        # Find links to member profile pages
        # Look for links containing "city-council" and a member slug
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            text = a.get_text(strip=True)
            if not text or len(text) < 3:
                continue
            # Match profile page links (e.g., /government/city-council/members/john-gettys)
            if "/city-council/" not in href:
                continue
            if "/members/" not in href.lower() and "/member/" not in href.lower():
                continue

            full_url = href if href.startswith("http") else BASE_URL + href

            # Avoid duplicates
            if any(m.get("_url") == full_url for m in members):
                continue

            members.append({
                "name": text,
                "title": "",
                "email": "",
                "phone": "",
                "_url": full_url,
            })

        # Fetch each profile page
        for member in members:
            url = member.pop("_url")
            title, email, phone = self._fetch_profile(url)
            member["title"] = title or "Council Member"
            member["email"] = email
            member["phone"] = normalize_phone(phone) if phone else ""

        members.sort(key=self._sort_key)
        return members

    @staticmethod
    def _fetch_profile(url: str) -> tuple[str, str, str]:
        """Fetch profile page and extract title, email, phone."""
        try:
            resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
            resp.raise_for_status()
        except requests.RequestException:
            return "", "", ""

        soup = BeautifulSoup(resp.text, "html.parser")

        # Email from mailto link
        email = ""
        mailto = soup.find("a", href=lambda h: h and h.startswith("mailto:"))
        if mailto:
            email = mailto["href"].replace("mailto:", "").strip()

        # Phone from tel link or text
        phone = ""
        tel = soup.find("a", href=lambda h: h and h.startswith("tel:"))
        if tel:
            phone = tel.get_text(strip=True)
        else:
            # Search page text for phone pattern
            text = soup.get_text()
            match = re.search(r"\(?\d{3}\)?[\s.\-]*\d{3}[\s.\-]*\d{4}", text)
            if match:
                phone = match.group(0)

        # Title: look for "Mayor", "Mayor Pro Tem", ward/district info
        title = ""
        text = soup.get_text(separator="\n", strip=True)
        for line in text.split("\n"):
            line = line.strip()
            lower = line.lower()
            if lower == "mayor":
                title = "Mayor"
                break
            if "mayor pro tem" in lower:
                title = "Mayor Pro Tem"
                break
            # Look for ward info like "Ward 1" or "At-Large"
            ward_match = re.match(r"^Ward\s+(\d+)$", line, re.IGNORECASE)
            if ward_match:
                title = f"Council Member, Ward {ward_match.group(1)}"
                break
            if lower == "at-large":
                title = "Council Member, At-Large"
                break

        return title, email, phone

    @staticmethod
    def _sort_key(member: dict) -> tuple:
        title = member["title"]
        if title == "Mayor":
            return (0, 0, "")
        if "Mayor Pro" in title:
            return (0, 1, "")
        match = re.search(r"Ward\s+(\d+)", title)
        if match:
            return (1, int(match.group(1)), "")
        if "At-Large" in title:
            return (2, 0, member["name"])
        return (3, 0, member["name"])
```

**Step 2: Register in `__main__.py`**

Add import:
```python
from .adapters.rock_hill import RockHillAdapter
```

Add to ADAPTERS dict:
```python
"rock_hill": RockHillAdapter,
```

**Step 3: Update `registry.json`**

Change the Rock Hill entry's adapter from `"masc"` to `"rock_hill"`.

**Step 4: Test**

Run: `python -m scrapers --jurisdiction place:rock-hill`
Expected: Members with individual emails and phones.

Run: `python validate.py`

**Step 5: Commit**

```bash
git add scrapers/adapters/rock_hill.py scrapers/__main__.py registry.json
git commit -m "feat: upgrade Rock Hill from MASC fallback to full adapter"
```

### Task 3b: Aiken City adapter

**Step 1: Write `scrapers/adapters/aiken_city.py`**

Aiken has phone numbers directly on the main council page alongside names and districts.

```python
"""Adapter for City of Aiken council members.

Scrapes the Aiken city website. The main council page lists members
with their district, phone number, and contact form link. No direct
email addresses are published — only phone numbers.
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter, normalize_phone

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"
PAGE_URL = "https://www.cityofaikensc.gov/government/city-council/"


class AikenCityAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("url", PAGE_URL)
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []

        # The page has member cards or sections with name, district, phone
        # Look for tel: links to find phone numbers near member names
        # Also look for structured content blocks
        text = soup.get_text(separator="\n", strip=True)
        lines = text.split("\n")

        # Strategy: find phone numbers and work backward to find associated name
        # OR find structured elements with both name and phone
        for a in soup.find_all("a", href=lambda h: h and h.startswith("tel:")):
            phone = a.get_text(strip=True) or a["href"].replace("tel:", "")
            # Walk up the DOM to find the parent section with the name
            parent = a.parent
            for _ in range(5):  # Walk up at most 5 levels
                if parent is None:
                    break
                name_el = parent.find(["h2", "h3", "h4", "strong"])
                if name_el:
                    name = name_el.get_text(strip=True)
                    if name and len(name) > 2:
                        # Check for district info nearby
                        section_text = parent.get_text(separator="\n", strip=True)
                        title = self._extract_title(section_text)
                        members.append({
                            "name": name,
                            "title": title or "Council Member",
                            "email": "",
                            "phone": normalize_phone(phone),
                        })
                        break
                parent = parent.parent

        # Deduplicate by name
        seen = set()
        unique = []
        for m in members:
            if m["name"] not in seen:
                seen.add(m["name"])
                unique.append(m)

        unique.sort(key=self._sort_key)
        return unique

    @staticmethod
    def _extract_title(text: str) -> str:
        """Extract title from section text."""
        lower = text.lower()
        if "mayor" in lower and "pro tem" not in lower:
            return "Mayor"
        if "mayor pro tem" in lower:
            return "Mayor Pro Tem"
        # Look for district
        match = re.search(r"district\s+(\d+)", lower)
        if match:
            return f"Council Member, District {match.group(1)}"
        if "at-large" in lower or "at large" in lower:
            return "Council Member, At-Large"
        return "Council Member"

    @staticmethod
    def _sort_key(member: dict) -> tuple:
        title = member["title"]
        if title == "Mayor":
            return (0, 0, "")
        if "Mayor Pro" in title:
            return (0, 1, "")
        match = re.search(r"District\s+(\d+)", title)
        if match:
            return (1, int(match.group(1)), "")
        return (2, 0, member["name"])
```

**Step 2: Register in `__main__.py` and update `registry.json`**

Same pattern as Rock Hill — add import, add to ADAPTERS dict, change registry entry from `"masc"` to `"aiken_city"`.

**Step 3: Test**

Run: `python -m scrapers --jurisdiction place:aiken`
Run: `python validate.py`

**Step 4: Commit**

```bash
git add scrapers/adapters/aiken_city.py scrapers/__main__.py registry.json
git commit -m "feat: upgrade Aiken from MASC fallback to full adapter with phones"
```

---

## Task 4: Fix existing adapters to capture missing fields

Four adapters have contact data on the page that they're not scraping.

### Task 4a: Richland County — add phone capture

**Files:**
- Modify: `scrapers/adapters/richland_county.py`

The adapter already parses `li.contact-email` and `li.contact-phone`. The research shows phones ARE on the page. Check if the phone parsing is working — the selector `li.contact-phone` should match. If the page structure changed, update the selector.

**Step 1: Verify current adapter behavior**

Run: `python -m scrapers --jurisdiction county:richland`

If phones still missing, inspect the HTML to find the correct selector and update the `parse()` method. The current code at lines 56-60 looks correct — `li.contact-phone` with an inner `<a>` tag. Likely the issue is that phone is in a different element (e.g., `<span>` instead of `<a>`).

Update to also check for text content if no `<a>` tag:

```python
# Phone from li.contact-phone
phone = ""
phone_li = article.find("li", class_="contact-phone")
if phone_li:
    phone_link = phone_li.find("a", href=True)
    if phone_link:
        phone = phone_link.get_text(strip=True)
    else:
        # Fallback: get text directly
        phone = phone_li.get_text(strip=True)
```

**Step 2: Test and commit**

Run: `python -m scrapers --jurisdiction county:richland`
Run: `python validate.py`

```bash
git add scrapers/adapters/richland_county.py
git commit -m "fix: capture phone numbers in Richland County adapter"
```

### Task 4b: Beaufort County — add phone from profile pages

**Files:**
- Modify: `scrapers/adapters/beaufort_county.py`

The adapter fetches individual member pages for email but doesn't look for phone. Research confirmed phones are on the profile pages.

**Step 1: Update `_fetch_email()` to also extract phone**

Rename `_fetch_email()` to `_fetch_contact()` and return both email and phone:

```python
def _fetch_contact(self, url: str) -> tuple[str, str]:
    """Fetch a member page and extract email and phone."""
    try:
        resp = requests.get(
            url, headers={"User-Agent": USER_AGENT}, timeout=30
        )
        resp.raise_for_status()
    except requests.RequestException:
        return "", ""

    soup = BeautifulSoup(resp.text, "html.parser")

    # Email from mailto link
    email = ""
    mailto = soup.find("a", href=lambda h: h and h.startswith("mailto:"))
    if mailto:
        email = mailto["href"].replace("mailto:", "").strip()

    # Phone from tel link or text pattern
    phone = ""
    tel = soup.find("a", href=lambda h: h and h.startswith("tel:"))
    if tel:
        phone = tel.get_text(strip=True)
    else:
        text = soup.get_text()
        match = re.search(r"\(?\d{3}\)?[\s.\-]*\d{3}[\s.\-]*\d{4}", text)
        if match:
            phone = match.group(0)

    return email, phone
```

Update the call site in `parse()`:

```python
# Fetch each member page for email and phone
for member in members:
    email, phone = self._fetch_contact(member.pop("_url"))
    member["email"] = email
    member["phone"] = normalize_phone(phone) if phone else ""
```

Add `normalize_phone` to the import from `.base`.

**Step 2: Test and commit**

Run: `python -m scrapers --jurisdiction county:beaufort`
Run: `python validate.py`

```bash
git add scrapers/adapters/beaufort_county.py
git commit -m "fix: capture phone numbers from Beaufort County profile pages"
```

### Task 4c: Kershaw County — add email from staff directory

**Files:**
- Create: `scrapers/adapters/kershaw_county.py` (new bespoke adapter replacing SCAC)
- Modify: `scrapers/__main__.py` — add import and ADAPTERS entry
- Modify: `registry.json` — change adapter from "scac" to "kershaw_county"

The SCAC adapter doesn't capture emails. Kershaw County's own site has a staff directory with emails in a table on `/our-county`.

**Step 1: Write the adapter**

```python
"""Adapter for Kershaw County Council members.

Scrapes the Kershaw County website. The /our-county page has a staff
directory widget with a table containing Name, Title, Department,
Phone, and Email columns for all council members.
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter, normalize_phone

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"
PAGE_URL = "https://www.kershaw.sc.gov/our-county"


class KershawCountyAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("url", PAGE_URL)
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []

        # Find the staff directory table
        for table in soup.find_all("table"):
            headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
            if "name" not in headers:
                continue

            name_idx = headers.index("name")
            title_idx = headers.index("title") if "title" in headers else -1
            phone_idx = headers.index("phone") if "phone" in headers else -1
            email_idx = headers.index("email") if "email" in headers else -1
            dept_idx = headers.index("department") if "department" in headers else -1

            for tr in table.find_all("tr"):
                cells = tr.find_all("td")
                if len(cells) <= name_idx:
                    continue

                name = cells[name_idx].get_text(strip=True)
                title = cells[title_idx].get_text(strip=True) if title_idx >= 0 and len(cells) > title_idx else ""
                dept = cells[dept_idx].get_text(strip=True) if dept_idx >= 0 and len(cells) > dept_idx else ""
                phone = cells[phone_idx].get_text(strip=True) if phone_idx >= 0 and len(cells) > phone_idx else ""
                email = ""
                if email_idx >= 0 and len(cells) > email_idx:
                    email_link = cells[email_idx].find("a", href=lambda h: h and "mailto:" in h)
                    if email_link:
                        email = email_link["href"].replace("mailto:", "").strip()
                    else:
                        email = cells[email_idx].get_text(strip=True)
                        if "@" not in email:
                            email = ""

                if not name:
                    continue

                # Filter to council members only
                combined = f"{title} {dept}".lower()
                is_council = any(kw in combined for kw in ["council", "chairman", "vice chair"])
                if not is_council:
                    continue

                members.append({
                    "name": name,
                    "title": self._normalize_title(title),
                    "email": email,
                    "phone": normalize_phone(phone) if phone else "",
                })

            break  # Use first matching table

        members.sort(key=self._sort_key)
        return members

    @staticmethod
    def _normalize_title(raw: str) -> str:
        lower = raw.lower().strip()
        if "chairman" in lower and "vice" not in lower:
            return "Chairman"
        if "vice" in lower:
            return "Vice Chairman"
        return "Council Member"

    @staticmethod
    def _sort_key(member: dict) -> tuple:
        title = member["title"]
        if "Chairman" in title and "Vice" not in title:
            return (0, 0, member["name"])
        if "Vice" in title:
            return (0, 1, member["name"])
        return (1, 0, member["name"])
```

**Step 2: Register and update registry, test and commit**

Same pattern — import, ADAPTERS entry, registry change.

Run: `python -m scrapers --jurisdiction county:kershaw`
Run: `python validate.py`

```bash
git add scrapers/adapters/kershaw_county.py scrapers/__main__.py registry.json
git commit -m "feat: add Kershaw County adapter with email support"
```

### Task 4d: Columbia — add phone from profile pages

**Files:**
- Modify: `scrapers/adapters/columbia.py`

The adapter already fetches profile pages at `citycouncil.columbiasc.gov` for email. Research confirmed phones are also on those pages.

**Step 1: Update `_fetch_profile()` to extract phone**

In `columbia.py`, the `_fetch_profile()` method already returns `(district, email)`. Add phone extraction:

```python
def _fetch_profile(self, url: str) -> tuple[str, str, str]:
    """Fetch a profile page and extract district, email, and phone."""
    try:
        resp = requests.get(
            url, headers={"User-Agent": USER_AGENT}, timeout=30
        )
        resp.raise_for_status()
    except requests.RequestException:
        return ("", "", "")

    soup = BeautifulSoup(resp.text, "html.parser")

    # Email from mailto link
    email = ""
    mailto = soup.find("a", href=lambda h: h and h.startswith("mailto:"))
    if mailto:
        email = mailto["href"].replace("mailto:", "").strip()

    # Phone from tel link
    phone = ""
    tel = soup.find("a", href=lambda h: h and h.startswith("tel:"))
    if tel:
        phone = tel.get_text(strip=True)
    else:
        text = soup.get_text()
        match = re.search(r"\(?\d{3}\)?[\s.\-]*\d{3}[\s.\-]*\d{4}", text)
        if match:
            phone = match.group(0)

    # District from text
    district = ""
    text = soup.get_text(separator="\n", strip=True)
    for line in text.split("\n"):
        line = line.strip()
        if re.match(r"^District\s+[IVX]+$", line):
            num = self._roman_to_arabic(line.split()[-1])
            district = f"District {num}"
            break
        if line == "At-Large":
            district = "At-Large"
            break

    return (district, email, phone)
```

Update the call site in `parse()` to use the new phone value:

```python
district, email, phone = self._fetch_profile(href)

title = "Council Member"
if district:
    title = f"Council Member, {district}"

members.append({
    "name": name.strip(),
    "title": title,
    "email": email,
    "phone": normalize_phone(phone) if phone else "",
})
```

Add `normalize_phone` to the import from `.base`.

**Step 2: Test and commit**

Run: `python -m scrapers --jurisdiction place:columbia`
Run: `python validate.py`

```bash
git add scrapers/adapters/columbia.py
git commit -m "fix: capture phone numbers from Columbia profile pages"
```

---

## Task 5: Add missing mayors to 10 city adapters

10 cities don't include their mayor. For each, determine whether the mayor is on the same page (selector needs widening) or a separate page (need to fetch a second URL).

**Files:**
- Modify: multiple adapters in `scrapers/adapters/`

The cities: Abbeville, Camden, Charleston, Columbia, Mount Pleasant, Myrtle Beach, Newberry, North Charleston, Ridgeland, Walterboro.

**Approach:** For each adapter, the implementer should:
1. Run the adapter and check current output for mayor
2. Fetch the council page and inspect HTML for mayor presence
3. If mayor is on the page but skipped, widen the parsing selector
4. If mayor is on a separate page, add a second fetch in `parse()` or a helper method
5. Test with `python -m scrapers --jurisdiction {id}`
6. Validate with `python validate.py`

**Specific known issues:**

- **Columbia** (`columbia.py` line 51): explicitly skips mayor with `if "mayor." in href: continue`. Remove this skip and handle the mayor profile page (which is at `mayor.columbiasc.gov`). Fetch the mayor page and extract name + contact.
- **Charleston** (`charleston_city.py`): Only looks for `District-*-Councilmember` URLs. Mayor page has a different URL pattern. Add mayor detection.
- **Myrtle Beach** (`revize.py` shared adapter): Need to check if the Revize adapter excludes mayor or if the page just lists council.
- **North Charleston**: Check if the adapter parses the full page or just a council section.

For each city, the implementer should probe the actual site during implementation since page structures may have changed.

**Commit after each city fix or batch related fixes:**

```bash
git commit -m "fix: add missing mayor to {city} adapter"
```

---

## Task 6: Governor + Lt. Governor in state.json

**Files:**
- Modify: `scrapers/state.py` — add `scrape_executive()` function
- Modify: `scrapers/__main__.py` — call `scrape_executive()` and merge into state.json
- Modify: `validate.py` — validate `executive` key in state.json

**Step 1: Add `scrape_executive()` to `scrapers/state.py`**

```python
def scrape_executive(state_code: str) -> list[dict]:
    """Scrape executive officials (Governor, Lt. Governor) for a state.

    Returns a list of executive member dicts.
    """
    if state_code != "SC":
        print(f"  Executive scraping not implemented for {state_code}")
        return []

    executives = []

    # Governor
    gov = _scrape_sc_governor()
    if gov:
        executives.append(gov)

    # Lt. Governor
    lt_gov = _scrape_sc_lt_governor()
    if lt_gov:
        executives.append(lt_gov)

    return executives


def _scrape_sc_governor() -> dict | None:
    """Scrape SC Governor info from governor.sc.gov."""
    try:
        resp = requests.get(
            "https://governor.sc.gov/",
            headers=HEADERS, timeout=30,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Extract name from the site — look for the governor's name
        # in the page title or prominent heading
        name = ""
        # Try meta og:site_name or page title
        title_tag = soup.find("title")
        if title_tag:
            text = title_tag.get_text(strip=True)
            # "Governor Henry McMaster | ..." pattern
            match = re.match(r"Governor\s+(.+?)(?:\s*[|\-])", text)
            if match:
                name = match.group(1).strip()

        if not name:
            # Fallback: look in headings
            for h in soup.find_all(["h1", "h2"]):
                text = h.get_text(strip=True)
                if "governor" in text.lower():
                    match = re.search(r"Governor\s+(.+)", text)
                    if match:
                        name = match.group(1).strip()
                        break

        return {
            "name": name or "Henry McMaster",
            "title": "Governor",
            "email": "governor@gov.sc.gov",
            "phone": normalize_phone("803-734-2100"),
            "website": "https://governor.sc.gov/",
            "source": "governor.sc.gov",
            "lastUpdated": date.today().isoformat(),
        }
    except Exception as e:
        print(f"  WARNING: Failed to scrape governor: {e}")
        return {
            "name": "Henry McMaster",
            "title": "Governor",
            "email": "governor@gov.sc.gov",
            "phone": normalize_phone("803-734-2100"),
            "website": "https://governor.sc.gov/",
            "source": "governor.sc.gov",
            "lastUpdated": date.today().isoformat(),
        }


def _scrape_sc_lt_governor() -> dict | None:
    """Scrape SC Lt. Governor info from ltgov.sc.gov."""
    try:
        resp = requests.get(
            "https://ltgov.sc.gov/",
            headers=HEADERS, timeout=30,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        name = ""
        title_tag = soup.find("title")
        if title_tag:
            text = title_tag.get_text(strip=True)
            match = re.search(r"(?:Lt\.?\s*Governor|Lieutenant\s+Governor)\s+(.+?)(?:\s*[|\-])", text)
            if match:
                name = match.group(1).strip()

        return {
            "name": name or "Pamela Evette",
            "title": "Lieutenant Governor",
            "email": "ltgovernor@ltgov.sc.gov",
            "phone": normalize_phone("803-734-2080"),
            "website": "https://ltgov.sc.gov/",
            "source": "ltgov.sc.gov",
            "lastUpdated": date.today().isoformat(),
        }
    except Exception as e:
        print(f"  WARNING: Failed to scrape lt. governor: {e}")
        return {
            "name": "Pamela Evette",
            "title": "Lieutenant Governor",
            "email": "ltgovernor@ltgov.sc.gov",
            "phone": normalize_phone("803-734-2080"),
            "website": "https://ltgov.sc.gov/",
            "source": "ltgov.sc.gov",
            "lastUpdated": date.today().isoformat(),
        }
```

**Step 2: Update `__main__.py` to merge executive data into state.json**

In the `scrape_state()` function, after `update_state_legislators()` is called, add executive scraping. The cleanest approach: after writing state.json, read it back, add executive data, and rewrite.

In `scrapers/__main__.py`, modify `scrape_state()`:

```python
def scrape_state(state_code, state_config, dry_run=False):
    from .state import update_state_legislators, scrape_executive

    # ... existing code ...

    if dry_run:
        print(f"  Would download: {source_url}")
        print(f"  Would write: {output_path}")
        return

    update_state_legislators(source_url, output_path, state_code=state_code)

    # Add executive officials
    executives = scrape_executive(state_code)
    if executives:
        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["executive"] = executives
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"  Added {len(executives)} executive officials")
```

**Step 3: Update `validate.py` to check executive key**

In `validate_state_json()`, add after the chamber validation loop:

```python
# Validate executive (optional)
executive = data.get("executive")
if executive is not None:
    if not isinstance(executive, list):
        error(label, "'executive' must be a list")
    else:
        for i, member in enumerate(executive):
            prefix = f"executive[{i}]"
            if not member.get("name"):
                error(label, f"{prefix}: missing 'name'")
            if not member.get("title"):
                error(label, f"{prefix}: missing 'title'")
            email = member.get("email", "")
            if email and not EMAIL_RE.match(email):
                warn(label, f"{prefix}: invalid email format '{email}'")
            phone = member.get("phone", "")
            if phone and not PHONE_RE.match(phone):
                warn(label, f"{prefix}: unexpected phone format '{phone}'")
```

**Step 4: Test**

Run: `python -m scrapers --state SC --state-only`
Run: `python validate.py`

Check `data/sc/state.json` for the `executive` key.

**Step 5: Commit**

```bash
git add scrapers/state.py scrapers/__main__.py validate.py
git commit -m "feat: add Governor and Lt. Governor to state.json"
```

---

## Task 7: Wire quality report into scrape.yml

**Files:**
- Modify: `.github/workflows/scrape.yml` — add quality report step after stale check

**Step 1: Add quality report step**

After the stale check step, add:

```yaml
- name: Run quality report
  run: python scripts/quality_report.py --summary-only > quality-summary.txt

- name: Upload quality report
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: quality-report
    path: quality-summary.txt
    retention-days: 30
```

Include the quality summary in the PR body by appending it in the "Create PR" step.

**Step 2: Test by reviewing the workflow YAML**

No live test needed — this is CI configuration.

**Step 3: Commit**

```bash
git add .github/workflows/scrape.yml
git commit -m "feat: add quality report to scrape workflow"
```

---

## Task 8: Run full scrape, validate, and produce final quality report

**Step 1:** Run: `python -m scrapers --state SC`
**Step 2:** Run: `python validate.py`
**Step 3:** Run: `python scripts/quality_report.py --summary-only`
**Step 4:** Compare to baseline from Task 1 — confirm improvement in email, phone, executive, and contact coverage.

**Step 5: Commit data changes**

```bash
git add data/
git commit -m "data: refresh SC data with quality improvements"
```

---

## Task 9: Update MANIFEST.md

**Step 1:** Regenerate `MANIFEST.md` to reflect new files (quality report script, new adapters).

**Step 2: Commit**

```bash
git add MANIFEST.md
git commit -m "docs: update MANIFEST.md with data quality changes"
```
