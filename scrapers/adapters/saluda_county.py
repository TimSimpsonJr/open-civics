"""Adapter for Saluda County Council members.

Scrapes a Drupal site where council members are listed in a simple
freeform HTML pattern within paragraph tags:
  <p>
    <strong>District No. 1</strong><br/>
    Name<br/>
    <a href="mailto:email">email</a>
  </p>

Some paragraphs contain multiple members separated by <br/> tags.
The first entry uses "At Large" instead of a district number and
includes "Chairman" in the name.
"""

import re

import requests
from bs4 import BeautifulSoup, NavigableString

from .base import BaseAdapter

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"


class SaludaCountyAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("url", self.url)
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []

        # Find all <strong> tags that contain district/seat labels
        for strong in soup.find_all("strong"):
            text = strong.get_text(strip=True)
            if not (
                re.match(r"District\s+No\.\s+\d+", text, re.I)
                or re.match(r"At\s+Large", text, re.I)
            ):
                continue

            # Determine district label
            dist_match = re.search(r"District\s+No\.\s+(\d+)", text, re.I)
            if dist_match:
                district = f"District {dist_match.group(1)}"
            else:
                district = "At Large"

            # Find the name: text node(s) between the strong tag and
            # the next mailto link, within the same parent <p>
            parent = strong.parent
            if not parent:
                continue

            # Walk siblings after the strong tag to find name and email
            name = ""
            email = ""

            # Collect text nodes and links after this strong tag
            found_strong = False
            for child in parent.children:
                if child is strong:
                    found_strong = True
                    continue
                if not found_strong:
                    # Check if this is another strong tag (next member in same p)
                    if hasattr(child, "name") and child.name == "strong":
                        found_strong = False
                    continue

                # Stop at next strong tag (next member)
                if hasattr(child, "name") and child.name == "strong":
                    break

                if hasattr(child, "name") and child.name == "a":
                    href = child.get("href", "")
                    if href.startswith("mailto:"):
                        email = href[7:].strip()
                    elif "@" in child.get_text(strip=True):
                        # Some links lack mailto: prefix
                        email = child.get_text(strip=True)
                    break
                elif hasattr(child, "name") and child.name == "br":
                    continue
                elif isinstance(child, NavigableString):
                    t = child.strip()
                    if t and not name:
                        name = t
                elif hasattr(child, "name") and child.name == "span":
                    t = child.get_text(strip=True)
                    if t and not name:
                        name = t

            if not name:
                continue

            # Extract title from name (e.g., "James L. Moore, Chairman")
            title = f"Council Member, {district}"
            title_match = re.search(
                r",\s*(Chairman|Vice\s+Chairman|Chair)\s*$", name, re.I
            )
            if title_match:
                role = title_match.group(1).strip()
                name = name[: title_match.start()].strip()
                title = f"{role}, {district}"

            members.append({
                "name": name,
                "title": title,
                "email": email,
                "phone": "",
            })

        return members
