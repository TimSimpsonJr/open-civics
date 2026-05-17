"""Tests for BaseAdapter contract from scrapers.adapters.base."""

import pytest
from scrapers.adapters.base import BaseAdapter


class StubAdapter(BaseAdapter):
    """Minimal concrete adapter for testing base class behavior."""

    def __init__(self, html="<html></html>", **kwargs):
        entry = {
            "id": "test-stub",
            "name": "Test Stub",
            "type": "place",
            "county": "Test",
            "url": "",
            "adapterConfig": {},
        }
        entry.update(kwargs)
        super().__init__(entry)
        self._test_html = html
        self._test_members = []

    def fetch(self) -> str:
        return self._test_html

    def parse(self, html: str) -> list[dict]:
        return self._test_members


class TestValidate:
    def test_raises_on_empty_list(self):
        adapter = StubAdapter()
        with pytest.raises(ValueError, match="produced 0 records"):
            adapter.validate([])

    def test_warns_missing_name(self):
        adapter = StubAdapter()
        records = [{"title": "Council Member", "email": "a@b.com"}]
        result = adapter.validate(records)
        assert len(result) == 1
        assert any("no name" in w for w in adapter.warnings)

    def test_warns_missing_title(self):
        adapter = StubAdapter()
        records = [{"name": "John", "email": "a@b.com"}]
        adapter.validate(records)
        assert any("no title" in w for w in adapter.warnings)

    def test_warns_no_contact_info(self):
        adapter = StubAdapter()
        records = [{"name": "John", "title": "Mayor"}]
        adapter.validate(records)
        assert any("no email or phone" in w for w in adapter.warnings)

    def test_valid_record_no_warnings(self):
        adapter = StubAdapter()
        records = [{"name": "John", "title": "Mayor", "email": "j@city.gov"}]
        adapter.validate(records)
        assert adapter.warnings == []


class TestNormalize:
    def test_normalizes_phone(self):
        adapter = StubAdapter()
        records = [{"name": "John", "phone": "803-555-1234"}]
        result = adapter.normalize(records)
        assert result[0]["phone"] == "(803) 555-1234"

    def test_sets_source_and_date(self):
        adapter = StubAdapter()
        records = [{"name": "John"}]
        result = adapter.normalize(records)
        # adapter_name() strips "adapter" suffix and lowercases: "StubAdapter" -> "stub"
        assert result[0]["source"] == "stub"
        assert "lastUpdated" in result[0]

    def test_preserves_existing_source(self):
        adapter = StubAdapter()
        records = [{"name": "John", "source": "custom"}]
        result = adapter.normalize(records)
        assert result[0]["source"] == "custom"


class TestGetContact:
    def test_default_returns_none(self):
        adapter = StubAdapter()
        assert adapter.get_contact() is None


class TestHtmlCaching:
    def test_html_initialized_to_none(self):
        adapter = StubAdapter()
        assert adapter._html is None

    def test_html_set_after_scrape(self):
        adapter = StubAdapter(html="<html>test</html>")
        adapter._test_members = [
            {"name": "John", "title": "Mayor", "email": "j@c.gov"}
        ]
        adapter.scrape()
        assert adapter._html == "<html>test</html>"


class TestAdapterName:
    def test_strips_adapter_suffix(self):
        adapter = StubAdapter()
        assert adapter.adapter_name() == "stub"


def test_base_adapter_normalize_calls_normalize_member():
    """BaseAdapter.normalize should populate structured seat fields."""
    from scrapers.adapters.base import BaseAdapter

    class DummyAdapter(BaseAdapter):
        def fetch(self): return ""
        def parse(self, html): return []

    adapter = DummyAdapter({"id": "place:test", "url": "http://example.com",
                            "type": "place"})
    raw = [{"name": "Joey Russo", "title": "Council Member, District 17",
            "email": "x@y.com", "phone": "8645551234"}]
    out = adapter.normalize(raw)
    assert out[0]["office"] == "council-member"
    assert out[0]["seatClass"] == "numbered"
    assert out[0]["seatId"] == "17"
    assert out[0]["vacant"] is False
    assert out[0]["partisan"] is False
