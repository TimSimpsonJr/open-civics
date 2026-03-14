"""Adapter for Town of McCormick council members.

Scrapes the WordPress/Divi-powered McCormick town site. The officials page
has council member names listed under a "Message from the Mayor" section
with structure:
  Mayor
  Roy Smith
  District 1
  Dolly P. Franklin
  District 2
  Nathan Jones
  ...

No email addresses or phone numbers are published on the page.
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"
PAGE_URL = "https://www.townofmccormicksc.com/government/town-officials-staff/"


class McCormickTownAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("url", PAGE_URL)
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator="\n", strip=True)
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        members = []

        # Find the "Mayor" label followed by a name
        i = 0
        while i < len(lines):
            if lines[i].lower() == "mayor":
                # Next line should be the mayor's name
                if i + 1 < len(lines):
                    name = lines[i + 1]
                    # Verify it looks like a name (not another label)
                    if not re.match(r"District\s+\d", name, re.IGNORECASE):
                        members.append({
                            "name": name,
                            "title": "Mayor",
                            "email": "",
                            "phone": "",
                        })
                        i += 2
                        continue
            i += 1

        # Find district entries: "District N" followed by name
        for i, line in enumerate(lines):
            district_match = re.match(r"^District\s+(\d+)$", line)
            if district_match and i + 1 < len(lines):
                district_num = district_match.group(1)
                name = lines[i + 1]
                # Make sure next line is a name (not another District label
                # or section heading like "Clerk / Treasurer")
                if re.match(r"District\s+\d", name, re.IGNORECASE):
                    continue
                if name.lower() in ("clerk / treasurer", "clerk/treasurer"):
                    continue

                members.append({
                    "name": name,
                    "title": f"Council Member, District {district_num}",
                    "email": "",
                    "phone": "",
                })

        # Sort: Mayor first, then by district
        members.sort(key=self._sort_key)
        return members

    def get_contact(self) -> dict | None:
        from .base import normalize_phone
        if not hasattr(self, "_html"):
            return None
        soup = BeautifulSoup(self._html, "html.parser")
        # Look for phone in footer or near "Office" label
        phone = ""
        footer = soup.find("footer") or soup.find("div", id=re.compile(r"footer", re.I))
        search_area = footer.get_text() if footer else soup.get_text()
        # Prefer phone labeled "(Office)"
        office_match = re.search(
            r"(\(?\d{3}\)?[\s.\-]*\d{3}[\s.\-]*\d{4})\s*\(?\s*Office\s*\)?",
            search_area,
        )
        if office_match:
            phone = normalize_phone(office_match.group(1))
        else:
            match = re.search(r"\(?\d{3}\)?[\s.\-]*\d{3}[\s.\-]*\d{4}", search_area)
            phone = normalize_phone(match.group(0)) if match else ""
        return {
            "phone": phone,
            "email": "",
            "note": "Town Hall - no individual council member contact info published",
        }

    @staticmethod
    def _sort_key(member: dict) -> tuple:
        title = member["title"]
        if title == "Mayor":
            return (0, 0)
        match = re.search(r"District\s+(\d+)", title)
        if match:
            return (1, int(match.group(1)))
        return (2, 0)
