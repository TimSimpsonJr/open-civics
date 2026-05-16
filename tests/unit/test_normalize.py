"""Unit tests for scrapers.normalize."""

import pytest

from scrapers.normalize import normalize_member, NormalizationContext


def test_normalize_member_idempotent_when_fields_already_set():
    record = {
        "name": "Joey Russo",
        "title": "Council Member, District 17",
        "office": "council-member",
        "leadership": None,
        "seatClass": "numbered",
        "seatLabel": "district",
        "seatId": "17",
        "vacant": False,
        "seatSource": "source",
        "partisan": False,
    }
    ctx = NormalizationContext(level="local", jurisdiction_type="county",
                               jurisdiction_id="county:greenville")
    out = normalize_member(record, ctx)
    # Idempotent: pre-set structured fields preserved exactly
    assert out["office"] == "council-member"
    assert out["seatId"] == "17"
    assert out["seatSource"] == "source"


@pytest.mark.parametrize("title, expected_class, expected_label, expected_id", [
    ("Council Member, District 17", "numbered", "district", "17"),
    ("Council Member, Ward 3", "numbered", "ward", "3"),
    ("Council Member, Seat 5", "numbered", "seat", "5"),
    ("District Number 3 - Councilman", "numbered", "district", "3"),
    ("Council Member, District 10", "numbered", "district", "10"),
])
def test_title_parsing_numeric_districts(title, expected_class, expected_label, expected_id):
    record = {"name": "Test", "title": title}
    ctx = NormalizationContext(level="local", jurisdiction_type="place",
                               jurisdiction_id="place:test")
    out = normalize_member(record, ctx)
    assert out["seatClass"] == expected_class
    assert out["seatLabel"] == expected_label
    assert out["seatId"] == expected_id
    assert out["seatSource"] == "parsed-title"
