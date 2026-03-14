"""Generic adapter for sites where council members are in an HTML table.

Auto-detects column roles (name, title, email, phone, district) from
header text. Handles mailto links in cells, concatenated name+email text,
and department-based filtering.

adapterConfig fields:
  - contentSelector: (optional) CSS selector for the table container
  - departmentFilter: (optional) only include rows where department column
    matches this value (e.g., "County Council")
  - memberFilter: (optional) list of title substrings to EXCLUDE
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"

# Map header keywords to column roles
HEADER_PATTERNS = {
    "name": re.compile(r"(name|member|representative|staff|council)", re.I),
    "title": re.compile(r"(title|position|role|office)", re.I),
    "email": re.compile(r"(email|e-mail)", re.I),
    "phone": re.compile(r"(phone|telephone|tel\.?$)", re.I),
    "district": re.compile(r"(district|ward|seat)", re.I),
    "department": re.compile(r"(department|dept)", re.I),
}

DEFAULT_EXCLUDE = ["clerk", "administrator", "manager", "secretary",
                   "treasurer", "attorney", "director", "assistant"]


class TableAdapter(BaseAdapter):

    def fetch(self) -> str:
        resp = requests.get(
            self.url, headers={"User-Agent": USER_AGENT}, timeout=30
        )
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")

        custom_sel = self.config.get("contentSelector")
        container = soup.select_one(custom_sel) if custom_sel else soup

        # Find the best table (most rows with data)
        best_table = None
        best_rows = 0
        for table in (container or soup).find_all("table"):
            rows = table.find_all("tr")
            if len(rows) > best_rows:
                best_rows = len(rows)
                best_table = table

        if not best_table or best_rows < 2:
            raise ValueError(f"No usable table found for {self.id}")

        rows = best_table.find_all("tr")

        # Detect column roles from header row
        header_cells = rows[0].find_all(["th", "td"])
        col_map = self._detect_columns(header_cells)

        if "name" not in col_map:
            raise ValueError(f"Cannot detect name column in table for {self.id}")

        dept_filter = self.config.get("departmentFilter", "").lower()
        exclude_terms = self.config.get("memberFilter", DEFAULT_EXCLUDE)
        members = []

        for row in rows[1:]:
            cells = row.find_all("td")
            if len(cells) < 2:
                continue

            record = self._extract_row(cells, col_map)

            # Filter by department if configured
            if dept_filter and record.get("_department", "").lower() != dept_filter:
                continue

            # Filter admin titles
            if self._should_exclude(record, exclude_terms):
                continue

            if record.get("name"):
                title = record.get("title", "Council Member")
                # "District 6" -> "Council Member, District 6"
                if re.match(r"^District\s+\d+$", title, re.I):
                    title = f"Council Member, {title}"
                members.append({
                    "name": record["name"],
                    "title": title or "Council Member",
                    "email": record.get("email", ""),
                    "phone": record.get("phone", ""),
                })

        return members

    def _detect_columns(self, headers: list) -> dict:
        col_map = {}
        for i, cell in enumerate(headers):
            text = cell.get_text(strip=True)
            for role, pattern in HEADER_PATTERNS.items():
                if pattern.search(text) and role not in col_map:
                    col_map[role] = i
                    break
        return col_map

    def _extract_row(self, cells: list, col_map: dict) -> dict:
        record = {}

        # Name
        name_idx = col_map.get("name", 0)
        if name_idx < len(cells):
            cell = cells[name_idx]
            name = cell.get_text(strip=True)
            # Check for mailto in name cell (concatenated name+email)
            mailto = cell.find("a", href=re.compile(r"^mailto:", re.I))
            if mailto:
                email = mailto["href"][7:].strip()
                # If name text contains the email, strip it
                if email.lower() in name.lower():
                    name = re.sub(re.escape(email), "", name, flags=re.I).strip()
                record["email"] = email
            # Reverse "Last, First" format (but not "John Smith, Jr." or titles)
            if name.count(",") == 1:
                left, right = name.split(",", 1)
                right = right.strip()
                # Skip if right side is a suffix (Jr., Sr., III, etc.)
                if not re.match(r"^(Jr|Sr|II|III|IV|Esq)\.?$", right, re.I):
                    # Only reverse if both parts start with uppercase
                    if left[0].isupper() and right[0].isupper() and " " not in left:
                        name = f"{right} {left}"
            # Clean honorifics
            name = re.sub(r"^(Mr\.?|Mrs\.?|Ms\.?|Dr\.?)\s+", "", name)
            # Strip trailing title suffixes
            name = re.sub(r",\s*(Chairman|Vice[- ]?Chair(?:man)?|Council\s*(?:man|woman|member))\s*$",
                          "", name, flags=re.I).strip()
            record["name"] = name

        # Title/Position
        title_idx = col_map.get("title")
        if title_idx is not None and title_idx < len(cells):
            record["title"] = cells[title_idx].get_text(strip=True)

        # District
        dist_idx = col_map.get("district")
        if dist_idx is not None and dist_idx < len(cells):
            dist_raw = cells[dist_idx].get_text(strip=True)
            if dist_raw:
                # Normalize: "District 5" -> "5", "5" -> "5"
                dist_num = re.sub(r"^District\s+", "", dist_raw, flags=re.I).strip()
                title = record.get("title", "")
                if not title or re.match(r"^District\s+\d+$", title, re.I):
                    record["title"] = f"Council Member, District {dist_num}"
                elif "district" not in title.lower():
                    record["title"] = f"{title}, District {dist_num}"

        # Email (if not already found in name cell)
        email_idx = col_map.get("email")
        if email_idx is not None and email_idx < len(cells) and "email" not in record:
            cell = cells[email_idx]
            mailto = cell.find("a", href=re.compile(r"^mailto:", re.I))
            if mailto:
                record["email"] = mailto["href"][7:].strip()
            else:
                text = cell.get_text(strip=True)
                if "@" in text:
                    record["email"] = text

        # Phone
        phone_idx = col_map.get("phone")
        if phone_idx is not None and phone_idx < len(cells):
            record["phone"] = cells[phone_idx].get_text(strip=True)

        # Department (for filtering)
        dept_idx = col_map.get("department")
        if dept_idx is not None and dept_idx < len(cells):
            record["_department"] = cells[dept_idx].get_text(strip=True)

        # Fallback: look for mailto/tel links in any cell
        if "email" not in record:
            for cell in cells:
                mailto = cell.find("a", href=re.compile(r"^mailto:", re.I))
                if mailto:
                    record["email"] = mailto["href"][7:].strip()
                    break
        if "phone" not in record:
            for cell in cells:
                tel = cell.find("a", href=re.compile(r"^tel:"))
                if tel:
                    record["phone"] = tel.get_text(strip=True)
                    break

        return record

    @staticmethod
    def _should_exclude(record: dict, exclude_terms: list) -> bool:
        for field in ("name", "title"):
            text = record.get(field, "").lower()
            if any(term.lower() in text for term in exclude_terms):
                return True
        return False
