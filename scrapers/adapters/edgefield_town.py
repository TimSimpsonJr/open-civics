"""Adapter for Town of Edgefield council members.

Scrapes the custom-built Edgefield community resources page. Council member
data is in plain text under the "Mayor & Town Council" heading with structure:
  Mayor
  W. Ken Durham
  Town Council Members
  Kelvin Thomas
  Scott Mims
  ...
  Robert M. Rodgers, Mayor Pro Tem

No email addresses or phone numbers are published on the page.
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"
PAGE_URL = "https://www.exploreedgefield.com/community-resources.html"


class EdgefieldTownAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("url", PAGE_URL)
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator="\n", strip=True)
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        members = []

        # Find the "Mayor & Town Council" section
        start_idx = None
        for i, line in enumerate(lines):
            if "Mayor & Town Council" in line:
                start_idx = i + 1
                break

        if start_idx is None:
            return members

        # Parse mayor
        mayor_name = None
        council_start = None
        for i in range(start_idx, min(start_idx + 5, len(lines))):
            line = lines[i]
            if line.lower() == "mayor":
                # Next line is the mayor's name
                if i + 1 < len(lines):
                    mayor_name = lines[i + 1]
            elif "Town Council Members" in line:
                council_start = i + 1
                break

        if mayor_name:
            members.append({
                "name": mayor_name,
                "title": "Mayor",
                "email": "",
                "phone": "",
            })

        # Parse council members - names appear one per line until we hit
        # a non-name line (like "2025 Council Meeting Schedule")
        if council_start is not None:
            for i in range(council_start, min(council_start + 20, len(lines))):
                line = lines[i]

                # Stop at meeting schedule or other sections
                if re.match(r"\d{4}\s+Council", line):
                    break
                if "Meeting Schedule" in line:
                    break
                if "Regular meetings" in line:
                    break

                # Skip empty/short lines
                if len(line) < 3:
                    continue

                # Check for Mayor Pro Tem designation
                title = "Council Member"
                name = line
                if "Mayor Pro Tem" in line:
                    title = "Mayor Pro Tem"
                    # Remove the "Mayor Pro Tem" suffix
                    name = re.sub(
                        r",?\s*Mayor\s+Pro\s+Tem\s*$", "", name, flags=re.IGNORECASE
                    ).strip()

                members.append({
                    "name": name,
                    "title": title,
                    "email": "",
                    "phone": "",
                })

        return members

    def get_contact(self) -> dict | None:
        from .base import normalize_phone
        if not hasattr(self, "_html"):
            return None
        soup = BeautifulSoup(self._html, "html.parser")
        text = soup.get_text()
        # Look for phone near "Town Hall" or "Town of Edgefield" context
        phone = ""
        # Try tel: links first
        tel_link = soup.find("a", href=re.compile(r"^tel:"))
        if tel_link:
            raw = re.sub(r"^tel:\+?1?", "", tel_link["href"])
            phone = normalize_phone(raw)
        if not phone:
            # Search near "Town Hall" text
            town_hall_match = re.search(
                r"Town\s+(?:Hall|of\s+Edgefield)[^0-9]*?"
                r"(\(?\d{3}\)?[\s.\-]*\d{3}[\s.\-]*\d{4})",
                text,
            )
            if town_hall_match:
                phone = normalize_phone(town_hall_match.group(1))
            else:
                # Fall back to first phone on page
                match = re.search(r"\(?\d{3}\)?[\s.\-]*\d{3}[\s.\-]*\d{4}", text)
                phone = normalize_phone(match.group(0)) if match else ""
        # Look for email address on the page
        email = ""
        email_match = re.search(r"townofedgefield@[\w.-]+\.\w+", text, re.IGNORECASE)
        if not email_match:
            email_match = re.search(r"[\w.+-]+@[\w.-]+\.\w+", text)
        if email_match:
            email = email_match.group(0)
        return {
            "phone": phone,
            "email": email,
            "note": "Town Hall - no individual council member contact info published",
        }
