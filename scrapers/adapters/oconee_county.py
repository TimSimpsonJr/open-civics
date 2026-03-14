"""Adapter for Oconee County Council members.

Scrapes the Joomla/SP Page Builder-powered Oconee County site. Council member
data is in structured blocks with bold labels:
  <strong>District N (Title)</strong>
  <strong>Name:</strong> Member Name
  <strong>Phone:</strong> <a href="tel:NNN">NNN</a>
  <strong>Email:</strong> <a href="mailto:email">email</a>

The actual member listing is at /council-home/council-officials (linked from
the /council-home/council-information page).
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"


class OconeeCountyAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("url", self.url)
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []

        # Find all <strong> tags that start with "District"
        for strong in soup.find_all("strong"):
            text = strong.get_text(strip=True)
            district_match = re.match(
                r"District\s+([IVXLCDM]+)", text, re.IGNORECASE
            )
            if not district_match:
                continue

            district_roman = district_match.group(1)
            district_num = self._roman_to_int(district_roman)

            # Extract role from parentheses: "District II (Chairman)"
            title = f"Council Member, District {district_num}"
            role_match = re.search(r"\(([^)]+)\)", text)
            if role_match:
                role = role_match.group(1).strip()
                title = f"{role}, District {district_num}"

            # Find sibling elements in the same container for Name/Phone/Email
            parent = strong.find_parent("div", class_=lambda c: c and "sppb" in c)
            if not parent:
                parent = strong.find_parent("div")
            if not parent:
                continue

            # Extract Name, Phone, Email from label patterns
            name = ""
            phone = ""
            email = ""

            for s in parent.find_all("strong"):
                label = s.get_text(strip=True)
                if label == "Name:":
                    # Name is the next text node after the strong tag
                    next_el = s.next_sibling
                    while next_el:
                        if hasattr(next_el, "get_text"):
                            t = next_el.get_text(strip=True)
                        else:
                            t = str(next_el).strip()
                        if t:
                            name = t
                            break
                        next_el = next_el.next_sibling
                elif label == "Phone:":
                    tel_link = parent.find(
                        "a", href=re.compile(r"^tel:", re.IGNORECASE)
                    )
                    if tel_link:
                        phone = tel_link.get_text(strip=True)
                    else:
                        next_el = s.next_sibling
                        while next_el:
                            t = str(next_el).strip() if not hasattr(next_el, "get_text") else next_el.get_text(strip=True)
                            if t and re.search(r"\d{3}", t):
                                phone = t
                                break
                            next_el = next_el.next_sibling
                elif label == "Email:":
                    mailto = parent.find(
                        "a", href=re.compile(r"^mailto:", re.IGNORECASE)
                    )
                    if mailto:
                        email = mailto["href"][7:].strip()

            if not name:
                continue

            members.append({
                "name": name,
                "title": title,
                "email": email,
                "phone": phone,
            })

        # Sort by district number
        members.sort(key=lambda m: self._district_sort_key(m["title"]))
        return members

    @staticmethod
    def _roman_to_int(roman: str) -> int:
        values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
        total = 0
        prev = 0
        for ch in reversed(roman.upper()):
            val = values.get(ch, 0)
            if val < prev:
                total -= val
            else:
                total += val
            prev = val
        return total

    @staticmethod
    def _district_sort_key(title: str) -> int:
        match = re.search(r"District\s+(\d+)", title)
        return int(match.group(1)) if match else 0
