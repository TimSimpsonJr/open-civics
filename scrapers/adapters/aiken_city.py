"""Adapter for City of Aiken council members.

Scrapes the Aiken City Council page, which uses a Divi theme layout
with et_pb_team_member modules. Each member card has:
  - h2.et_pb_module_header: member name
  - p.et_pb_member_position: title (Mayor, District N)
  - a[href^="tel:"]: phone number

Individual emails are not available (only contact forms).

Note: This site uses Cloudflare bot protection. If requests are
blocked (403), the scraper will raise an error. The GitHub Actions
workflow runs from IPs that Cloudflare typically allows.
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter, normalize_phone

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"


class AikenCityAdapter(BaseAdapter):
    """Scraper for City of Aiken council members."""

    def fetch(self) -> str:
        url = self.config.get("url", self.url)
        resp = requests.get(
            url, headers={"User-Agent": USER_AGENT}, timeout=30
        )
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []
        seen_names = set()

        # Each member is inside a div.et_pb_team_member_description
        for desc_div in soup.find_all("div", class_="et_pb_team_member_description"):
            # Name from heading
            heading = desc_div.find(["h2", "h3", "h4"], class_="et_pb_module_header")
            if not heading:
                continue
            name = heading.get_text(strip=True)
            if not name or name in seen_names:
                continue
            seen_names.add(name)

            # Title/position
            position_el = desc_div.find("p", class_="et_pb_member_position")
            raw_position = position_el.get_text(strip=True) if position_el else ""

            title = self._build_title(raw_position)

            # Phone from tel: link
            tel_link = desc_div.find("a", href=lambda h: h and h.startswith("tel:"))
            phone = ""
            if tel_link:
                phone = normalize_phone(tel_link.get_text(strip=True))

            members.append({
                "name": name,
                "title": title,
                "email": "",
                "phone": phone,
            })

        members.sort(key=self._sort_key)
        return members

    @staticmethod
    def _build_title(raw: str) -> str:
        lower = raw.lower().strip()

        if lower == "mayor":
            return "Mayor"
        if "mayor pro" in lower:
            return "Mayor Pro Tem"

        # "District N" -> "Council Member District N"
        dist_match = re.search(r"district\s+(\d+)", lower)
        if dist_match:
            return f"Council Member District {dist_match.group(1)}"

        if "council" in lower:
            return "Council Member"

        return raw or "Council Member"

    @staticmethod
    def _sort_key(member: dict) -> tuple:
        title = member.get("title", "")
        if title == "Mayor":
            return (0, 0)
        if "Mayor Pro" in title:
            return (0, 1)
        dist_match = re.search(r"District\s+(\d+)", title)
        if dist_match:
            return (1, int(dist_match.group(1)))
        return (2, 0)
