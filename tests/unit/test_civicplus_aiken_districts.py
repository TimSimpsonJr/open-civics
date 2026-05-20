"""Tests for CivicPlus council-members supplementary page logic.

The CivicPlus directory at /directory.aspx?did=N gives "Council Member" with
no district info for some sites (Aiken County). The council-members landing
page groups members under "District N" headings — we fetch it as a secondary
HTTP call in scrape() (NOT in parse()) and rewrite titles.
"""

import os
import pytest
from scrapers.adapters.civicplus import CivicPlusAdapter


SNAPSHOT = os.path.join(os.path.dirname(__file__), "..", "fixtures",
                        "snapshots", "civicplus_aiken_council_members.html")


def test_council_members_page_yields_district_map():
    with open(SNAPSHOT, "r", encoding="utf-8") as f:
        html = f.read()
    mapping = CivicPlusAdapter._extract_district_map_from_council_page(html)
    assert len(mapping) == 8  # Aiken County has 8 single-member districts
    for district_num, name in mapping.items():
        assert 1 <= district_num <= 8
        assert isinstance(name, str) and name


def test_apply_district_map_updates_titles():
    members = [
        {"name": "Honorable Ron Felder", "title": "Council Member"},
        {"name": "Honorable Mike Kellems", "title": "Council Member"},
        {"name": "Honorable Gary Bunker", "title": "Chairman"},
    ]
    mapping = {1: "Honorable Ron Felder", 2: "Honorable Mike Kellems"}
    CivicPlusAdapter._apply_district_map(members, mapping)
    by_name = {m["name"]: m["title"] for m in members}
    assert by_name["Honorable Ron Felder"] == "Council Member, District 1"
    assert by_name["Honorable Mike Kellems"] == "Council Member, District 2"
    assert by_name["Honorable Gary Bunker"] == "Chairman"


def test_apply_district_map_tolerates_honorable_prefix_variance():
    """Directory may have 'Ron Felder' while the council page has 'Honorable Ron Felder',
    or vice versa. Match should still succeed."""
    members = [{"name": "Ron Felder", "title": "Council Member"}]
    mapping = {1: "Honorable Ron Felder"}
    CivicPlusAdapter._apply_district_map(members, mapping)
    assert members[0]["title"] == "Council Member, District 1"


def test_aiken_directory_plus_supplement_end_to_end():
    """End-to-end on the real Aiken snapshots: parse the directory, apply the
    supplement map, normalize. All 8 non-chair council members must end up
    seatClass=numbered with a populated seatLabel/seatId. This is the test
    that catches partial name-match failures — the validator's all-unknown
    check would let 6-of-8 coverage slip through."""
    from scrapers.normalize import normalize_member, NormalizationContext

    here = os.path.dirname(__file__)
    snaps = os.path.join(here, "..", "fixtures", "snapshots")
    with open(os.path.join(snaps, "civicplus_aiken_directory.html"),
              "r", encoding="utf-8") as f:
        directory_html = f.read()
    with open(os.path.join(snaps, "civicplus_aiken_council_members.html"),
              "r", encoding="utf-8") as f:
        supplement_html = f.read()

    adapter = CivicPlusAdapter({
        "id": "county:aiken",
        "url": "https://www.aikencountysc.gov/528/County-Council",
        "adapterConfig": {
            "baseUrl": "https://www.aikencountysc.gov",
            "councilPageId": "528",
            "directoryDeptId": "117",
            "councilMembersUrl": "https://sc-aikencounty.civicplus.com/529/Council-Members",
        },
    })
    members = adapter.parse(directory_html)
    mapping = CivicPlusAdapter._extract_district_map_from_council_page(supplement_html)
    CivicPlusAdapter._apply_district_map(members, mapping)

    ctx = NormalizationContext(level="local", jurisdiction_type="county",
                               jurisdiction_id="county:aiken")
    for m in members:
        normalize_member(m, ctx)

    district_members = [m for m in members
                        if m.get("office") == "council-member"
                        and m.get("leadership") not in ("chair", "vice-chair")]
    assert len(district_members) == 8, \
        f"Expected 8 district council members, got {len(district_members)}: " \
        f"{[m['name'] for m in district_members]}"
    for m in district_members:
        assert m["seatClass"] == "numbered", \
            f"{m['name']!r} got seatClass={m['seatClass']!r} (title={m['title']!r}) — " \
            f"likely a name-match failure between directory and supplement"
        assert m["seatLabel"] == "district", m
        assert m["seatId"] is not None, m
    # All 8 district IDs should be present, no duplicates
    ids = sorted(int(m["seatId"]) for m in district_members)
    assert ids == [1, 2, 3, 4, 5, 6, 7, 8], f"district ids = {ids}"
