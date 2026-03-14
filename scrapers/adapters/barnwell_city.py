"""Adapter for City of Barnwell council members.

Scrapes the Drupal-powered Barnwell site. The government page has a
simple list of council members in <li> tags with format:
  "District N: Council Member Name"
  "District N: Council Member/Mayor Pro Tem Name"
  "Entire City: Mayor Name"

No email addresses or phone numbers are published. Only names, titles,
and district assignments are available.
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"
PAGE_URL = "https://www.cityofbarnwell.com/government"


class BarnwellCityAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("url", PAGE_URL)
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []

        # Find the main content
        content = (
            soup.find("main")
            or soup.find("article")
            or soup.find("div", class_="node__content")
            or soup.body
        )
        if not content:
            return members

        for li in content.find_all("li"):
            text = li.get_text(strip=True)
            member = self._parse_member_line(text)
            if member:
                members.append(member)

        # Sort: Mayor first, then Mayor Pro Tem, then by district
        members.sort(key=self._sort_key)
        return members

    @staticmethod
    def _parse_member_line(text: str) -> dict | None:
        """Parse a line like 'District 1: Council Member Ricky Dixon'."""

        # "Entire City: Mayor Name"
        mayor_match = re.match(
            r"Entire\s+City:\s*Mayor\s+(.+)", text, re.IGNORECASE
        )
        if mayor_match:
            return {
                "name": mayor_match.group(1).strip(),
                "title": "Mayor",
                "email": "",
                "phone": "",
            }

        # "District N: Council Member/Mayor Pro Tem Name"
        pro_tem_match = re.match(
            r"District\s+(\d+):\s*Council\s+Member/Mayor\s+Pro\s+Tem\s+(.+)",
            text, re.IGNORECASE,
        )
        if pro_tem_match:
            return {
                "name": pro_tem_match.group(2).strip(),
                "title": f"Mayor Pro Tem, District {pro_tem_match.group(1)}",
                "email": "",
                "phone": "",
            }

        # "District N: Council Member Name"
        district_match = re.match(
            r"District\s+(\d+):\s*Council\s+Member\s+(.+)",
            text, re.IGNORECASE,
        )
        if district_match:
            return {
                "name": district_match.group(2).strip(),
                "title": f"Council Member, District {district_match.group(1)}",
                "email": "",
                "phone": "",
            }

        return None

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
