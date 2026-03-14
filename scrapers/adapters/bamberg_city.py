"""Adapter for City of Bamberg council members.

Scrapes a CivicLive/ConnectSuite staff directory widget. The page
renders member cards client-side from a JSON API, so we hit the
API directly:
  - /sys/api/directory?widgetId={id}&viewId=directory-photo-bio&...
  - Returns JSON with NameLastFirst, NameFirstLast, JobTitle, PhoneNumber

The widget ID is extracted from the page HTML (data-widget-id attribute
on div.cs-userlist-bios) or can be set in adapterConfig.widgetId.

Note: This site does not expose individual email addresses. All
EmailAddress fields are null; members are contacted via a web form.
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter, normalize_phone

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"

DEFAULT_WIDGET_ID = "8d7cdc6630b84929b958d9aa3934ad17"
DEFAULT_VIEW_ID = "directory-photo-bio"


class BambergCityAdapter(BaseAdapter):
    """Scraper for City of Bamberg council members via CivicLive API."""

    def fetch(self) -> str:
        """Fetch JSON from the CivicLive directory API.

        We first try to get the widget ID from the page HTML, falling
        back to the hardcoded default. Then hit the JSON API.
        """
        url = self.config.get("url", self.url)
        widget_id = self.config.get("widgetId", "")

        if not widget_id:
            # Try to extract from the page
            try:
                resp = requests.get(
                    url, headers={"User-Agent": USER_AGENT}, timeout=30
                )
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")
                widget_el = soup.find(attrs={"data-widget-id": True})
                if widget_el:
                    widget_id = widget_el["data-widget-id"]
            except Exception:
                pass

        if not widget_id:
            widget_id = DEFAULT_WIDGET_ID

        # Build API URL from the page URL's origin
        from urllib.parse import urlparse
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"

        view_id = self.config.get("viewId", DEFAULT_VIEW_ID)
        api_url = (
            f"{base}/sys/api/directory"
            f"?widgetId={widget_id}"
            f"&viewId={view_id}"
            f"&itemCount=50"
            f"&pageNum=0"
            f"&pageSize=50"
            f"&searchStr="
        )

        resp = requests.get(
            api_url, headers={"User-Agent": USER_AGENT}, timeout=30
        )
        resp.raise_for_status()
        return resp.text

    def parse(self, json_text: str) -> list[dict]:
        import json
        data = json.loads(json_text)

        members = []

        for item in data:
            dept = (item.get("Department") or "").strip()
            if "council" not in dept.lower() and "mayor" not in dept.lower():
                continue

            # Name: prefer NameLastFirst ("Last, First") for clean parsing
            name_lf = (item.get("NameLastFirst") or "").strip()
            name_fl = (item.get("NameFirstLast") or "").strip()

            if name_lf and "," in name_lf:
                parts = name_lf.split(",", 1)
                name = f"{parts[1].strip()} {parts[0].strip()}"
            else:
                name = name_fl

            if not name:
                continue

            # District: often appended to NameFirstLast like "Bobbi Bunch District 4"
            district = ""
            dist_match = re.search(r"District\s+(\d+)", name_fl, re.I)
            if dist_match:
                district = dist_match.group(1)
                # Clean district from name if it leaked in
                name = re.sub(r"\s+District\s+\d+", "", name, flags=re.I).strip()

            # Title
            job_title = (item.get("JobTitle") or "").strip()
            title = self._build_title(job_title, district)

            # Email (usually null for this site)
            email = (item.get("EmailAddress") or "").strip()

            # Phone
            phone = normalize_phone(item.get("PhoneNumber") or "")

            members.append({
                "name": name,
                "title": title,
                "email": email,
                "phone": phone,
            })

        members.sort(key=self._sort_key)
        return members

    @staticmethod
    def _build_title(job_title: str, district: str) -> str:
        lower = job_title.lower() if job_title else ""

        if "mayor pro" in lower:
            if district:
                return f"Mayor Pro Tem, District {district}"
            return "Mayor Pro Tem"

        if lower == "mayor":
            return "Mayor"

        if district:
            if "council" in lower or not job_title:
                return f"Council Member, District {district}"
            return f"{job_title}, District {district}"

        if job_title:
            return job_title

        return "Council Member"

    @staticmethod
    def _sort_key(member: dict) -> tuple:
        title = member.get("title", "")
        if "Mayor" in title and "Pro Tem" not in title:
            return (0, 0)
        if "Mayor Pro" in title:
            return (0, 1)
        dist_match = re.search(r"District\s+(\d+)", title)
        if dist_match:
            return (1, int(dist_match.group(1)))
        return (2, 0)
