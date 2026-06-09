"""Tests for the manual seat_overrides covering Akamai-blocked counties.

Tasks 5, 6, 7 of the districted-scraper-bugs plan. The override keys live in
scrapers/seat_overrides.py; this test verifies that, after normalization,
every council member of these jurisdictions carries a specific
(seatClass, seatLabel, seatId) tuple with seatSource=manual. Asserting the
exact tuple catches transposition bugs (e.g., swapped district numbers)
that a coarser seatClass-only check would miss.
"""
import json
import os
import pytest

from scrapers.normalize import normalize_member, NormalizationContext

DATA = os.path.join(os.path.dirname(__file__), "..", "..", "data", "sc", "local")


# Expected (seatClass, seatLabel, seatId) tuple for every council member in
# each manually-overridden jurisdiction. If a name drifts in seat_overrides.py
# (e.g., a district number swap), this dict diverges from reality and the
# parametrized assertion below fails with a clear message naming the member.
EXPECTED: dict[str, dict[str, tuple]] = {
    "county:kershaw": {
        "Ben Connell":     ("at-large", None,       None),
        "Russell Brazell": ("numbered", "district", "1"),
        "Sammie Tucker":   ("numbered", "district", "2"),
        "Derek Shoemake":  ("numbered", "district", "3"),
        "Jimmy Jones":     ("numbered", "district", "4"),
        "Brant Tomlinson": ("numbered", "district", "5"),
        "Danny Catoe":     ("numbered", "district", "6"),
    },
    "county:dorchester": {
        "Peter Smith":      ("numbered", "district", "1"),
        "C. David Chinnis": ("numbered", "district", "2"),
        "Rita May Ranck":   ("numbered", "district", "3"),
        "S. Todd Friddle":  ("numbered", "district", "4"),
        "Edward Crosby":    ("numbered", "district", "5"),
        "Frankie Staropoli": ("numbered", "district", "6"),
        "James Byars":      ("numbered", "district", "7"),
    },
    "county:jasper": {
        "Joey Rowell":     ("numbered", "township", "Pocotaligo"),
        "Joseph Arzillo":  ("numbered", "township", "Hardeeville"),
        "Chris VanGeison": ("numbered", "township", "Robertville"),
        "Gene Ceccarelli": ("numbered", "township", "Coosawhatchie"),
        "John Kemp":       ("at-large", None,       None),
    },
}


def _load(jid: str) -> list[dict]:
    path = os.path.join(DATA, f"{jid.replace(':', '-')}.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)["members"]


@pytest.mark.parametrize("jurisdiction", list(EXPECTED.keys()))
def test_all_council_members_resolved_via_manual_override(jurisdiction):
    """Every council member (including chair / vice-chair) should resolve via
    the manual override stage to the exact (seatClass, seatLabel, seatId)
    tuple in EXPECTED, with seatSource: 'manual'."""
    ctx = NormalizationContext(level="local", jurisdiction_type="county",
                               jurisdiction_id=jurisdiction)
    raw_members = _load(jurisdiction)
    for raw in raw_members:
        # Reset normalized fields so the override stage is exercised cleanly
        for k in ("seatClass", "seatLabel", "seatId", "seatSource"):
            raw.pop(k, None)
        normalize_member(raw, ctx)

    council_members = [m for m in raw_members if m.get("office") == "council-member"]
    assert council_members, f"{jurisdiction}: no council members in data"

    expected_by_name = EXPECTED[jurisdiction]
    # Sanity check: every member in the data file is covered by EXPECTED.
    # Drift in either direction (data adds/drops a name, EXPECTED forgets one)
    # surfaces here rather than silently passing.
    actual_names = {m["name"] for m in council_members}
    expected_names = set(expected_by_name.keys())
    assert actual_names == expected_names, (
        f"{jurisdiction}: member names diverge.\n"
        f"  in data but not EXPECTED: {sorted(actual_names - expected_names)}\n"
        f"  in EXPECTED but not data: {sorted(expected_names - actual_names)}"
    )

    for m in council_members:
        name = m["name"]
        expected = expected_by_name[name]
        actual = (m["seatClass"], m["seatLabel"], m["seatId"])
        assert m["seatClass"] in ("numbered", "at-large"), \
            f"{jurisdiction}: {name} got seatClass={m['seatClass']!r}, expected numbered or at-large"
        assert m["seatSource"] == "manual", \
            f"{jurisdiction}: {name} seatSource={m['seatSource']!r}, expected manual"
        assert actual == expected, (
            f"{jurisdiction}: {name} got "
            f"(seatClass={actual[0]!r}, seatLabel={actual[1]!r}, seatId={actual[2]!r}), "
            f"expected (seatClass={expected[0]!r}, seatLabel={expected[1]!r}, seatId={expected[2]!r})"
        )
