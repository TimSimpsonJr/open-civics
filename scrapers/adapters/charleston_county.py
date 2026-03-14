"""Adapter for Charleston County Council members.

Scrapes the Charleston County elected officials detail page, which has
individual sections for each council member anchored by #d1 through #d9.

Each section contains:
  - h3 with member name
  - h4 with "Title: Councilmember" (or Vice Chair, Council Chair)
  - Email in a mailto link (username only in href) with full address
    displayed across two spans (uname class)
  - Phone in a span.phonefaxnumber element

The main council page (/departments/county-council/) only has a carousel
with names and districts but no contact info, so we scrape the detail page
at /departments/county-council/countycouncil.php instead.
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"

# Detail page with individual member bios and contact info
DETAIL_URL = "https://www.charlestoncounty.gov/departments/county-council/countycouncil.php"


class CharlestonCountyAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("detailUrl", DETAIL_URL)
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []
        seen_names = set()

        # Find the "Councilmembers" heading to scope our search.
        # The heading is nested inside col-12 > row > container-fluid,
        # so we walk up to the container-fluid level to find all member h3s.
        start = soup.find("h2", string=re.compile(r"Councilmembers", re.I))
        container = soup
        if start:
            p = start
            for _ in range(5):
                p = p.parent
                if p and p.find_all("h3"):
                    container = p
                    break

        # Each member has an h3 with their name
        for h3 in container.find_all("h3"):
            name = h3.get_text(strip=True)
            if not name or not re.match(r"^[A-Z]", name):
                continue
            # Skip non-member headings
            if any(x in name.lower() for x in [
                "website", "get to know", "council related",
                "elected", "bios", "clerk",
            ]):
                continue

            if name in seen_names:
                continue
            seen_names.add(name)

            # Find the enclosing section for this member
            # Walk up a few levels to find a div with an anchor id (d1..d9)
            section = h3
            for _ in range(8):
                section = section.parent
                if not section:
                    break
                if section.get("id", "").startswith("d") and section["id"][1:].isdigit():
                    break

            if not section:
                continue

            # District from anchor id
            dist_id = section.get("id", "")
            district = ""
            if dist_id.startswith("d") and dist_id[1:].isdigit():
                district = dist_id[1:]

            # Title from h4 containing "Title:"
            title = "Council Member"
            for h4 in section.find_all("h4"):
                h4_text = h4.get_text(strip=True)
                if h4_text.startswith("Title:"):
                    raw_title = h4_text.replace("Title:", "").strip()
                    if raw_title:
                        title = raw_title
                    break

            # Add district info
            if district:
                if title in ("Councilmember", "Council Member"):
                    title = f"Council Member, District {district}"
                else:
                    title = f"{title}, District {district}"

            # Email: look for mailto link, then get full address from
            # the span.uname element which has username + domain
            email = ""
            uname_span = section.find("span", class_="uname")
            if uname_span:
                email = uname_span.get_text(strip=True)
            if not email:
                mailto = section.find("a", href=re.compile(r"^mailto:", re.I))
                if mailto:
                    raw = mailto["href"][7:].split("?")[0]
                    # If it lacks @, append domain
                    if "@" not in raw and raw:
                        email = f"{raw}@CharlestonCounty.org"
                    else:
                        email = raw

            # Phone: look for phone pattern in text
            phone = ""
            phone_span = section.find("span", class_="phonefaxnumber")
            if phone_span:
                phone_text = phone_span.get_text(strip=True)
                phone_match = re.search(
                    r"\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]\d{4}", phone_text
                )
                if phone_match:
                    phone = phone_match.group(0)

            # Fallback: search entire section text for phone
            if not phone:
                section_text = section.get_text()
                phone_match = re.search(
                    r"\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]\d{4}", section_text
                )
                if phone_match:
                    phone = phone_match.group(0)

            members.append({
                "name": name,
                "title": title,
                "email": email,
                "phone": phone,
            })

        return members
