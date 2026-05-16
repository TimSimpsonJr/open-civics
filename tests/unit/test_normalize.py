"""Unit tests for scrapers.normalize."""

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
