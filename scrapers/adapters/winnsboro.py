"""Adapter for Town of Winnsboro council members.

Scrapes a WordPress site that uses a custom "ps-box employees-list-layout"
pattern. Each staff/council member is in a div.ps-box with:
  - h3 containing the name, and a <span> inside with their title
  - mailto link for email
  - tel link for phone

The page lists both staff and council members. We filter to only include
council members (Mayor, Mayor Pro-Tem, Town Council) by checking the title
in the h3 span.
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"

# Titles that indicate a council member (not staff)
COUNCIL_TITLES = re.compile(
    r"(Mayor|Town\s+Council|Council\s*(?:man|woman|member)?)",
    re.I,
)


class WinnsboroAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("url", self.url)
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []

        boxes = soup.find_all("div", class_="ps-box")
        for box in boxes:
            h3 = box.find("h3")
            if not h3:
                continue

            # Title is in a <span> inside h3
            span = h3.find("span")
            title = span.get_text(strip=True) if span else ""

            # Name is the h3 text minus the span text
            full_text = h3.get_text(strip=True)
            if title:
                name = full_text.replace(title, "", 1).strip()
            else:
                name = full_text

            if not name:
                continue

            # Only include council members, not staff
            if not COUNCIL_TITLES.search(title):
                continue

            # Normalize title
            title = self._normalize_title(title)

            # Email: first mailto link
            mailto = box.find("a", href=re.compile(r"^mailto:", re.I))
            email = mailto["href"][7:].strip() if mailto else ""

            # Phone: first tel link
            tel = box.find("a", href=re.compile(r"^tel:", re.I))
            phone = tel.get_text(strip=True) if tel else ""

            members.append({
                "name": name,
                "title": title,
                "email": email,
                "phone": phone,
            })

        return members

    @staticmethod
    def _normalize_title(raw_title: str) -> str:
        """Normalize titles like 'Mayor Pro-Tem, District #1'."""
        title = raw_title.strip()

        # "Town Council, District #3" -> "Council Member, District 3"
        # "Town Council #3" -> "Council Member, District 3"
        m = re.match(r"Town\s+Council,?\s*(?:District\s*)?#?(\d+)", title, re.I)
        if m:
            return f"Council Member, District {m.group(1)}"

        # "Mayor Pro-Tem, District #1" -> "Mayor Pro Tem, District 1"
        m = re.match(r"(Mayor\s+Pro[- ]?Tem),?\s*(?:District\s*)?#?(\d+)", title, re.I)
        if m:
            return f"Mayor Pro Tem, District {m.group(2)}"

        if re.match(r"^Mayor$", title, re.I):
            return "Mayor"

        return title
