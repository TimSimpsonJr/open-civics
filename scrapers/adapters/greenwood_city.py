"""Adapter for City of Greenwood (SC) council members.

Scrapes a Revize-powered site where each council member has:
  - h2#contact-header with title (Mayor, Ward One, etc.)
  - strong#contact-name with member name
  - mailto: link for email in a sibling <ul>
  - tel: link for phone in a sibling <ul>

The contact blocks are inside <main> but outside <article>, so the
standard Revize content area detection misses them. This adapter
parses the h2/strong/ul structure directly.
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"


class GreenwoodCityAdapter(BaseAdapter):
    """Scraper for City of Greenwood council members."""

    def fetch(self) -> str:
        url = self.config.get("url", self.url)
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []

        # Each council member has an h2#contact-header followed by
        # strong#contact-name and a <ul> with mailto/tel links
        for h2 in soup.find_all("h2", id="contact-header"):
            raw_title = h2.get_text(strip=True)

            # Find the next strong#contact-name
            strong = h2.find_next("strong", id="contact-name")
            if not strong:
                continue
            name = strong.get_text(strip=True)
            if not name:
                continue

            # Find email and phone in the nearby <ul>
            ul = h2.find_next("ul")
            email = ""
            phone = ""
            if ul:
                email_link = ul.find(
                    "a", href=lambda h: h and h.startswith("mailto:")
                )
                if email_link:
                    email = email_link["href"][7:].strip()

                phone_link = ul.find(
                    "a", href=lambda h: h and h.startswith("tel:")
                )
                if phone_link:
                    # Extract phone from href to avoid sr-only label text
                    raw_phone = phone_link["href"][4:].strip()
                    # Clean up encoded characters and formatting
                    raw_phone = raw_phone.replace("%28", "(").replace("%29", ")")
                    phone = raw_phone

            title = self._normalize_title(raw_title)

            members.append({
                "name": name,
                "title": title,
                "email": email,
                "phone": phone,
            })

        return members

    @staticmethod
    def _normalize_title(raw_title: str) -> str:
        """Normalize ward titles like 'Mayor Pro Tem Ward Two'."""
        raw = raw_title.strip()

        # "Mayor Pro Tem Ward Two" -> "Mayor Pro Tem, Ward Two"
        if "Mayor Pro Tem" in raw:
            ward_match = re.search(r"Ward\s+\w+", raw, re.I)
            if ward_match:
                return f"Mayor Pro Tem, {ward_match.group(0)}"
            return "Mayor Pro Tem"

        if raw.lower() == "mayor":
            return "Mayor"

        # "Ward One" -> "Council Member, Ward One"
        ward_match = re.match(r"^(Ward\s+\w+)$", raw, re.I)
        if ward_match:
            return f"Council Member, {ward_match.group(1)}"

        return raw
