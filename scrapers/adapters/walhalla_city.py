"""Adapter for City of Walhalla council members.

Scrapes the WordPress Jupiter-themed Walhalla site across two pages:
  1. /government/mayor/ — Mayor name, email, and phone
  2. /government/walhalla-city-council-meet/ — Council member names and
     emails in mk-text-block divs

Each council member block is a mk-text-block div containing the member's
title + name on the first line and their email as a mailto link. The
mayor page has similar structure with name and contact info in centered
divs.
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"
MAYOR_URL = "https://www.cityofwalhalla.com/government/mayor/"
COUNCIL_URL = "https://www.cityofwalhalla.com/government/walhalla-city-council-meet/"


class WalhallaCityAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("url", MAYOR_URL)
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        # Also fetch the council page
        council_resp = requests.get(
            COUNCIL_URL, headers={"User-Agent": USER_AGENT}, timeout=30
        )
        council_resp.raise_for_status()
        self._council_html = council_resp.text
        return resp.text

    def parse(self, html: str) -> list[dict]:
        members = []

        # Parse mayor page
        mayor = self._parse_mayor(html)
        if mayor:
            members.append(mayor)

        # Parse council page
        council = self._parse_council(self._council_html)
        members.extend(council)

        return members

    def _parse_mayor(self, html: str) -> dict | None:
        """Parse the mayor page for name, email, phone."""
        soup = BeautifulSoup(html, "html.parser")

        for block in soup.find_all("div", class_="mk-text-block"):
            text = block.get_text(separator="\n", strip=True)
            if "Mayor" not in text:
                continue

            lines = [l.strip() for l in text.split("\n") if l.strip()]

            # Find name (line after "City of Walhalla Mayor" or just the name line)
            name = ""
            for i, line in enumerate(lines):
                if "Mayor" in line and "City" in line:
                    # Next line should be the name
                    if i + 1 < len(lines):
                        name = lines[i + 1]
                    break

            if not name:
                continue

            # Get email
            email = ""
            mailto = block.find("a", href=re.compile(r"mailto:", re.IGNORECASE))
            if mailto:
                email = mailto["href"].replace("mailto:", "").strip()

            # Get phone
            phone = ""
            phone_match = re.search(
                r"Phone:\s*(\d{3}[-.]?\d{3}[-.]?\d{4})", text
            )
            if phone_match:
                phone = phone_match.group(1)

            return {
                "name": name,
                "title": "Mayor",
                "email": email,
                "phone": phone,
            }

        return None

    def _parse_council(self, html: str) -> list[dict]:
        """Parse the council members page."""
        soup = BeautifulSoup(html, "html.parser")
        members = []

        for block in soup.find_all("div", class_="mk-text-block"):
            text = block.get_text(separator="\n", strip=True)

            # Look for blocks with title + name pattern
            mailto = block.find("a", href=re.compile(r"mailto:", re.IGNORECASE))
            if not mailto:
                continue

            email = mailto["href"].replace("mailto:", "").strip()
            lines = [l.strip() for l in text.split("\n") if l.strip()]

            if not lines:
                continue

            # First line is "Title Name" (e.g., "Mayor Pro-Tem Josh Holliday")
            first_line = lines[0]

            name, title = self._parse_title_name(first_line)
            if not name or not title:
                continue

            # Skip if this is the mayor (handled separately)
            if title == "Mayor":
                continue

            members.append({
                "name": name,
                "title": title,
                "email": email,
                "phone": "",
            })

        return members

    @staticmethod
    def _parse_title_name(text: str) -> tuple[str, str]:
        """Parse 'Mayor Pro-Tem Josh Holliday' into (name, title)."""
        for prefix, title in [
            ("Mayor Pro-Tem", "Mayor Pro Tem"),
            ("Mayor Pro Tem", "Mayor Pro Tem"),
            ("Councilwoman", "Council Member"),
            ("Councilman", "Council Member"),
            ("Council Member", "Council Member"),
        ]:
            if text.lower().startswith(prefix.lower()):
                name = text[len(prefix):].strip()
                return name, title

        return "", ""
