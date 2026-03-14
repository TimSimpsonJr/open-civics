"""Adapter for Allendale County Council members.

Scrapes a Revize CMS freeform page. Council members are in a table
with one member per <td> cell. Each cell contains:
  - An image
  - "Chair" or "Vice Chair" text (optional)
  - <strong>Council Member</strong>
  - "District #N" text
  - Member name as plain text
  - Phone as <a href="tel:..."> link
  - Email as <a href="mailto:..."> link

The HTML structure is inconsistent (mix of <div> and <p> wrappers)
so we parse each <td> by extracting structured elements (mailto, tel)
and using text content for name/district/role.
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter, normalize_phone

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"


class AllendaleCountyAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("url", self.url)
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []

        article = soup.find("article", class_="entry")
        if not article:
            article = soup

        # Find all <td> cells that contain a mailto link (= a member cell)
        for td in article.find_all("td"):
            mailto = td.find("a", href=re.compile(r"^mailto:", re.I))
            if not mailto:
                continue

            email = mailto["href"][7:].strip()

            # Phone
            phone = ""
            tel = td.find("a", href=re.compile(r"^tel:"))
            if tel:
                phone = normalize_phone(tel.get_text(strip=True))

            # Get full text for name/district/role parsing
            text = td.get_text(separator="\n", strip=True)
            lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

            # District
            district = ""
            for line in lines:
                dist_match = re.search(r"District\s*#?\s*(\d+)", line, re.I)
                if dist_match:
                    district = dist_match.group(1)
                    break

            # Role (Chair, Vice Chair)
            role = ""
            for line in lines:
                lower = line.lower().strip()
                if lower in ("chair", "vice chair", "chairman", "vice chairman"):
                    role = line.strip()
                    break

            # Name: find the line that is a person's name
            # Skip known non-name lines: district, role, email, phone, address, "Council Member"
            name = ""
            skip_patterns = [
                r"District\s*#?\d+",
                r"Council\s+Member",
                r"Chair",
                r"Vice\s+Chair",
                r"@",
                r"^\(\d{3}\)",
                r"^\d{3}[\-.]",
                r"SC\s+\d{5}",
                r"P\.?O\.?\s+Box",
                r"^\d+\s+\w+\s+(St|Ave|Rd|Dr|Blvd|Lane|Ln|Street|Drive|Highway)",
            ]
            for line in lines:
                if any(re.search(p, line, re.I) for p in skip_patterns):
                    continue
                # A name line should have at least 2 words and start with a letter
                words = line.split()
                if len(words) >= 2 and words[0][0].isalpha():
                    # Skip lines that are just city/state
                    if re.match(r"^[A-Za-z]+,?\s+SC", line):
                        continue
                    name = line
                    break

            if not name:
                continue

            # Clean name of decorative asterisks
            name = re.sub(r"[*]+\s*", "", name).strip()

            # Build title
            if role.lower() in ("chair", "chairman"):
                title = f"Chair, District {district}" if district else "Chair"
            elif role.lower() in ("vice chair", "vice chairman"):
                title = f"Vice Chair, District {district}" if district else "Vice Chair"
            elif district:
                title = f"Council Member, District {district}"
            else:
                title = "Council Member"

            members.append({
                "name": name,
                "title": title,
                "email": email,
                "phone": phone,
            })

        members.sort(key=self._sort_key)
        return members

    @staticmethod
    def _sort_key(member: dict) -> tuple:
        title = member.get("title", "")
        if "Chair" in title and "Vice" not in title:
            return (0, 0)
        if "Vice" in title:
            return (0, 1)
        dist_match = re.search(r"District\s+(\d+)", title)
        if dist_match:
            return (1, int(dist_match.group(1)))
        return (2, 0)
