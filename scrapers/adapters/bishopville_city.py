"""Adapter for City of Bishopville council members.

Scrapes the WordPress Breakdance-powered Bishopville site. The council
page at /government/city-council/ has member names in <h3> headings
with titles in adjacent text within the parent container:
  - "Luke D. Giddings" with "Mayor" nearby
  - "Gloria S. Lewis" with "Mayor Pro Tempore" nearby
  - Other members with "City Council" nearby

Contact info is only available through popup forms (not in the HTML),
so only names and titles are extracted.
"""

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"
PAGE_URL = "https://cityofbishopvillesc.com/government/city-council/"


class BishopvilleCityAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("url", PAGE_URL)
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []

        # Known member names appear as h3 headings with titles in parent divs
        known_names = set()
        for h3 in soup.find_all("h3"):
            name = h3.get_text(strip=True)
            if not name or len(name) < 3 or len(name) > 50:
                continue

            # Check parent for title context
            parent = h3.parent
            if not parent:
                continue

            parent_text = parent.get_text(separator="|", strip=True)

            # Only process entries that have Mayor/Council context
            if "Mayor" not in parent_text and "Council" not in parent_text:
                continue
            if "Contact" not in parent_text:
                continue

            # Skip if already seen
            if name in known_names:
                continue
            known_names.add(name)

            # Determine title from parent text
            title = self._extract_title(parent_text)

            members.append({
                "name": name,
                "title": title,
                "email": "",
                "phone": "",
            })

        return members

    def get_contact(self) -> dict | None:
        import re
        from .base import normalize_phone
        if not hasattr(self, "_html"):
            return None
        soup = BeautifulSoup(self._html, "html.parser")
        text = soup.get_text()
        match = re.search(r"\(?\d{3}\)?[\s.\-]*\d{3}[\s.\-]*\d{4}", text)
        phone = normalize_phone(match.group(0)) if match else ""
        return {
            "phone": phone,
            "email": "",
            "note": "City Hall - no individual council member contact info published",
        }

    @staticmethod
    def _extract_title(parent_text: str) -> str:
        """Extract the title from the parent container text."""
        parts = [p.strip() for p in parent_text.split("|") if p.strip()]

        for part in parts:
            lower = part.lower()
            if lower == "mayor":
                return "Mayor"
            if "mayor pro" in lower:
                return "Mayor Pro Tem"

        # Default for regular council members
        return "Council Member"
