"""Adapter for York County Council members.

Scrapes the CivicPlus-powered York County site by:
  1. Fetching the main County Council page to discover district sub-page
     links (e.g., /385/District-1, /393/District-2)
  2. Fetching each district page to extract the member name, title, and
     phone from the fr-view content area
  3. Names are in the first line, titles in the second line, and phone
     numbers follow a "Phone:" label

York County does not publish individual email addresses on the district
pages. The site has an "Email Us" form but no direct mailto links.
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"
LISTING_URL = "https://www.yorkcountygov.com/375/County-Council"
BASE_URL = "https://www.yorkcountygov.com"

# District page IDs in order
DISTRICT_PAGES = {
    1: "385",
    2: "393",
    3: "395",
    4: "398",
    5: "401",
    6: "404",
    7: "406",
}


class YorkCountyAdapter(BaseAdapter):

    def fetch(self) -> str:
        """Fetch the main council page (used for discovery/validation)."""
        url = self.config.get("url", LISTING_URL)
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        members = []

        for district_num, page_id in DISTRICT_PAGES.items():
            member = self._fetch_district(district_num, page_id)
            if member:
                members.append(member)

        return members

    def _fetch_district(self, district_num: int, page_id: str) -> dict | None:
        """Fetch a district sub-page and extract member data."""
        url = f"{BASE_URL}/{page_id}/"
        try:
            resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
            resp.raise_for_status()
        except requests.RequestException:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        # Find the first fr-view div with substantial content
        for frview in soup.find_all("div", class_="fr-view"):
            text = frview.get_text(separator="\n", strip=True)
            if text and len(text) > 30:
                lines = [l.strip() for l in text.split("\n") if l.strip()]
                if not lines:
                    continue

                name = lines[0]

                # Determine title
                title = self._build_title(lines, district_num)

                # Phone: look for "Phone: NNN-NNN-NNNN"
                phone = ""
                phone_match = re.search(
                    r"Phone:\s*(\(?\d{3}\)?[-.\s]*\d{3}[-.\s]*\d{4})", text
                )
                if phone_match:
                    phone = phone_match.group(1)

                # Email: check for mailto links (rarely present)
                email = ""
                email_link = frview.find(
                    "a", href=re.compile(r"mailto:", re.IGNORECASE)
                )
                if email_link:
                    email = email_link["href"].replace("mailto:", "").strip()

                return {
                    "name": name,
                    "title": title,
                    "email": email,
                    "phone": phone,
                }

        return None

    @staticmethod
    def _build_title(lines: list[str], district_num: int) -> str:
        """Build a title string from the page content lines."""
        # Check if any line has a leadership role
        for line in lines[:3]:
            lower = line.lower()
            if "chairman" in lower or "chairwoman" in lower:
                if "vice" in lower:
                    return f"Vice Chairman, District {district_num}"
                return f"Chairman, District {district_num}"

        return f"Council Member, District {district_num}"
