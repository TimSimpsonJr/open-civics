"""Adapter for Bamberg County Council members.

Scrapes the CivicPlus-powered Bamberg County site. The main council page
links to individual district pages at /county-council/district-N. Each
district page contains:
  - Title (Councilman/Councilwoman/Chairman)
  - Name (in indented text after the title)
  - Phone number
  - Email address

The adapter fetches all 7 district pages to build the member list.
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"
BASE_URL = "https://www.bambergcounty.sc.gov"


class BambergCountyAdapter(BaseAdapter):

    def fetch(self) -> str:
        """Fetch all district pages and concatenate with markers."""
        pages = []
        for d in range(1, 8):
            url = f"{BASE_URL}/county-council/district-{d}"
            try:
                resp = requests.get(
                    url, headers={"User-Agent": USER_AGENT}, timeout=30
                )
                resp.raise_for_status()
                pages.append(f"<!--DISTRICT:{d}-->\n{resp.text}")
            except requests.RequestException:
                continue
        return "\n".join(pages)

    def parse(self, html: str) -> list[dict]:
        members = []

        # Split by district markers
        parts = re.split(r"<!--DISTRICT:(\d+)-->", html)
        # parts: ['', '1', html1, '2', html2, ...]
        for i in range(1, len(parts), 2):
            district_num = parts[i]
            district_html = parts[i + 1] if i + 1 < len(parts) else ""

            member = self._parse_district(district_num, district_html)
            if member:
                members.append(member)

        members.sort(key=self._sort_key)
        return members

    def _parse_district(self, district_num: str, html: str) -> dict | None:
        """Parse a single district page for member info."""
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator="\n", strip=True)
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        name = ""
        role = ""
        phone = ""
        email = ""

        # Phone pattern: (NNN) NNN-NNNN or NNN-NNN-NNNN
        phone_re = re.compile(
            r"^\(?\d{3}\)?[\s.-]*\d{3}[\s.-]*\d{4}"
        )

        role_keywords = {"Councilman", "Councilwoman", "Chairman",
                         "Vice Chairman", "Council Chairman",
                         "Council Vice Chairman"}
        skip_labels = {"Address", "Phone", "Email", "Term Begins",
                       "Term Expires", ":", "Date of Most Recent Election",
                       "Date First Elected",
                       "Council Committees/Civic Involvement",
                       "Meeting Information"}

        # Find the role keyword first (Councilman/Councilwoman/Chairman)
        # then extract name from the next line
        found_role = False
        for i, line in enumerate(lines):
            if line in role_keywords and not found_role:
                role = line
                found_role = True
                continue

            if found_role and not name:
                if line not in skip_labels:
                    name = line.strip()
                    continue

            # Only look for phone/email after we found the name
            if not name:
                continue

            # Phone: line matching phone pattern
            if not phone and phone_re.match(line):
                phone = line
                continue

            # Email
            if not email and "@" in line:
                email = line.strip()
                continue

            # Stop at term/date sections
            if line.startswith("Term") or line.startswith("Date") or \
               line.startswith("Council Committees"):
                break

        if not name:
            return None

        # Build title
        title = f"Council Member, District {district_num}"
        if "Chairman" in role and "Vice" not in role:
            title = f"Chairman, District {district_num}"
        elif "Vice" in role:
            title = f"Vice Chairman, District {district_num}"

        return {
            "name": name,
            "title": title,
            "email": email,
            "phone": phone,
        }

    @staticmethod
    def _sort_key(member: dict) -> int:
        match = re.search(r"District\s+(\d+)", member["title"])
        return int(match.group(1)) if match else 0
