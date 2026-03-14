"""Adapter for Laurens County Council members.

Scrapes a Revize site that uses the "rz-business-block" directory layout.
Each council member is in a div.rz-business-block with:
  - First line: "County Council District N- Name" (with optional title like Chairman)
  - Second line: "Current Term: YYYY-YYYY"
  - Email as mailto link
  - Phone as tel link (not always present)
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"


class LaurensCountyAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("url", self.url)
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []

        blocks = soup.find_all("div", class_="rz-business-block")
        for block in blocks:
            text = block.get_text(separator="|", strip=True)
            lines = [line.strip() for line in text.split("|") if line.strip()]
            if not lines:
                continue

            # First line format: "County Council District N- Name"
            # or "County Council District N- Title Name"
            first_line = lines[0]
            match = re.match(
                r"County Council District\s+(\d+)\s*[-\u2013\u2014]\s*(.*)",
                first_line,
            )
            if not match:
                continue

            district = match.group(1)
            name_part = match.group(2).strip()

            # Extract title prefix (Chairman, Vice Chairman)
            title = f"Council Member, District {district}"
            title_match = re.match(
                r"(Vice\s+Chairman|Chairman)\s+(.*)", name_part, re.I
            )
            if title_match:
                role = title_match.group(1).strip()
                name = title_match.group(2).strip()
                title = f"{role}, District {district}"
            else:
                name = name_part

            # Clean up name: remove non-breaking spaces
            name = name.replace("\xa0", " ").strip()

            # Email
            mailto = block.find("a", href=re.compile(r"^mailto:", re.I))
            email = mailto["href"][7:].strip() if mailto else ""

            # Phone
            tel = block.find("a", href=re.compile(r"^tel:", re.I))
            phone = tel.get_text(strip=True) if tel else ""

            # Also check for phone in text (some have it as plain text)
            if not phone:
                phone_match = re.search(
                    r"\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]\d{4}", text
                )
                if phone_match:
                    phone = phone_match.group(0)

            members.append({
                "name": name,
                "title": title,
                "email": email,
                "phone": phone,
            })

        return members
