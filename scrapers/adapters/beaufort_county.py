"""Adapter for Beaufort County Council members.

Scrapes the Beaufort County government site. The council members page
lists members as links in a sidebar with format:
  "District N - Full Name"

Each member has an individual page at:
  /council/council-members/{slug}.html
containing their email as a mailto: link.

The adapter first fetches a known member page to discover all member
links from the sidebar, then fetches each member page for email.
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"
INDEX_URL = "https://www.beaufortcountysc.gov/council/council-members/howard-alice.html"


class BeaufortCountyAdapter(BaseAdapter):

    def fetch(self) -> str:
        """Fetch a member page (sidebar has the full member list).

        The registry URL points to the council index page, which only has
        a few member links. We instead fetch a known member page that
        contains the full sidebar listing all council members.
        """
        resp = requests.get(INDEX_URL, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []

        # Find all member links: "District N - Name"
        # Links are relative (e.g., "dawson-gerald.html") within the sidebar
        base_url = "https://www.beaufortcountysc.gov/council/council-members/"
        for a in soup.find_all("a"):
            href = a.get("href", "")
            text = a.get_text(strip=True)

            # Match "District N - Full Name" pattern
            match = re.match(
                r"District\s+(\d+)\s*[-\u2013]\s*(.+)", text
            )
            if not match:
                continue
            if not href.endswith(".html"):
                continue

            district = match.group(1)
            name = match.group(2).strip()

            # Build full URL from relative href
            if href.startswith("http"):
                full_url = href
            elif href.startswith("/"):
                full_url = "https://www.beaufortcountysc.gov" + href
            else:
                full_url = base_url + href

            # Avoid duplicates
            if not any(m["name"] == name for m in members):
                members.append({
                    "name": name,
                    "title": f"Council Member, District {district}",
                    "email": "",
                    "phone": "",
                    "_url": full_url,
                })

        # Fetch each member page for email
        for member in members:
            email = self._fetch_email(member.pop("_url"))
            member["email"] = email

        # Check for chair/vice-chair from the index page text
        text = soup.get_text(separator="\n", strip=True)
        self._detect_roles(text, members)

        members.sort(key=self._sort_key)
        return members

    def _fetch_email(self, url: str) -> str:
        """Fetch a member page and extract email from mailto link."""
        try:
            resp = requests.get(
                url, headers={"User-Agent": USER_AGENT}, timeout=30
            )
            resp.raise_for_status()
        except requests.RequestException:
            return ""

        soup = BeautifulSoup(resp.text, "html.parser")
        mailto = soup.find("a", href=lambda h: h and h.startswith("mailto:"))
        if mailto:
            return mailto["href"].replace("mailto:", "").strip()
        return ""

    @staticmethod
    def _detect_roles(text: str, members: list[dict]):
        """Update titles for Chair and Vice Chair if mentioned on page."""
        lines = text.split("\n")
        for i, line in enumerate(lines):
            line = line.strip()
            if line == "Chair:" and i + 1 < len(lines):
                chair_name = lines[i + 1].strip()
                for m in members:
                    if chair_name in m["name"] or m["name"] in chair_name:
                        dist = re.search(r"District\s+\d+", m["title"])
                        if dist:
                            m["title"] = f"Chair, {dist.group()}"
            elif line == "Vice Chair:" and i + 1 < len(lines):
                vc_name = lines[i + 1].strip()
                for m in members:
                    if vc_name in m["name"] or m["name"] in vc_name:
                        dist = re.search(r"District\s+\d+", m["title"])
                        if dist:
                            m["title"] = f"Vice Chair, {dist.group()}"

    @staticmethod
    def _sort_key(member: dict) -> int:
        match = re.search(r"District\s+(\d+)", member["title"])
        return int(match.group(1)) if match else 0
