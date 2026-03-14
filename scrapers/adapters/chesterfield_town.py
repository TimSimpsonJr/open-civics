"""Adapter for Chesterfield Town Council members.

Scrapes the Wix-powered Chesterfield Town site. Council member data is in
span elements with a pattern of:
  - Mayor / District N (span)
  - Member Name (span)
  - Address (span)
  - Phone number (span)
  - Email (mailto link)

All members are in one section. The structure uses spans rather than
bold/strong/heading tags, so generic adapters don't work here.
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"


class ChesterfieldTownAdapter(BaseAdapter):

    def fetch(self) -> str:
        resp = requests.get(
            self.url, headers={"User-Agent": USER_AGENT}, timeout=30
        )
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []

        # Collect all mailto links and their emails
        mailto_links = soup.find_all(
            "a", href=re.compile(r"^mailto:", re.IGNORECASE)
        )

        # Build a map of all spans containing member-related text
        # Find the section with council member info by looking for the section
        # containing "Mayor" and "District" spans
        spans = soup.find_all("span")

        # Walk through spans to find member blocks.
        # Pattern: "Mayor" or "District N" -> Name -> Address -> Phone
        member_blocks = []
        current_block = None

        for span in spans:
            text = span.get_text(strip=True)
            if not text:
                continue

            # Check for district/mayor header
            if text == "Mayor":
                if current_block and current_block.get("name"):
                    member_blocks.append(current_block)
                current_block = {"role": "Mayor", "district": None}
                continue

            district_match = re.match(r"^District\s+(\d+)$", text)
            if district_match:
                if current_block and current_block.get("name"):
                    member_blocks.append(current_block)
                current_block = {
                    "role": "Council Member",
                    "district": district_match.group(1),
                }
                continue

            if current_block is None:
                continue

            # Fill in fields in order: name, address lines, phone
            if "name" not in current_block:
                # Name should be a person's name (not an address, phone, etc.)
                if self._looks_like_name(text):
                    current_block["name"] = text
            elif "phone" not in current_block:
                # Look for phone numbers
                phone_match = re.search(
                    r"\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]\d{4}", text
                )
                if phone_match:
                    current_block["phone"] = phone_match.group(0)

        # Don't forget the last block
        if current_block and current_block.get("name"):
            member_blocks.append(current_block)

        # Now match emails to members by position order
        # Filter to only personal emails (not generic ones)
        personal_emails = []
        seen_emails = set()
        for a in mailto_links:
            email = a["href"][7:].strip().lower()
            if email not in seen_emails and not self._is_generic_email(email):
                seen_emails.add(email)
                personal_emails.append(email)

        # Assign emails to members in order
        for i, block in enumerate(member_blocks):
            email = personal_emails[i] if i < len(personal_emails) else ""
            title = block["role"]
            if block.get("district"):
                if title == "Council Member":
                    title = f"Council Member, District {block['district']}"
                else:
                    title = f"{title}, District {block['district']}"

            members.append({
                "name": block["name"],
                "title": title,
                "email": email,
                "phone": block.get("phone", ""),
            })

        return members

    @staticmethod
    def _looks_like_name(text: str) -> bool:
        """Check if text looks like a person's name."""
        if not text or len(text) < 3 or len(text) > 50:
            return False
        if not text[0].isupper():
            return False
        # Must have at least a first and last name
        if text.count(" ") < 1:
            return False
        # Reject addresses, phone-like strings, etc.
        if re.search(r"\d{3}[\s.\-]\d{3}", text):
            return False
        if any(word in text.lower() for word in [
            "box", "street", "road", "drive", "avenue", "po ", "p.o.",
            "sc ", "district", "election", "method", "term",
        ]):
            return False
        return True

    @staticmethod
    def _is_generic_email(email: str) -> bool:
        local = email.split("@")[0].lower()
        generic = ["info", "council", "clerk", "webmaster", "admin",
                    "contact", "help", "support", "general", "office"]
        return local in generic
