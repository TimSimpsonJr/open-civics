"""Adapter for City of Marion council members.

Scrapes the WordPress-powered Marion site. The council listing page uses
the lsvr_person-list-widget with structured HTML:
  - h4.lsvr_person-list-widget__item-title: member name (with link to
    individual profile page)
  - h5.lsvr_person-list-widget__item-subtitle: title
    (e.g., "Councilman | Electoral District 1")

Individual profile pages have a shared city clerk email and the main
city hall phone number, so contact data is limited. The main listing page
provides names and titles reliably.
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"
PAGE_URL = "https://marionsc.gov/city-council-marion-sc/"


class MarionCityAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("url", PAGE_URL)
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []

        for li in soup.find_all("li", class_=re.compile(
            r"lsvr_person-list-widget__item"
        )):
            # Name
            name_tag = li.find(
                "h4", class_="lsvr_person-list-widget__item-title"
            )
            if not name_tag:
                continue

            name_link = name_tag.find("a")
            name = (name_link or name_tag).get_text(strip=True)

            # Clean name: remove prefix titles like "Mr.", "Mrs.", "Mayor"
            name = re.sub(r"^(?:Mr\.|Mrs\.|Ms\.|Dr\.|Mayor|Councilman|Councilwoman)\s+", "", name).strip()

            if not name:
                continue

            # Title
            subtitle = li.find(
                "h5", class_="lsvr_person-list-widget__item-subtitle"
            )
            raw_title = subtitle.get_text(strip=True) if subtitle else ""
            title = self._normalize_title(raw_title)

            members.append({
                "name": name,
                "title": title,
                "email": "",
                "phone": "",
            })

        # Sort: Mayor first, then by electoral district
        members.sort(key=self._sort_key)
        return members

    @staticmethod
    def _normalize_title(raw: str) -> str:
        """Normalize titles like 'Councilman | Electoral District 1'."""
        if not raw:
            return "Council Member"

        lower = raw.lower().strip()

        if lower == "mayor":
            return "Mayor"

        # "Mayor Pro Tempore| Councilman | Electoral District 3"
        if "mayor pro tem" in lower:
            district_match = re.search(r"District\s+(\d+)", raw, re.IGNORECASE)
            if district_match:
                return f"Mayor Pro Tem, District {district_match.group(1)}"
            return "Mayor Pro Tem"

        district_match = re.search(r"District\s+(\d+)", raw, re.IGNORECASE)
        if district_match:
            return f"Council Member, District {district_match.group(1)}"

        return raw

    @staticmethod
    def _sort_key(member: dict) -> tuple:
        title = member["title"]
        if title == "Mayor":
            return (0, 0)
        if "Mayor Pro Tem" in title:
            return (0, 1)
        match = re.search(r"District\s+(\d+)", title)
        if match:
            return (1, int(match.group(1)))
        return (2, 0)
