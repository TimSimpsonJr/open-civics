"""Adapter for Lee County Council members.

Scrapes a Revize freeform page where council members are listed as
bold name + bold title lines followed by address and phone text.
No mailto links for council members (only admin staff have emails).

URL: https://www.leecountysc.org/county_council/council_members.php
"""

import re

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

from .base import BaseAdapter, normalize_phone

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"

PHONE_PATTERN = re.compile(r"\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]\d{4}")

# Staff titles to exclude
EXCLUDE_TERMS = ["administrator", "clerk", "assistant", "manager",
                 "secretary", "treasurer", "attorney", "director"]


class LeeCountyAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("url", self.url)
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")

        content = (
            soup.find("div", class_="fr-view")
            or soup.find("div", id="divContent")
            or soup.find("div", class_="cms-area")
            or soup.find("article")
            or soup.find("main")
            or soup.body
        )
        if not content:
            raise RuntimeError(f"Could not find content area for {self.id}")

        members = []
        current_name = None
        current_title = None
        current_phone = None

        # Walk through elements linearly. Pattern:
        # <strong>Name</strong>
        # <strong>Title, District N</strong>
        # ...address lines...
        # phone number as text
        for el in content.descendants:
            if isinstance(el, Tag) and el.name in ("strong", "b"):
                text = el.get_text(strip=True)
                if not text:
                    continue

                # Check if this is a title line (contains "District" or "Chairman" etc.)
                if re.search(r"(District\s+\d+|Chairman|Vice.?Chair)", text, re.I):
                    current_title = text
                elif self._looks_like_name(text):
                    # If we have a previous member, save it
                    if current_name:
                        members.append(self._build_member(
                            current_name, current_title, current_phone
                        ))
                    current_name = text
                    current_title = None
                    current_phone = None

            elif isinstance(el, NavigableString):
                text = str(el).strip()
                if text and current_name:
                    match = PHONE_PATTERN.search(text)
                    if match and not current_phone:
                        current_phone = match.group(0)

        # Don't forget the last member
        if current_name:
            members.append(self._build_member(
                current_name, current_title, current_phone
            ))

        # Filter out admin staff
        members = [
            m for m in members
            if not any(t in m.get("title", "").lower() for t in EXCLUDE_TERMS)
            and not any(t in m.get("name", "").lower() for t in EXCLUDE_TERMS)
        ]

        return members

    def _build_member(self, name: str, title: str | None,
                      phone: str | None) -> dict:
        # Normalize title
        if not title:
            title = "Council Member"
        else:
            # Extract district number if present
            dist_match = re.search(r"District\s+(\d+)", title, re.I)
            chair_match = re.search(r"(Chairman|Vice.?Chairman)", title, re.I)

            if chair_match and dist_match:
                title = f"{chair_match.group(1)}, District {dist_match.group(1)}"
            elif dist_match:
                title = f"Council Member, District {dist_match.group(1)}"
            elif chair_match:
                title = chair_match.group(1)

        return {
            "name": name.strip(),
            "title": title,
            "email": "",
            "phone": normalize_phone(phone) if phone else "",
        }

    @staticmethod
    def _looks_like_name(text: str) -> bool:
        """Check if text looks like a person's name."""
        if not text or len(text) < 3 or len(text) > 60:
            return False
        if text.count(" ") < 1:
            return False
        if not text[0].isupper():
            return False
        # Reject if it looks like a title/position
        if re.search(r"(District|Chairman|Vice|Administrator|Clerk|County|Council\b)", text, re.I):
            return False
        # Reject if has too many digits
        digits = sum(1 for c in text if c.isdigit())
        if digits > len(text) * 0.2:
            return False
        # Reject common non-name patterns
        if any(x in text.lower() for x in [
            "phone", "fax", "address", "email", "@", "http",
            "po box", "street", "highway", "road",
        ]):
            return False
        return True
