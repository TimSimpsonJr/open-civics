"""Reusable adapter for CivicPlus-powered government websites.

CivicPlus is a platform used by many SC county/city websites. This adapter
scrapes council member data from the CivicPlus Staff Directory page, which
presents a table of Name, Title, Email, and Phone for each department.

Strategy:
  1. Fetch the council landing page to discover the directory department ID
     (from the sidebar "Directory" link: /directory.aspx?did=N)
  2. Fetch the directory page /directory.aspx?did=N
  3. Parse the staff table for name, title, email, and phone
  4. Filter out non-council members (e.g., Clerk) and normalize titles

Email obfuscation:
  CivicPlus directory pages hide email addresses behind inline JavaScript
  using document.write(). The pattern is:
      var w = "localpart";
      var x = "domain.org";
  The adapter extracts these variables and reconstructs the email address.

Cloudflare note:
  Some CivicPlus sites (e.g., spartanburgcounty.org) use Cloudflare bot
  protection on their .org domain. The same content is often available on
  a .gov domain without Cloudflare. The adapter follows redirects, which
  typically resolves .org -> .gov automatically. If the base URL is blocked,
  the adapter tries the .gov variant.

adapterConfig fields:
  - baseUrl: the site root, e.g., "https://spartanburgcounty.org"
  - councilPageId: the CivicPlus page ID for the council landing page
  - directoryDeptId: (optional) the directory department ID; auto-discovered
    from the council page if not provided
  - memberFilter: (optional) list of title substrings to EXCLUDE from results
    (default: ["clerk"])
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"

# Titles containing these substrings (case-insensitive) are excluded
# from the results by default. Override via adapterConfig.memberFilter.
DEFAULT_EXCLUDE = ["clerk"]


class CivicPlusAdapter(BaseAdapter):
    """Scraper for CivicPlus-powered government council directories."""

    def fetch(self) -> str:
        """Fetch the staff directory page for the council department.

        Steps:
          1. Resolve the base URL (follow redirects past Cloudflare)
          2. Fetch the council landing page to discover the directory dept ID
          3. Fetch the directory page and return its HTML

        Returns the directory page HTML for parse().
        """
        base_url = self.config.get("baseUrl", "").rstrip("/")
        page_id = self.config.get("councilPageId", "")
        dir_dept_id = self.config.get("directoryDeptId", "")

        if not base_url or not page_id:
            raise RuntimeError(
                "CivicPlus adapter requires adapterConfig with "
                "'baseUrl' and 'councilPageId'"
            )

        headers = {"User-Agent": USER_AGENT}

        # Step 1: Resolve the base URL by fetching the council page.
        # This follows redirects (e.g., .org -> .gov) and establishes
        # the working base URL.
        council_url = f"{base_url}/{page_id}"
        council_resp = self._get_with_fallback(council_url, headers)
        council_resp.raise_for_status()

        # Derive the resolved base URL from the final redirect target.
        resolved_base = self._extract_base_url(council_resp.url)
        self._council_html = council_resp.text

        # Step 2: Discover the directory department ID if not provided.
        if not dir_dept_id:
            dir_dept_id = self._discover_directory_id(council_resp.text)
            if not dir_dept_id:
                raise RuntimeError(
                    f"Could not discover directory department ID from "
                    f"{council_resp.url}. Set 'directoryDeptId' in "
                    f"adapterConfig."
                )

        # Step 3: Fetch the directory page.
        dir_url = f"{resolved_base}/directory.aspx?did={dir_dept_id}"
        dir_resp = requests.get(dir_url, headers=headers, timeout=30)
        dir_resp.raise_for_status()

        return dir_resp.text

    def parse(self, html: str) -> list[dict]:
        """Parse the directory page staff table into member records.

        The table has columns: Name, Title, Email, Phone, (Additional Phone).
        Names are in "Last, First" format. Emails are JS-obfuscated.
        """
        soup = BeautifulSoup(html, "html.parser")

        table = soup.find(
            "table", id=re.compile(r"cityDirectoryDepartmentDetails", re.I)
        )
        if not table:
            raise RuntimeError(
                "Could not find the staff directory table. "
                "The page may have changed structure."
            )

        exclude_terms = self.config.get("memberFilter", DEFAULT_EXCLUDE)
        members = []

        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 4:
                continue

            name_raw = cells[0].get_text(strip=True)
            title_raw = cells[1].get_text(strip=True)
            email = self._extract_email(cells[2])
            phone = self._format_phone(cells[3].get_text(strip=True))

            # Skip non-council members (e.g., Clerk to County Council)
            if self._should_exclude(title_raw, exclude_terms):
                continue

            name = self._flip_name(name_raw)
            title = self._normalize_title(title_raw)

            members.append({
                "name": name,
                "title": title,
                "email": email,
                "phone": phone,
            })

        # If a mayorUrl is configured and no Mayor was found, fetch it
        mayor_url = self.config.get("mayorUrl")
        if mayor_url and not any(
            "Mayor" in m.get("title", "") for m in members
        ):
            mayor = self._fetch_mayor_page(mayor_url)
            if mayor:
                members.append(mayor)

        # Sort: chairman/chair first, then districts in order
        members.sort(key=self._sort_key)
        return members

    # --- Mayor fetch ---

    @staticmethod
    def _fetch_mayor_page(url: str) -> dict | None:
        """Fetch a separate mayor page and extract name, email, phone.

        Works with CivicPlus pages that have the mayor's info in
        fr-view content areas with mailto/tel links.
        """
        try:
            resp = requests.get(
                url, headers={"User-Agent": USER_AGENT}, timeout=30
            )
            resp.raise_for_status()
        except requests.RequestException:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        # Find the mayor's name from headings
        name = ""
        for tag in soup.find_all(["h1", "h2", "h3", "h4"]):
            text = tag.get_text(strip=True)
            if not text or len(text) < 3:
                continue
            match = re.match(r"^Mayor\s+(.+)", text, re.I)
            if match:
                name = match.group(1).strip()
                break

        if not name:
            # Try bold text or the page title
            for tag in soup.find_all(["strong", "b"]):
                text = tag.get_text(strip=True)
                if text and " " in text and len(text) < 60:
                    name = text
                    break

        email = ""
        for a in soup.find_all("a", href=re.compile(r"mailto:", re.I)):
            addr = a["href"].replace("mailto:", "").strip()
            if addr and "@" in addr:
                email = addr
                break

        phone = ""
        for a in soup.find_all("a", href=re.compile(r"^tel:", re.I)):
            phone = a.get_text(strip=True)
            break

        if not name:
            return None

        return {
            "name": name,
            "title": "Mayor",
            "email": email,
            "phone": phone,
        }

    # --- Helpers ---

    @staticmethod
    def _get_with_fallback(url: str, headers: dict) -> requests.Response:
        """Fetch a URL, trying .gov fallback if .org returns 403.

        Some CivicPlus .org domains have Cloudflare protection while the
        .gov equivalent does not. This method handles that transparently.
        """
        resp = requests.get(
            url, headers=headers, timeout=30, allow_redirects=True
        )
        if resp.status_code == 403 and ".org" in url:
            gov_url = url.replace(".org", ".gov")
            resp = requests.get(
                gov_url, headers=headers, timeout=30, allow_redirects=True
            )
        return resp

    @staticmethod
    def _extract_base_url(url: str) -> str:
        """Extract scheme + host from a full URL.

        Example: "https://www.spartanburgcounty.gov/189/Council" ->
                 "https://www.spartanburgcounty.gov"
        """
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    @staticmethod
    def _discover_directory_id(html: str) -> str:
        """Find the directory department ID from a council page.

        Looks for a link like /directory.aspx?did=42 in the page HTML.
        """
        match = re.search(r"/directory\.aspx\?did=(\d+)", html, re.I)
        return match.group(1) if match else ""

    @staticmethod
    def _extract_email(cell) -> str:
        """Extract email from a JS-obfuscated directory table cell.

        The cell contains a script tag with:
            var w = "localpart";
            var x = "domain.org";
        We reconstruct the email as localpart@domain.org.
        """
        script = cell.find("script")
        if not script or not script.string:
            # Fall back to a direct mailto link if present
            link = cell.find("a", href=re.compile(r"mailto:"))
            if link:
                return link["href"].replace("mailto:", "")
            return ""

        js = script.string
        local_match = re.search(r'var\s+w\s*=\s*"([^"]+)"', js)
        domain_match = re.search(r'var\s+x\s*=\s*"([^"]+)"', js)

        if local_match and domain_match:
            return f"{local_match.group(1)}@{domain_match.group(1)}"
        return ""

    @staticmethod
    def _format_phone(phone_raw: str) -> str:
        """Format a phone number to (NNN) NNN-NNNN style.

        CivicPlus directories use various formats:
            864-596-2528, 864.596.2528, (864) 596-2528
        """
        if not phone_raw:
            return ""
        match = re.search(r"(\d{3})[-.\s)]*(\d{3})[-.](\d{4})", phone_raw)
        if match:
            return f"({match.group(1)}) {match.group(2)}-{match.group(3)}"
        return phone_raw

    @staticmethod
    def _flip_name(name_raw: str) -> str:
        """Convert 'Last, First' to 'First Last'.

        Handles suffixes: 'Lynch, A. Manning' -> 'A. Manning Lynch'
        Passes through names without commas unchanged.
        """
        if "," not in name_raw:
            return name_raw.strip()
        parts = name_raw.split(",", 1)
        last = parts[0].strip()
        first = parts[1].strip()
        return f"{first} {last}"

    @staticmethod
    def _should_exclude(title: str, exclude_terms: list[str]) -> bool:
        """Check if a title matches any exclusion term."""
        title_lower = title.lower()
        return any(term.lower() in title_lower for term in exclude_terms)

    @staticmethod
    def _normalize_title(title_raw: str) -> str:
        """Normalize CivicPlus directory titles to our standard format.

        Examples:
          "County Council Chairman" -> "Chairman"
          "District 1 Representative" -> "Council Member, District 1"
          "Vice Chairman" -> "Vice Chairman"
        """
        title = title_raw.strip()

        # Extract district number
        district_match = re.search(r"District\s+(\d+)", title, re.IGNORECASE)
        if district_match:
            return f"Council Member, District {district_match.group(1)}"

        # Chairman / Vice Chairman
        if re.search(r"\bchairman\b", title, re.IGNORECASE):
            if re.search(r"\bvice\b", title, re.IGNORECASE):
                return "Vice Chairman"
            return "Chairman"

        # At-large
        if re.search(r"at[- ]large", title, re.IGNORECASE):
            return "Council Member, At Large"

        # Fallback: return as-is
        return title

    @staticmethod
    def _sort_key(member: dict) -> tuple:
        """Sort key: Mayor first, Chairman, then districts, then others."""
        title = member["title"]

        if title == "Mayor":
            return (0, 0, "")
        if title == "Chairman":
            return (0, 1, "")
        if title == "Vice Chairman":
            return (0, 2, "")

        district_match = re.search(r"District\s+(\d+)", title)
        if district_match:
            return (1, int(district_match.group(1)), "")

        # At-large or other: sort alphabetically
        return (2, 0, member["name"])
