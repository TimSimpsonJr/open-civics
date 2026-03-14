"""Adapter for McCormick County Council members.

Scrapes the Revize-powered McCormick County site. The county council page
uses an FAQ accordion layout where each council member is a collapsible
section. The section heading contains the district and role, and the body
contains a key-value table with Name, Address, Phone/Cell, Term, and Email.

Only county council members are scraped (districts 1-5). State
representatives, the administrator, and clerk to council are excluded.
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"
PAGE_URL = "https://www.mccormickcountysc.org/government/county_council.php"


class McCormickCountyAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("url", PAGE_URL)
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []

        # The page content has council member data in the main content area.
        # Parse the text content looking for District # blocks.
        # Find the content area containing council data
        content = soup.find("div", class_="col-xl-9") or soup.find("main") or soup.body
        if not content:
            return members

        text = content.get_text(separator="\n", strip=True)
        lines = [l.strip() for l in text.split("\n") if l.strip()]

        i = 0
        while i < len(lines):
            line = lines[i]

            # Match "District #N"
            district_match = re.match(r"District\s+#(\d+)$", line)
            if not district_match:
                i += 1
                continue

            district_num = district_match.group(1)

            # Next line should be role (Chairman, Vice Chairman, Council Member)
            role_line = lines[i + 1] if i + 1 < len(lines) else ""

            # Determine title
            if "chairman" in role_line.lower() and "vice" not in role_line.lower():
                title = f"Chairman, District {district_num}"
            elif "vice chairman" in role_line.lower():
                title = f"Vice Chairman, District {district_num}"
            elif "council member" in role_line.lower():
                title = f"Council Member, District {district_num}"
            else:
                i += 1
                continue

            # Parse the key-value block that follows
            name = ""
            phone = ""
            email = ""

            j = i + 2
            while j < len(lines) and j < i + 20:
                key_line = lines[j]

                if key_line == "Name:" and j + 1 < len(lines):
                    name = lines[j + 1]
                    j += 2
                    continue

                if key_line in ("Phone:", "Cell:") and j + 1 < len(lines):
                    candidate = lines[j + 1]
                    # Only use if it looks like a phone number
                    if re.search(r"\d{3}", candidate):
                        phone = candidate
                    j += 2
                    continue

                if key_line == "Home:" and j + 1 < len(lines):
                    # Use home phone if no other phone set
                    candidate = lines[j + 1]
                    if not phone and re.search(r"\d{3}", candidate):
                        phone = candidate
                    j += 2
                    continue

                if key_line == "Email:" and j + 1 < len(lines):
                    # May have personal + official email on consecutive lines
                    # Prefer @mccormickcountysc.org
                    candidate = lines[j + 1]
                    if "@" in candidate:
                        email = candidate
                    if j + 2 < len(lines) and "@" in lines[j + 2]:
                        next_email = lines[j + 2]
                        if "mccormickcountysc" in next_email:
                            email = next_email
                    j += 2
                    continue

                if key_line in ("Address:", "Term:"):
                    # Skip address and term lines
                    j += 2
                    continue

                # Hit next district or non-matching content
                if re.match(r"District\s+#", key_line):
                    break
                if re.match(r"Representative\s+District", key_line):
                    break
                if re.match(r"Senator\s+District", key_line):
                    break
                if key_line in ("Administrator", "Clerk to Council"):
                    break

                j += 1

            if name:
                members.append({
                    "name": name,
                    "title": title,
                    "email": email,
                    "phone": phone,
                })

            i = j

        # Sort by district number
        members.sort(key=self._sort_key)
        return members

    @staticmethod
    def _sort_key(member: dict) -> tuple:
        title = member["title"]
        match = re.search(r"District\s+(\d+)", title)
        district = int(match.group(1)) if match else 99
        if "Chairman" in title and "Vice" not in title:
            return (0, district)
        if "Vice Chairman" in title:
            return (0, district)
        return (1, district)
