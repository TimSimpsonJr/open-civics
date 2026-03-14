"""Adapter for Columbia City Council members.

Scrapes the WordPress-powered Columbia City Council site. The main page
lists members in "team-member" divs with titles like "Councilman Name"
or "Mayor Name" linking to individual profile pages.

Each profile page contains:
  - District info (e.g., "District II") or "At-Large" in a heading
  - Email as a mailto: link
  - Phone as a tel: link or in page text

The adapter scrapes the main page for the member list, then fetches each
profile page for district/email/phone details. The mayor links to
mayor.columbiasc.gov which is handled separately.
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter, normalize_phone

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"
PAGE_URL = "https://citycouncil.columbiasc.gov/"


class ColumbiaAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("url", PAGE_URL)
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []
        seen = set()

        for tm in soup.find_all("div", class_="team-member"):
            h4 = tm.find("h4")
            if not h4:
                continue
            link = h4.find("a")
            if not link:
                continue

            raw_name = h4.get_text(strip=True)
            href = link.get("href", "")

            # Deduplicate
            if href in seen:
                continue
            seen.add(href)

            # Detect mayor (links to mayor.columbiasc.gov)
            is_mayor = "mayor." in href

            # Parse "Councilman Edward H. McDowell, Jr." -> name
            name = raw_name
            for prefix in ["Councilman ", "Councilwoman ", "Council Member ",
                           "Mayor "]:
                if name.startswith(prefix):
                    name = name[len(prefix):]
                    break

            if is_mayor:
                # Fetch mayor page for email/phone
                email, phone = self._fetch_mayor(href)
                title = "Mayor"
            else:
                # Fetch profile page for district, email, and phone
                district, email, phone = self._fetch_profile(href)
                title = "Council Member"
                if district:
                    title = f"Council Member, {district}"

            members.append({
                "name": name.strip(),
                "title": title,
                "email": email,
                "phone": normalize_phone(phone) if phone else "",
            })

        members.sort(key=self._sort_key)
        return members

    def _fetch_mayor(self, url: str) -> tuple[str, str]:
        """Fetch the mayor's page and extract email and phone."""
        try:
            resp = requests.get(
                url, headers={"User-Agent": USER_AGENT}, timeout=30
            )
            resp.raise_for_status()
        except requests.RequestException:
            return ("", "")

        soup = BeautifulSoup(resp.text, "html.parser")

        email = ""
        mailto = soup.find("a", href=lambda h: h and h.startswith("mailto:"))
        if mailto:
            email = mailto["href"].replace("mailto:", "").strip()

        phone = ""
        tel = soup.find("a", href=lambda h: h and h.startswith("tel:"))
        if tel:
            phone = tel.get_text(strip=True)

        return (email, phone)

    def _fetch_profile(self, url: str) -> tuple[str, str, str]:
        """Fetch a profile page and extract district, email, and phone."""
        try:
            resp = requests.get(
                url, headers={"User-Agent": USER_AGENT}, timeout=30
            )
            resp.raise_for_status()
        except requests.RequestException:
            return ("", "", "")

        soup = BeautifulSoup(resp.text, "html.parser")

        # Find email from mailto link
        email = ""
        mailto = soup.find("a", href=lambda h: h and h.startswith("mailto:"))
        if mailto:
            email = mailto["href"].replace("mailto:", "").strip()

        # Find phone from tel: link or text
        phone = ""
        tel = soup.find("a", href=lambda h: h and h.startswith("tel:"))
        if tel:
            phone = tel.get_text(strip=True)
        else:
            text = soup.get_text()
            match = re.search(r"\(?\d{3}\)?[\s.\-]*\d{3}[\s.\-]*\d{4}", text)
            if match:
                phone = match.group(0)

        # Find district from text like "District II" or "At-Large"
        district = ""
        text = soup.get_text(separator="\n", strip=True)
        for line in text.split("\n"):
            line = line.strip()
            # Match "District II", "District IV", etc.
            if re.match(r"^District\s+[IVX]+$", line):
                num = self._roman_to_arabic(line.split()[-1])
                district = f"District {num}"
                break
            if line == "At-Large":
                district = "At-Large"
                break

        return (district, email, phone)

    @staticmethod
    def _roman_to_arabic(roman: str) -> int:
        """Convert a simple Roman numeral to integer."""
        values = {"I": 1, "V": 5, "X": 10}
        result = 0
        prev = 0
        for ch in reversed(roman.upper()):
            val = values.get(ch, 0)
            if val < prev:
                result -= val
            else:
                result += val
            prev = val
        return result

    @staticmethod
    def _sort_key(member: dict) -> tuple:
        title = member["title"]
        if title == "Mayor":
            return (0, 0, "")
        match = re.search(r"District\s+(\d+)", title)
        if match:
            return (1, int(match.group(1)), "")
        if "At-Large" in title:
            return (2, 0, member["name"])
        return (3, 0, member["name"])
