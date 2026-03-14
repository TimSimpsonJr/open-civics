"""Adapter for City of Florence council members.

Scrapes the Drupal-powered Florence site in two stages:
  1. The main /city-council page lists members in views-row divs with
     links to individual /person/<slug> pages and shows name + title
  2. Each /person/<slug> sub-page has mailto links for email and tel
     links for phone numbers

The main listing uses a views display with name, title, and term info
separated by pipes when text is extracted.
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"
LISTING_URL = "https://www.cityofflorencesc.gov/city-council"
BASE_URL = "https://www.cityofflorencesc.gov"


class FlorenceCityAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("url", LISTING_URL)
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []

        # Find member rows with links to /person/ pages
        for row in soup.find_all("div", class_=re.compile(r"views-row")):
            link = row.find("a", href=re.compile(r"/person/"))
            if not link:
                continue

            href = link["href"]
            if href.startswith("/"):
                href = BASE_URL + href

            # Extract text: "Name | Title | Term Expires: ..."
            text = row.get_text(separator="|", strip=True)
            parts = [p.strip() for p in text.split("|") if p.strip()]
            if len(parts) < 2:
                continue

            name = parts[0]
            raw_title = parts[1]

            # Fetch sub-page for contact info
            email, phone = self._fetch_contact(href)

            title = self._normalize_title(raw_title)

            members.append({
                "name": name,
                "title": title,
                "email": email,
                "phone": phone,
            })

        # Sort: Mayor first, then At-Large, then by district
        members.sort(key=self._sort_key)
        return members

    @staticmethod
    def _fetch_contact(url: str) -> tuple[str, str]:
        """Fetch a member's profile page and extract email and phone."""
        try:
            resp = requests.get(
                url, headers={"User-Agent": USER_AGENT}, timeout=30
            )
            resp.raise_for_status()
        except requests.RequestException:
            return "", ""

        soup = BeautifulSoup(resp.text, "html.parser")

        email = ""
        for a in soup.find_all("a", href=re.compile(r"mailto:", re.IGNORECASE)):
            candidate = a["href"].replace("mailto:", "").strip()
            if "@" in candidate and "cityofflorence" in candidate.lower():
                email = candidate
                break

        phone = ""
        for a in soup.find_all("a", href=re.compile(r"^tel:", re.IGNORECASE)):
            phone_text = a.get_text(strip=True)
            if phone_text and re.search(r"\d{3}", phone_text):
                phone = phone_text
                break

        return email, phone

    @staticmethod
    def _normalize_title(raw: str) -> str:
        """Normalize Florence-style titles."""
        if not raw:
            return "Council Member"

        lower = raw.lower().strip()
        if lower == "mayor":
            return "Mayor"
        if "mayor pro tempore" in lower or "mayor pro tem" in lower:
            if "at-large" in lower or "at large" in lower:
                return "Mayor Pro Tem, At Large"
            return "Mayor Pro Tem"
        if "at-large" in lower or "at large" in lower:
            return "Council Member, At Large"

        district_match = re.search(r"District\s+(\d+)", raw, re.IGNORECASE)
        if district_match:
            return f"Council Member, District {district_match.group(1)}"

        return raw

    @staticmethod
    def _sort_key(member: dict) -> tuple:
        title = member["title"]
        if title == "Mayor":
            return (0, 0)
        if "Mayor Pro Tem" in title:
            return (0, 1)
        if "At Large" in title:
            return (1, 0)
        match = re.search(r"District\s+(\d+)", title)
        if match:
            return (2, int(match.group(1)))
        return (3, 0)
