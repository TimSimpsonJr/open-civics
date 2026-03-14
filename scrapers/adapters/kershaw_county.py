"""Adapter for Kershaw County Council members.

Scrapes the Kershaw County government site staff directory table at
https://www.kershaw.sc.gov/our-county which has columns for Name, Title,
Department, Phone, and Email.

Filters to council members only (titles containing "council", "chairman",
or "vice chair").
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter, normalize_phone

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"

COUNCIL_TITLE_PATTERNS = re.compile(
    r"council|chairman|vice\s*chair", re.IGNORECASE
)


class KershawCountyAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("url", "https://www.kershaw.sc.gov/our-county")
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []

        # Find directory table(s)
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            if not rows:
                continue

            # Detect header row to find column indices
            header = rows[0]
            headers = [th.get_text(strip=True).lower() for th in header.find_all(["th", "td"])]

            # Map column names to indices
            col_map = {}
            for i, h in enumerate(headers):
                if "name" in h:
                    col_map["name"] = i
                elif "title" in h:
                    col_map["title"] = i
                elif "phone" in h:
                    col_map["phone"] = i
                elif "email" in h or "mail" in h:
                    col_map["email"] = i

            if "name" not in col_map:
                continue

            for row in rows[1:]:
                cells = row.find_all(["td", "th"])
                if len(cells) <= col_map.get("name", 0):
                    continue

                name = cells[col_map["name"]].get_text(strip=True) if "name" in col_map else ""
                title = cells[col_map["title"]].get_text(strip=True) if "title" in col_map and col_map["title"] < len(cells) else ""

                if not name or not COUNCIL_TITLE_PATTERNS.search(title):
                    continue

                # Extract phone
                phone = ""
                if "phone" in col_map and col_map["phone"] < len(cells):
                    phone_cell = cells[col_map["phone"]]
                    tel_link = phone_cell.find("a", href=lambda h: h and h.startswith("tel:"))
                    if tel_link:
                        phone = tel_link.get_text(strip=True)
                    else:
                        phone = phone_cell.get_text(strip=True)

                # Extract email
                email = ""
                if "email" in col_map and col_map["email"] < len(cells):
                    email_cell = cells[col_map["email"]]
                    mailto = email_cell.find("a", href=lambda h: h and h.startswith("mailto:"))
                    if mailto:
                        email = mailto["href"].replace("mailto:", "").strip()
                    else:
                        # Look for @-containing text
                        cell_text = email_cell.get_text(strip=True)
                        if "@" in cell_text:
                            email = cell_text.strip()

                # Normalize title
                title = self._normalize_title(title)

                members.append({
                    "name": name,
                    "title": title,
                    "email": email,
                    "phone": normalize_phone(phone) if phone else "",
                })

        members.sort(key=self._sort_key)
        return members

    @staticmethod
    def _normalize_title(raw_title: str) -> str:
        """Normalize council titles to consistent format."""
        lower = raw_title.lower().strip()
        if "chairman" in lower or "chairperson" in lower:
            if "vice" in lower:
                return "Vice Chair"
            return "Chair"
        return "Council Member"

    @staticmethod
    def _sort_key(member: dict) -> tuple:
        title = member["title"]
        if title == "Chair":
            return (0, member["name"])
        if title == "Vice Chair":
            return (1, member["name"])
        return (2, member["name"])
