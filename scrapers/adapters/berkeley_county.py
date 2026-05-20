"""Adapter for Berkeley County Council elected officials.

The primary site is a WordPress page where each member appears in a
<figure class="wp-block-image"> whose <figcaption class="wp-element-caption">
contains text like 'District N' and the member's name, sometimes split
across multiple anchor elements joined by <br>. The county uses
Supervisor-Council form, so the Supervisor is an at-large position
separate from district seats.

Phone and email live on per-member detail pages linked by figcaption hrefs.
v1 of this adapter does NOT visit those pages - name + district is the
priority (it's what closes the validator's districted-but-all-unknown
warning). As a known consequence, every scraped member triggers a
`no email or phone` warning from BaseAdapter.validate(); the per-jurisdiction
run report will be `warned` rather than `ok` until detail-page enrichment
is added.

A future enhancement can add that enrichment via a separate `scrape()`
override that runs after parse() returns the index members.
"""

import re
import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter

USER_AGENT = "OpenCivics/1.0 (+https://github.com/TimSimpsonJr/open-civics)"

_DISTRICT_RE = re.compile(r"District\s+(\d+)", re.IGNORECASE)
_SUPERVISOR_RE = re.compile(r"\bSupervisor\b", re.IGNORECASE)
# Zero-width and other invisible chars that show up in the WordPress captions
# (e.g. trailing U+200B after "Tommy Newell"). Strip these so names print
# cleanly on all consoles and don't break downstream string comparisons.
_INVISIBLE_RE = re.compile(
    "[​-‏"  # zero-width space, ZWNJ, ZWJ, LRM, RLM
    "  "    # line/paragraph separator
    "‪-‮"   # bidi embedding/override
    "⁠"          # word joiner
    "﻿]"         # zero-width no-break space (BOM)
)


def _clean(s: str) -> str:
    return _INVISIBLE_RE.sub("", s).strip()


class BerkeleyCountyAdapter(BaseAdapter):

    def fetch(self) -> str:
        resp = requests.get(
            self.url, headers={"User-Agent": USER_AGENT}, timeout=30,
            allow_redirects=True,
        )
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        members = []
        for fig in soup.find_all("figure", class_="wp-block-image"):
            cap = fig.find("figcaption")
            if not cap:
                continue
            text = cap.get_text(separator="\n", strip=True)
            lines = [_clean(ln) for ln in text.split("\n")]
            lines = [ln for ln in lines if ln]
            if not lines:
                continue

            district_match = _DISTRICT_RE.search(text)
            is_supervisor = _SUPERVISOR_RE.search(text)

            # Member name is the line in the caption that is NOT a label
            label_predicates = (_DISTRICT_RE, _SUPERVISOR_RE,
                                re.compile(r"^Chair(?:man|woman)?$", re.IGNORECASE),
                                re.compile(r"^Vice", re.IGNORECASE))
            name = next(
                (ln for ln in lines
                 if not any(p.search(ln) for p in label_predicates)),
                "",
            )
            if not name:
                continue

            if district_match:
                title = f"Council Member, District {district_match.group(1)}"
            elif is_supervisor:
                title = "Chairman"  # Supervisor-Council form: supervisor IS the chair-equivalent
            else:
                # Non-district, non-supervisor figure - other constitutional officers
                # (Auditor, Sheriff, Treasurer, etc.) which are out of scope for the
                # council adapter, or unrelated page imagery.
                continue

            members.append({
                "name": name,
                "title": title,
                "email": "",
                "phone": "",
            })

        # Surface drift between parsed districts and registry.districts so a
        # future redistricting silently growing the council doesn't slip past CI.
        expected = self.entry.get("districts")
        if expected is not None:
            actual = sum(1 for m in members
                         if _DISTRICT_RE.search(m["title"]))
            if actual != expected:
                self.warnings.append(
                    f"parsed {actual} districts but registry expects {expected}"
                )

        members.sort(key=self._sort_key)
        return members

    @staticmethod
    def _sort_key(m: dict) -> tuple:
        title = m["title"]
        if title == "Chairman":
            return (0, 0)
        match = _DISTRICT_RE.search(title)
        if match:
            return (1, int(match.group(1)))
        return (2, 0)
