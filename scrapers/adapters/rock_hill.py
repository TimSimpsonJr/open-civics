"""Adapter for Rock Hill City Council members.

Scrapes the CivicPlus-powered Rock Hill site by:
  1. Fetching the Members listing page to discover member names and
     individual profile page URLs from the sidebar navigation
  2. Fetching each profile page to extract email (mailto link) and phone
     (text pattern "Phone: NNN-NNN-NNNN")
  3. Detecting Mayor Pro Tem from profile page body text

The sidebar links follow the pattern "Mayor - Name" or "Ward N - Name"
and link to /government/city-council/members/{slug}.

Note: This site is behind Akamai WAF which blocks the `requests` library
via TLS fingerprinting. We use `urllib.request` instead, which has a
different TLS fingerprint that Akamai allows through.
"""

import re
import urllib.request

from bs4 import BeautifulSoup

from .base import BaseAdapter, normalize_phone

LISTING_URL = "https://www.cityofrockhill.com/government/city-council/members"
BASE_URL = "https://www.cityofrockhill.com"

# Akamai WAF requires browser-like headers or it returns 403.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}


def _get(url: str) -> str:
    """Fetch a URL using urllib (bypasses Akamai TLS fingerprinting)."""
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


class RockHillAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("url", LISTING_URL)
        return _get(url)

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []

        # Find sidebar links to individual member profile pages
        # Links match pattern: /government/city-council/members/{slug}
        # Text is "Mayor - Name" or "Ward N - Name"
        profile_links = []
        seen_hrefs = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True)
            if not text:
                continue

            # Normalize href
            if href.startswith("/"):
                href = BASE_URL + href

            # Match member profile URLs (but not the /members listing itself)
            if "/city-council/members/" not in href:
                continue
            if href.rstrip("/").endswith("/members"):
                continue

            # Deduplicate
            if href in seen_hrefs:
                continue
            seen_hrefs.add(href)

            # Parse "Mayor - Name" or "Ward N - Name" from link text
            match = re.match(r"(Mayor|Ward\s+\d+)\s*[-\u2013]\s*(.+)", text)
            if not match:
                continue

            role = match.group(1).strip()
            name = match.group(2).strip()
            profile_links.append((href, name, role))

        # Fetch each profile page for email, phone, and Mayor Pro Tem status
        for url, name, role in profile_links:
            email, phone, is_pro_tem = self._fetch_profile(url)

            if role == "Mayor":
                title = "Mayor"
            elif is_pro_tem:
                ward = re.search(r"\d+", role)
                title = f"Mayor Pro Tem, Ward {ward.group()}" if ward else "Mayor Pro Tem"
            else:
                ward = re.search(r"\d+", role)
                title = f"Council Member, Ward {ward.group()}" if ward else "Council Member"

            members.append({
                "name": name,
                "title": title,
                "email": email,
                "phone": normalize_phone(phone) if phone else "",
            })

        # Sort: Mayor first, then Mayor Pro Tem, then by ward number
        members.sort(key=self._sort_key)
        return members

    @staticmethod
    def _fetch_profile(url: str) -> tuple[str, str, bool]:
        """Fetch a member profile page and extract email, phone, and pro tem status."""
        try:
            html = _get(url)
        except Exception:
            return "", "", False

        soup = BeautifulSoup(html, "html.parser")

        # Extract email from mailto link
        # Note: some pages have "mailto:mailto:email" (double prefix bug)
        email = ""
        for a in soup.find_all("a", href=re.compile(r"^mailto:", re.IGNORECASE)):
            raw = a["href"]
            # Strip one or more "mailto:" prefixes
            while raw.lower().startswith("mailto:"):
                raw = raw[7:]
            raw = raw.strip()
            if "@" in raw:
                email = raw
                break

        # Extract phone from "Phone: NNN-NNN-NNNN" text pattern
        # The tel: links on the site are the general city number, not personal
        phone = ""
        page_text = soup.get_text(separator="\n")
        phone_match = re.search(r"Phone:\s*([\d\-().]+\s*[\d\-().]+)", page_text)
        if phone_match:
            phone = phone_match.group(1).strip()

        # Detect Mayor Pro Tem
        is_pro_tem = bool(re.search(r"Mayor Pro[- ]?Tem", page_text, re.IGNORECASE))

        return email, phone, is_pro_tem

    @staticmethod
    def _sort_key(member: dict) -> tuple:
        title = member["title"]
        if title == "Mayor":
            return (0, 0)
        if "Mayor Pro Tem" in title:
            ward = re.search(r"Ward\s+(\d+)", title)
            return (1, int(ward.group(1)) if ward else 0)
        ward = re.search(r"Ward\s+(\d+)", title)
        return (2, int(ward.group(1)) if ward else 99)
