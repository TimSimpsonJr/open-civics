"""Adapter for Lexington County Council members.

Scrapes the Drupal-powered Lexington County site. Council member data is in
centered paragraphs with bold labels. All districts are siblings within a
single container div, so parsing must be done linearly:

  <p><strong>District N - Description</strong></p>
  <p><strong>Council Member:</strong><br/>Name</p>
  ... (Term, Occupation, Address paragraphs) ...
  <p><strong>Telephone:</strong><br/>(NNN) NNN-NNNN</p>
  ... (FAX paragraph) ...
  <p><strong>EMAIL:</strong><br/><a href="mailto:email">email</a></p>
  ... next district ...

The actual member listing is at /county-council/council-members.
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"


class LexingtonCountyAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("url", self.url)
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []

        # Find the container with all the mailto links
        mailto_links = soup.find_all(
            "a", href=re.compile(r"^mailto:", re.IGNORECASE)
        )
        if not mailto_links:
            return []

        # Walk up to find the common container
        container = mailto_links[0]
        for parent in mailto_links[0].parents:
            if parent.name == "body":
                container = parent
                break
            all_mailtos = parent.find_all(
                "a", href=re.compile(r"^mailto:", re.IGNORECASE)
            )
            if len(all_mailtos) >= 9:
                container = parent
                break

        # Collect all <p> tags in order from the container
        paragraphs = container.find_all("p")

        # Parse linearly: group paragraphs between "District N -" headers
        current = None
        for p in paragraphs:
            strong = p.find("strong")
            if not strong:
                continue
            label = strong.get_text(strip=True)

            # New district header
            district_match = re.match(r"District\s+(\d+)\s*-", label)
            if district_match:
                # Save previous member
                if current and current.get("name"):
                    members.append(current)
                current = {
                    "district": district_match.group(1),
                    "name": "",
                    "title": "",
                    "email": "",
                    "phone": "",
                }
                continue

            if current is None:
                continue

            if label in ("Council Member:", "Council Member"):
                # Name and possible title follow in text after the strong tag
                p_text = p.get_text(separator="\n", strip=True)
                lines = [
                    l.strip() for l in p_text.split("\n")
                    if l.strip() and l.strip() not in ("Council Member:", "Council Member")
                ]
                if lines:
                    current["name"] = lines[0]
                # Check for Chairman/Vice Chairman on subsequent lines
                for line in lines[1:]:
                    if "Vice" in line and "Chair" in line:
                        current["_role"] = "Vice Chairman"
                    elif "Chair" in line:
                        current["_role"] = "Chairman"

            elif label in ("Telephone:", "Phone:"):
                p_text = p.get_text()
                match = re.search(
                    r"\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]\d{4}", p_text
                )
                if match:
                    current["phone"] = match.group(0)

            elif label in ("EMAIL:", "Email:"):
                mailto = p.find(
                    "a", href=re.compile(r"^mailto:", re.IGNORECASE)
                )
                if mailto:
                    email = mailto["href"][7:].strip()
                    # Skip generic council email
                    if not self._is_generic_email(email):
                        current["email"] = email

        # Don't forget the last member
        if current and current.get("name"):
            members.append(current)

        # Build final records with proper titles
        result = []
        for m in members:
            district = m["district"]
            role = m.pop("_role", "")
            if role:
                title = f"{role}, District {district}"
            else:
                title = f"Council Member, District {district}"

            # Filter admin entries
            if any(term in m["name"].lower() for term in [
                "clerk", "administrator", "manager", "secretary"
            ]):
                continue

            result.append({
                "name": m["name"],
                "title": title,
                "email": m["email"],
                "phone": m["phone"],
            })

        result.sort(key=lambda r: self._district_sort_key(r["title"]))
        return result

    @staticmethod
    def _is_generic_email(email: str) -> bool:
        local = email.split("@")[0].lower()
        generic = ["info", "council", "clerk", "webmaster", "admin",
                    "contact", "help", "support", "general", "office",
                    "countycouncil"]
        return local in generic

    @staticmethod
    def _district_sort_key(title: str) -> int:
        match = re.search(r"District\s+(\d+)", title)
        return int(match.group(1)) if match else 0
