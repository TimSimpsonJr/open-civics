"""Download OpenStates CSV and update state legislators JSON."""

import csv
import io
import json
import re
import time
from datetime import date

import requests
from bs4 import BeautifulSoup

from .adapters.base import normalize_phone
from .state_email_rules import generate_email

HEADERS = {"User-Agent": "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"}


REQUIRED_CSV_COLUMNS = {"name", "current_district", "current_chamber", "current_party"}


def download_csv(url: str) -> list[dict]:
    """Download the OpenStates CSV and return rows as dicts."""
    print(f"  Downloading {url}...")
    resp = requests.get(url, timeout=60, headers=HEADERS)
    resp.raise_for_status()
    reader = csv.DictReader(io.StringIO(resp.text))
    rows = list(reader)

    # Validate CSV has expected columns
    if rows:
        actual_columns = set(rows[0].keys())
        missing = REQUIRED_CSV_COLUMNS - actual_columns
        if missing:
            raise ValueError(
                f"OpenStates CSV is missing expected columns: {missing}. "
                f"Available: {sorted(actual_columns)}"
            )

    return rows


def normalize_row(row: dict) -> dict:
    """Convert an OpenStates CSV row to our unified schema."""
    record = {
        "name": row.get("name", "").strip(),
        "district": row.get("current_district", "").strip(),
        "party": _abbreviate_party(row.get("current_party", "")),
        "email": row.get("email", "").strip(),
        "phone": normalize_phone(row.get("capitol_voice", "")),
        "photoUrl": row.get("image", "").strip(),
        "website": _first_link(row.get("links", "")),
        "source": "openstates",
        "lastUpdated": date.today().isoformat(),
    }

    # Optional social media fields -- only include if present
    if row.get("twitter", "").strip():
        record["twitter"] = row["twitter"].strip()
    if row.get("facebook", "").strip():
        record["facebook"] = row["facebook"].strip()

    return record


def _abbreviate_party(party: str) -> str:
    party = party.strip().lower()
    if party.startswith("democrat"):
        return "D"
    if party.startswith("republican"):
        return "R"
    if party.startswith("independent"):
        return "I"
    return party[:1].upper() if party else ""


def _first_link(links_str: str) -> str:
    """Extract first URL from OpenStates links field (semicolon-separated)."""
    if not links_str or not links_str.strip():
        return ""
    return links_str.strip().split(";")[0].strip()


def _scrape_phone(member_url: str) -> str:
    """Scrape Columbia office phone from a scstatehouse.gov member page."""
    try:
        resp = requests.get(member_url, timeout=15, headers=HEADERS)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for span in soup.find_all("span"):
            if span.get_text(strip=True) == "Business Phone":
                p_text = span.parent.get_text(strip=True)
                match = re.search(r"\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}", p_text)
                if match:
                    return normalize_phone(match.group(0))
        return ""
    except Exception as e:
        print(f"    WARNING: Failed to scrape phone from {member_url}: {e}")
        return ""


def _backfill_phones(data: dict):
    """Fetch phone numbers from scstatehouse.gov for members missing them."""
    members = []
    for chamber in ("senate", "house"):
        for dist, rec in data.get(chamber, {}).items():
            if not rec.get("phone") and rec.get("website"):
                members.append(rec)

    if not members:
        print("  All members already have phone numbers")
        return

    print(f"  Backfilling phone numbers for {len(members)} members from scstatehouse.gov...")
    filled = 0
    for i, rec in enumerate(members):
        phone = _scrape_phone(rec["website"])
        if phone:
            rec["phone"] = phone
            filled += 1
        if (i + 1) % 20 == 0:
            print(f"    ... {i + 1}/{len(members)} done")
        time.sleep(0.3)  # polite rate limiting

    print(f"  Backfilled {filled}/{len(members)} phone numbers")


def update_state_legislators(
    source_url: str,
    output_path: str,
    state_code: str = "SC",
):
    """Download OpenStates CSV and write state legislators JSON.

    Args:
        source_url: URL to the OpenStates CSV download.
        output_path: Path to write the output JSON file.
        state_code: Two-letter state code (default: "SC").
    """
    rows = download_csv(source_url)
    print(f"  Downloaded {len(rows)} rows")

    senate = {}
    house = {}

    for row in rows:
        chamber = row.get("current_chamber", "").strip().lower()
        district = row.get("current_district", "").strip()
        if not district:
            continue

        record = normalize_row(row)

        if chamber == "upper":
            senate[district] = record
        elif chamber == "lower":
            house[district] = record
        else:
            print(f"  WARNING: Unknown chamber '{chamber}' for {record['name']}")

    print(f"  Senate: {len(senate)} members, House: {len(house)} members")

    # Sanity checks -- these thresholds are SC-specific (46 senate, 124 house).
    # Other states will need their own thresholds or these checks disabled.
    if state_code == "SC":
        if len(senate) < 37:  # 80% threshold
            raise ValueError(
                f"Only {len(senate)} senate members found (expected ~46). "
                f"Data source may have changed."
            )
        if len(house) < 99:  # 80% threshold
            raise ValueError(
                f"Only {len(house)} house members found (expected ~124). "
                f"Data source may have changed."
            )

    # Validate individual records
    for chamber_name, chamber_data in [("senate", senate), ("house", house)]:
        for district, record in chamber_data.items():
            if not record.get("name"):
                print(f"  WARNING: {chamber_name}[{district}] has no name")
            if not record.get("email") and not record.get("phone"):
                print(f"  WARNING: {chamber_name}[{district}] ({record.get('name', '?')}) has no email or phone")

    data = {
        "meta": {
            "state": state_code,
            "level": "state",
            "lastUpdated": date.today().isoformat(),
            "source": "openstates",
        },
        "senate": senate,
        "house": house,
    }

    # Backfill missing emails from state-specific rules
    for chamber_key in ("senate", "house"):
        for district, record in data.get(chamber_key, {}).items():
            if not record.get("email"):
                name = record.get("name", "")
                parts = name.split(" ", 1)
                if len(parts) == 2:
                    first, last = parts
                    email = generate_email(state_code, chamber_key, first, last)
                    if email:
                        record["email"] = email
                        record["emailVerified"] = False

    # Backfill phone numbers from scstatehouse.gov member pages
    if state_code == "SC":
        _backfill_phones(data)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"  Wrote {output_path}")
