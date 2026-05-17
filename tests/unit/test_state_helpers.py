"""Tests for helper functions in scrapers.state."""

import pytest
from scrapers.state import _abbreviate_party, _first_link, normalize_row


class TestAbbreviateParty:
    @pytest.mark.parametrize("party,expected", [
        ("Democratic", "D"),
        ("democratic", "D"),
        ("Democrat", "D"),
        ("Republican", "R"),
        ("republican", "R"),
        ("Independent", "I"),
        ("", ""),
        # These hit the fallback: first char uppercased
        ("Libertarian", "L"),
        ("Green", "G"),
        ("  Republican  ", "R"),
    ])
    def test_abbreviate_party(self, party, expected):
        assert _abbreviate_party(party) == expected


class TestFirstLink:
    @pytest.mark.parametrize("links_str,expected", [
        # Semicolon-separated -> first URL
        ("https://a.com; https://b.com", "https://a.com"),
        # Single URL
        ("https://example.com", "https://example.com"),
        # Empty/blank
        ("", ""),
        ("   ", ""),
        # Whitespace around URL
        ("  https://example.com  ", "https://example.com"),
        # Multiple semicolons
        ("https://a.com;https://b.com;https://c.com", "https://a.com"),
    ])
    def test_first_link(self, links_str, expected):
        assert _first_link(links_str) == expected


def test_normalize_row_synthesizes_title_for_senate():
    row = {
        "name": "Shane Massey",
        "current_district": "25",
        "current_chamber": "upper",
        "current_party": "Republican",
        "capitol_voice": "803-212-6330",
    }
    rec = normalize_row(row, chamber="upper")
    assert rec["title"] == "State Senator, District 25"
    assert rec["office"] == "state-senator"
    assert rec["seatClass"] == "numbered"
    assert rec["seatLabel"] == "district"
    assert rec["seatId"] == "25"
    assert rec["partisan"] is True
    assert rec["vacant"] is False


def test_normalize_row_synthesizes_title_for_house():
    row = {
        "name": "Bill Hager",
        "current_district": "122",
        "current_chamber": "lower",
        "current_party": "Republican",
        "capitol_voice": "",
    }
    rec = normalize_row(row, chamber="lower")
    assert rec["title"] == "State Representative, District 122"
    assert rec["office"] == "state-representative"


def test_normalize_row_uses_structured_csv_columns_as_source():
    row = {
        "name": "Shane Massey",
        "current_district": "25",
        "current_chamber": "upper",
        "current_party": "Republican",
        "capitol_voice": "803-212-6330",
    }
    rec = normalize_row(row, chamber="upper")
    assert rec["seatSource"] == "source"  # stage-1 provenance
    assert rec["seatClass"] == "numbered"
    assert rec["seatId"] == "25"
