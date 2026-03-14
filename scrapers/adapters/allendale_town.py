"""Adapter for Town of Allendale council members.

Scrapes a Drupal site where member data is split across two sections:
  1. A <table> in div.field--name-body with title/name columns
  2. A sidebar div.field--name-field-right-column-content with name-to-email
     mappings in <p> tags containing mailto: links

Names may have decorative asterisks (* or **) indicating training
institute graduation, which must be stripped. The two sections are
joined by fuzzy name matching since names may differ slightly
(e.g., "Lee E. Harley-Fitts" vs "Lee Harley-Fitts").
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"


class AllendaleTownAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("url", self.url)
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")

        # 1. Parse the table for title/name pairs
        #    Table may be in div.field--name-body or in main content area
        table_members = []
        table = None
        body_div = soup.find("div", class_="field--name-body")
        if body_div:
            table = body_div.find("table")
        if not table:
            main = soup.find("main") or soup.find("div", class_="layout-content")
            if main:
                table = main.find("table")
        if not table:
            table = soup.find("table")

        if table:
            for tr in table.find_all("tr"):
                cells = tr.find_all("td")
                if len(cells) < 2:
                    continue
                raw_title = cells[0].get_text(strip=True).rstrip(":")
                raw_name = cells[1].get_text(strip=True)
                # Strip decorative asterisks
                raw_name = re.sub(r"[*]+\s*", "", raw_name).strip()
                if not raw_name:
                    continue
                table_members.append({
                    "raw_title": raw_title,
                    "name": raw_name,
                })

        # 2. Parse the sidebar for name-to-email mappings
        email_map = {}  # name_key -> email
        right_div = soup.find("div", class_=re.compile(r"field--name-field-right-column"))
        if right_div:
            for p in right_div.find_all("p"):
                mailto = p.find("a", href=re.compile(r"^mailto:", re.I))
                if not mailto:
                    continue
                email = mailto["href"][7:].strip()
                # The name is in the <strong> text before the link
                strong = p.find("strong")
                if strong:
                    label = strong.get_text(strip=True).rstrip(":")
                    # Remove title prefixes like "Mayor", "Councilmember"
                    label = re.sub(
                        r"^(Mayor|Councilmember|Council\s*Member)\s+",
                        "", label, flags=re.I
                    ).strip()
                    # Clean unicode issues
                    label = label.replace("\ufffd", "").strip()
                    if label:
                        email_map[self._name_key(label)] = email

        # 3. Join table members with emails
        members = []
        for tm in table_members:
            name = tm["name"]
            raw_title = tm["raw_title"]

            # Normalize title
            lower_title = raw_title.lower()
            if "mayor" in lower_title:
                title = "Mayor"
            elif "councilmember" in lower_title or "council member" in lower_title:
                title = "Council Member"
            else:
                title = raw_title or "Council Member"

            # Match email by fuzzy name key
            email = email_map.get(self._name_key(name), "")

            # If no exact match, try partial matching (last name)
            if not email:
                last = name.split()[-1].lower() if name.split() else ""
                for key, addr in email_map.items():
                    if last and last in key:
                        email = addr
                        break

            members.append({
                "name": name,
                "title": title,
                "email": email,
                "phone": "",
            })

        members.sort(key=self._sort_key)
        return members

    @staticmethod
    def _name_key(name: str) -> str:
        """Create a normalized key for fuzzy name matching."""
        # Remove middle initials, punctuation, lowercase
        key = re.sub(r"\b[A-Z]\.\s*", "", name)
        key = re.sub(r"[^a-z\s]", "", key.lower())
        return " ".join(key.split())

    @staticmethod
    def _sort_key(member: dict) -> tuple:
        title = member.get("title", "")
        if title == "Mayor":
            return (0, member.get("name", ""))
        return (1, member.get("name", ""))
