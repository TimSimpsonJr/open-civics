"""Adapter for City of Chester council members.

Scrapes the CivicPlus-powered Chester City site. Council member data is in
widgetStaffDirectory widgets on the City Council page with structure:
  <div class="widget widgetStaffDirectory">
    <ol><li class="widgetItem h-card">
      <h4 class="widgetTitle field p-name">Name</h4>
      <div class="field p-job-title">Ward N</div>
      <div class="field u-email"><a href="mailto:...">...</a></div>
      <div class="field p-tel">Phone: <a href="tel:...">...</a></div>
    </li></ol>
  </div>

Names, wards, emails, and phone numbers are available.
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"
PAGE_URL = "https://www.chestersc.org/160/City-Council"


class ChesterCityAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("url", PAGE_URL)
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []

        for widget in soup.find_all("div", class_="widgetStaffDirectory"):
            li = widget.find("li", class_="widgetItem")
            if not li:
                continue

            # Name
            name_el = li.find("h4", class_="widgetTitle")
            name = name_el.get_text(strip=True) if name_el else ""
            if not name:
                continue

            # Title / Ward
            title_el = li.find("div", class_="p-job-title")
            raw_title = title_el.get_text(strip=True) if title_el else ""

            # Normalize title
            title = self._normalize_title(raw_title)

            # Skip non-person entries (e.g. the "Contact Us" widget for
            # "City Council" at the bottom of the page)
            if title == "Council Member" and raw_title == "":
                continue

            # Email from mailto link
            email = ""
            mailto = li.find("a", href=re.compile(r"^mailto:", re.IGNORECASE))
            if mailto:
                email = mailto["href"].replace("mailto:", "").strip()

            # Phone from tel link
            phone = ""
            tel = li.find("a", href=re.compile(r"^tel:", re.IGNORECASE))
            if tel:
                phone = tel.get_text(strip=True)

            members.append({
                "name": name,
                "title": title,
                "email": email,
                "phone": phone,
            })

        # Sort: Mayor first, then by ward
        members.sort(key=self._sort_key)
        return members

    @staticmethod
    def _normalize_title(raw: str) -> str:
        """Convert ward labels like 'Ward I' to standardized titles."""
        if raw.lower() == "mayor":
            return "Mayor"
        # Match Ward + Roman or Arabic numeral
        ward_match = re.match(
            r"Ward\s+([IVX]+|\d+)", raw, re.IGNORECASE
        )
        if ward_match:
            ward = ward_match.group(1)
            # Convert Roman numerals to Arabic
            roman_map = {"I": 1, "II": 2, "III": 3, "IV": 4}
            ward_num = roman_map.get(ward.upper(), ward)
            return f"Council Member, Ward {ward_num}"
        return raw or "Council Member"

    @staticmethod
    def _sort_key(member: dict) -> tuple:
        title = member["title"]
        if title == "Mayor":
            return (0, 0)
        match = re.search(r"Ward\s+(\d+)", title)
        if match:
            return (1, int(match.group(1)))
        return (2, 0)
