"""Adapter for Town of Hampton council members.

Scrapes the Drupal-powered Hampton town site. The mayor/council page has
a table with columns: Council Member, Address, Phone Number.

The "Council Member" column contains titles and names together, e.g.:
  "Mayor Robert Brown (Public Works)"
  "Mayor Pro-Tem Beth Chafin(Administration)"
  "Councilman Pete Mixson (Police and Fire Commissioner)"

All members share the same office phone number. No email addresses are
published.
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"
PAGE_URL = "https://www.hamptonsc.gov/mayor-council"


class HamptonTownAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("url", PAGE_URL)
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []

        # Find the table with council member data
        table = None
        for t in soup.find_all("table"):
            text = t.get_text(strip=True)
            if "Council Member" in text and "Phone Number" in text:
                table = t
                break

        if not table:
            return members

        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all(["td", "th"])
            if len(cells) < 3:
                continue

            member_text = cells[0].get_text(strip=True)
            phone_text = cells[2].get_text(strip=True)

            # Skip header row
            if member_text == "Council Member":
                continue

            parsed = self._parse_member_cell(member_text)
            if not parsed:
                continue

            name, title = parsed

            # Normalize phone - add area code if missing
            phone = phone_text
            if re.match(r"^\d{3}-\d{4}$", phone):
                phone = f"(803) {phone[:3]}-{phone[4:]}"

            members.append({
                "name": name,
                "title": title,
                "email": "",
                "phone": phone,
            })

        # Sort: Mayor first, then Mayor Pro Tem, then others
        members.sort(key=self._sort_key)
        return members

    @staticmethod
    def _parse_member_cell(text: str) -> tuple[str, str] | None:
        """Parse the member cell text into (name, title).

        Examples:
          "Mayor Robert Brown\xa0(Public Works)" -> ("Robert Brown", "Mayor")
          "Mayor Pro-Tem\xa0Beth Chafin(Administration)" -> ("Beth Chafin", "Mayor Pro Tem")
          "Councilman Pete Mixson\xa0(Police and Fire Commissioner)" -> ("Pete Mixson", "Council Member")
        """
        # Normalize whitespace
        text = text.replace("\xa0", " ").strip()

        # Remove parenthetical committee assignments
        text = re.sub(r"\s*\([^)]*\)\s*$", "", text).strip()

        # Match "Mayor Pro-Tem Name"
        match = re.match(
            r"Mayor\s+Pro[\s-]?Tem\s+(.+)", text, re.IGNORECASE
        )
        if match:
            return (match.group(1).strip(), "Mayor Pro Tem")

        # Match "Mayor Name"
        match = re.match(r"Mayor\s+(.+)", text, re.IGNORECASE)
        if match:
            return (match.group(1).strip(), "Mayor")

        # Match "Councilman/Councilwoman Name"
        match = re.match(
            r"Council(?:wo)?man\s+(.+)", text, re.IGNORECASE
        )
        if match:
            return (match.group(1).strip(), "Council Member")

        return None

    @staticmethod
    def _sort_key(member: dict) -> tuple:
        title = member["title"]
        if title == "Mayor":
            return (0,)
        if "Mayor Pro Tem" in title:
            return (1,)
        return (2,)
