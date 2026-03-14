"""Tests for CivicPlus adapter parsing logic."""

import pytest
from bs4 import BeautifulSoup
from scrapers.adapters.civicplus import CivicPlusAdapter, DEFAULT_EXCLUDE
from tests.conftest import load_fixture, make_adapter


@pytest.fixture
def adapter():
    return make_adapter(CivicPlusAdapter, {
        "adapterConfig": {
            "baseUrl": "https://www.testcounty.gov",
            "councilPageId": "189/Council",
            "directoryDeptId": "42",
        },
    })


@pytest.fixture
def directory_html():
    return load_fixture("civicplus_directory.html")


# ---------------------------------------------------------------------------
# TestCivicPlusParse
# ---------------------------------------------------------------------------

class TestCivicPlusParse:
    """Parse civicplus_directory.html: 4 rows, clerk excluded, 3 members."""

    def test_extracts_three_members(self, adapter, directory_html):
        """Clerk row is excluded, leaving 3 council members."""
        members = adapter.parse(directory_html)
        assert len(members) == 3

    def test_clerk_excluded(self, adapter, directory_html):
        """Davis (Clerk to County Council) should be filtered out."""
        members = adapter.parse(directory_html)
        names = [m["name"] for m in members]
        assert "Tom Davis" not in names

    def test_name_flipping(self, adapter, directory_html):
        """'Smith, John' -> 'John Smith'."""
        members = adapter.parse(directory_html)
        names = [m["name"] for m in members]
        assert "John Smith" in names
        assert "Jane Williams" in names
        assert "Alice Brown" in names

    def test_chairman_title_normalized(self, adapter, directory_html):
        """'County Council Chairman' normalizes to 'Chairman'."""
        members = adapter.parse(directory_html)
        by_name = {m["name"]: m for m in members}
        assert by_name["John Smith"]["title"] == "Chairman"

    def test_district_title_normalized(self, adapter, directory_html):
        """'District 3 Representative' normalizes to 'Council Member, District 3'."""
        members = adapter.parse(directory_html)
        by_name = {m["name"]: m for m in members}
        assert by_name["Jane Williams"]["title"] == "Council Member, District 3"

    def test_vice_chairman_title_normalized(self, adapter, directory_html):
        """'Vice Chairman' stays 'Vice Chairman'."""
        members = adapter.parse(directory_html)
        by_name = {m["name"]: m for m in members}
        assert by_name["Alice Brown"]["title"] == "Vice Chairman"

    def test_js_email_extraction(self, adapter, directory_html):
        """JS-obfuscated emails are reconstructed from var w/x."""
        members = adapter.parse(directory_html)
        by_name = {m["name"]: m for m in members}
        assert by_name["John Smith"]["email"] == "jsmith@county.gov"
        assert by_name["Jane Williams"]["email"] == "jwilliams@county.gov"
        assert by_name["Alice Brown"]["email"] == "abrown@county.gov"

    def test_phone_formatting_parentheses(self, adapter, directory_html):
        """'(864) 596-2528' -> '(864) 596-2528'."""
        members = adapter.parse(directory_html)
        by_name = {m["name"]: m for m in members}
        assert by_name["John Smith"]["phone"] == "(864) 596-2528"

    def test_phone_formatting_dashes(self, adapter, directory_html):
        """'864-596-2529' -> '(864) 596-2529'."""
        members = adapter.parse(directory_html)
        by_name = {m["name"]: m for m in members}
        assert by_name["Jane Williams"]["phone"] == "(864) 596-2529"

    def test_phone_formatting_dots(self, adapter, directory_html):
        """'864.596.2530' -> '(864) 596-2530'."""
        members = adapter.parse(directory_html)
        by_name = {m["name"]: m for m in members}
        assert by_name["Alice Brown"]["phone"] == "(864) 596-2530"

    def test_sort_order(self, adapter, directory_html):
        """Chairman first, Vice Chairman second, then district members."""
        members = adapter.parse(directory_html)
        titles = [m["title"] for m in members]
        assert titles[0] == "Chairman"
        assert titles[1] == "Vice Chairman"
        assert titles[2] == "Council Member, District 3"

    def test_no_table_raises(self, adapter):
        """Missing directory table raises RuntimeError."""
        with pytest.raises(RuntimeError, match="Could not find the staff directory table"):
            adapter.parse("<html><body><p>No table here</p></body></html>")


# ---------------------------------------------------------------------------
# TestCivicPlusHelpers
# ---------------------------------------------------------------------------

class TestCivicPlusFlipName:
    """Tests for CivicPlusAdapter._flip_name()."""

    @pytest.mark.parametrize("raw, expected", [
        ("Smith, John", "John Smith"),
        ("Lynch, A. Manning", "A. Manning Lynch"),
        ("O'Brien, Mary", "Mary O'Brien"),
        ("John Smith", "John Smith"),
        ("  Williams, Jane  ", "Jane Williams"),
    ])
    def test_flip_name(self, raw, expected):
        assert CivicPlusAdapter._flip_name(raw) == expected


class TestCivicPlusNormalizeTitle:
    """Tests for CivicPlusAdapter._normalize_title()."""

    @pytest.mark.parametrize("raw, expected", [
        ("County Council Chairman", "Chairman"),
        ("Vice Chairman", "Vice Chairman"),
        ("District 1 Representative", "Council Member, District 1"),
        ("District 12 Representative", "Council Member, District 12"),
        ("Council Member At-Large", "Council Member, At Large"),
        ("At Large Representative", "Council Member, At Large"),
        ("Treasurer", "Treasurer"),
    ])
    def test_normalize_title(self, raw, expected):
        assert CivicPlusAdapter._normalize_title(raw) == expected


class TestCivicPlusShouldExclude:
    """Tests for CivicPlusAdapter._should_exclude()."""

    def test_excludes_clerk_by_default(self):
        assert CivicPlusAdapter._should_exclude("Clerk to County Council", DEFAULT_EXCLUDE) is True

    def test_excludes_clerk_case_insensitive(self):
        assert CivicPlusAdapter._should_exclude("CLERK TO COUNCIL", DEFAULT_EXCLUDE) is True

    def test_does_not_exclude_chairman(self):
        assert CivicPlusAdapter._should_exclude("County Council Chairman", DEFAULT_EXCLUDE) is False

    def test_custom_filter(self):
        assert CivicPlusAdapter._should_exclude("Fire Chief", ["fire"]) is True
        assert CivicPlusAdapter._should_exclude("Chairman", ["fire"]) is False


class TestCivicPlusDiscoverDirectoryId:
    """Tests for CivicPlusAdapter._discover_directory_id()."""

    def test_finds_directory_id(self):
        html = '<a href="/directory.aspx?did=42">Directory</a>'
        assert CivicPlusAdapter._discover_directory_id(html) == "42"

    def test_finds_id_case_insensitive(self):
        html = '<a href="/Directory.aspx?DID=99">Staff</a>'
        assert CivicPlusAdapter._discover_directory_id(html) == "99"

    def test_returns_empty_when_missing(self):
        html = "<html><body><p>No directory link</p></body></html>"
        assert CivicPlusAdapter._discover_directory_id(html) == ""


class TestCivicPlusExtractEmail:
    """Tests for CivicPlusAdapter._extract_email()."""

    def test_extracts_from_js_vars(self):
        html = '<td><script type="text/javascript">var w = "jsmith"; var x = "county.gov"; document.write("test");</script></td>'
        soup = BeautifulSoup(html, "html.parser")
        cell = soup.find("td")
        assert CivicPlusAdapter._extract_email(cell) == "jsmith@county.gov"

    def test_falls_back_to_mailto(self):
        html = '<td><a href="mailto:direct@county.gov">direct@county.gov</a></td>'
        soup = BeautifulSoup(html, "html.parser")
        cell = soup.find("td")
        assert CivicPlusAdapter._extract_email(cell) == "direct@county.gov"

    def test_empty_when_no_email(self):
        html = "<td>No email</td>"
        soup = BeautifulSoup(html, "html.parser")
        cell = soup.find("td")
        assert CivicPlusAdapter._extract_email(cell) == ""

    def test_empty_script_no_vars(self):
        html = '<td><script type="text/javascript">alert("hi");</script></td>'
        soup = BeautifulSoup(html, "html.parser")
        cell = soup.find("td")
        assert CivicPlusAdapter._extract_email(cell) == ""


class TestCivicPlusFormatPhone:
    """Tests for CivicPlusAdapter._format_phone()."""

    @pytest.mark.parametrize("raw, expected", [
        ("(864) 596-2528", "(864) 596-2528"),
        ("864-596-2529", "(864) 596-2529"),
        ("864.596.2530", "(864) 596-2530"),
        ("", ""),
    ])
    def test_format_phone(self, raw, expected):
        assert CivicPlusAdapter._format_phone(raw) == expected
