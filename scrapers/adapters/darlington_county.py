"""Adapter for Darlington County Council members.

Scrapes a Revize-powered site with freeform HTML content. Council members
appear in a flat text layout with:
  - Bold district headings: "District #N - Location"
  - Names as plain text: "Mr./Ms./Mrs. Name" or "Name" after district heading
  - Roles in bold/italic: "Chairman", "Vice Chairman", "Chaplain"
  - Email as mailto: links
  - Phone numbers as plain text (NNN-NNN-NNNN format)

The page URL is:
  https://www.darcosc.com/government/county_council/index.php
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"

# Phone pattern: 843-758-0472 or (843) 758-0472
PHONE_RE = re.compile(r"\(?(\d{3})\)?[\s.\-]*(\d{3})[\s.\-](\d{4})")


class DarlingtonCountyAdapter(BaseAdapter):
    """Scraper for Darlington County Council members."""

    def fetch(self) -> str:
        url = self.config.get("url", self.url)
        resp = requests.get(
            url, headers={"User-Agent": USER_AGENT},
            timeout=30, allow_redirects=True,
        )
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")

        # The content is a flat sequence of styled spans, strongs, and links.
        # Strategy: scan for "District #N" headings, then extract name, role,
        # email, and phone from the following content until the next district.

        # Get the main content area
        content = (
            soup.find("div", class_="fr-view")
            or soup.find("div", id="divContent")
            or soup.find("article")
            or soup.find("main")
            or soup.body
        )
        if not content:
            return []

        text = content.get_text(separator="\n")
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        # Find all mailto links and their emails (in order)
        all_mailtos = []
        for a in content.find_all("a", href=lambda h: h and "mailto:" in h.lower()):
            href = a["href"]
            email = re.sub(r"^[Mm]ailto:\s*", "", href).strip()
            if email:
                all_mailtos.append(email)

        # Parse district blocks from the text
        members = []
        # Regex for district heading
        district_re = re.compile(r"District\s*#?\s*(\d+)")

        # Track which mailto we're at (they appear in order matching districts)
        mailto_idx = 0
        # Exclude non-council emails
        excluded_emails = {"jbishop@darcosc.net", "webadmin@darcosc.com",
                           "subscribers@darcosc.com"}

        i = 0
        while i < len(lines):
            line = lines[i]
            dist_match = district_re.search(line)
            if not dist_match:
                i += 1
                continue

            district_num = dist_match.group(1)

            # Collect lines until next district heading or end
            block_lines = []
            i += 1
            while i < len(lines):
                if district_re.search(lines[i]):
                    break
                block_lines.append(lines[i])
                i += 1

            block_text = "\n".join(block_lines)

            # Extract name: look for "Mr./Ms./Mrs. Name" on a single line
            name = ""
            for bline in block_lines:
                name_match = re.match(
                    r"(?:Mr\.|Ms\.|Mrs\.)\s+([A-Z][a-zA-Z ,.'-]+)",
                    bline.strip()
                )
                if name_match:
                    name = name_match.group(1).strip()
                    # Clean trailing noise
                    name = re.split(r"\d{2,}", name)[0].strip()
                    name = name.rstrip(",. ")
                    break

            if not name:
                continue

            # Extract role
            role = "Council Member"
            if re.search(r"\bChairman\b", block_text, re.I) and \
               not re.search(r"\bVice\s+Chairman\b", block_text, re.I):
                role = "Chairman"
            elif re.search(r"\bVice\s+Chairman\b", block_text, re.I):
                role = "Vice Chairman"
            elif re.search(r"\bChaplain\b", block_text, re.I):
                role = "Chaplain"

            title = f"{role}, District {district_num}"

            # Extract email from the ordered mailto list
            email = ""
            while mailto_idx < len(all_mailtos):
                candidate = all_mailtos[mailto_idx]
                mailto_idx += 1
                if candidate.lower() not in excluded_emails:
                    email = candidate
                    break

            # Extract phone
            phone = ""
            phone_match = PHONE_RE.search(block_text)
            if phone_match:
                phone = phone_match.group(0)

            members.append({
                "name": name,
                "title": title,
                "email": email,
                "phone": phone,
            })

        return members
