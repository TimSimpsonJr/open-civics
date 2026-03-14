"""Adapter for Abbeville City Council members.

Scrapes the CivicPlus-powered Abbeville City site. Council members are
listed in separate fr-view divs with structure:
  "Name, District N"
  "Term: YYYY-YYYY"
  (optional) "Email:" followed by email address
  (optional) "Cell Number:" followed by phone

Only 2 of 8 members currently have email/phone listed.

The mayor is on a separate page (/188/Mayor) and is fetched additionally.
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter, normalize_phone

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"
PAGE_URL = "https://www.abbevillecitysc.com/189/City-Council"
MAYOR_URL = "https://www.abbevillecitysc.com/188/Mayor"


class AbbevilleAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("url", PAGE_URL)
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []

        for fr in soup.find_all("div", class_="fr-view"):
            text = fr.get_text(separator="\n", strip=True)
            lines = [line.strip() for line in text.split("\n") if line.strip()]

            if not lines:
                continue

            # First line should match "Name, District N"
            match = re.match(
                r"^(.+?),\s*District\s+(\d+)$", lines[0]
            )
            if not match:
                continue

            name = match.group(1).strip()
            district = match.group(2)

            # Extract optional email and phone from remaining lines
            email = ""
            phone = ""
            for line in lines[1:]:
                if "@" in line and not line.startswith("Email"):
                    email = line.strip()
                elif line.lower().startswith("cell number:"):
                    phone = line.split(":", 1)[1].strip()

            # Also check for mailto links
            for a in fr.find_all("a", href=lambda h: h and "mailto:" in h):
                email = a["href"].replace("mailto:", "").strip()

            members.append({
                "name": name,
                "title": f"Council Member, District {district}",
                "email": email,
                "phone": normalize_phone(phone) if phone else "",
            })

        # Fetch mayor from separate page
        mayor = self._fetch_mayor()
        if mayor:
            members.insert(0, mayor)

        members.sort(key=self._sort_key)
        return members

    @staticmethod
    def _fetch_mayor() -> dict | None:
        """Fetch the mayor's page and extract name, email, phone."""
        try:
            resp = requests.get(
                MAYOR_URL, headers={"User-Agent": USER_AGENT}, timeout=30
            )
            resp.raise_for_status()
        except requests.RequestException:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        # Find the mayor's name from headings or bold text
        name = ""
        for tag in soup.find_all(["h1", "h2", "h3", "h4", "strong", "b"]):
            text = tag.get_text(strip=True)
            if not text:
                continue
            match = re.match(r"^Mayor\s+(.+)", text, re.I)
            if match:
                name = match.group(1).strip()
                break

        if not name:
            # Try the fr-view content for "Mayor FirstName LastName"
            fr = soup.find("div", class_="fr-view")
            if fr:
                text = fr.get_text(separator=" ", strip=True)
                match = re.search(r"Mayor\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)", text)
                if match:
                    name = match.group(1).strip()

        email = ""
        for a in soup.find_all("a", href=lambda h: h and "mailto:" in h):
            email = a["href"].replace("mailto:", "").strip()
            break
        if not email:
            # Search page text for email addresses
            text = soup.get_text()
            email_match = re.search(
                r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text
            )
            if email_match:
                email = email_match.group(0)

        phone = ""
        for a in soup.find_all("a", href=lambda h: h and h.startswith("tel:")):
            phone = a.get_text(strip=True)
            break
        if not phone:
            # Search text for phone pattern
            text = soup.get_text()
            phone_match = re.search(
                r"\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]\d{4}", text
            )
            if phone_match:
                phone = phone_match.group(0)

        if not name:
            return None

        return {
            "name": name,
            "title": "Mayor",
            "email": email,
            "phone": normalize_phone(phone) if phone else "",
        }

    @staticmethod
    def _sort_key(member: dict) -> tuple:
        if member["title"] == "Mayor":
            return (0, 0)
        match = re.search(r"District\s+(\d+)", member["title"])
        return (1, int(match.group(1))) if match else (2, 0)
