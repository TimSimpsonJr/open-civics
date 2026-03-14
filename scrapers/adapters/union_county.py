"""Adapter for Union County Council members.

Scrapes a WordPress site using the ThemeFuse fw-team widget. Each
council member is a card inside a div.fw-team container:
  - div.fw-team-name > h5: member name (may include ", Vice Chairman" suffix)
  - div.fw-team-name > span: district label (e.g., "DISTRICT 3")
  - div.fw-team-text a[href^="mailto:"]: email (link text preferred over href,
    as some href values are outdated)
  - Phone numbers are plain text in div.fw-team-text <p> elements

Note: Some members have a stale mailto href pointing to a predecessor's
email. The link text is the correct email address.
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter, normalize_phone

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"


class UnionCountyAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("url", self.url)
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []

        for card in soup.find_all("div", class_="fw-team"):
            # Name
            name_el = card.find("h5")
            if not name_el:
                continue
            raw_name = name_el.get_text(strip=True)
            if not raw_name:
                continue

            # Strip title suffix from name (e.g., ", Vice Chairman")
            name = raw_name
            role = ""
            for suffix in [", Vice Chairman", ", Chairman", ", Vice Chair", ", Chair"]:
                if suffix in name:
                    role = suffix.lstrip(", ")
                    name = name.replace(suffix, "").strip()
                    break

            # District
            district = ""
            dist_span = card.find("div", class_="fw-team-name")
            if dist_span:
                span = dist_span.find("span")
                if span:
                    dist_text = span.get_text(strip=True)
                    dist_match = re.search(r"(\d+)", dist_text)
                    if dist_match:
                        district = dist_match.group(1)

            # Email: prefer link TEXT over href (href may be stale)
            email = ""
            text_div = card.find("div", class_="fw-team-text")
            if text_div:
                mailto = text_div.find("a", href=re.compile(r"^mailto:", re.I))
                if mailto:
                    link_text = mailto.get_text(strip=True)
                    if "@" in link_text:
                        email = link_text
                    else:
                        email = mailto["href"][7:].strip()

            # Phone: find pattern in text content
            phone = ""
            if text_div:
                text = text_div.get_text(separator="\n", strip=True)
                phone_match = re.search(r"\d{3}[\-\.]\d{3}[\-\.]\d{4}", text)
                if phone_match:
                    phone = normalize_phone(phone_match.group())

            # Build title
            title = self._build_title(role, district)

            members.append({
                "name": name,
                "title": title,
                "email": email,
                "phone": phone,
            })

        members.sort(key=self._sort_key)
        return members

    @staticmethod
    def _build_title(role: str, district: str) -> str:
        lower = role.lower() if role else ""
        if "chairman" in lower or "chair" in lower:
            if "vice" in lower:
                if district:
                    return f"Vice Chairman, District {district}"
                return "Vice Chairman"
            if district:
                return f"Chairman, District {district}"
            return "Chairman"
        if district:
            return f"Council Member, District {district}"
        return "Council Member"

    @staticmethod
    def _sort_key(member: dict) -> tuple:
        title = member.get("title", "")
        if "Chairman" in title and "Vice" not in title:
            return (0, 0)
        if "Vice" in title:
            return (0, 1)
        dist_match = re.search(r"District\s+(\d+)", title)
        if dist_match:
            return (1, int(dist_match.group(1)))
        return (2, 0)
