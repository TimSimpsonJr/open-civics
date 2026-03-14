"""Adapter for Chester County Council members.

Scrapes the WordPress-powered Chester County site. The council members
page lists members in structured blocks, each containing:
  - A header with "District N" or "At Large"
  - Member name
  - Optional role (Chair, Vice Chair)
  - Email (Cloudflare-obfuscated)
  - Phone number
  - Address and term info

Each member block is wrapped in a container with a child element
carrying the class "section-icon". Emails are protected by Cloudflare
email obfuscation and must be decoded using data-cfemail attributes.
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter, deobfuscate_cf_email

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"
PAGE_URL = "https://chestercountysc.gov/government/chester-county-council/county-council-members/"


class ChesterCountyAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("url", PAGE_URL)
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []

        # Each member block has a child with class "section-icon"
        for icon_el in soup.find_all(True, class_="section-icon"):
            container = icon_el.parent
            if not container:
                continue

            text = container.get_text(separator="\n", strip=True)
            lines = [line.strip() for line in text.split("\n") if line.strip()]

            if not lines:
                continue

            # First line should be "District N" or "At Large"
            first = lines[0]
            district_match = re.match(r"^District\s+(\d+)$", first)
            at_large = first == "At Large"

            if not district_match and not at_large:
                continue

            if district_match:
                district_label = f"District {district_match.group(1)}"
            else:
                district_label = "At-Large"

            # Name is the second line
            name = lines[1] if len(lines) > 1 else ""
            if not name:
                continue

            # Check for role (Chair, Vice Chair)
            role = ""
            idx = 2
            if len(lines) > idx and lines[idx] in (
                "Chair", "Vice Chair", "Chairman", "Vice Chairman"
            ):
                role = lines[idx]

            # Email from CF-protected link
            email = ""
            cf_span = container.find(attrs={"data-cfemail": True})
            if cf_span:
                email = deobfuscate_cf_email(cf_span["data-cfemail"])

            # Phone
            phone = ""
            for line in lines:
                if re.match(r"^\(\d{3}\)\s*\d{3}", line):
                    phone = line
                    break

            # Build title
            title = f"Council Member, {district_label}"
            if role in ("Chair", "Chairman"):
                title = f"Chair, {district_label}"
            elif role in ("Vice Chair", "Vice Chairman"):
                title = f"Vice Chair, {district_label}"

            members.append({
                "name": name,
                "title": title,
                "email": email,
                "phone": phone,
            })

        members.sort(key=self._sort_key)
        return members

    @staticmethod
    def _sort_key(member: dict) -> tuple:
        title = member["title"]
        if "At-Large" in title:
            return (1, 0)
        match = re.search(r"District\s+(\d+)", title)
        if match:
            return (0, int(match.group(1)))
        return (2, 0)
