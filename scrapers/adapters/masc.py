"""Shared adapter for municipal councils via MASC directory.

The Municipal Association of South Carolina (masc.sc) maintains a
directory of elected officials for all SC municipalities. Each
municipality page has a table of officials with Title and Name columns
inside a Drupal view (view-display-id-municipal_officials).

This adapter is used as a fallback for cities/towns whose own websites
block automated access (WAF/403). It provides names and titles but
typically no individual email or phone data.

The MASC URL is constructed from the municipality slug in the adapter
config or derived from the jurisdiction ID.
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"
MASC_BASE = "https://www.masc.sc/municipality"


class MascAdapter(BaseAdapter):
    """Scraper for municipal officials via MASC directory."""

    def fetch(self) -> str:
        # Use MASC URL from config, or construct from jurisdiction ID
        slug = self.config.get("mascSlug", "")
        if not slug:
            # Derive from jurisdiction ID: "place:rock-hill" -> "rock-hill"
            slug = self.id.split(":", 1)[-1] if ":" in self.id else self.id

        url = f"{MASC_BASE}/{slug}"
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []

        # Find the officials view
        view = soup.find(
            "div", class_=re.compile(r"view-display-id-municipal_officials")
        )
        if not view:
            raise ValueError(
                f"No municipal_officials view found for {self.id}"
            )

        table = view.find("table")
        if not table:
            raise ValueError(
                f"No officials table found for {self.id}"
            )

        for tr in table.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) < 2:
                continue

            raw_title = cells[0].get_text(strip=True)
            name = cells[1].get_text(strip=True)

            if not name:
                continue

            # Normalize title
            title = self._normalize_title(raw_title)

            members.append({
                "name": name,
                "title": title,
                "email": "",
                "phone": "",
            })

        members.sort(key=self._sort_key)
        return members

    @staticmethod
    def _normalize_title(raw: str) -> str:
        lower = raw.lower().strip()
        if lower == "mayor":
            return "Mayor"
        if "mayor pro" in lower:
            return "Mayor Pro Tem"
        if "councilmember" in lower or "council member" in lower:
            return "Council Member"
        return raw or "Council Member"

    def get_contact(self) -> dict | None:
        """Fetch the primary site URL and scrape a phone number from it.

        MASC pages don't have local phone numbers, so we try the
        jurisdiction's own website (self.url from registry) instead.
        Returns None if the primary site is unreachable.
        """
        from .base import normalize_phone
        if not self.url:
            return None
        try:
            resp = requests.get(
                self.url,
                headers={"User-Agent": USER_AGENT},
                timeout=30,
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            text = soup.get_text()
            match = re.search(r"\(?\d{3}\)?[\s.\-]*\d{3}[\s.\-]*\d{4}", text)
            phone = normalize_phone(match.group(0)) if match else ""
            if not phone:
                return None
            return {
                "phone": phone,
                "email": "",
                "note": "City/Town Hall - no individual council member contact info published",
            }
        except Exception:
            return None

    @staticmethod
    def _sort_key(member: dict) -> tuple:
        title = member.get("title", "")
        if title == "Mayor":
            return (0, member.get("name", ""))
        if "Mayor Pro" in title:
            return (0, member.get("name", ""))
        return (1, member.get("name", ""))
