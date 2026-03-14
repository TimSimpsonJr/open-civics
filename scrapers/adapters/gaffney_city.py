"""Adapter for City of Gaffney council members.

Scrapes the CivicPlus-powered Gaffney site. Unlike most CivicPlus sites
that use a directory table, Gaffney's council page has mailto links
directly in the fr-view content area with format:
  Mayor Name (Title)  ->  mailto link text

The mailto link text contains both the title and name, e.g.:
  "Mayor Lyman D. Dawkins III"
  "Councilwoman Cameo Wilson (District 1)"
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"
PAGE_URL = "https://www.cityofgaffney-sc.gov/184/City-Council"


class GaffneyCityAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("url", PAGE_URL)
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []

        # Find all mailto links in the content
        for a in soup.find_all("a", href=re.compile(r"mailto:", re.IGNORECASE)):
            email = a["href"].replace("mailto:", "").strip()
            link_text = a.get_text(strip=True)

            if not link_text or not email:
                continue

            name, title = self._parse_link_text(link_text)
            if not name:
                continue

            members.append({
                "name": name,
                "title": title,
                "email": email,
                "phone": "",
            })

        # Sort: Mayor first, then by district
        members.sort(key=self._sort_key)
        return members

    @staticmethod
    def _parse_link_text(text: str) -> tuple[str, str]:
        """Parse link text like 'Mayor Lyman D. Dawkins III' or
        'Councilwoman Cameo Wilson (District 1)'.

        Returns (name, title).
        """
        # Remove parenthetical district info to extract it separately
        district = ""
        district_match = re.search(r"\(District\s+(\d+)\)", text, re.IGNORECASE)
        if district_match:
            district = district_match.group(1)
            text = text[: district_match.start()].strip()

        # Parse title prefix
        title_prefix = ""
        for prefix in [
            "Mayor Pro Tem",
            "Mayor",
            "Councilwoman",
            "Councilman",
            "Council Member",
        ]:
            if text.lower().startswith(prefix.lower()):
                title_prefix = prefix
                name = text[len(prefix) :].strip()
                break
        else:
            name = text
            title_prefix = "Council Member"

        # Build title
        if title_prefix.lower() == "mayor":
            title = "Mayor"
        elif title_prefix.lower() == "mayor pro tem":
            title = "Mayor Pro Tem"
        elif district:
            title = f"Council Member, District {district}"
        else:
            title = "Council Member"

        # Clean up name: remove leading/trailing punctuation
        name = re.sub(r"^[.\s]+|[.\s]+$", "", name).strip()
        # Handle "C. Allen Montgomery, Jr." style names
        name = re.sub(r"\s+", " ", name)

        return name, title

    @staticmethod
    def _sort_key(member: dict) -> tuple:
        title = member["title"]
        if title == "Mayor":
            return (0, 0)
        if title == "Mayor Pro Tem":
            return (0, 1)
        match = re.search(r"District\s+(\d+)", title)
        if match:
            return (1, int(match.group(1)))
        return (2, 0)
