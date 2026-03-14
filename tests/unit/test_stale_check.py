"""Tests for stale detection logic from scripts/stale_check.py."""

import json
import os
import sys
from datetime import date, timedelta

import pytest

# scripts/ is not a Python package (no __init__.py), so add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts.stale_check import find_stale_files


def _write_local_json(data_dir, state, filename, meta):
    """Helper to write a local JSON file under data_dir/{state}/local/."""
    local_dir = os.path.join(data_dir, state, "local")
    os.makedirs(local_dir, exist_ok=True)
    filepath = os.path.join(local_dir, filename)
    data = {"meta": meta, "members": []}
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestFindStaleFiles:
    def test_old_file_flagged(self, tmp_path):
        old_date = (date.today() - timedelta(days=100)).isoformat()
        _write_local_json(tmp_path, "sc", "county-test.json", {
            "jurisdiction": "county:test",
            "label": "Test County",
            "dataLastChanged": old_date,
        })
        stale = find_stale_files(str(tmp_path), threshold_days=90)
        assert len(stale) == 1
        assert stale[0]["jurisdiction"] == "county:test"
        assert stale[0]["daysSinceChange"] == 100

    def test_recent_file_not_flagged(self, tmp_path):
        recent_date = (date.today() - timedelta(days=50)).isoformat()
        _write_local_json(tmp_path, "sc", "county-test.json", {
            "jurisdiction": "county:test",
            "label": "Test County",
            "dataLastChanged": recent_date,
        })
        stale = find_stale_files(str(tmp_path), threshold_days=90)
        assert len(stale) == 0

    def test_today_not_flagged(self, tmp_path):
        _write_local_json(tmp_path, "sc", "place-test.json", {
            "jurisdiction": "place:test",
            "label": "Test City",
            "dataLastChanged": date.today().isoformat(),
        })
        stale = find_stale_files(str(tmp_path), threshold_days=90)
        assert len(stale) == 0

    def test_falls_back_to_last_updated(self, tmp_path):
        old_date = (date.today() - timedelta(days=100)).isoformat()
        _write_local_json(tmp_path, "sc", "county-test.json", {
            "jurisdiction": "county:test",
            "label": "Test County",
            "lastUpdated": old_date,
            # no dataLastChanged key
        })
        stale = find_stale_files(str(tmp_path), threshold_days=90)
        assert len(stale) == 1
        assert stale[0]["dataLastChanged"] == old_date

    def test_data_last_changed_preferred_over_last_updated(self, tmp_path):
        """dataLastChanged takes precedence when both are present."""
        recent = (date.today() - timedelta(days=10)).isoformat()
        old = (date.today() - timedelta(days=200)).isoformat()
        _write_local_json(tmp_path, "sc", "county-test.json", {
            "jurisdiction": "county:test",
            "label": "Test County",
            "dataLastChanged": recent,
            "lastUpdated": old,
        })
        stale = find_stale_files(str(tmp_path), threshold_days=90)
        assert len(stale) == 0

    def test_skips_invalid_dates(self, tmp_path):
        _write_local_json(tmp_path, "sc", "county-test.json", {
            "jurisdiction": "county:test",
            "label": "Test County",
            "dataLastChanged": "not-a-date",
        })
        stale = find_stale_files(str(tmp_path), threshold_days=90)
        assert len(stale) == 0

    def test_skips_missing_dates(self, tmp_path):
        _write_local_json(tmp_path, "sc", "county-test.json", {
            "jurisdiction": "county:test",
            "label": "Test County",
        })
        stale = find_stale_files(str(tmp_path), threshold_days=90)
        assert len(stale) == 0

    def test_empty_directory(self, tmp_path):
        os.makedirs(tmp_path / "sc" / "local", exist_ok=True)
        stale = find_stale_files(str(tmp_path), threshold_days=90)
        assert stale == []

    def test_nonexistent_directory(self, tmp_path):
        stale = find_stale_files(str(tmp_path / "nope"), threshold_days=90)
        assert stale == []

    def test_invalid_json_skipped(self, tmp_path):
        local_dir = tmp_path / "sc" / "local"
        os.makedirs(local_dir, exist_ok=True)
        (local_dir / "broken.json").write_text("NOT JSON", encoding="utf-8")
        stale = find_stale_files(str(tmp_path), threshold_days=90)
        assert stale == []

    def test_multiple_states(self, tmp_path):
        old_date = (date.today() - timedelta(days=100)).isoformat()
        _write_local_json(tmp_path, "sc", "county-a.json", {
            "jurisdiction": "county:a",
            "label": "County A",
            "dataLastChanged": old_date,
        })
        _write_local_json(tmp_path, "nc", "county-b.json", {
            "jurisdiction": "county:b",
            "label": "County B",
            "dataLastChanged": old_date,
        })
        stale = find_stale_files(str(tmp_path), threshold_days=90)
        assert len(stale) == 2
