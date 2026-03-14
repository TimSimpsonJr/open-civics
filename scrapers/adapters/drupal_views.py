"""Shared adapter for Drupal sites using the Views module.

Handles two common Drupal patterns:
  1. views-row with views-field-* CSS classes:
     - views-field-title: member name (often a link)
     - views-field-field-district: "District N"
     - views-field-field-job-title: role (Chairman, Councilman, etc.)
     - views-field-field-email-address: email (mailto link)
     - views-field-field-phone-numbers: phone (tel link)

  2. person-item articles:
     - person-item__title: member name
     - person-item__job-title: title
     - person-item__email-address: email
     - person-item__phone-numbers: phone
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"


class DrupalViewsAdapter(BaseAdapter):
    """Scraper for Drupal Views-powered council pages."""

    def fetch(self) -> str:
        resp = requests.get(
            self.url, headers={"User-Agent": USER_AGENT}, timeout=30
        )
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")

        # Try person-item pattern first (Orangeburg-style)
        articles = soup.find_all("article", class_=re.compile(r"person-item"))
        if articles:
            return self._parse_person_items(articles)

        # Try views-row pattern (Newberry/Colleton-style)
        rows = soup.find_all("div", class_="views-row")
        if rows:
            return self._parse_views_rows(rows)

        raise ValueError(f"No Drupal Views rows or person-items found for {self.id}")

    def _parse_views_rows(self, rows: list) -> list[dict]:
        """Parse views-row divs with views-field-* children."""
        members = []
        exclude = ["clerk", "administrator", "manager", "secretary",
                    "treasurer", "attorney", "director", "assistant"]

        for row in rows:
            # Name
            name_el = row.find(class_=re.compile(r"views-field-title"))
            if not name_el:
                continue
            link = name_el.find("a")
            name = (link or name_el).get_text(strip=True)
            if not name:
                continue
            # Skip non-person entries
            if any(x in name.lower() for x in exclude):
                continue

            # District
            district = ""
            dist_el = row.find(class_=re.compile(r"views-field-field-district"))
            if dist_el:
                dist_text = dist_el.get_text(strip=True)
                dist_match = re.search(r"(\d+)", dist_text)
                if dist_match:
                    district = dist_match.group(1)

            # Job title / role
            title = ""
            title_el = row.find(class_=re.compile(r"views-field-field-job-title"))
            if title_el:
                title = title_el.get_text(strip=True)

            title = self._normalize_title(title, district)

            # Email
            email = ""
            email_el = row.find(class_=re.compile(r"views-field-field-email"))
            if email_el:
                mailto = email_el.find("a", href=re.compile(r"^mailto:", re.I))
                if mailto:
                    email = mailto["href"][7:].strip()
                else:
                    text = email_el.get_text(strip=True)
                    if "@" in text:
                        email = text

            # Phone
            phone = ""
            phone_el = row.find(class_=re.compile(r"views-field-field-phone"))
            if phone_el:
                tel = phone_el.find("a", href=re.compile(r"^tel:"))
                if tel:
                    phone = tel.get_text(strip=True)
                else:
                    phone = phone_el.get_text(strip=True)

            members.append({
                "name": name,
                "title": title,
                "email": email,
                "phone": phone,
            })

        members.sort(key=self._sort_key)
        return members

    def _parse_person_items(self, articles: list) -> list[dict]:
        """Parse person-item articles (Orangeburg-style)."""
        members = []

        for article in articles:
            # Name
            name_el = article.find(class_=re.compile(r"person-item__title"))
            if not name_el:
                continue
            link = name_el.find("a")
            name = (link or name_el).get_text(strip=True)
            if not name:
                continue

            # Title
            title = ""
            title_el = article.find(class_=re.compile(r"person-item__job-title"))
            if title_el:
                title = title_el.get_text(strip=True)
            title = self._normalize_title(title, "")

            # Email
            email = ""
            email_el = article.find(class_=re.compile(r"person-item__email"))
            if email_el:
                mailto = email_el.find("a", href=re.compile(r"^mailto:", re.I))
                if mailto:
                    email = mailto["href"][7:].strip()
                else:
                    text = email_el.get_text(strip=True)
                    if "@" in text:
                        email = text

            # Phone
            phone = ""
            phone_el = article.find(class_=re.compile(r"person-item__phone"))
            if phone_el:
                tel = phone_el.find("a", href=re.compile(r"^tel:"))
                if tel:
                    phone = tel.get_text(strip=True)
                else:
                    phone = phone_el.get_text(strip=True)

            members.append({
                "name": name,
                "title": title,
                "email": email,
                "phone": phone,
            })

        members.sort(key=self._sort_key)
        return members

    @staticmethod
    def _normalize_title(raw: str, district: str) -> str:
        """Normalize title text to standard form."""
        if not raw and not district:
            return "Council Member"

        lower = raw.lower().strip() if raw else ""

        if lower == "mayor":
            return "Mayor"

        if "mayor pro" in lower or "mayor pro tem" in lower:
            if district:
                return f"Mayor Pro Tem, District {district}"
            return "Mayor Pro Tem"

        if "chairman" in lower or "chair" in lower:
            if "vice" in lower:
                if district:
                    return f"Vice Chairman, District {district}"
                return "Vice Chairman"
            if district:
                return f"Chairman, District {district}"
            return "Chairman"

        # District from title text
        dist_match = re.search(r"District\s+(\d+)", raw, re.I) if raw else None
        if dist_match:
            return f"Council Member, District {dist_match.group(1)}"

        # Seat-based (Colleton style: "Seat #4 Western")
        seat_match = re.search(r"Seat\s*#?(\d+)", raw, re.I) if raw else None
        if seat_match:
            return f"Council Member, Seat {seat_match.group(1)}"

        if district:
            return f"Council Member, District {district}"

        if raw:
            return raw

        return "Council Member"

    @staticmethod
    def _sort_key(member: dict) -> tuple:
        title = member.get("title", "")
        if "Mayor" in title and "Pro Tem" not in title:
            return (0, 0, "")
        if "Mayor Pro" in title:
            return (0, 1, "")
        if "Chairman" in title and "Vice" not in title:
            return (1, 0, "")
        if "Vice" in title:
            return (1, 1, "")
        dist_match = re.search(r"District\s+(\d+)", title)
        if dist_match:
            return (2, int(dist_match.group(1)), "")
        seat_match = re.search(r"Seat\s+(\d+)", title)
        if seat_match:
            return (2, int(seat_match.group(1)), "")
        return (3, 0, member.get("name", ""))
