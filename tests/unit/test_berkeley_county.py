import os
import re
import pytest

# Import lazily so the test still reports a useful failure when the adapter
# file doesn't exist yet (rather than collection-time ImportError).

SNAPSHOT = os.path.join(os.path.dirname(__file__), "..", "fixtures",
                        "snapshots", "berkeley_county.html")


@pytest.fixture
def html():
    with open(SNAPSHOT, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def adapter():
    from scrapers.adapters.berkeley_county import BerkeleyCountyAdapter
    return BerkeleyCountyAdapter({
        "id": "county:berkeley",
        "url": "https://berkeleycountysc.gov/dept/council/elected-officials/",
        "adapterConfig": {},
    })


def _expected_district_ids(html: str) -> list[int]:
    """Discover the set of district numbers present in the snapshot."""
    ids = sorted({int(m.group(1))
                  for m in re.finditer(r"District\s+(\d+)", html)})
    assert ids and ids[0] == 1, "snapshot district numbering changed unexpectedly"
    # Must be contiguous from 1
    assert ids == list(range(1, ids[-1] + 1))
    return ids


class TestBerkeleyCountyParse:

    def test_district_count_matches_snapshot(self, adapter, html):
        expected = _expected_district_ids(html)
        members = adapter.parse(html)
        district_members = [m for m in members if "District" in m.get("title", "")]
        assert len(district_members) == len(expected)

    def test_district_ids_match_snapshot(self, adapter, html):
        expected = _expected_district_ids(html)
        members = adapter.parse(html)
        ids = sorted(int(re.search(r"District\s+(\d+)", m["title"]).group(1))
                     for m in members if "District" in m.get("title", ""))
        assert ids == expected

    def test_supervisor_present(self, adapter, html):
        members = adapter.parse(html)
        # Supervisor parses as Chairman-equivalent (chair leadership).
        assert any("Supervisor" in m.get("title", "") or m.get("title") == "Chairman"
                   for m in members)

    def test_full_pipeline_produces_numbered_seats(self, adapter, html):
        from scrapers.normalize import normalize_member, NormalizationContext
        raw = adapter.parse(html)
        ctx = NormalizationContext(level="local", jurisdiction_type="county",
                                   jurisdiction_id="county:berkeley")
        for r in raw:
            normalize_member(r, ctx)
        district_members = [m for m in raw if "District" in m.get("title", "")]
        for m in district_members:
            assert m["seatClass"] == "numbered"
            assert m["seatLabel"] == "district"
