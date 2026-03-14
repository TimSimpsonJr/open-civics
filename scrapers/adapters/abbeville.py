"""Adapter for Abbeville City Council members.

Scrapes the CivicPlus-powered Abbeville City site. Council members are
listed in separate fr-view divs with structure:
  "Name, District N"
  "Term: YYYY-YYYY"
  (optional) "Email:" followed by email address
  (optional) "Cell Number:" followed by phone

Only 2 of 8 members currently have email/phone listed.
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"
PAGE_URL = "https://www.abbevillecitysc.com/189/City-Council"


class AbbevilleAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("url", PAGE_URL)
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []

        for fr in soup.find_all("div", class_="fr-view"):
            text = fr.get_text(separator="\n", strip=True)
            lines = [line.strip() for line in text.split("\n") if line.strip()]

            if not lines:
                continue

            # First line should match "Name, District N"
            match = re.match(
                r"^(.+?),\s*District\s+(\d+)$", lines[0]
            )
            if not match:
                continue

            name = match.group(1).strip()
            district = match.group(2)

            # Extract optional email and phone from remaining lines
            email = ""
            phone = ""
            for line in lines[1:]:
                if "@" in line and not line.startswith("Email"):
                    email = line.strip()
                elif line.lower().startswith("cell number:"):
                    phone = line.split(":", 1)[1].strip()

            # Also check for mailto links
            for a in fr.find_all("a", href=lambda h: h and "mailto:" in h):
                email = a["href"].replace("mailto:", "").strip()

            members.append({
                "name": name,
                "title": f"Council Member, District {district}",
                "email": email,
                "phone": phone,
            })

        members.sort(key=self._sort_key)
        return members

    @staticmethod
    def _sort_key(member: dict) -> int:
        match = re.search(r"District\s+(\d+)", member["title"])
        return int(match.group(1)) if match else 0
