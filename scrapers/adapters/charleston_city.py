"""Adapter for City of Charleston council members.

Scrapes the CivicPlus-powered Charleston site by:
  1. Fetching the Members & Districts listing page to discover member names
     and individual profile page URLs from links matching /NNN/District-*
  2. Fetching each profile page to extract email (mailto link) and phone
     (tel link) from the fr-view content area
  3. Extracting district numbers from the URL path

The main listing page has no contact info — all emails and phones are on
the individual member profile pages.
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"
LISTING_URL = "https://www.charleston-sc.gov/180/Members-Districts"
BASE_URL = "https://www.charleston-sc.gov"


class CharlestonCityAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("url", LISTING_URL)
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []

        # Find all links to individual council member profile pages
        # Match "District-*-Councilmember" but not historical pages like
        # "African-American-Councilmembers" (plural)
        profile_links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True)
            if (
                re.search(r"District-\w+-Councilmember\b", href)
                and text
                and len(text) > 2
            ):
                if href.startswith("/"):
                    href = BASE_URL + href
                profile_links.append((href, text))

        # Fetch each profile page for email and phone
        for url, name in profile_links:
            district = self._extract_district(url)
            email, phone = self._fetch_profile(url)

            members.append({
                "name": name,
                "title": f"Council Member, District {district}" if district else "Council Member",
                "email": email,
                "phone": phone,
            })

        # Sort by district number
        members.sort(key=lambda m: self._district_sort_key(m["title"]))
        return members

    @staticmethod
    def _extract_district(url: str) -> str:
        """Extract district number from URL like /471/District-One-Councilmember."""
        word_to_num = {
            "one": "1", "two": "2", "three": "3", "four": "4",
            "five": "5", "six": "6", "seven": "7", "eight": "8",
            "nine": "9", "ten": "10", "eleven": "11", "twelve": "12",
        }
        # Try numeric: District-2-Councilmember
        match = re.search(r"District-(\d+)", url, re.IGNORECASE)
        if match:
            return match.group(1)
        # Try word: District-One-Councilmember
        match = re.search(r"District-(\w+)-Councilmember", url, re.IGNORECASE)
        if match:
            word = match.group(1).lower()
            return word_to_num.get(word, word)
        return ""

    @staticmethod
    def _fetch_profile(url: str) -> tuple[str, str]:
        """Fetch a member profile page and extract email and phone."""
        try:
            resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
            resp.raise_for_status()
        except requests.RequestException:
            return "", ""

        soup = BeautifulSoup(resp.text, "html.parser")

        email = ""
        for a in soup.find_all("a", href=re.compile(r"mailto:", re.IGNORECASE)):
            email = a["href"].replace("mailto:", "").strip()
            break

        phone = ""
        for a in soup.find_all("a", href=re.compile(r"^tel:", re.IGNORECASE)):
            phone = a.get_text(strip=True)
            break

        return email, phone

    @staticmethod
    def _district_sort_key(title: str) -> tuple:
        match = re.search(r"District\s+(\d+)", title)
        if match:
            return (1, int(match.group(1)))
        return (0, 0)
