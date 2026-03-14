"""Adapter for Goose Creek City Council members.

Scrapes the Drupal-powered Goose Creek site. The main council page lists
members in h4 tags with links to individual staff pages:
  <h4><a href="/staff/slug">Title Name</a></h4>

Each staff page contains:
  - Title (Mayor, Mayor Pro Tem, City Councilmember)
  - Phone number
  - Email (Cloudflare-obfuscated via /cdn-cgi/l/email-protection#HEX)

The adapter scrapes the main page for the member list, then fetches each
staff page for email and phone.
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter, deobfuscate_cf_email

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"
PAGE_URL = "https://www.goosecreeksc.gov/government/mayor-and-city-council"


class GooseCreekAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("url", PAGE_URL)
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []
        seen = set()

        for h4 in soup.find_all("h4"):
            a = h4.find("a")
            if not a:
                continue
            href = a.get("href", "")
            if "/staff/" not in href:
                continue

            raw_text = h4.get_text(strip=True)

            # Skip duplicates
            if href in seen:
                continue
            seen.add(href)

            # Parse title and name from text like "Mayor Gregory Habib"
            # or "Mayor Pro Tem Jerry Tekac" or "Councilmember Name"
            title, name = self._parse_title_name(raw_text)
            if not name:
                continue

            # Build full URL
            if href.startswith("/"):
                full_url = "https://www.goosecreeksc.gov" + href
            else:
                full_url = href

            email, phone = self._fetch_staff_page(full_url)

            members.append({
                "name": name,
                "title": title,
                "email": email,
                "phone": phone,
            })

        members.sort(key=self._sort_key)
        return members

    @staticmethod
    def _parse_title_name(text: str) -> tuple[str, str]:
        """Parse 'Mayor Pro Tem Jerry Tekac' into (title, name)."""
        prefixes = [
            ("Mayor Pro Tem ", "Mayor Pro Tem"),
            ("Mayor ", "Mayor"),
            ("Councilmember ", "Council Member"),
            ("Council Member ", "Council Member"),
        ]
        for prefix, title in prefixes:
            if text.startswith(prefix):
                return (title, text[len(prefix):].strip())
        return ("Council Member", text)

    def _fetch_staff_page(self, url: str) -> tuple[str, str]:
        """Fetch a staff page and extract email and phone."""
        try:
            resp = requests.get(
                url, headers={"User-Agent": USER_AGENT}, timeout=30
            )
            resp.raise_for_status()
        except requests.RequestException:
            return ("", "")

        soup = BeautifulSoup(resp.text, "html.parser")

        # Email: Cloudflare-protected link with "Email" text (not "Email Clerk")
        email = ""
        for a in soup.find_all("a", href=lambda h: h and "email-protection" in h):
            link_text = a.get_text(strip=True)
            if "Email" in link_text and "Clerk" not in link_text:
                encoded = a["href"].split("#")[-1] if "#" in a["href"] else ""
                if encoded:
                    email = deobfuscate_cf_email(encoded)
                break

        # Phone: text starting with "Phone:"
        phone = ""
        text = soup.get_text(separator="\n", strip=True)
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("Phone:"):
                phone = line.replace("Phone:", "").strip()
                # Remove extension info for cleaner format
                phone = re.split(r"\s*ext\.?\s*", phone, flags=re.IGNORECASE)[0].strip()
                break

        return (email, phone)

    @staticmethod
    def _sort_key(member: dict) -> tuple:
        title = member["title"]
        if title == "Mayor":
            return (0,)
        if title == "Mayor Pro Tem":
            return (1,)
        return (2, member["name"])
