"""Adapter for Town of St. George council members.

Scrapes the GoDaddy Builder-powered St. George site. The administration
page has council member data in plain text with structure:
  "Councilwoman Betty Collins -1st District"

No email addresses or phone numbers are published on the page. Names and
district assignments are extracted from text patterns matching
Council(wo)man Name - Nth District.
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"
PAGE_URL = "https://www.saintgeorgesc.org/administration"


class StGeorgeAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("url", PAGE_URL)
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator="\n", strip=True)
        members = []

        # Find Mayor - name is on same line
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            mayor_match = re.match(
                r"^Mayor\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)$", line
            )
            if mayor_match:
                members.append({
                    "name": mayor_match.group(1).strip(),
                    "title": "Mayor",
                    "email": "",
                    "phone": "",
                })
                break

        # Find council members: "Council(wo)man Name - Nth District"
        pattern = re.compile(
            r"Council(?:wo)?man\s+"
            r"([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*(?:\s+[A-Z][a-zA-Z]+)*)"
            r"\s*[-–]\s*(\d+)(?:st|nd|rd|th)\s+District",
            re.IGNORECASE,
        )
        for match in pattern.finditer(text):
            name = match.group(1).strip()
            district = match.group(2)

            # Clean name: remove "(not Pictured)" etc.
            name = re.sub(r"\s*\([^)]*\)", "", name).strip()

            if name:
                members.append({
                    "name": name,
                    "title": f"Council Member, District {district}",
                    "email": "",
                    "phone": "",
                })

        # Sort: Mayor first, then by district
        members.sort(key=self._sort_key)
        return members

    def get_contact(self) -> dict | None:
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
            "note": "Town Hall - no individual council member contact info published",
        }

    @staticmethod
    def _sort_key(member: dict) -> tuple:
        if member["title"] == "Mayor":
            return (0, 0)
        match = re.search(r"District\s+(\d+)", member["title"])
        if match:
            return (1, int(match.group(1)))
        return (2, 0)
