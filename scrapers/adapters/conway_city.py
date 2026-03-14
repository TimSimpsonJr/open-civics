"""Adapter for Conway City Council.

The Conway Revize site has council members listed as plain text
with mailto links labeled "Email". Multiple members can be in a
single <p> tag, separated by <br/> tags. The pattern per member is:
    Title Name - <strong><a href="mailto:...">Email</a></strong>

Examples:
    Mayor Barbara Jo Blain - <strong><a href="mailto:mayor@conwaysc.gov">Email</a></strong>
    Council Member William Goldfinch IV, <em>Mayor Pro Tem</em> - <strong>...

Strategy: split the HTML on mailto links, then extract the name/title
from the text fragment immediately before each link.
"""

import re
from html import unescape

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"

# Matches a mailto link, capturing the email address
MAILTO_PATTERN = re.compile(
    r'<a\s+href=["\']mailto:([^"\']+)["\']',
    re.IGNORECASE,
)


class ConwayCityAdapter(BaseAdapter):
    """Scraper for Conway City Council page."""

    def fetch(self) -> str:
        url = self.url
        if not url:
            raise RuntimeError(f"No URL configured for {self.id}")
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        members = []

        # Find the content area containing council members
        soup = BeautifulSoup(html, "html.parser")
        content = None
        for div in soup.find_all("div"):
            if "mayor@conwaysc.gov" in str(div) and len(str(div)) < 3000:
                content = div
                break

        if not content:
            return members

        raw_html = str(content)

        # Find all mailto links and their positions
        matches = list(MAILTO_PATTERN.finditer(raw_html))

        for i, match in enumerate(matches):
            email = match.group(1).strip().rstrip("?")
            if not email:
                continue

            # Skip generic emails
            local = email.split("@")[0].lower()
            if local in ("info", "council", "clerk", "webmaster", "ashelley"):
                continue

            # Extract the text fragment before this mailto link
            # (from the end of the previous mailto block, or start of content)
            if i == 0:
                start = 0
            else:
                # Find end of previous mailto's </a></strong> block
                prev_end = matches[i - 1].end()
                start = prev_end

            fragment = raw_html[start:match.start()]

            # Strip HTML tags
            text = re.sub(r"<[^>]+>", " ", fragment)
            # Decode HTML entities
            text = unescape(text)
            # Normalize whitespace
            text = re.sub(r"\s+", " ", text).strip()
            # Remove trailing separators
            text = text.rstrip(" \xa0\u2013\u2014-").strip()

            # Check if Mayor Pro Tem appears in the fragment (may be in <em> tag)
            is_mayor_pro_tem = bool(
                re.search(r"Mayor\s+Pro\s+Tem", fragment, re.I)
            )

            # Find the last "Mayor ..." or "Council Member ..." in the text
            member = self._parse_last_member(text, email, is_mayor_pro_tem)
            if member:
                members.append(member)

        # Deduplicate by email
        seen = set()
        unique = []
        for m in members:
            if m["email"] not in seen:
                seen.add(m["email"])
                unique.append(m)

        unique.sort(key=self._sort_key)
        return unique

    @staticmethod
    def _parse_last_member(text: str, email: str, is_pro_tem: bool) -> dict | None:
        """Extract the last member mention from a text fragment."""
        if not text:
            return None

        # Find the LAST occurrence of "Council Member" or "Mayor" (but not
        # "Mayor Pro Tem" which is a title suffix, not a name prefix).
        # We search for all start positions, then use the last one.
        starts = [m.start() for m in re.finditer(
            r"(?:Council\s+Member|Mayor(?!\s+Pro\s+Tem))\b", text, re.I,
        )]

        if not starts:
            return None

        member_text = text[starts[-1]:].strip()
        member_text = member_text.rstrip(" \xa0\u2013\u2014-").strip()

        title = "Council Member"
        name = member_text

        mayor_match = re.match(r"^Mayor\s+(.+)", member_text, re.I)
        cm_match = re.match(r"^Council\s+Member\s+(.+)", member_text, re.I)

        if mayor_match and not is_pro_tem:
            title = "Mayor"
            name = mayor_match.group(1).strip()
        elif cm_match:
            name = cm_match.group(1).strip()
            if is_pro_tem:
                title = "Mayor Pro Tem"

        # Remove trailing ", Mayor Pro Tem" from name
        name = re.sub(r",?\s*Mayor\s+Pro\s+Tem\s*$", "", name, flags=re.I).strip()
        # Remove trailing commas and special chars
        name = name.rstrip(", \xa0").strip()

        if not name or len(name) < 3:
            return None

        # Filter out non-council members
        exclude = ["clerk", "administrator", "manager"]
        if any(term in name.lower() for term in exclude):
            return None

        return {
            "name": name,
            "title": title,
            "email": email,
            "phone": "",
        }

    @staticmethod
    def _sort_key(member: dict) -> tuple:
        title = member["title"]
        if title == "Mayor":
            return (0, 0)
        if title == "Mayor Pro Tem":
            return (0, 1)
        return (1, 0, member.get("name", ""))
