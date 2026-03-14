"""Adapter for Revize-powered government websites.

Revize is a CMS used by many SC county/city governments. Unlike CivicPlus,
Revize council pages use freeform WYSIWYG content rather than a structured
staff directory module. The HTML varies per site.

Strategy:
  The adapter pairs each mailto: link with the nearest preceding bold/heading
  text (the member's name), then searches forward for a phone number. This
  works because Revize freeform pages consistently follow a pattern of:
    Name (in bold/heading) -> Email (mailto link) -> Phone (tel link or text)

adapterConfig fields:
  - memberFilter: (optional) list of title substrings to EXCLUDE
    (default: ["clerk"])
"""

import re

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

from .base import BaseAdapter, deobfuscate_cf_email

USER_AGENT = "CallYourRep/1.0 (+https://github.com/TimSimpsonJr/call-your-rep)"

DEFAULT_EXCLUDE = ["clerk", "administrator", "manager", "secretary",
                   "treasurer", "attorney", "director", "assistant"]

PHONE_PATTERN = re.compile(r"\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]\d{4}")


class RevizeAdapter(BaseAdapter):
    """Scraper for Revize-powered government council pages."""

    def fetch(self) -> str:
        url = self.url
        if not url:
            raise RuntimeError(f"No URL configured for {self.id}")

        headers = {"User-Agent": USER_AGENT}
        resp = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")

        content = (
            soup.find("div", class_="fr-view")
            or soup.find("div", id="divContent")
            or soup.find("div", class_="cms-area")
            or soup.find("article")
            or soup.find("main")
            or soup.body
        )
        if not content:
            raise RuntimeError(f"Could not find content area for {self.id}")

        # Flatten the content into a linear sequence of elements for processing.
        # This handles freeform Revize pages where everything is flat siblings.
        elements = list(content.descendants)

        # Build a list of (element, type) pairs for key items:
        # - "name": bold/heading text that looks like a person name
        # - "email": mailto link
        # - "phone": tel link or phone-pattern text
        # - "separator": hr or heading that starts a new section
        markers = []
        seen_texts = set()

        for el in elements:
            if isinstance(el, Tag):
                if el.name == "hr":
                    markers.append(("separator", None, el))
                elif el.name == "a" and el.get("href", "").lower().startswith("mailto:"):
                    email = el["href"][7:].strip().rstrip("?")
                    if email and not self._is_generic_email(email):
                        markers.append(("email", email, el))
                        # If link text is a name (not an email), also add as name
                        link_text = el.get_text(strip=True)
                        if link_text and "@" not in link_text and self._looks_like_name(link_text):
                            if link_text not in seen_texts:
                                seen_texts.add(link_text)
                                markers.append(("name", link_text, el))
                elif el.name == "a" and "/email-protection#" in el.get("href", ""):
                    # Cloudflare-obfuscated email
                    encoded = el["href"].split("#", 1)[-1]
                    email = deobfuscate_cf_email(encoded)
                    if email and not self._is_generic_email(email):
                        markers.append(("email", email, el))
                elif el.name == "span" and el.get("data-cfemail"):
                    # Cloudflare inline obfuscation
                    email = deobfuscate_cf_email(el["data-cfemail"])
                    if email and not self._is_generic_email(email):
                        markers.append(("email", email, el))
                elif el.name == "a" and el.get("href", "").lower().startswith("tel:"):
                    phone_text = el.get_text(strip=True)
                    if phone_text:
                        markers.append(("phone", phone_text, el))
                elif el.name in ("strong", "b", "h2", "h3", "h4", "h5", "dt"):
                    text = el.get_text(strip=True)
                    if text and text not in seen_texts and self._looks_like_name(text):
                        seen_texts.add(text)
                        markers.append(("name", text, el))
                elif el.name == "a" and el.get("href", ""):
                    # Profile links: <a href="/member/...">Name</a>
                    href = el.get("href", "")
                    if not href.startswith(("mailto:", "tel:", "#", "javascript:")):
                        text = el.get_text(strip=True)
                        if text and text not in seen_texts and self._looks_like_name(text):
                            seen_texts.add(text)
                            markers.append(("name", text, el))
            elif isinstance(el, NavigableString):
                text = str(el).strip()
                if text:
                    match = PHONE_PATTERN.search(text)
                    if match:
                        markers.append(("phone", match.group(0), el))

        # Now pair names with emails. Strategy: for each email, find the
        # closest preceding name marker (not yet claimed by another email).
        exclude_terms = self.config.get("memberFilter", DEFAULT_EXCLUDE)
        members = []
        claimed_names = set()

        for i, (mtype, mval, mel) in enumerate(markers):
            if mtype != "email":
                continue

            # Find closest preceding name
            name = ""
            name_idx = -1
            for j in range(i - 1, -1, -1):
                if markers[j][0] == "separator":
                    break
                if markers[j][0] == "name" and j not in claimed_names:
                    name = markers[j][1]
                    name_idx = j
                    break

            if not name:
                continue

            claimed_names.add(name_idx)

            # Find phone: look forward from email until next separator or name
            phone = ""
            for j in range(i + 1, len(markers)):
                if markers[j][0] in ("separator", "name", "email"):
                    break
                if markers[j][0] == "phone":
                    phone = markers[j][1]
                    break

            # Also check backward between name and email for phone
            if not phone:
                for j in range(i - 1, max(name_idx, -1), -1):
                    if markers[j][0] == "phone":
                        phone = markers[j][1]
                        break

            # Strip trailing title suffixes like ", Councilmember"
            name, suffix_title = self._strip_title_suffix(name)

            # Extract title from the name text or nearby context
            title = self._extract_title_from_name(name)
            if title:
                # Remove title prefix from name
                name = self._strip_title_from_name(name, title)

            # Use suffix-extracted title if no prefix title was found
            if not title and suffix_title:
                title = suffix_title

            if not title:
                # Check nearby text for title keywords
                title = self._find_title_near(markers, i, name_idx)

            if self._should_exclude(name, exclude_terms):
                continue
            if title and self._should_exclude(title, exclude_terms):
                continue

            members.append({
                "name": name.strip(),
                "title": title or "Council Member",
                "email": mval,
                "phone": phone,
            })

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
    def _looks_like_name(text: str) -> bool:
        if not text or len(text) < 3 or len(text) > 80:
            return False
        if text.count(" ") < 1:
            return False
        if any(x in text.lower() for x in [
            "http", "@", "phone", "fax",
            "address", "meeting", "agenda", "click",
            "more info", "read more", "public forum",
            "county council", "city council", "town council",
            "office:", "contact us", "appearances",
            "quorum", "voting", "rules of order",
            "regular meeting", "special meeting",
            "mailing", "navigation", "accessibility",
            "search", "menu", "login", "sign in",
            "home", "about", "news", "events",
            "boards and commissions", "commission",
            "website", "privacy", "copyright",
            "powered by", "all rights", "site map",
            "subscribe", "follow us", "connect with",
            "departments", "services", "resources",
            "dark mode", "font size", "high contrast",
            "directory", "elected officials",
            "storm", "weather", "alert", "notice",
            "growth in", "moves to",
        ]):
            return False
        if not text[0].isupper():
            return False
        # Reject lines that are mostly numbers (addresses)
        digits = sum(1 for c in text if c.isdigit())
        if digits > len(text) * 0.3:
            return False
        return True

    @staticmethod
    def _strip_title_suffix(name: str) -> tuple[str, str]:
        """Remove trailing title like ', Councilmember' or ', Mayor Pro Tem'.

        Returns (cleaned_name, extracted_title). The title is "" if none found.
        """
        suffix_to_title = [
            (r",\s*Mayor\s+Pro\s+Tem\b", "Mayor Pro Tem"),
            (r",\s*Mayor\b", "Mayor"),
            (r",\s*Council\s*(?:man|woman|member|person)\b", ""),
            (r",\s*Vice\s+Chair(?:man|person|woman)?\b", ""),
            (r",\s*Chair(?:man|person|woman)?\b", ""),
        ]
        for pat, title in suffix_to_title:
            match = re.search(pat, name, re.I)
            if match:
                return name[:match.start()].strip(), title
        # Also strip trailing comma
        return name.rstrip(", ").strip(), ""

    @staticmethod
    def _extract_title_from_name(text: str) -> str:
        """Extract title prefix from a name string like 'Mayor John Smith'."""
        patterns = [
            (r"^(Mayor\s+Pro\s+Tem)\b", "Mayor Pro Tem"),
            (r"^(Mayor)\b", "Mayor"),
            (r"^(Vice\s+Chair(?:man|person|woman)?)\b", None),
            (r"^(Chair(?:man|person|woman)?)\b", None),
            (r"^(Council\s*(?:man|woman|member|person))\b", None),
        ]
        for pat, fixed_title in patterns:
            match = re.match(pat, text, re.I)
            if match:
                return fixed_title or match.group(1).title()
        return ""

    @staticmethod
    def _strip_title_from_name(name: str, title: str) -> str:
        """Remove a title prefix from a name string."""
        # Try to strip the title prefix
        for prefix in [title, title.lower(), title.upper()]:
            if name.lower().startswith(prefix.lower()):
                rest = name[len(prefix):].strip()
                # Remove leading comma or dash
                rest = rest.lstrip(",-–— ").strip()
                if rest:
                    return rest
        return name

    @staticmethod
    def _find_title_near(markers, email_idx, name_idx):
        """Search markers near a member for title context."""
        # Check text between name and email for district/title info
        for j in range(max(name_idx, 0), min(email_idx + 3, len(markers))):
            mtype, mval, _ = markers[j]
            if mtype == "name" and mval:
                district_match = re.search(r"District\s+(\d+)", mval, re.I)
                if district_match:
                    return f"Council Member, District {district_match.group(1)}"

        # Also scan elements between name and email for standalone title text
        # (e.g., <strong>Mayor</strong> on its own line)
        if name_idx >= 0 and name_idx < len(markers):
            name_el = markers[name_idx][2]
            email_el = markers[email_idx][2]
            # Walk siblings between name and email elements
            from bs4 import Tag
            current = name_el
            for _ in range(20):  # limit traversal
                current = current.next_element
                if current is None or current is email_el:
                    break
                if isinstance(current, Tag) and current.name in (
                    "strong", "b", "h2", "h3", "h4", "h5", "em", "span", "div",
                ):
                    text = current.get_text(strip=True)
                    text_lower = text.lower().strip()
                    if text_lower == "mayor pro tem":
                        return "Mayor Pro Tem"
                    if text_lower == "mayor":
                        return "Mayor"

        return ""

    @staticmethod
    def _is_generic_email(email: str) -> bool:
        local = email.split("@")[0].lower()
        generic = ["info", "council", "clerk", "webmaster", "admin",
                    "contact", "help", "support", "general", "office",
                    "dearcitycouncil", "dearcouncil"]
        return local in generic

    @staticmethod
    def _should_exclude(text: str, exclude_terms: list[str]) -> bool:
        text_lower = text.lower()
        return any(term.lower() in text_lower for term in exclude_terms)

    @staticmethod
    def _sort_key(member: dict) -> tuple:
        title = member.get("title", "")
        if "Mayor" in title and "Pro Tem" not in title:
            return (0, 0, "")
        if "Mayor Pro" in title:
            return (0, 1, "")
        if title in ("Chairman", "Chairperson", "Chair"):
            return (1, 0, "")
        if "Vice" in title:
            return (1, 1, "")
        district_match = re.search(r"District\s+(\d+)", title)
        if district_match:
            return (2, int(district_match.group(1)), "")
        return (3, 0, member.get("name", ""))
