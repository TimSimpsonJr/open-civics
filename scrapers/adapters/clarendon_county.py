"""Adapter for Clarendon County Council members.

Scrapes the Elementor-powered Clarendon County site. Council members are
listed in elementor-image-box widgets with:
  - h6.elementor-image-box-title: member name
  - p.elementor-image-box-description: title (CHAIRMAN, COUNCILMAN - District N)

Additional p.small elements contain addresses and phone numbers in a
predictable sequence following each member's title block.
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"
PAGE_URL = "https://www.clarendoncountysc.gov/our-government/council/"


class ClarendonCountyAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("url", PAGE_URL)
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []

        # Get all names from h6.elementor-image-box-title
        name_elements = soup.find_all("h6", class_="elementor-image-box-title")

        # Get all p.small elements for titles, addresses, phones
        small_ps = soup.find_all("p", class_="small")
        small_texts = [p.get_text(separator=" ", strip=True) for p in small_ps]

        # Filter out empty p.small elements
        small_texts = [t for t in small_texts if t]

        # Phone pattern: NNN-NNN-NNNN or (NNN) NNN-NNNN
        phone_re = re.compile(
            r"^\(?\d{3}\)?[\s.-]*\d{3}[\s.-]*\d{4}$"
        )
        # Title pattern: CHAIRMAN, COUNCILMAN - District N, etc.
        title_re = re.compile(
            r"^(CHAIRMAN|VICE[- ]CHAIRMAN|COUNCIL(?:WO)?MAN)"
        )

        # Parse the p.small sequence: each member has:
        #   1. Title (CHAIRMAN, COUNCILMAN - District N)
        #   2. Optional additional title (VICE-CHAIRMAN)
        #   3. Address line (skip)
        #   4. Phone number (NNN-NNN-NNNN)
        member_idx = 0
        i = 0
        while i < len(small_texts) and member_idx < len(name_elements):
            text = small_texts[i]
            name = name_elements[member_idx].get_text(strip=True)

            # This should be a title line
            if not title_re.match(text):
                i += 1
                continue

            title_raw = text
            vice = False
            i += 1

            # Check for secondary title (VICE-CHAIRMAN)
            if i < len(small_texts) and title_re.match(small_texts[i]) and \
               "VICE" in small_texts[i]:
                vice = True
                i += 1

            # Consume address lines (skip non-phone, non-title lines)
            phone = ""
            while i < len(small_texts):
                if title_re.match(small_texts[i]):
                    break  # next member's title
                if phone_re.match(small_texts[i]):
                    phone = small_texts[i]
                    i += 1
                    break
                i += 1  # skip address line

            # Build title
            title = self._parse_title(title_raw, vice)

            members.append({
                "name": name,
                "title": title,
                "email": "",
                "phone": phone,
            })
            member_idx += 1

        members.sort(key=self._sort_key)
        return members

    @staticmethod
    def _parse_title(raw: str, vice: bool) -> str:
        """Parse 'COUNCILMAN - District 1' or 'CHAIRMAN' into a title."""
        district_match = re.search(r"District\s+(\d+)", raw)

        if "CHAIRMAN" in raw and not district_match:
            if vice:
                return "Vice Chairman"
            return "Chairman"

        if district_match:
            dist = district_match.group(1)
            if vice:
                return f"Vice Chairman, District {dist}"
            return f"Council Member, District {dist}"

        return "Council Member"

    @staticmethod
    def _sort_key(member: dict) -> tuple:
        title = member["title"]
        if title == "Chairman":
            return (0, 0)
        if title == "Vice Chairman":
            return (0, 1)
        match = re.search(r"District\s+(\d+)", title)
        if match:
            return (1, int(match.group(1)))
        return (2, 0)
