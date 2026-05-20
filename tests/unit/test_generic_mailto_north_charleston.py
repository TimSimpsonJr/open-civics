"""Tests for GenericMailtoAdapter against the North Charleston snapshot.

This jurisdiction has district info as <li>District N</li> inside a
<ul class="category-list"> sitting above each member's <h2> name.
The adapter must attach those districts to each member's title so the
normalizer's stage-2 title parser produces seatClass: numbered.
"""

import os
import re

import pytest

from scrapers.adapters.generic_mailto import GenericMailtoAdapter
from scrapers.normalize import normalize_member, NormalizationContext

SNAPSHOT = os.path.join(os.path.dirname(__file__), "..", "fixtures",
                        "snapshots", "generic_mailto_north_charleston.html")


@pytest.fixture
def html():
    with open(SNAPSHOT, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def adapter():
    return GenericMailtoAdapter({
        "id": "place:north-charleston",
        "url": "",
        "adapterConfig": {},
    })


class TestNorthCharlestonDistricts:

    def test_parse_yields_ten_members(self, adapter, html):
        members = adapter.parse(html)
        # 10 districts; mayor not necessarily on this page (fetched separately
        # via mayorUrl); assert lower bound on the district members.
        district_members = [m for m in members if "District" in m.get("title", "")]
        assert len(district_members) >= 10

    def test_district_titles_format(self, adapter, html):
        members = adapter.parse(html)
        ids = sorted(int(re.search(r"District\s+(\d+)", m["title"]).group(1))
                     for m in members if "District" in m.get("title", ""))
        assert ids == list(range(1, 11))

    def test_full_pipeline_produces_numbered_seats(self, adapter, html):
        """parse → normalize → every council member has seatClass: numbered."""
        raw = adapter.parse(html)
        ctx = NormalizationContext(
            level="local", jurisdiction_type="place",
            jurisdiction_id="place:north-charleston",
        )
        for r in raw:
            normalize_member(r, ctx)
        district_members = [m for m in raw if "District" in m.get("title", "")]
        for m in district_members:
            assert m["seatClass"] == "numbered", m
            assert m["seatLabel"] == "district", m
            assert m["seatId"] is not None, m
