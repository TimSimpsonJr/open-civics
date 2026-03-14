"""Adapter for City of Darlington council members.

Scrapes the WordPress citygov-themed Darlington site. Council member data
is in a simple unordered list within the entry-content area, with each
<li> containing:
  - Title + Name (e.g., "Mayor CURTIS Boyd")
  - Phone number in parenthesized format
  - Email address as domain suffix

Example list item text:
  "Mayor CURTIS Boyd(843) 206-4389mayorcboyd@cityofdarlington.com"

The parser splits each line by phone pattern to extract name, phone, email.
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"
PAGE_URL = "https://www.cityofdarlington.com/mayor-council/"


class DarlingtonCityAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("url", PAGE_URL)
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []

        # Find the content area
        content = (
            soup.find("div", class_="entry-content")
            or soup.find("article")
            or soup.find("main")
        )
        if not content:
            return members

        # Council members are in <li> tags
        for li in content.find_all("li"):
            text = li.get_text(strip=True)
            if not text:
                continue

            member = self._parse_member_line(text)
            if member:
                members.append(member)

        # Sort: Mayor first, then Mayor Pro Tem, then by ward
        members.sort(key=self._sort_key)
        return members

    @staticmethod
    def _parse_member_line(text: str) -> dict | None:
        """Parse a member line like:
        'Mayor CURTIS Boyd(843) 206-4389mayorcboyd@cityofdarlington.com'
        """
        # Extract phone number pattern
        phone_match = re.search(
            r"\((\d{3})\)\s*(\d{3})[-.]?(\d{4})", text
        )
        phone = ""
        if phone_match:
            phone = f"({phone_match.group(1)}) {phone_match.group(2)}-{phone_match.group(3)}"

        # Extract email - must start with a letter (not a digit from phone)
        email_match = re.search(
            r"([A-Za-z][A-Za-z0-9._%+-]*@[A-Za-z0-9.-]+\.[A-Za-z]{2,})", text
        )
        email = email_match.group(1) if email_match else ""

        # Extract name and title: everything before the phone number
        if phone_match:
            name_title = text[: phone_match.start()].strip()
        elif email_match:
            name_title = text[: email_match.start()].strip()
        else:
            name_title = text.strip()

        if not name_title:
            return None

        # Parse title prefix
        name, title = _parse_title_name(name_title)
        if not name:
            return None

        return {
            "name": name,
            "title": title,
            "email": email,
            "phone": phone,
        }

    @staticmethod
    def _sort_key(member: dict) -> tuple:
        title = member["title"]
        if title == "Mayor":
            return (0, 0)
        if "Mayor Pro Tem" in title:
            return (0, 1)
        match = re.search(r"Ward\s+(\d+)", title)
        if match:
            return (1, int(match.group(1)))
        # At Large
        return (2, 0)


def _parse_title_name(text: str) -> tuple[str, str]:
    """Parse 'Mayor CURTIS Boyd' or 'JOHN SEGARS, Mayor Pro Tempore - Ward 3'."""
    # Check for "Name, Title - Ward N" pattern
    comma_match = re.match(
        r"(.+?),\s*(Mayor Pro Tem(?:pore)?)\s*[-–]\s*Ward\s*(\d+)",
        text, re.IGNORECASE,
    )
    if comma_match:
        name = _normalize_name(comma_match.group(1).strip())
        return name, f"Mayor Pro Tem, Ward {comma_match.group(3)}"

    # Check for "Name, Member At Large" pattern
    atlarge_match = re.match(
        r"(.+?),\s*Member\s+At\s+Large", text, re.IGNORECASE
    )
    if atlarge_match:
        name = _normalize_name(atlarge_match.group(1).strip())
        return name, "Council Member, At Large"

    # Check for "Name, Ward N" pattern
    ward_match = re.match(
        r"(.+?),\s*Ward\s*(\d+)", text, re.IGNORECASE
    )
    if ward_match:
        name = _normalize_name(ward_match.group(1).strip())
        return name, f"Council Member, Ward {ward_match.group(2)}"

    # Check for title prefix: "Mayor NAME"
    for prefix in ["Mayor", "Councilwoman", "Councilman", "Council Member"]:
        if text.lower().startswith(prefix.lower()):
            name = _normalize_name(text[len(prefix):].strip())
            if prefix.lower() == "mayor":
                return name, "Mayor"
            return name, "Council Member"

    # Fallback
    return _normalize_name(text), "Council Member"


def _normalize_name(name: str) -> str:
    """Normalize ALL-CAPS or mixed-case names to Title Case."""
    # If the name looks all-caps, title-case it
    if name.isupper():
        return name.title()
    # Handle mixed like "CURTIS Boyd" -> split and title-case uppercase words
    words = name.split()
    fixed = []
    for w in words:
        if w.isupper() and len(w) > 2:
            fixed.append(w.title())
        else:
            fixed.append(w)
    return " ".join(fixed).strip()
