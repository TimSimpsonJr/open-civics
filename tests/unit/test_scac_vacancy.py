import os

import pytest

SNAPSHOT = os.path.join(os.path.dirname(__file__), "..", "fixtures",
                        "snapshots", "scac_dorchester.html")

# The 7 sitting Dorchester County Council members as of 2026-06-09 (verified
# against news coverage + Ballotpedia; District 6 = Frankie Staropoli, who won
# the 2026 special election to replace Bill Hearn after Hearn became county
# attorney). The SCAC directory also lists a stale "DorchesterCouncil Vacant"
# placeholder row, which the adapter must skip.
EXPECTED_NAMES = {
    "Peter Smith", "C. David Chinnis", "Rita May Ranck", "S. Todd Friddle",
    "Edward Crosby", "Frankie Staropoli", "James Byars",
}


@pytest.fixture
def html():
    with open(SNAPSHOT, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def adapter():
    from scrapers.adapters.scac import ScacAdapter
    return ScacAdapter({
        "id": "county:dorchester",
        "url": "https://www.dorchestercountysc.gov/government/county-council/council-members",
    })


class TestScacVacancy:

    def test_skips_vacant_placeholder_row(self, adapter, html):
        names = {m["name"] for m in adapter.parse(html)}
        assert not any("vacant" in n.lower() for n in names)

    def test_returns_seven_real_members(self, adapter, html):
        assert {m["name"] for m in adapter.parse(html)} == EXPECTED_NAMES
