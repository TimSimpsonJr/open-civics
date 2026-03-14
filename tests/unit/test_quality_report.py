"""Tests for scripts/quality_report.py pure functions."""

import json
import os
import sys

import pytest

# scripts/ is not a Python package (no __init__.py), so add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.quality_report import (
    _has_title_match,
    analyze_local_file,
    check_contact,
    check_executive,
    format_summary,
)


# ---------------------------------------------------------------------------
# check_executive
# ---------------------------------------------------------------------------

class TestCheckExecutive:
    def test_mayor_found_in_place(self):
        members = [
            {"name": "Alice", "title": "Council Member"},
            {"name": "Bob", "title": "Mayor"},
        ]
        assert check_executive(members, "place") == "Mayor"

    def test_chairman_found_in_county(self):
        members = [
            {"name": "Alice", "title": "Council Member"},
            {"name": "Bob", "title": "Chairman"},
        ]
        assert check_executive(members, "county") == "Chairman"

    def test_chairwoman_found_in_county(self):
        members = [{"name": "Carol", "title": "Chairwoman"}]
        assert check_executive(members, "county") == "Chairwoman"

    def test_vice_chairman_skipped(self):
        members = [
            {"name": "Alice", "title": "Vice Chairman"},
            {"name": "Bob", "title": "Council Member"},
        ]
        assert check_executive(members, "county") is None

    def test_vice_mayor_skipped(self):
        members = [{"name": "Alice", "title": "Vice Mayor"}]
        assert check_executive(members, "place") is None

    def test_deputy_chairman_skipped(self):
        members = [{"name": "Alice", "title": "Deputy Chairman"}]
        assert check_executive(members, "county") is None

    def test_no_executive_found(self):
        members = [
            {"name": "Alice", "title": "Council Member"},
            {"name": "Bob", "title": "Council Member"},
        ]
        assert check_executive(members, "place") is None

    def test_empty_members(self):
        assert check_executive([], "place") is None

    def test_title_with_comma_returns_first_part(self):
        members = [{"name": "Bob", "title": "Mayor, City of Springfield"}]
        assert check_executive(members, "place") == "Mayor"

    def test_mayor_not_found_in_county(self):
        """Mayor is a place executive, not county."""
        members = [{"name": "Bob", "title": "Mayor"}]
        assert check_executive(members, "county") is None

    def test_chairman_not_found_in_place(self):
        """Chairman is a county executive, not place."""
        members = [{"name": "Bob", "title": "Chairman"}]
        assert check_executive(members, "place") is None


# ---------------------------------------------------------------------------
# check_contact
# ---------------------------------------------------------------------------

class TestCheckContact:
    def test_contact_with_phone_and_email(self):
        meta = {"contact": {"phone": "(555) 123-4567", "email": "info@city.gov"}}
        assert check_contact(meta) == "(555) 123-4567 info@city.gov"

    def test_contact_with_phone_only(self):
        meta = {"contact": {"phone": "(555) 123-4567"}}
        assert check_contact(meta) == "(555) 123-4567"

    def test_contact_with_email_only(self):
        meta = {"contact": {"email": "info@city.gov"}}
        assert check_contact(meta) == "info@city.gov"

    def test_contact_with_label(self):
        meta = {"contact": {"label": "City Hall", "phone": "(555) 123-4567"}}
        assert check_contact(meta) == "City Hall (555) 123-4567"

    def test_empty_contact(self):
        meta = {"contact": {}}
        assert check_contact(meta) is None

    def test_missing_contact_key(self):
        meta = {}
        assert check_contact(meta) is None

    def test_contact_not_a_dict(self):
        meta = {"contact": "not a dict"}
        assert check_contact(meta) is None

    def test_contact_is_none(self):
        meta = {"contact": None}
        assert check_contact(meta) is None


# ---------------------------------------------------------------------------
# _has_title_match
# ---------------------------------------------------------------------------

class TestHasTitleMatch:
    def test_exact_match(self):
        assert _has_title_match("mayor", {"mayor"}) is True

    def test_match_within_longer_title(self):
        assert _has_title_match("the mayor of springfield", {"mayor"}) is True

    def test_no_match(self):
        assert _has_title_match("council member", {"mayor"}) is False

    def test_vice_prefix_blocks(self):
        assert _has_title_match("vice mayor", {"mayor"}) is False

    def test_deputy_prefix_blocks(self):
        assert _has_title_match("deputy chairman", {"chairman"}) is False

    def test_vice_hyphen_prefix_blocks(self):
        assert _has_title_match("vice-chairman", {"chairman"}) is False

    def test_partial_word_no_match(self):
        """'chairman' should not match inside 'chairmanship' if word boundary works."""
        assert _has_title_match("chairmanship", {"chairman"}) is False

    def test_multiple_targets_first_matches(self):
        assert _has_title_match("chair of the board", {"chair", "chairman"}) is True

    def test_empty_targets(self):
        assert _has_title_match("mayor", set()) is False


# ---------------------------------------------------------------------------
# format_summary
# ---------------------------------------------------------------------------

class TestFormatSummary:
    def test_basic_summary(self):
        local_results = [
            {"has_email": True, "has_phone": True, "executive": "Mayor", "contact": "(555) 123-4567", "members": 5},
            {"has_email": False, "has_phone": True, "executive": None, "contact": None, "members": 7},
            {"has_email": True, "has_phone": False, "executive": None, "contact": "(555) 999-0000", "members": 0},
        ]
        state_results = [
            {"state": "SC", "legislators": 170, "has_executive": True},
        ]
        result = format_summary(local_results, state_results)
        assert result.startswith("Coverage: ")
        assert "3 jurisdictions" in result
        assert "2 with email" in result
        assert "2 with phone" in result
        assert "1 with executive" in result
        assert "2 with contact info" in result
        assert "1 with 0 members" in result
        assert "SC state: 170 legislators (executive: yes)" in result

    def test_empty_results(self):
        result = format_summary([], [])
        assert "0 jurisdictions" in result
        assert "0 with email" in result

    def test_no_empty_members_omitted(self):
        local_results = [
            {"has_email": True, "has_phone": True, "executive": "Mayor", "contact": None, "members": 5},
        ]
        result = format_summary(local_results, [])
        assert "0 members" not in result


# ---------------------------------------------------------------------------
# analyze_local_file
# ---------------------------------------------------------------------------

class TestAnalyzeLocalFile:
    def test_valid_place_file(self, tmp_path):
        data = {
            "meta": {
                "state": "SC",
                "jurisdiction": "place:springfield",
                "label": "Springfield",
            },
            "members": [
                {"name": "Alice", "title": "Mayor", "email": "alice@city.gov", "phone": "(555) 123-4567"},
                {"name": "Bob", "title": "Council Member", "email": "", "phone": ""},
            ],
        }
        filepath = tmp_path / "place-springfield.json"
        filepath.write_text(json.dumps(data), encoding="utf-8")
        result = analyze_local_file(str(filepath))
        assert result is not None
        assert result["name"] == "place-springfield"
        assert result["label"] == "Springfield"
        assert result["state"] == "SC"
        assert result["members"] == 2
        assert result["has_email"] is True
        assert result["has_phone"] is True
        assert result["executive"] == "Mayor"

    def test_valid_county_file(self, tmp_path):
        data = {
            "meta": {
                "state": "SC",
                "jurisdiction": "county:greenville",
                "label": "Greenville County",
            },
            "members": [
                {"name": "Bob", "title": "Chairman", "email": "", "phone": ""},
            ],
        }
        filepath = tmp_path / "county-greenville.json"
        filepath.write_text(json.dumps(data), encoding="utf-8")
        result = analyze_local_file(str(filepath))
        assert result is not None
        assert result["executive"] == "Chairman"

    def test_invalid_json(self, tmp_path):
        filepath = tmp_path / "broken.json"
        filepath.write_text("NOT JSON", encoding="utf-8")
        assert analyze_local_file(str(filepath)) is None

    def test_file_not_found(self):
        assert analyze_local_file("/nonexistent/path.json") is None

    def test_jurisdiction_from_filename(self, tmp_path):
        """When meta.jurisdiction is empty, name falls back to filename stem."""
        data = {"meta": {"state": "SC"}, "members": []}
        filepath = tmp_path / "place-test-city.json"
        filepath.write_text(json.dumps(data), encoding="utf-8")
        result = analyze_local_file(str(filepath))
        assert result["name"] == "place-test-city"

    def test_contact_included(self, tmp_path):
        data = {
            "meta": {
                "state": "SC",
                "jurisdiction": "place:test",
                "contact": {"phone": "(555) 000-1111"},
            },
            "members": [],
        }
        filepath = tmp_path / "place-test.json"
        filepath.write_text(json.dumps(data), encoding="utf-8")
        result = analyze_local_file(str(filepath))
        assert result["contact"] == "(555) 000-1111"
