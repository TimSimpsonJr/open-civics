"""Tests for the manual seat_overrides covering Akamai-blocked counties.

Tasks 5, 6, 7 of the districted-scraper-bugs plan. The override keys live in
scrapers/seat_overrides.py; this test verifies that, after normalization,
every council member of these jurisdictions carries either seatClass=numbered
or seatClass=at-large (i.e., NOT seatClass=unknown), with seatSource=manual.
"""
import json
import os
import pytest

from scrapers.normalize import normalize_member, NormalizationContext

DATA = os.path.join(os.path.dirname(__file__), "..", "..", "data", "sc", "local")


def _load(jid: str) -> list[dict]:
    path = os.path.join(DATA, f"{jid.replace(':', '-')}.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)["members"]


@pytest.mark.parametrize("jurisdiction", [
    "county:dorchester",
    "county:kershaw",
    "county:jasper",
])
def test_all_council_members_resolved_via_manual_override(jurisdiction):
    """After normalization, every council member (excluding chair/vice-chair)
    should carry seatClass: numbered OR at-large with seatSource: manual."""
    ctx = NormalizationContext(level="local", jurisdiction_type="county",
                               jurisdiction_id=jurisdiction)
    raw_members = _load(jurisdiction)
    for raw in raw_members:
        # Reset normalized fields so the override stage is exercised cleanly
        for k in ("seatClass", "seatLabel", "seatId", "seatSource"):
            raw.pop(k, None)
        normalize_member(raw, ctx)
    council_members = [m for m in raw_members
                       if m.get("office") == "council-member"
                       and m.get("leadership") not in ("chair", "vice-chair")]
    assert council_members, f"{jurisdiction}: no non-leadership council members in data"
    for m in council_members:
        assert m["seatClass"] in ("numbered", "at-large"), \
            f"{jurisdiction}: {m['name']} got seatClass={m['seatClass']!r}, expected numbered or at-large"
        assert m["seatSource"] == "manual", \
            f"{jurisdiction}: {m['name']} seatSource={m['seatSource']!r}, expected manual"
