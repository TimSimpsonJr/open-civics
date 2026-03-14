"""Adapter for Dillon County Council members.

Scrapes a Revize CMS business directory page. Each member is a
div.rz-business-block containing:
  - h2: member name
  - span.rz-business-desc: district, title (Chairman/Vice-Chair),
    sometimes inline email
  - div.rz-business-links: phone (tel: link), email (mailto: link),
    address (Google Maps link)

Some members have TWO emails: an official @dilloncountysc.org in the
description span, and a personal email in the sidebar links. We prefer
the official email when available.

Note: The site has moved from dilloncounty.sc.gov to dilloncountysc.org.
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter, normalize_phone

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"


class DillonCountyAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("url", self.url)
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []

        for block in soup.find_all("div", class_="rz-business-block"):
            # Name
            h2 = block.find("h2")
            if not h2:
                continue
            name = h2.get_text(strip=True)
            if not name:
                continue

            # Description: district, title, sometimes inline email
            desc_el = block.find("span", class_="rz-business-desc")
            desc_text = ""
            desc_email = ""
            district = ""
            role = ""

            if desc_el:
                # Check for inline email in description
                desc_mailto = desc_el.find("a", href=re.compile(r"^mailto:", re.I))
                if desc_mailto:
                    desc_email = desc_mailto.get_text(strip=True)
                    if "@" not in desc_email:
                        desc_email = desc_mailto["href"][7:].strip()

                desc_text = desc_el.get_text(separator="\n", strip=True)
                lines = [ln.strip() for ln in desc_text.split("\n") if ln.strip()]

                for line in lines:
                    # District
                    d = re.search(r"District\s+(\d+)", line, re.I)
                    if d:
                        district = d.group(1)
                    # Role
                    lower = line.lower()
                    if "chairman" in lower or "chair" in lower:
                        if "vice" in lower:
                            role = "Vice Chairman"
                        else:
                            role = "Chairman"

            # Sidebar links: phone and email
            sidebar_email = ""
            phone = ""
            links_div = block.find("div", class_="rz-business-links")
            if links_div:
                tel = links_div.find("a", href=re.compile(r"^tel:"))
                if tel:
                    phone = normalize_phone(tel.get_text(strip=True))

                mailto = links_div.find("a", href=re.compile(r"^mailto:", re.I))
                if mailto:
                    sidebar_email = mailto.get_text(strip=True)
                    if "@" not in sidebar_email:
                        sidebar_email = mailto["href"][7:].strip()

            # Prefer official email (from desc) over personal (from sidebar)
            email = desc_email or sidebar_email

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
        if "Vice" in role:
            if district:
                return f"Vice Chairman, District {district}"
            return "Vice Chairman"
        if "Chairman" in role or "Chair" in role:
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
