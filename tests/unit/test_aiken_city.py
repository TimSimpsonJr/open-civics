"""Tests for AikenCityAdapter against the saved snapshot.

The Aiken City Council site is a Divi-themed page with et_pb_team_member
cards. Each member's district lives in <p class="et_pb_member_position">.
The adapter already converts "District N" into "Council Member District N"
titles, which the normalizer's stage-2 title parser turns into
seatClass: numbered. This test pins that behavior.
"""

import os
import re

import pytest

from scrapers.adapters.aiken_city import AikenCityAdapter
from scrapers.normalize import normalize_member, NormalizationContext

SNAPSHOT = os.path.join(os.path.dirname(__file__), "..", "fixtures",
                        "snapshots", "aiken_city.html")


@pytest.fixture
def adapter():
    return AikenCityAdapter({"id": "place:aiken", "url": "", "adapterConfig": {}})


@pytest.fixture
def html():
    with open(SNAPSHOT, "r", encoding="utf-8") as f:
        return f.read()


class TestAikenCity:

    def test_extracts_mayor_and_six_districts(self, adapter, html):
        members = adapter.parse(html)
        mayors = [m for m in members if m["title"] == "Mayor"]
        districts = [m for m in members if "District" in m["title"]]
        assert len(mayors) == 1
        assert len(districts) == 6

    def test_districts_are_1_through_6(self, adapter, html):
        members = adapter.parse(html)
        ids = sorted(int(re.search(r"District\s+(\d+)", m["title"]).group(1))
                     for m in members if "District" in m["title"])
        assert ids == [1, 2, 3, 4, 5, 6]

    def test_full_pipeline_produces_numbered_seats(self, adapter, html):
        raw = adapter.parse(html)
        ctx = NormalizationContext(level="local", jurisdiction_type="place",
                                   jurisdiction_id="place:aiken")
        for r in raw:
            normalize_member(r, ctx)
        for m in raw:
            if m.get("office") == "mayor":
                continue
            assert m["seatClass"] == "numbered", m
            assert m["seatLabel"] == "district", m
