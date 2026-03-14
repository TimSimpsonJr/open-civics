"""Adapter for Anderson County Council members.

Scrapes a WordPress site with Bootstrap card layout. Council member data
is split across two HTML structures that are merged by name:

1. Card elements (visible on page):
   - h4.card-title: "Hon. Name"
   - sibling p/span: "District N"
   - h6.text-blue-medium: role (e.g. "Council Member | Chairman")

2. Modal dialogs (expanded bio/contact):
   - h5.modal-title: "Hon. Name"
   - <p><strong>Contact</strong>: phone | email</p>
   - or mailto: links for email
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"


class AndersonCountyAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("url", self.url)
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")

        # Step 1: Extract name -> (district, role) from card titles
        name_info = {}
        for h4 in soup.find_all("h4", class_="card-title"):
            raw_name = h4.get_text(strip=True)
            if not raw_name.startswith("Hon."):
                continue
            name = re.sub(r"^Hon\.?\s+", "", raw_name).strip()

            # District from next sibling p or span
            next_el = h4.find_next_sibling(["p", "span"])
            district = ""
            if next_el:
                dt = next_el.get_text(strip=True)
                dm = re.match(r"District\s+(.+)", dt, re.I)
                if dm:
                    district = dm.group(1).strip()

            # Role from h6 in parent container
            parent = h4.parent
            role = "Council Member"
            if parent:
                h6 = parent.find(
                    "h6", class_=lambda c: c and "text-blue" in str(c)
                )
                if h6:
                    r = h6.get_text(strip=True)
                    if r:
                        role = r

            # Keep first occurrence with district info
            if name not in name_info:
                name_info[name] = {"district": district, "role": role}
            elif district and not name_info[name]["district"]:
                name_info[name]["district"] = district

        # Step 2: Extract contact info from modal dialogs
        name_contact = {}
        for modal in soup.find_all("div", class_="modal"):
            modal_id = modal.get("id", "")
            if not modal_id.startswith("councilModalCenter"):
                continue
            title_el = modal.find("h5", class_="modal-title")
            if not title_el:
                continue
            name = re.sub(
                r"^Hon\.?\s+", "", title_el.get_text(strip=True)
            ).strip()

            body = modal.find("div", class_="modal-body")
            email = ""
            phone = ""
            if body:
                # Email from mailto link
                email_link = body.find(
                    "a", href=lambda h: h and h.startswith("mailto:")
                )
                if email_link:
                    email = email_link["href"][7:].strip()
                else:
                    # Fallback: email in text
                    text = body.get_text()
                    em = re.search(
                        r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})",
                        text,
                    )
                    if em:
                        email = em.group(1)

                # Phone from text
                text = body.get_text()
                pm = re.search(
                    r"\(?(\d{3})\)?[\s.\-]*(\d{3})[\s.\-]*(\d{4})", text
                )
                if pm:
                    phone = (
                        f"({pm.group(1)}) {pm.group(2)}-{pm.group(3)}"
                    )

            name_contact[name] = {"email": email, "phone": phone}

        # Step 3: Merge card info with contact info
        members = []
        for name, info in name_info.items():
            contact = name_contact.get(name, {})
            district = info["district"]
            role = info["role"]

            # Normalize role separators: "Council Member | Chairman"
            if "|" in role:
                parts = [p.strip() for p in role.split("|")]
                role = ", ".join(parts)

            if district:
                title = f"{role}, District {district}"
            else:
                title = role

            members.append({
                "name": name,
                "title": title,
                "email": contact.get("email", ""),
                "phone": contact.get("phone", ""),
            })

        return members
