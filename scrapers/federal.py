"""Download federal legislator data from unitedstates/congress-legislators."""

import json
import os
from datetime import date

import requests
import yaml

from .adapters.base import normalize_phone

HEADERS = {"User-Agent": "OpenCivics/1.0 (+https://github.com/TimSimpsonJr/open-civics)"}

LEGISLATORS_URL = (
    "https://raw.githubusercontent.com/unitedstates/"
    "congress-legislators/main/legislators-current.yaml"
)


def download_legislators(url: str = LEGISLATORS_URL) -> list[dict]:
    """Download the congress-legislators YAML and return parsed entries."""
    print(f"  Downloading {url}...")
    resp = requests.get(url, timeout=60, headers=HEADERS)
    resp.raise_for_status()
    return yaml.safe_load(resp.text)


def _abbreviate_party(party: str) -> str:
    party = party.strip().lower()
    if party.startswith("democrat"):
        return "D"
    if party.startswith("republican"):
        return "R"
    if party.startswith("independent"):
        return "I"
    return party[:1].upper() if party else ""


def _normalize_legislator(entry: dict) -> dict | None:
    """Convert a congress-legislators entry to our schema using the current term."""
    terms = entry.get("terms", [])
    if not terms:
        return None

    term = terms[-1]  # current term is always last
    name_block = entry.get("name", {})

    record = {
        "name": name_block.get("official_full", "").strip()
        or f"{name_block.get('first', '')} {name_block.get('last', '')}".strip(),
        "party": _abbreviate_party(term.get("party", "")),
        "phone": normalize_phone(term.get("phone", "")),
        "website": term.get("url", ""),
        "contactForm": term.get("contact_form", ""),
        "office": term.get("office", ""),
        "source": "unitedstates/congress-legislators",
        "lastUpdated": date.today().isoformat(),
    }

    # Chamber-specific fields
    if term.get("type") == "sen":
        record["chamber"] = "senate"
        record["state"] = term.get("state", "")
        rank = term.get("state_rank", "")
        if rank:
            record["seatClass"] = str(term.get("class", ""))
            record["stateRank"] = rank
    elif term.get("type") == "rep":
        record["chamber"] = "house"
        record["state"] = term.get("state", "")
        record["district"] = str(term.get("district", "0"))
    else:
        return None

    # IDs for cross-referencing
    ids = entry.get("id", {})
    if ids.get("bioguide"):
        record["bioguideId"] = ids["bioguide"]

    return record


def update_federal_legislators(output_dir: str, state_filter: str | None = None):
    """Download congress-legislators YAML and write per-state federal.json files.

    Args:
        output_dir: Base data directory (e.g., "data").
        state_filter: If set, only write data for this state code.
    """
    entries = download_legislators()
    print(f"  Downloaded {len(entries)} legislators")

    # Group by state
    by_state: dict[str, dict] = {}

    for entry in entries:
        record = _normalize_legislator(entry)
        if record is None:
            continue

        state = record.pop("state", "")
        if not state:
            continue

        if state_filter and state.upper() != state_filter.upper():
            continue

        if state not in by_state:
            by_state[state] = {"senate": {}, "house": {}}

        chamber = record.pop("chamber")
        if chamber == "senate":
            # Key by seat class (1, 2, or 3)
            key = record.get("seatClass", "")
            if not key:
                key = str(len(by_state[state]["senate"]) + 1)
            by_state[state]["senate"][key] = record
        elif chamber == "house":
            # Key by district number
            key = record.get("district", "0")
            by_state[state]["house"][key] = record

    # Write per-state files
    for state, chambers in sorted(by_state.items()):
        state_dir = os.path.join(output_dir, state.lower())
        os.makedirs(state_dir, exist_ok=True)
        output_path = os.path.join(state_dir, "federal.json")

        data = {
            "meta": {
                "state": state,
                "level": "federal",
                "lastUpdated": date.today().isoformat(),
                "source": "unitedstates/congress-legislators",
            },
            "senate": chambers["senate"],
            "house": chambers["house"],
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")

        s_count = len(chambers["senate"])
        h_count = len(chambers["house"])
        print(f"  {state}: {s_count} senators, {h_count} representatives -> {output_path}")

    total_states = len(by_state)
    print(f"  Wrote federal data for {total_states} state(s)")
