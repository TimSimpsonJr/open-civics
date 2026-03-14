"""Adapter for City of Anderson council members.

Scrapes the council contacts page which has a table with one <td>
per member. Each cell contains:
  - <strong>Seat N</strong> or <strong>Mayor</strong> (seat/title)
  - <strong>Mr./Mrs./Dr. Name</strong> (name with honorific)
  - Address, phone as plain text
  - <a href="mailto:..."> email link

The Mayor row spans all columns (colspan=4). Regular members are
in a 4-column layout. Vacant seats have no mailto link.

Note: The site has a broken SSL certificate. We must use verify=False.
The correct URL is /city-council-contacts/ (not /city-council/).
"""

import re

import requests
import urllib3
from bs4 import BeautifulSoup

from .base import BaseAdapter, normalize_phone

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"


class AndersonCityAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("url", self.url)
        resp = requests.get(
            url, headers={"User-Agent": USER_AGENT}, timeout=30, verify=False
        )
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []

        table = soup.find("table")
        if not table:
            raise ValueError("No table found on Anderson city contacts page")

        for cell in table.find_all("td"):
            text = cell.get_text(separator="\n", strip=True)
            lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

            if not lines:
                continue

            # Skip vacant seats
            if "Vacant" in text:
                continue

            # Must have an email link to be a valid member
            mailto = cell.find("a", href=re.compile(r"^mailto:", re.I))
            if not mailto:
                continue

            # Prefer link text over href (some hrefs are wrong)
            email_text = mailto.get_text(strip=True)
            if "@" in email_text:
                email = email_text
            else:
                email = mailto["href"][7:].strip()

            # Determine seat/title and name from <strong>/<b> tags
            seat = ""
            name = ""
            role_suffix = ""
            strongs = cell.find_all(["strong", "b"])

            for s in strongs:
                s_text = s.get_text(separator=" ", strip=True)
                s_text = s_text.replace("\xa0", " ").strip()

                if not s_text or "@" in s_text or s_text == "Vacant":
                    continue

                # Check for seat/title label
                if re.match(r"^(Seat\s+\d+|At\s+Large\s+Seat\s+\d+)$", s_text, re.I):
                    seat = s_text
                    continue

                # Mayor cell: "Mayor Firstname Lastname" all in one <strong>
                mayor_match = re.match(r"^Mayor\s+(.+)", s_text, re.I)
                if mayor_match:
                    seat = "Mayor"
                    name = mayor_match.group(1).strip()
                    continue

                if s_text.lower() == "mayor":
                    seat = "Mayor"
                    continue

                # This should be the name
                if not name:
                    name = s_text

            if not name:
                continue

            # Strip honorifics
            name = re.sub(r"^(Mr\.|Mrs\.|Ms\.|Dr\.)\s+", "", name).strip()
            # Strip title suffixes like "/ Mayor Pro Tem"
            if "/" in name:
                parts = name.split("/", 1)
                name = parts[0].strip()
                role_suffix = parts[1].strip()

            # Phone: find phone pattern in text
            phone = ""
            for line in lines:
                # Match various phone formats
                ph = re.search(r"\(?\d{3}\)?[\s\-\.]*\d{3}[\s\-\.]*\d{4}", line)
                if ph and "fax" not in line.lower():
                    phone = normalize_phone(ph.group())
                    break

            # Build title
            title = self._build_title(seat, role_suffix)

            members.append({
                "name": name,
                "title": title,
                "email": email,
                "phone": phone,
            })

        members.sort(key=self._sort_key)
        return members

    @staticmethod
    def _build_title(seat: str, role_suffix: str) -> str:
        if role_suffix and "mayor pro" in role_suffix.lower():
            seat_match = re.search(r"Seat\s+(\d+)", seat, re.I)
            if seat_match:
                return f"Mayor Pro Tem, Seat {seat_match.group(1)}"
            return "Mayor Pro Tem"

        if seat.lower() == "mayor":
            return "Mayor"

        seat_match = re.search(r"Seat\s+(\d+)", seat, re.I)
        at_large = "at large" in seat.lower()

        if seat_match:
            num = seat_match.group(1)
            if at_large:
                return f"Council Member, At-Large Seat {num}"
            return f"Council Member, Seat {num}"

        return "Council Member"

    @staticmethod
    def _sort_key(member: dict) -> tuple:
        title = member.get("title", "")
        if title == "Mayor":
            return (0, 0)
        if "Mayor Pro" in title:
            return (0, 1)
        at_large = "At-Large" in title
        seat_match = re.search(r"Seat\s+(\d+)", title)
        if seat_match:
            return (2 if at_large else 1, int(seat_match.group(1)))
        return (3, 0)
