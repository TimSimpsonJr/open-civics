"""Adapter for Abbeville County Council.

The Abbeville County WordPress site lists council members in h3 headings
with format: "Name, Council District N" or just "Council District N" (vacant).

Each section has:
  - h3: "Brandon Johnson, Council District One" (name + district)
  - Optional <strong>: "Vice Chairman" or "Chairman"
  - Contact info paragraph with generic info@abbevillecountysc.com email
  - Phone number in contact paragraph

All individual emails are the same generic address, so we use that as the
shared contact email. Phone numbers are per-member.
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"

# Map word-based district numbers to integers
DISTRICT_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}

PHONE_PATTERN = re.compile(r"\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]\d{4}")


class AbbevilleCountyAdapter(BaseAdapter):
    """Scraper for Abbeville County Council page."""

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

        for h3 in soup.find_all("h3"):
            text = h3.get_text(strip=True)
            if "District" not in text:
                continue

            # Parse name and district from h3
            name, district_num = self._parse_heading(text)
            if district_num is None:
                continue

            # Skip vacant seats (no name)
            if not name:
                continue

            # Look at siblings between this h3 and the next h3 for
            # chairman label and phone number
            chairman_label = ""
            phone = ""
            sib = h3.find_next_sibling()
            while sib:
                if sib.name == "h3":
                    break
                sib_text = sib.get_text(strip=True)

                # Check for Chairman/Vice Chairman label
                if "Chairman" in sib_text and len(sib_text) < 30:
                    chairman_label = sib_text.strip()

                # Check for phone number
                phone_match = PHONE_PATTERN.search(sib_text)
                if phone_match:
                    phone = phone_match.group(0)

                sib = sib.find_next_sibling()

            # Build title
            title = self._build_title(district_num, chairman_label)

            members.append({
                "name": name,
                "title": title,
                "email": "info@abbevillecountysc.com",
                "phone": phone,
            })

        members.sort(key=self._sort_key)
        return members

    @staticmethod
    def _parse_heading(text: str) -> tuple[str, int | None]:
        """Parse an h3 heading like 'Brandon Johnson, Council District One'.

        Returns (name, district_number). Name may be empty for vacant seats.
        """
        # Clean up special characters
        text = text.replace("\xa0", " ").strip()
        text = text.rstrip(",").strip()

        # Try to extract district number (word or digit)
        district_match = re.search(
            r"(?:Council\s+)?District\s+(\w+)", text, re.I
        )
        if not district_match:
            return ("", None)

        district_str = district_match.group(1).lower()
        district_num = DISTRICT_WORDS.get(district_str)
        if district_num is None:
            try:
                district_num = int(district_str)
            except ValueError:
                return ("", None)

        # Extract name (everything before "Council District" or ", District")
        name_part = text[:district_match.start()].strip()
        # Remove trailing comma and "Council" prefix
        name_part = re.sub(r",?\s*Council\s*$", "", name_part, flags=re.I).strip()
        name_part = name_part.rstrip(", ").strip()

        return (name_part, district_num)

    @staticmethod
    def _build_title(district_num: int, chairman_label: str) -> str:
        """Build a title string from district number and chairman label."""
        if "Vice" in chairman_label:
            return f"Vice Chairman, District {district_num}"
        if "Chairman" in chairman_label:
            return f"Chairman, District {district_num}"
        return f"Council Member, District {district_num}"

    @staticmethod
    def _sort_key(member: dict) -> tuple:
        title = member["title"]
        if "Chairman" in title and "Vice" not in title:
            return (0, 0)
        if "Vice Chairman" in title:
            return (0, 1)
        district_match = re.search(r"District\s+(\d+)", title)
        if district_match:
            return (1, int(district_match.group(1)))
        return (2, 0)
