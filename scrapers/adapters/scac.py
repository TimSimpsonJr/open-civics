"""Shared adapter for county councils via SCAC directory.

The SC Association of Counties (sccounties.org) maintains a directory
for each county with a table of officials. The table has columns:
Name, Position, Phone, Address. However, the table includes ALL
county officials (administrator, clerk, treasurer, etc.), so we
filter to only council-related positions.

Emails are in a separate section of the page (div.views-row elements)
but are NOT per-council-member — they're general contact emails
for the county office.

The SCAC URL is constructed from the county name slug in the adapter
config or derived from the jurisdiction ID.
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter, normalize_phone

USER_AGENT = "OpenCivics/1.0 (+https://github.com/TimSimpsonJr/open-civics)"
SCAC_BASE = "https://www.sccounties.org/county"

# Positions that indicate a council member
COUNCIL_POSITIONS = [
    "council", "supervisor", "chairman", "chairwoman", "vice chair",
]

# Positions to exclude (non-elected staff)
EXCLUDE_POSITIONS = [
    "administrator", "manager", "clerk", "auditor", "treasurer",
    "coroner", "sheriff", "assessor", "attorney", "solicitor",
    "register", "probate", "director", "coordinator", "chief",
    "deputy", "magistrate", "fire", "ems", "911", "building",
    "planning", "zoning", "finance", "purchasing", "tax",
    "comptroller", "information", "engineer", "inspector",
    "voter", "election", "library", "veteran", "economic",
    "emergency", "detention", "parks", "recreation", "public",
    "road", "transportation", "solid waste", "water", "sewer",
    "animal", "code enforcement", "human resources", "budget",
    "communications", "gis", "it ", "technology", "development",
    "services", "maintenance", "facilities",
]


class ScacAdapter(BaseAdapter):
    """Scraper for county council via SCAC directory."""

    def fetch(self) -> str:
        slug = self.config.get("scacSlug", "")
        if not slug:
            # Derive from jurisdiction ID: "county:berkeley" -> "berkeley-county"
            county_name = self.id.split(":", 1)[-1] if ":" in self.id else self.id
            slug = f"{county_name}-county"

        url = f"{SCAC_BASE}/{slug}/directory"
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []

        table = soup.find("table")
        if not table:
            raise ValueError(f"No directory table found for {self.id}")

        for tr in table.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) < 3:
                continue

            name = cells[0].get_text(strip=True)
            position = cells[1].get_text(strip=True)
            phone = cells[2].get_text(strip=True) if len(cells) > 2 else ""

            if not name or not position:
                continue

            # Skip vacant-seat placeholder rows: SCAC lists an unfilled seat as
            # a "<County>Council Vacant" name with no real person behind it.
            if "vacant" in name.lower():
                continue

            pos_lower = position.lower()

            # Must match a council position
            if not any(p in pos_lower for p in COUNCIL_POSITIONS):
                continue

            # Exclude non-council staff that happen to have "council" in title
            if any(ex in pos_lower for ex in EXCLUDE_POSITIONS):
                continue

            # Normalize phone
            phone = normalize_phone(phone) if phone else ""

            # Build title
            title = self._normalize_title(position)

            members.append({
                "name": name,
                "title": title,
                "email": "",
                "phone": phone,
            })

        members.sort(key=self._sort_key)
        return members

    @staticmethod
    def _normalize_title(raw: str) -> str:
        lower = raw.lower().strip()

        if "supervisor" in lower and "chairman" in lower:
            return "Chairman"
        if "supervisor" in lower and "deputy" not in lower:
            return "County Supervisor"
        if "vice chair" in lower:
            return "Vice Chairman"
        if "chairman" in lower or "chairwoman" in lower:
            return "Chairman"
        if "county council" in lower:
            return "Council Member"
        if "council" in lower:
            return "Council Member"
        return raw or "Council Member"

    @staticmethod
    def _sort_key(member: dict) -> tuple:
        title = member.get("title", "")
        if "Chairman" in title and "Vice" not in title:
            return (0, 0, member.get("name", ""))
        if "Supervisor" in title:
            return (0, 0, member.get("name", ""))
        if "Vice" in title:
            return (0, 1, member.get("name", ""))
        return (1, 0, member.get("name", ""))
