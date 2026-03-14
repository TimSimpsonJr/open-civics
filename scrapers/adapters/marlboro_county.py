"""Adapter for Marlboro County Council members.

Scrapes the Revize-powered Marlboro County site. Council member data is in
h3/h4 heading tags. The name and district are in large-font spans/strong
tags, while addresses are in smaller font spans. Most members use h4 but
at least one uses h3. Structure varies per member but follows:

  <h4>  (or <h3>)
    <span style="font-size: 24px"><strong>Name, District N</strong></span>
    <span style="font-size: 16px">Address...</span>
    Telephone: <a href="tel:NNN">NNN</a>
  </h4>

Some members have split spans for the name. Role (Chairman, Vice Chairwoman)
may appear in parentheses either inside or outside the name span.

No email addresses are available for council members.
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"


class MarlboroCountyAdapter(BaseAdapter):

    def fetch(self) -> str:
        resp = requests.get(
            self.url, headers={"User-Agent": USER_AGENT}, timeout=30
        )
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []

        for h4 in soup.find_all(["h3", "h4"]):
            # Collect text from large-font spans (24px) which contain
            # the name and district. May be split across multiple spans.
            large_spans = h4.find_all(
                "span", style=re.compile(r"font-size:\s*24px")
            )
            if large_spans:
                # Concatenate text from all 24px spans
                name_text = "".join(
                    s.get_text(strip=True) for s in large_spans
                )
                # Also check for role text outside the spans but inside strong
                full_strong_text = ""
                for strong in h4.find_all("strong"):
                    full_strong_text += strong.get_text(strip=True)
            else:
                # Fallback: use separator to split name from address
                full_text = h4.get_text(separator="\n", strip=True)
                lines = [l.strip() for l in full_text.split("\n") if l.strip()]
                name_text = lines[0] if lines else ""
                full_strong_text = name_text

            # Match "Name, District N" pattern
            district_match = re.search(r",\s*District\s+(\d+)", name_text)
            if not district_match:
                continue

            district_num = district_match.group(1)

            # Extract name: everything before ", District N"
            name = name_text[:district_match.start()].strip()

            # Check for role in parentheses in either the name text or the
            # full h4 text (role sometimes appears outside the 24px span)
            h4_text = h4.get_text(strip=True)
            title = f"Council Member, District {district_num}"
            role_match = re.search(
                r"\(([^)]*(?:Chair|Vice)[^)]*)\)", h4_text
            )
            if role_match:
                role = role_match.group(1).strip()
                title = f"{role}, District {district_num}"
                # Clean role from name if it got included
                name = re.sub(
                    r"\s*\([^)]*(?:Chair|Vice)[^)]*\)", "", name
                ).strip()

            # Clean honorifics
            name = re.sub(r"^(Mr\.?|Mrs\.?|Ms\.?|Dr\.?)\s+", "", name)
            # Clean trailing comma or whitespace
            name = name.rstrip(", ").strip()

            # Phone from tel: link in the h4
            phone = ""
            tel_link = h4.find("a", href=re.compile(r"^tel:", re.IGNORECASE))
            if tel_link:
                phone = tel_link.get_text(strip=True)
            else:
                # Fallback: look for phone pattern in h4 text
                phone_match = re.search(
                    r"\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]\d{4}", h4_text
                )
                if phone_match:
                    phone = phone_match.group(0)

            if not name:
                continue

            members.append({
                "name": name,
                "title": title,
                "email": "",
                "phone": phone,
            })

        # Sort by district number
        members.sort(key=lambda m: self._district_sort_key(m["title"]))
        return members

    @staticmethod
    def _district_sort_key(title: str) -> int:
        match = re.search(r"District\s+(\d+)", title)
        return int(match.group(1)) if match else 0
