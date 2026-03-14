"""Adapter for Town of St. Matthews council members.

Scrapes a Drupal site where elected officials are displayed as
<figure class="caption caption-img"> elements within a rich-text
body field. Each figure has:
  - <img alt="Name"> (cleanest name source)
  - <figcaption>Name</figcaption> (may have trailing whitespace/nbsp)

The page sections are divided by <h2> headings: "Mayor" and
"Town Council". We only scrape those two sections, skipping
"Administrative Staff", "Police Department", etc.

Note: This site has NO individual email or phone data per member.
The only contact info is the Town Hall number in the footer.
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"


class StMatthewsAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("url", self.url)
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []

        # Find all figures with their section context
        # Figures may be inside div.field--name-body or directly in the page
        for figure in soup.find_all("figure", class_=re.compile(r"caption")):
            # Determine section from nearest preceding h2
            section = ""
            prev_h2 = figure.find_previous("h2")
            if prev_h2:
                section = prev_h2.get_text(strip=True).lower()

            # Only process Mayor and Town Council sections
            if section not in ("mayor", "town council"):
                continue

            # Get name from img alt (cleanest) or figcaption
            img = figure.find("img")
            caption = figure.find("figcaption")

            raw_name = ""
            if img and img.get("alt"):
                raw_name = img["alt"].strip()
            elif caption:
                raw_name = caption.get_text(strip=True)

            if not raw_name:
                continue

            # Clean non-breaking spaces and whitespace
            raw_name = raw_name.replace("\xa0", " ").strip()

            # Check for title suffix like "- Mayor"
            name = raw_name
            title = "Council Member"

            if " - " in raw_name:
                parts = raw_name.split(" - ", 1)
                name = parts[0].strip()
                role = parts[1].strip()
                if role.lower() == "mayor":
                    title = "Mayor"
                elif role:
                    title = role

            if section == "mayor" and title == "Council Member":
                title = "Mayor"

            members.append({
                "name": name,
                "title": title,
                "email": "",
                "phone": "",
            })

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
        title = member.get("title", "")
        if title == "Mayor":
            return (0, member.get("name", ""))
        return (1, member.get("name", ""))
