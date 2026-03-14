"""Adapter for Chesterfield County Council members.

Scrapes the Wix-powered Chesterfield County site. Despite being Wix,
enough server-side rendered content is available to extract member names
and district assignments. The page structure places district headings
and member names in span/p tags within the Wix rich-text content.

No email addresses or phone numbers are published on this page. The
council members are listed by district with some leadership roles noted
(Chair, Vice Chair).
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"
PAGE_URL = "https://www.chesterfieldcountysc.com/countycouncil"


class ChesterfieldCountyAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("url", PAGE_URL)
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator="\n", strip=True)
        members = []

        lines = [l.strip() for l in text.split("\n") if l.strip()]

        # Walk through lines looking for "District N" followed by name
        i = 0
        while i < len(lines):
            line = lines[i]
            district_match = re.match(r"^District\s+(\d+)$", line, re.IGNORECASE)
            if district_match:
                district_num = district_match.group(1)
                # Next non-empty line(s) may have term info, then name
                # Look ahead for name (skip "Term Expires:" lines)
                j = i - 1  # Name is BEFORE the District line
                # Actually, look backwards - the name precedes the district
                if j >= 0:
                    name_line = lines[j]
                    # Skip if it's a generic heading
                    if (
                        name_line.lower() not in (
                            "county council", "council", "county",
                        )
                        and not re.match(r"^District\s+\d+$", name_line, re.I)
                        and len(name_line) > 2
                    ):
                        name, title = self._parse_name_title(
                            name_line, district_num
                        )
                        if name:
                            members.append({
                                "name": name,
                                "title": title,
                                "email": "",
                                "phone": "",
                            })
                i += 1
                continue
            i += 1

        # Deduplicate (same person may appear multiple times in SSR)
        seen = set()
        unique = []
        for m in members:
            key = m["name"]
            if key not in seen:
                seen.add(key)
                unique.append(m)

        # Sort by district
        unique.sort(key=lambda m: self._district_sort_key(m["title"]))
        return unique

    @staticmethod
    def _parse_name_title(name_line: str, district: str) -> tuple[str, str]:
        """Parse a name line that may include role suffix like ', Chair'."""
        # Check for "Name, Chair" or "Name, Vice Chair"
        chair_match = re.match(
            r"(.+?),\s*(Vice\s+Chair|Chair)", name_line, re.IGNORECASE
        )
        if chair_match:
            name = chair_match.group(1).strip()
            role = chair_match.group(2).strip().title()
            return name, f"{role}, District {district}"

        # Check for "Bishop, Dr. Johnnie McLendon" - name with prefix
        return name_line.strip(), f"Council Member, District {district}"

    @staticmethod
    def _district_sort_key(title: str) -> int:
        match = re.search(r"District\s+(\d+)", title)
        return int(match.group(1)) if match else 0
