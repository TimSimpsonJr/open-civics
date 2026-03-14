"""Adapter for Town of Kingstree Mayor & Town Council.

Scrapes a WordPress Elementor page where members are displayed as
image cards with:
  - Name in a heading (e.g., <h3> or Elementor heading widget)
  - Title text like "Mayor" or "Town Councilman District 1"
  - "Contact" links that open popup forms (no direct email/phone per member)

The town phone (843-355-7484) is used as a shared contact number.

URL: https://www.kingstree.org/government/mayor-town-council/
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"

TOWN_PHONE = "(843) 355-7484"


class KingstreeAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("url", self.url)
        resp = requests.get(
            url, headers={"User-Agent": USER_AGENT},
            timeout=30, allow_redirects=True
        )
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []

        # Elementor pages structure members as widget groups.
        # Each member has:
        #   - An image widget
        #   - A heading widget with the name
        #   - A text widget with title like "Mayor" or "Town Councilman District N"
        #   - A link widget for "Contact Mayor" etc.

        # Find all Elementor heading widgets that look like names
        headings = soup.find_all(
            class_=re.compile(r"elementor-heading-title")
        )

        i = 0
        while i < len(headings):
            name_el = headings[i]
            name = name_el.get_text(strip=True)

            if not self._looks_like_name(name):
                i += 1
                continue

            # Look for title in the next heading or in nearby text
            title = ""
            if i + 1 < len(headings):
                next_text = headings[i + 1].get_text(strip=True)
                if self._looks_like_title(next_text):
                    title = self._normalize_title(next_text)
                    i += 2
                else:
                    i += 1
            else:
                i += 1

            if not title:
                # Try to find title in sibling elements
                title = self._find_title_near(name_el)

            if not title:
                title = "Council Member"

            members.append({
                "name": name,
                "title": title,
                "email": "",
                "phone": TOWN_PHONE,
            })

        # If the heading approach didn't work well, try a different strategy:
        # look for name + title patterns in the page text
        if len(members) < 3:
            members = self._fallback_parse(soup)

        # Deduplicate by title (Elementor may repeat sections for responsive)
        seen_titles = set()
        unique = []
        for m in members:
            if m["title"] not in seen_titles:
                seen_titles.add(m["title"])
                unique.append(m)

        return unique

    def _fallback_parse(self, soup: BeautifulSoup) -> list[dict]:
        """Fallback parser using full page text patterns."""
        members = []
        text = soup.get_text(separator="\n")
        lines = [l.strip() for l in text.split("\n") if l.strip()]

        i = 0
        while i < len(lines):
            line = lines[i]

            # Look for a name line followed by a title line
            if self._looks_like_name(line):
                title = ""
                # Check next lines for title
                for j in range(i + 1, min(i + 3, len(lines))):
                    if self._looks_like_title(lines[j]):
                        title = self._normalize_title(lines[j])
                        break

                if title:
                    members.append({
                        "name": line,
                        "title": title,
                        "email": "",
                        "phone": TOWN_PHONE,
                    })
            i += 1

        return members

    def _find_title_near(self, element) -> str:
        """Find title text near a name element."""
        # Check siblings and parent's children
        parent = element.parent
        if not parent:
            return ""

        # Look at the grandparent's descendants for title text
        grandparent = parent.parent
        if not grandparent:
            return ""

        for el in grandparent.find_all(
            class_=re.compile(r"elementor-heading-title|elementor-text-editor")
        ):
            text = el.get_text(strip=True)
            if self._looks_like_title(text) and text != element.get_text(strip=True):
                return self._normalize_title(text)

        return ""

    @staticmethod
    def _looks_like_name(text: str) -> bool:
        if not text or len(text) < 4 or len(text) > 40:
            return False
        if " " not in text:
            return False
        if not text[0].isupper():
            return False
        # Reject title-like text
        if re.search(
            r"(Mayor|Council|District|Town|Click|Contact|Agenda|Meeting|Government|Board|"
            r"Code of|Ordinance|Resolution|Notice|Public|Request|Report|Minutes|Home|"
            r"Staff|Department|Finance|Utility|Water|Sewer|Police|Fire|Business|License|"
            r"Building|Permit|Zoning|Planning|Recreation|Library|Cemetery|Community)",
            text, re.I
        ):
            return False
        # Should be mostly letters
        alpha = sum(1 for c in text if c.isalpha() or c == " ")
        if alpha < len(text) * 0.8:
            return False
        return True

    @staticmethod
    def _looks_like_title(text: str) -> bool:
        return bool(re.search(
            r"(Mayor|Council(?:man|woman|member)|District\s+\d+|Pro\s+Tem)",
            text, re.I
        ))

    @staticmethod
    def _normalize_title(raw: str) -> str:
        """Normalize title text like 'Town Councilman District 1' to standard form."""
        raw = raw.strip()

        # Check for Mayor
        if re.match(r"^Mayor$", raw, re.I):
            return "Mayor"

        # Mayor Pro Tem
        if re.search(r"Mayor\s+Pro\s+Tem", raw, re.I):
            dist_match = re.search(r"District\s+(\d+)", raw, re.I)
            if dist_match:
                return f"Mayor Pro Tem, District {dist_match.group(1)}"
            return "Mayor Pro Tem"

        # Council member with district
        dist_match = re.search(r"District\s+(\d+)", raw, re.I)
        if dist_match:
            return f"Council Member, District {dist_match.group(1)}"

        # Generic council
        if re.search(r"Council", raw, re.I):
            return "Council Member"

        return raw
