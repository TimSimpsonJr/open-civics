"""Generic adapter for government sites with mailto links.

Works on any HTML page where council members have:
  - Names in bold/strong/heading tags
  - Email addresses as mailto: links
  - Optionally phone numbers as tel: links or plain text

Extends the Revize adapter's marker-based parsing with wider content
area detection to handle WordPress, Drupal, custom sites, etc.

adapterConfig fields:
  - contentSelector: (optional) CSS selector for the content area
  - memberFilter: (optional) list of title substrings to EXCLUDE
    (default: ["clerk", "administrator", "manager", etc.])
  - mayorUrl: (optional) URL for a separate mayor page; if set and no
    Mayor is found on the main page, fetches this page and extracts
    the mayor's name, email, and phone
"""

import re

import requests
from bs4 import BeautifulSoup

from .revize import RevizeAdapter

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"


class GenericMailtoAdapter(RevizeAdapter):
    """Generic scraper for any page with mailto links paired with names."""

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")

        # Try custom selector first, then a wide range of common containers
        custom = self.config.get("contentSelector")
        if custom:
            content = soup.select_one(custom)
        else:
            content = None

        if not content:
            content = (
                # Revize
                soup.find("div", class_="fr-view")
                or soup.find("div", id="divContent")
                or soup.find("div", class_="cms-area")
                # WordPress
                or soup.find("div", class_="entry-content")
                or soup.find("div", class_="et_pb_section")  # Divi
                or soup.find("div", class_="elementor-widget-wrap")
                or soup.find("div", class_="wpb_wrapper")
                # Drupal
                or soup.find("div", class_="field--name-body")
                or soup.find("div", class_="node__content")
                or soup.find("div", class_="view-content")
                # Granicus / generic
                or soup.find("div", class_="content_area")
                or soup.find("div", id="content")
                or soup.find("div", class_="content")
                or soup.find("article")
                or soup.find("main")
                or soup.body
            )

        if not content:
            raise RuntimeError(f"Could not find content area for {self.id}")

        # Use parent class's marker-based parsing logic
        # Temporarily swap the content in, call the parent's parse with a
        # modified HTML where we only keep the content area
        html_subset = str(content)
        members = super().parse(f"<body>{html_subset}</body>")

        # If a mayorUrl is configured and no Mayor was found, fetch it
        mayor_url = self.config.get("mayorUrl")
        if mayor_url and not any(
            m.get("title", "").startswith("Mayor") for m in members
        ):
            mayor = self._fetch_mayor_page(mayor_url)
            if mayor:
                members.insert(0, mayor)
                members.sort(key=self._sort_key)

        return members

    @staticmethod
    def _fetch_mayor_page(url: str) -> dict | None:
        """Fetch a separate mayor page and extract name, email, phone."""
        try:
            resp = requests.get(
                url, headers={"User-Agent": USER_AGENT}, timeout=30
            )
            resp.raise_for_status()
        except requests.RequestException:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        # Strategy for finding the mayor's name:
        # 1. Look for "Mayor FirstName LastName" in any heading or bold text
        # 2. Look for a person-like name in <strong>/<b> tags
        # 3. Fall back to "Mayor FirstName LastName" in body text
        name = ""

        # Pass 1: look for "Mayor Name" pattern in headings and bold text
        for tag in soup.find_all(["h1", "h2", "h3", "h4", "strong", "b"]):
            text = tag.get_text(strip=True)
            if not text or len(text) < 3:
                continue
            match = re.match(r"^Mayor\s+(.+)", text, re.I)
            if match:
                name = match.group(1).strip()
                break

        # Pass 2: look for a person name in <strong>/<b> (not headings)
        if not name:
            for tag in soup.find_all(["strong", "b"]):
                text = tag.get_text(strip=True)
                if not text or len(text) < 5 or len(text) > 60:
                    continue
                # Must have at least two words and look like a name
                words = text.split()
                if len(words) >= 2 and words[0][0].isupper():
                    # Skip generic phrases
                    lower = text.lower()
                    if any(skip in lower for skip in [
                        "contact", "office", "phone", "address",
                        "email", "fax", "physical", "mailing",
                    ]):
                        continue
                    name = text
                    break

        # Pass 3: extract "Mayor FirstName LastName" from body text
        if not name:
            page_text = soup.get_text(separator=" ", strip=True)
            match = re.search(
                r"Mayor\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)", page_text
            )
            if match:
                name = match.group(1).strip()

        email = ""
        for a in soup.find_all("a", href=re.compile(r"mailto:", re.I)):
            addr = a["href"][7:].strip().rstrip("?")
            if addr and "@" in addr:
                # Skip generic emails
                local = addr.split("@")[0].lower()
                if local not in ("info", "council", "clerk", "webmaster",
                                 "admin", "contact", "help", "support"):
                    email = addr
                    break

        phone = ""
        for a in soup.find_all("a", href=re.compile(r"^tel:", re.I)):
            phone = a.get_text(strip=True)
            break
        if not phone:
            # Try to find phone in text
            text = soup.get_text()
            phone_match = re.search(
                r"\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]\d{4}", text
            )
            if phone_match:
                phone = phone_match.group(0)

        if not name:
            return None

        return {
            "name": name,
            "title": "Mayor",
            "email": email,
            "phone": phone,
        }
