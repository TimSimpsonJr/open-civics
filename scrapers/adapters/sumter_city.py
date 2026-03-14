"""Adapter for City of Sumter council members.

Scrapes the Drupal-powered Sumter City site. The city council page has
council member data in div.staff-item elements with structure:
  <div class="staff-item">
    <div class="staff-item__title">Name</div>
    <div class="staff-item__job-title">Title - Ward N</div>
    <div class="staff-item__email">
      <a href="/cdn-cgi/l/email-protection#HEX">
        <span data-cfemail="HEX">[email protected]</span>
      </a>
    </div>
  </div>

Emails are protected by Cloudflare email obfuscation.
No phone numbers are published on this page.
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter, deobfuscate_cf_email

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"
PAGE_URL = "https://www.sumtersc.gov/city-council"


class SumterCityAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("url", PAGE_URL)
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []

        for item in soup.find_all("div", class_="staff-item"):
            # Name is in staff-item__title
            name_el = item.find(class_="staff-item__title")
            name = name_el.get_text(strip=True) if name_el else ""
            if not name:
                continue

            # Title/role is in staff-item__job-title
            title_el = item.find(class_="staff-item__job-title")
            raw_title = title_el.get_text(strip=True) if title_el else ""
            title = self._normalize_title(raw_title)

            # Email from CF-protected span
            email = ""
            cf_span = item.find(attrs={"data-cfemail": True})
            if cf_span:
                email = deobfuscate_cf_email(cf_span["data-cfemail"])

            members.append({
                "name": name,
                "title": title,
                "email": email,
                "phone": "",
            })

        # Sort: Mayor first, then Mayor Pro Tem, then by ward
        members.sort(key=self._sort_key)
        return members

    @staticmethod
    def _normalize_title(raw: str) -> str:
        """Normalize titles like 'Councilman - Ward 2' to 'Council Member, Ward 2'."""
        if raw.lower() == "mayor":
            return "Mayor"

        # "Councilman and Mayor Pro Tem - Ward 2"
        if "mayor pro tem" in raw.lower():
            ward_match = re.search(r"Ward\s+(\d+)", raw)
            if ward_match:
                return f"Mayor Pro Tem, Ward {ward_match.group(1)}"
            return "Mayor Pro Tem"

        # "Councilman - Ward N" or "Councilwoman - Ward N"
        ward_match = re.search(r"Ward\s+(\d+)", raw)
        if ward_match:
            return f"Council Member, Ward {ward_match.group(1)}"

        return raw or "Council Member"

    @staticmethod
    def _sort_key(member: dict) -> tuple:
        title = member["title"]
        if title == "Mayor":
            return (0, 0)
        if "Mayor Pro Tem" in title:
            match = re.search(r"Ward\s+(\d+)", title)
            return (0, 1, int(match.group(1)) if match else 0)
        match = re.search(r"Ward\s+(\d+)", title)
        if match:
            return (1, int(match.group(1)), 0)
        return (2, 0, 0)
