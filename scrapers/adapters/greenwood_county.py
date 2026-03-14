"""Adapter for Greenwood County Council members.

Scrapes a Wix-based site where council members are in server-side rendered
rich text blocks. Each member block is a div[data-testid="richTextElement"]
containing:
  - Bold spans (font-weight:bold) with "District N" and "Mr./Ms. Name"
  - tel: links for phone numbers
  - mailto: links for email addresses

The actual URL is https://www.greenwoodcounty-sc.gov/county-council
(redirected from greenwoodsc.gov).
"""

import re

import requests
from bs4 import BeautifulSoup, NavigableString

from .base import BaseAdapter

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"


class GreenwoodCountyAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("url", self.url)
        resp = requests.get(
            url, headers={"User-Agent": USER_AGENT},
            timeout=30, allow_redirects=True,
        )
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []

        # Find all rich text elements that contain council member data
        for el in soup.find_all("div", attrs={"data-testid": "richTextElement"}):
            text = el.get_text(strip=True)
            # Filter to blocks containing district info and member data
            if not re.search(r"District\s+\d", text):
                continue
            # Must have an email to be a member block
            email_link = el.find("a", href=lambda h: h and h.startswith("mailto:"))
            if not email_link:
                continue

            # Extract bold items
            bolds = []
            for child in el.descendants:
                if hasattr(child, "get") and child.get("style", "") and \
                   "font-weight:bold" in child.get("style", ""):
                    t = child.get_text(strip=True)
                    if t:
                        bolds.append(t)

            # Parse district and name from bold items
            district = ""
            name = ""
            title_suffix = ""

            for bold in bolds:
                dist_match = re.match(r"District\s+(\d+)", bold, re.I)
                if dist_match:
                    district = dist_match.group(1)
                elif re.match(r"(Mr\.|Ms\.|Mrs\.|Dr\.)\s+", bold):
                    # This is a name, possibly with title suffix
                    name_part = bold
                    # Extract chairman/vice chairman from name
                    chairman_match = re.search(
                        r",\s*(Vice\s+Chairman|Council\s+Chairman|Chairman)",
                        name_part, re.I
                    )
                    if chairman_match:
                        title_suffix = chairman_match.group(1)
                        name_part = name_part[:chairman_match.start()].strip()
                    name = name_part

            # If name not found in bolds, try to extract from plain text
            # Pattern: "District N" followed by "Mr./Ms./Mrs. Name"
            if not name:
                name_match = re.search(
                    r"District\s+\d+\s*((?:Mr\.|Ms\.|Mrs\.|Dr\.)\s+[A-Z][a-zA-Z\s,.'-]+?)(?:\d|$)",
                    text
                )
                if name_match:
                    name = name_match.group(1).strip().rstrip(",.")

            if not name:
                continue

            # Strip honorific prefix
            name = re.sub(r"^(Mr\.|Ms\.|Mrs\.|Dr\.)\s+", "", name).strip()

            # Email
            email = email_link["href"][7:].strip()

            # Phone - take the first personal phone (skip office 942-8507)
            phone = ""
            for tel_link in el.find_all("a", href=lambda h: h and h.startswith("tel:")):
                phone_text = tel_link.get_text(strip=True)
                # Skip the shared office number
                if "942-8507" not in phone_text:
                    phone = phone_text
                    break
            # If only office number available, use it
            if not phone:
                tel_link = el.find("a", href=lambda h: h and h.startswith("tel:"))
                if tel_link:
                    phone = tel_link.get_text(strip=True)

            # Build title
            if title_suffix and district:
                title = f"{title_suffix}, District {district}"
            elif title_suffix:
                title = title_suffix
            elif district:
                title = f"Council Member, District {district}"
            else:
                title = "Council Member"

            members.append({
                "name": name,
                "title": title,
                "email": email,
                "phone": phone,
            })

        return members
