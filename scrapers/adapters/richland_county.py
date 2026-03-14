"""Adapter for Richland County Council members.

Scrapes a Granicus govAccess page using the structured "elected officials"
widget with semantic CSS classes like .contact-email and .contact-phone.
"""

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter, normalize_phone

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"


class RichlandCountyAdapter(BaseAdapter):

    def fetch(self) -> str:
        url = self.config.get("url", self.url)
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []

        for article in soup.find_all("article"):
            header = article.find("header")
            if not header:
                continue

            # Name is in the <a> tag inside header
            link = header.find("a")
            if not link:
                continue
            name = link.get_text(strip=True)

            # Title is remaining text in header after the link
            header_text = header.get_text(separator="\n", strip=True)
            title_lines = [
                line.strip() for line in header_text.split("\n")
                if line.strip() and line.strip() != name
            ]
            title = ", ".join(title_lines) if title_lines else "Council Member"

            # Email from li.contact-email
            email = ""
            email_li = article.find("li", class_="contact-email")
            if email_li:
                email_link = email_li.find("a", href=True)
                if email_link:
                    email = email_link["href"].replace("mailto:", "").strip()

            # Phone from li.contact-phone
            phone = ""
            phone_li = article.find("li", class_="contact-phone")
            if phone_li:
                phone_link = phone_li.find("a", href=True)
                if phone_link:
                    phone = phone_link.get_text(strip=True)
                else:
                    phone = phone_li.get_text(strip=True)
            phone = normalize_phone(phone) if phone else ""

            members.append({
                "name": name,
                "title": title,
                "email": email,
                "phone": phone,
            })

        return members
