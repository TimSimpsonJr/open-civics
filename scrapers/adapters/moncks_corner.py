"""Adapter for Town of Moncks Corner elected officials.

Scrapes the WordPress Elementor-powered Moncks Corner site. Each elected
official is in a div.elected-container block with:
  - h4.elected-title: member name
  - h3: title (Mayor, Mayor Pro-Tem, Councilman, Councilwoman)
  - span.__cf_email__[data-cfemail]: Cloudflare-obfuscated email
  - span.phone-value: phone number (may be empty)

All emails are Cloudflare-protected and decoded via deobfuscate_cf_email.
"""

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter, deobfuscate_cf_email

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"
PAGE_URL = "https://www.monckscornersc.gov/government/elected-officials"


class MoncksCornerAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("url", PAGE_URL)
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []

        for container in soup.find_all("div", class_="elected-container"):
            name_tag = container.find("h4", class_="elected-title")
            title_tag = container.find("h3")
            cf_span = container.find(attrs={"data-cfemail": True})
            phone_span = container.find("span", class_="phone-value")

            if not name_tag:
                continue

            name = name_tag.get_text(strip=True)
            title = title_tag.get_text(strip=True) if title_tag else "Council Member"

            # Normalize title
            title = self._normalize_title(title)

            # Decode Cloudflare email
            email = ""
            if cf_span:
                email = deobfuscate_cf_email(cf_span["data-cfemail"])

            phone = ""
            if phone_span:
                phone = phone_span.get_text(strip=True)

            if name:
                members.append({
                    "name": name,
                    "title": title,
                    "email": email,
                    "phone": phone,
                })

        return members

    @staticmethod
    def _normalize_title(title: str) -> str:
        """Normalize title variations."""
        lower = title.lower().strip()
        if lower == "mayor":
            return "Mayor"
        if lower in ("mayor pro-tem", "mayor pro tem"):
            return "Mayor Pro Tem"
        if lower in ("councilman", "councilwoman", "councilmember"):
            return "Council Member"
        return title
