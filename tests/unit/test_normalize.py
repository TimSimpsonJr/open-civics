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


@pytest.mark.parametrize("title, expected_id", [
    ("Council Member, District One", "1"),
    ("Council Member, District Two", "2"),
    ("Council Member, District Three", "3"),
    ("Council Member, Ward Four", "4"),
    ("Council Member, District Twelve", "12"),
])
def test_title_parsing_word_form_numbers(title, expected_id):
    record = {"name": "Test", "title": title}
    ctx = NormalizationContext(level="local", jurisdiction_type="place",
                               jurisdiction_id="place:test")
    out = normalize_member(record, ctx)
    assert out["seatClass"] == "numbered"
    assert out["seatId"] == expected_id


@pytest.mark.parametrize("title", [
    "Council Member, At Large",
    "Council Member, At-Large",
    "Vice Chair, At-Large",
    "Mayor Pro Tem, At Large",
])
def test_title_parsing_at_large(title):
    record = {"name": "Test", "title": title}
    ctx = NormalizationContext(level="local", jurisdiction_type="place",
                               jurisdiction_id="place:test")
    out = normalize_member(record, ctx)
    assert out["seatClass"] == "at-large"
    assert out["seatLabel"] is None
    assert out["seatId"] is None


def test_title_parsing_mayor():
    record = {"name": "Knox White", "title": "Mayor"}
    ctx = NormalizationContext(level="local", jurisdiction_type="place",
                               jurisdiction_id="place:greenville")
    out = normalize_member(record, ctx)
    assert out["office"] == "mayor"
    assert out["leadership"] is None
    assert out["seatClass"] == "at-large"
    assert out["seatLabel"] is None
    assert out["seatId"] is None


@pytest.mark.parametrize("title, expected_seat_id", [
    ("Mayor Pro Tem, District 2", "2"),
])
def test_title_parsing_mayor_pro_tem(title, expected_seat_id):
    record = {"name": "Test", "title": title}
    ctx = NormalizationContext(level="local", jurisdiction_type="place",
                               jurisdiction_id="place:test")
    out = normalize_member(record, ctx)
    assert out["office"] == "council-member"
    assert out["leadership"] == "mayor-pro-tem"
    assert out["seatId"] == expected_seat_id


@pytest.mark.parametrize("title, expected_leadership, expected_seat_id", [
    ("Chairman, District 4", "chair", "4"),
    ("Vice Chairman, District 3", "vice-chair", "3"),
])
def test_title_parsing_leadership(title, expected_leadership, expected_seat_id):
    record = {"name": "Test", "title": title}
    ctx = NormalizationContext(level="local", jurisdiction_type="county",
                               jurisdiction_id="county:test")
    out = normalize_member(record, ctx)
    assert out["office"] == "council-member"
    assert out["leadership"] == expected_leadership
    assert out["seatId"] == expected_seat_id


@pytest.mark.parametrize("title", [
    "Council Member",
    "Councilman",
    "Town Council Member",
    "",
])
def test_title_parsing_plain_council_member(title):
    record = {"name": "Test", "title": title}
    ctx = NormalizationContext(level="local", jurisdiction_type="place",
                               jurisdiction_id="place:test")
    out = normalize_member(record, ctx)
    assert out["office"] == "council-member"
    assert out["leadership"] is None
    assert out["seatClass"] == "unknown"
    assert out["seatLabel"] is None
    assert out["seatId"] is None


@pytest.mark.parametrize("title, expected_leadership", [
    ("Chairman", "chair"),
    ("Chair", "chair"),
    ("Vice Chairman", "vice-chair"),
    ("Vice Chair", "vice-chair"),
    ("Mayor Pro Tem", "mayor-pro-tem"),
    ("Mayor Pro-Tem", "mayor-pro-tem"),
])
def test_leadership_only_titles_get_unknown_seat_class(title, expected_leadership):
    """Chairman / Vice Chairman / Mayor Pro Tem with no embedded seat: leadership set, seat unknown."""
    record = {"name": "Test", "title": title}
    ctx = NormalizationContext(level="local", jurisdiction_type="county",
                               jurisdiction_id="county:test")
    out = normalize_member(record, ctx)
    assert out["office"] == "council-member"
    assert out["leadership"] == expected_leadership
    assert out["seatClass"] == "unknown"
    assert out["seatLabel"] is None
    assert out["seatId"] is None


@pytest.mark.parametrize("name, expected_vacant, expected_seat_id", [
    ("Vacant", True, None),
    ("Vacant District 5", True, "5"),
    ("vacant district 7", True, "7"),
    ("Joey Russo", False, None),
])
def test_vacancy_detection(name, expected_vacant, expected_seat_id):
    record = {"name": name, "title": "Council Member"}
    ctx = NormalizationContext(level="local", jurisdiction_type="place",
                               jurisdiction_id="place:test")
    out = normalize_member(record, ctx)
    assert out["vacant"] == expected_vacant
    if expected_seat_id is not None:
        assert out["seatId"] == expected_seat_id
