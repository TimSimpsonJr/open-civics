"""Adapter for Hilton Head Island Town Council.

The Hilton Head site uses a custom PHP layout with member cards in
`div.tile-employee-info` containers. Each card has:
  - h2.tile-employee-name: member name
  - strong.tile-employee-title: title (Mayor, Mayor Pro-Tem Ward N, Ward N)
  - a[href^="tel:"]: phone number in <span>
  - a[href^="mailto:"]: email address

The Town Manager is listed on the same page and should be filtered out.
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"

# Titles containing these substrings are excluded
DEFAULT_EXCLUDE = ["manager", "clerk", "administrator", "assistant", "staff"]


class HiltonHeadAdapter(BaseAdapter):
    """Scraper for Hilton Head Island Town Council page."""

    def fetch(self) -> str:
        url = self.url
        if not url:
            raise RuntimeError(f"No URL configured for {self.id}")
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []
        exclude_terms = self.config.get("memberFilter", DEFAULT_EXCLUDE)

        for tile in soup.find_all("div", class_="tile-employee-info"):
            name_el = tile.find("h2", class_="tile-employee-name")
            title_el = tile.find("strong", class_="tile-employee-title")
            phone_el = tile.find("a", href=lambda h: h and h.startswith("tel:"))
            email_el = tile.find("a", href=lambda h: h and h.startswith("mailto:"))

            name = name_el.get_text(strip=True) if name_el else ""
            title_raw = title_el.get_text(strip=True) if title_el else ""
            phone = ""
            if phone_el:
                span = phone_el.find("span")
                phone = span.get_text(strip=True) if span else phone_el.get_text(strip=True)
            email = email_el["href"].replace("mailto:", "") if email_el else ""

            if not name:
                continue

            # Skip non-council members
            if any(term.lower() in title_raw.lower() for term in exclude_terms):
                continue

            title = self._normalize_title(title_raw)

            members.append({
                "name": name,
                "title": title,
                "email": email,
                "phone": phone,
            })

        members.sort(key=self._sort_key)
        return members

    @staticmethod
    def _normalize_title(title_raw: str) -> str:
        """Normalize ward-based titles to standard format.

        Examples:
          "Mayor" -> "Mayor"
          "Mayor Pro-Tem, Ward 1" -> "Mayor Pro Tem, Ward 1"
          "Ward 2" -> "Council Member, Ward 2"
        """
        title = title_raw.strip()

        # Mayor Pro Tem with ward
        if re.search(r"Pro[- ]?Tem", title, re.I):
            ward_match = re.search(r"Ward\s+(\d+)", title, re.I)
            if ward_match:
                return f"Mayor Pro Tem, Ward {ward_match.group(1)}"
            return "Mayor Pro Tem"

        if re.match(r"^Mayor$", title, re.I):
            return "Mayor"

        # Ward N -> Council Member, Ward N
        ward_match = re.search(r"Ward\s+(\d+)", title, re.I)
        if ward_match:
            return f"Council Member, Ward {ward_match.group(1)}"

        return title or "Council Member"

    @staticmethod
    def _sort_key(member: dict) -> tuple:
        title = member["title"]
        if title == "Mayor":
            return (0, 0)
        if "Mayor Pro Tem" in title:
            return (0, 1)
        ward_match = re.search(r"Ward\s+(\d+)", title)
        if ward_match:
            return (1, int(ward_match.group(1)))
        return (2, 0, member.get("name", ""))
