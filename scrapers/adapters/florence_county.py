"""Adapter for Florence County Council members.

Scrapes a Mobirise-built site with card layout. Each council member
appears in a div.card-wrap with:
  - h5.card-title (strong > name, may contain <br> line breaks)
  - h6.mbr-role (district/chairman info)
  - a[href*=mailto] (email link)

No phone numbers are provided on this site.
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"


class FlorenceCountyAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("url", self.url)
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []

        for card in soup.find_all("div", class_="card-wrap"):
            # Name from h5.card-title
            h5 = card.find("h5", class_="card-title")
            if not h5:
                continue
            # Must have the mbr-section-title class to be a council member card
            h5_classes = h5.get("class", [])
            if "mbr-section-title" not in h5_classes:
                continue

            name = h5.get_text(separator=" ", strip=True)
            if not name or len(name) < 3:
                continue

            # Clean up multiple spaces from <br> replacements
            name = re.sub(r"\s+", " ", name).strip()

            # Role/district from h6.mbr-role
            h6 = card.find("h6", class_="mbr-role")
            role_text = ""
            if h6:
                role_text = h6.get_text(separator=" ", strip=True)
                role_text = re.sub(r"\s+", " ", role_text).strip()

            # Parse title: could be "District N", "Chairman", "District N" etc.
            title = self._parse_role(role_text)

            # Email from mailto link
            email = ""
            email_link = card.find("a", href=lambda h: h and "mailto:" in h.lower())
            if email_link:
                href = email_link["href"]
                # Handle "mailto: email" (with space)
                email = re.sub(r"^mailto:\s*", "", href, flags=re.I).strip()

            members.append({
                "name": name,
                "title": title,
                "email": email,
                "phone": "",
            })

        return members

    @staticmethod
    def _parse_role(role_text: str) -> str:
        """Parse role text into a standardized title."""
        if not role_text:
            return "Council Member"

        # Check for chairman in role text
        is_chairman = "chairman" in role_text.lower()
        is_vice = "vice" in role_text.lower()

        # Extract district number
        district_match = re.search(r"District\s+(\d+)", role_text, re.I)

        if is_chairman and not is_vice:
            if district_match:
                return f"Chairman, District {district_match.group(1)}"
            return "Chairman"
        if is_vice:
            if district_match:
                return f"Vice Chairman, District {district_match.group(1)}"
            return "Vice Chairman"
        if district_match:
            return f"Council Member, District {district_match.group(1)}"

        return role_text or "Council Member"
