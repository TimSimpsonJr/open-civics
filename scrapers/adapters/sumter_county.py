"""Adapter for Sumter County Council members.

Scrapes the Revize-powered Sumter County site. Council member names and
districts are listed in the sidebar navigation of the FAQ page as links like:
  "District 6 - James T. McCain Jr. - Chairman"
  "District 1 - Carlton B. Washington"

Each member has an individual detail page with phone numbers and email.
The adapter scrapes the sidebar for names/districts, then visits each
member's detail page for contact information.
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"
FAQ_URL = "https://www.sumtercountysc.gov/our_council/council_information/council_frequently_asked_questions.php"
BASE_URL = "https://www.sumtercountysc.gov/"


class SumterCountyAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("url", FAQ_URL)
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []

        # Find council member links in the sidebar menu
        # Links follow pattern: "District N - Name" or "District N - Name - Chairman"
        for link in soup.find_all("a", class_="menuA"):
            text = link.get_text(strip=True)
            match = re.match(
                r"District\s+(\d+)\s*-\s*(.+?)(?:\s*-\s*(Chairman|Vice\s+Chairman))?\s*$",
                text, re.IGNORECASE,
            )
            if not match:
                continue

            district = match.group(1)
            name = match.group(2).strip()
            role = match.group(3)

            if role and "vice" in role.lower():
                title = f"Vice Chairman, District {district}"
            elif role and "chairman" in role.lower():
                title = f"Chairman, District {district}"
            else:
                title = f"Council Member, District {district}"

            href = link.get("href", "")

            members.append({
                "name": name,
                "title": title,
                "email": "",
                "phone": "",
                "_href": href,
            })

        # Fetch individual member pages for contact info
        for member in members:
            href = member.pop("_href", "")
            if not href:
                continue
            try:
                detail_url = BASE_URL + href.lstrip("/")
                resp = requests.get(
                    detail_url,
                    headers={"User-Agent": USER_AGENT},
                    timeout=15,
                )
                if resp.status_code == 200:
                    self._parse_detail_page(resp.text, member)
            except Exception:
                pass  # Keep member with empty contact info

        members.sort(key=self._sort_key)
        return members

    @staticmethod
    def _parse_detail_page(html: str, member: dict) -> None:
        """Extract phone and email from a member's detail page."""
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator="\n", strip=True)
        lines = [l.strip() for l in text.split("\n") if l.strip()]

        for i, line in enumerate(lines):
            # Find email
            if re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", line):
                # Prefer county email
                if "sumtercountysc" in line:
                    member["email"] = line
                elif not member["email"]:
                    member["email"] = line

            # Find phone numbers
            if line.startswith(("Home Phone:", "Mobile Phone:", "Phone:")):
                # Phone on same line after colon
                phone_text = line.split(":", 1)[1].strip()
                if re.search(r"\d{3}", phone_text) and not member["phone"]:
                    member["phone"] = phone_text

    @staticmethod
    def _sort_key(member: dict) -> tuple:
        title = member["title"]
        match = re.search(r"District\s+(\d+)", title)
        district = int(match.group(1)) if match else 99
        if "Chairman" in title and "Vice" not in title:
            return (0, district)
        if "Vice Chairman" in title:
            return (0, district)
        return (1, district)
