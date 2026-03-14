"""Adapter for Edgefield County Council.

The Edgefield County WordPress/Divi site lists council members in
et_pb_column blocks. Each block has:
  - <strong>: title like "Vice Chairman - District 1" or "District 2"
  - <p>: name (first non-title, non-address, non-phone paragraph)
  - <p>: address lines
  - <p>: phone number
  - <a href="mailto:...">: email

The Clerk to Council is also listed and should be filtered out.
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"

DEFAULT_EXCLUDE = ["clerk", "administrator", "manager", "secretary"]

PHONE_PATTERN = re.compile(r"\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]\d{4}")


class EdgefieldCountyAdapter(BaseAdapter):
    """Scraper for Edgefield County Council page."""

    def fetch(self) -> str:
        url = self.url
        if not url:
            raise RuntimeError(f"No URL configured for {self.id}")
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []
        exclude_terms = self.config.get("memberFilter", DEFAULT_EXCLUDE)

        for col in soup.find_all("div", class_="et_pb_column"):
            mailto = col.find("a", href=lambda h: h and "mailto:" in h)
            if not mailto:
                continue

            email = mailto["href"].replace("mailto:", "").strip()

            # Get title from <strong> tag
            strong = col.find("strong")
            title_raw = strong.get_text(strip=True) if strong else ""

            # Clean up special characters
            title_raw = title_raw.replace("\xa0", " ").strip()

            # Skip non-council members
            if any(term.lower() in title_raw.lower() for term in exclude_terms):
                continue

            # Extract name and phone from <p> tags
            paragraphs = [p.get_text(strip=True) for p in col.find_all("p")]
            name = ""
            phone = ""

            for p_text in paragraphs:
                if not p_text:
                    continue
                # Skip the title text
                if p_text == title_raw:
                    continue
                # Skip email text
                if "@" in p_text:
                    continue
                # Check if it's a phone number
                if PHONE_PATTERN.search(p_text) and not name:
                    # Could be a phone line, but check if it also contains a name
                    phone = PHONE_PATTERN.search(p_text).group(0)
                    continue
                if PHONE_PATTERN.search(p_text):
                    phone = PHONE_PATTERN.search(p_text).group(0)
                    continue
                # Skip address lines
                if self._looks_like_address(p_text):
                    continue
                # First remaining text is likely the name
                if not name:
                    name = p_text.replace("\xa0", " ").strip()

            if not name:
                continue

            title = self._normalize_title(title_raw)

            members.append({
                "name": name,
                "title": title,
                "email": email,
                "phone": phone,
            })

        members.sort(key=self._sort_key)
        return members

    @staticmethod
    def _looks_like_address(text: str) -> bool:
        """Check if text looks like a street address."""
        text_lower = text.lower().strip()

        # "Dr." at the start is an honorific, not a street suffix
        if text_lower.startswith("dr.") and len(text_lower.split()) > 2:
            return False

        # Check for SC zip code pattern
        if re.search(r"\b(sc|s\.c\.)\s*\d{5}", text_lower):
            return True

        # Must contain a number to look like a street address
        # (avoids matching names that happen to contain a keyword)
        has_number = bool(re.search(r"\d", text_lower))

        address_keywords = [
            "hwy", "highway", "road", "rd", "street", "st.",
            "ave", "avenue", "drive", "dr.", "lane", "ln",
            "blvd", "court", "ct.", "circle", "way",
            "p.o. box", "po box",
        ]
        if has_number and any(kw in text_lower for kw in address_keywords):
            return True

        return False

    @staticmethod
    def _normalize_title(title_raw: str) -> str:
        """Normalize title to standard format.

        Examples:
          "Vice Chairman - District 1" -> "Vice Chairman, District 1"
          "Chairman- District 3" -> "Chairman, District 3"
          "District 2" -> "Council Member, District 2"
        """
        title = title_raw.strip()
        # Remove various dash separators
        title = re.sub(r"[\u2013\u2014\-]+\s*", " ", title).strip()

        district_match = re.search(r"District\s+(\d+)", title, re.I)
        if not district_match:
            return title or "Council Member"

        district_num = district_match.group(1)

        if re.search(r"\bVice\s+Chair", title, re.I):
            return f"Vice Chairman, District {district_num}"
        if re.search(r"\bChair", title, re.I):
            return f"Chairman, District {district_num}"

        return f"Council Member, District {district_num}"

    @staticmethod
    def _sort_key(member: dict) -> tuple:
        title = member["title"]
        if "Chairman" in title and "Vice" not in title:
            return (0, 0)
        if "Vice Chairman" in title:
            return (0, 1)
        district_match = re.search(r"District\s+(\d+)", title)
        if district_match:
            return (1, int(district_match.group(1)))
        return (2, 0, member.get("name", ""))
