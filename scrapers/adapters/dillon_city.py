"""Adapter for City of Dillon council members.

Scrapes the MembershipWare People API used by the Dillon city website.
The citycouncil page loads council data from an external JS API at
app.membershipware.com. The response is a JS assignment of a JSON object
containing a "people" array with names and category text (district info).

No email addresses or phone numbers are published.
"""

import json
import re

import requests

from .base import BaseAdapter

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"
API_URL = (
    "https://app.membershipware.com/api/public/mwjsPeople"
    "?et=wYHxoV0HZTY%2fzJguM9IJ6A%3d%3d"
    "&eb=mqrUEcbgUJW%252BCAVMNnT5lw%3d%3d"
)


class DillonCityAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("apiUrl", API_URL)
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        # Response is JS: var mwjsMemberData={...};...
        # Extract JSON object using raw_decode
        idx = html.index("{")
        json_text = html[idx:]
        decoder = json.JSONDecoder()
        data, _ = decoder.raw_decode(json_text)

        members = []
        for person in data.get("people", []):
            name = person.get("personName", "").strip()
            if not name:
                continue

            # Category text contains district/title info
            # e.g. "Mayor - Dillon District - 2023-2027"
            # e.g. "District 1 - 2025-2027"
            # e.g. "Mayor Pro Tem - District 2 - 2023-2027"
            cat_text = ""
            for cat in person.get("cats", []):
                cat_text = cat.get("ItemText", "")
                break

            title = self._parse_title(cat_text)
            email = person.get("personEmail", "") or ""
            phone = person.get("personPhone", "") or ""

            members.append({
                "name": name,
                "title": title,
                "email": email,
                "phone": phone,
            })

        # Sort by the order field from the API
        members.sort(key=self._sort_key)
        return members

    @staticmethod
    def _parse_title(cat_text: str) -> str:
        """Parse category text into a normalized title."""
        if not cat_text:
            return "Council Member"

        # "Mayor - Dillon District - 2023-2027"
        if re.match(r"Mayor\s*-", cat_text, re.IGNORECASE):
            if "pro tem" in cat_text.lower():
                district_match = re.search(r"District\s+(\d+)", cat_text)
                if district_match:
                    return f"Mayor Pro Tem, District {district_match.group(1)}"
                return "Mayor Pro Tem"
            return "Mayor"

        # "Mayor Pro Tem - District 2 - 2023-2027"
        if "pro tem" in cat_text.lower():
            district_match = re.search(r"District\s+(\d+)", cat_text)
            if district_match:
                return f"Mayor Pro Tem, District {district_match.group(1)}"
            return "Mayor Pro Tem"

        # "District N - YYYY-YYYY"
        district_match = re.search(r"District\s+(\d+)", cat_text)
        if district_match:
            return f"Council Member, District {district_match.group(1)}"

        return "Council Member"

    def get_contact(self) -> dict | None:
        from .base import normalize_phone
        # The API response has no phone; fetch the actual city page instead
        try:
            from bs4 import BeautifulSoup
            resp = requests.get(
                self.url or "https://cityofdillonsc.gov/citycouncil",
                headers={"User-Agent": USER_AGENT},
                timeout=30,
            )
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            # Prefer tel: links for reliable phone extraction
            phone = ""
            tel_link = soup.find("a", href=re.compile(r"^tel:"))
            if tel_link:
                raw = re.sub(r"^tel:\+?1?", "", tel_link["href"])
                phone = normalize_phone(raw)
            else:
                text = soup.get_text()
                match = re.search(r"\(?\d{3}\)?[\s.\-]*\d{3}[\s.\-]*\d{4}", text)
                phone = normalize_phone(match.group(0)) if match else ""
            return {
                "phone": phone,
                "email": "",
                "note": "City Hall - no individual council member contact info published",
            }
        except Exception:
            return None

    @staticmethod
    def _sort_key(member: dict) -> tuple:
        title = member["title"]
        if title == "Mayor":
            return (0, 0)
        if "Mayor Pro Tem" in title:
            match = re.search(r"District\s+(\d+)", title)
            return (0, 1, int(match.group(1)) if match else 0)
        match = re.search(r"District\s+(\d+)", title)
        if match:
            return (1, int(match.group(1)), 0)
        return (2, 0, 0)
