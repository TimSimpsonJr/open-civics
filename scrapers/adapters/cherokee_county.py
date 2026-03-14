"""Adapter for Cherokee County Council members.

Scrapes the WordPress/Elementor-powered Cherokee County site. Council
member data is in centered paragraph blocks with structure:
  <strong>County Council District N</strong><br/>
  Name<br/>
  Phone: <a href="tel:NNNN">NNN-NNN-NNNN</a><br/>
  Email: <a href="/cdn-cgi/l/email-protection#HEX">...</a>

Emails are protected by Cloudflare email obfuscation and must be decoded
using data-cfemail attributes.

District 7 is listed as VACANT when unoccupied.
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter, deobfuscate_cf_email

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"
PAGE_URL = "https://cherokeecountysc.gov/county-council-administration/"


class CherokeeCountyAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("url", PAGE_URL)
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []

        # Find all <strong> tags containing "County Council District N"
        for strong in soup.find_all("strong"):
            text = strong.get_text(strip=True)
            district_match = re.match(
                r"County Council District\s+(\d+)", text, re.IGNORECASE
            )
            if not district_match:
                continue

            district_num = district_match.group(1)

            # The parent <p> tag contains the full member block
            parent_p = strong.find_parent("p")
            if not parent_p:
                continue

            block_text = parent_p.get_text(separator="\n", strip=True)

            # Check for VACANT
            if "VACANT" in block_text.upper():
                continue

            # Extract name: line after the district heading
            lines = [l.strip() for l in block_text.split("\n") if l.strip()]
            name = ""
            for line in lines:
                if "County Council District" in line:
                    continue
                if line.startswith("Phone:") or line.startswith("Email:"):
                    continue
                if line.startswith("Master Clerk"):
                    continue
                if not name:
                    name = line
                    break

            if not name:
                continue

            # Extract title (check for Chairman in name)
            title = f"Council Member, District {district_num}"
            chairman_match = re.search(
                r"\(([^)]*Chairman[^)]*)\)", name, re.IGNORECASE
            )
            if chairman_match:
                role = chairman_match.group(1).strip()
                name = name[: chairman_match.start()].strip()
                title = f"{role}, District {district_num}"

            # Phone from tel: link
            phone = ""
            tel_link = parent_p.find("a", href=re.compile(r"^tel:", re.IGNORECASE))
            if tel_link:
                phone = tel_link.get_text(strip=True)

            # Email from CF-protected link
            email = ""
            cf_span = parent_p.find(attrs={"data-cfemail": True})
            if cf_span:
                email = deobfuscate_cf_email(cf_span["data-cfemail"])

            members.append({
                "name": name,
                "title": title,
                "email": email,
                "phone": phone,
            })

        # Sort by district number
        members.sort(key=lambda m: self._district_sort_key(m["title"]))
        return members

    @staticmethod
    def _district_sort_key(title: str) -> int:
        match = re.search(r"District\s+(\d+)", title)
        return int(match.group(1)) if match else 0
