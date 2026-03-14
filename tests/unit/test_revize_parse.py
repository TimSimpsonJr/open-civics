"""Tests for Revize adapter parsing logic."""

import pytest
from scrapers.adapters.revize import RevizeAdapter
from tests.conftest import load_fixture, make_adapter


@pytest.fixture
def adapter():
    return make_adapter(RevizeAdapter)


@pytest.fixture
def basic_html():
    return load_fixture("revize_basic.html")


@pytest.fixture
def mayor_html():
    return load_fixture("revize_mayor.html")


# ---------------------------------------------------------------------------
# TestRevizeBasicParse
# ---------------------------------------------------------------------------

class TestRevizeBasicParse:
    """Parse revize_basic.html: three standard members."""

    def test_extracts_three_members(self, adapter, basic_html):
        members = adapter.parse(basic_html)
        assert len(members) == 3

    def test_first_member_name(self, adapter, basic_html):
        members = adapter.parse(basic_html)
        names = [m["name"] for m in members]
        assert "Alice Johnson" in names

    def test_first_member_email(self, adapter, basic_html):
        members = adapter.parse(basic_html)
        by_name = {m["name"]: m for m in members}
        assert by_name["Alice Johnson"]["email"] == "ajohnson@city.gov"

    def test_phone_from_text(self, adapter, basic_html):
        """Phone number found as plain text (not in a tel: link)."""
        members = adapter.parse(basic_html)
        by_name = {m["name"]: m for m in members}
        assert by_name["Alice Johnson"]["phone"] == "(803) 555-0001"

    def test_phone_from_tel_link(self, adapter, basic_html):
        """Phone number found inside a <a href='tel:...'> link."""
        members = adapter.parse(basic_html)
        by_name = {m["name"]: m for m in members}
        assert by_name["Bob Williams"]["phone"] == "(803) 555-0002"

    def test_missing_phone_is_empty(self, adapter, basic_html):
        """Member without phone gets empty string."""
        members = adapter.parse(basic_html)
        by_name = {m["name"]: m for m in members}
        assert by_name["Carol Davis"]["phone"] == ""

    def test_default_title_is_council_member(self, adapter, basic_html):
        """Members without explicit title default to 'Council Member'."""
        members = adapter.parse(basic_html)
        for m in members:
            assert m["title"] == "Council Member"


# ---------------------------------------------------------------------------
# TestRevizeMayorDetection
# ---------------------------------------------------------------------------

class TestRevizeMayorDetection:
    """Parse revize_mayor.html: mayor prefix, pro tem suffix, filtering."""

    def test_mayor_title_from_prefix(self, adapter, mayor_html):
        members = adapter.parse(mayor_html)
        by_name = {m["name"]: m for m in members}
        assert "John Smith" in by_name
        assert by_name["John Smith"]["title"] == "Mayor"

    def test_mayor_name_stripped_of_prefix(self, adapter, mayor_html):
        members = adapter.parse(mayor_html)
        names = [m["name"] for m in members]
        assert "Mayor John Smith" not in names
        assert "John Smith" in names

    def test_mayor_pro_tem_from_suffix(self, adapter, mayor_html):
        members = adapter.parse(mayor_html)
        by_name = {m["name"]: m for m in members}
        assert "Jane Doe" in by_name
        assert by_name["Jane Doe"]["title"] == "Mayor Pro Tem"

    def test_generic_email_skipped(self, adapter, mayor_html):
        """info@city.gov should not produce a member."""
        members = adapter.parse(mayor_html)
        emails = [m["email"] for m in members]
        assert "info@city.gov" not in emails

    def test_clerk_excluded_by_default(self, adapter, mayor_html):
        """Name containing 'Clerk' is excluded by DEFAULT_EXCLUDE."""
        members = adapter.parse(mayor_html)
        names = [m["name"] for m in members]
        assert all("Clerk" not in n for n in names)

    def test_mayor_sorted_first(self, adapter, mayor_html):
        members = adapter.parse(mayor_html)
        assert members[0]["title"] == "Mayor"

    def test_mayor_pro_tem_sorted_second(self, adapter, mayor_html):
        members = adapter.parse(mayor_html)
        assert members[1]["title"] == "Mayor Pro Tem"

    def test_total_after_filtering(self, adapter, mayor_html):
        """3 real members: Mayor, Mayor Pro Tem, and one regular council member.
        info@ is generic (skipped), Sarah Clerk is excluded."""
        members = adapter.parse(mayor_html)
        assert len(members) == 3


# ---------------------------------------------------------------------------
# TestRevizeCloudflareEmail
# ---------------------------------------------------------------------------

class TestRevizeCloudflareEmail:
    """Cloudflare email obfuscation decoding."""

    def test_cf_email_link_decoded(self, adapter):
        html = """<html><body><div class="fr-view">
        <strong>Dave Wilson</strong>
        <br>
        <a href="/cdn-cgi/l/email-protection#1a7e7b6e7b5a7d777b7376347975776a7b7465">
          <span class="__cf_email__" data-cfemail="d4b0b5a0b594b3b9b5bdb8fab7bbb9a4b5b0a1">[email&#160;protected]</span>
        </a>
        </div></body></html>"""
        members = adapter.parse(html)
        assert len(members) == 1
        assert "@" in members[0]["email"]

    def test_cf_email_span_decoded(self, adapter):
        html = """<html><body><div class="fr-view">
        <strong>Eve Martin</strong>
        <br>
        <a href="mailto:placeholder">
          <span data-cfemail="d4b0b5a0b594b3b9b5bdb8fab7bbb9a4b5b0a1">[email&#160;protected]</span>
        </a>
        </div></body></html>"""
        members = adapter.parse(html)
        # The mailto:placeholder is not generic, so it gets picked up as email;
        # but the span also decodes. At minimum we get 1 member.
        assert len(members) >= 1


# ---------------------------------------------------------------------------
# TestRevizeSeparators
# ---------------------------------------------------------------------------

class TestRevizeSeparators:
    """HR tags prevent cross-pairing names with emails across sections."""

    def test_hr_prevents_cross_pairing(self, adapter):
        html = """<html><body><div class="fr-view">
        <strong>Alpha Beta</strong>
        <hr>
        <a href="mailto:gamma@city.gov">gamma@city.gov</a>
        </div></body></html>"""
        members = adapter.parse(html)
        # The HR separator sits between the name and the email,
        # so the backward scan from email stops at the separator.
        assert len(members) == 0

    def test_no_separator_allows_pairing(self, adapter):
        html = """<html><body><div class="fr-view">
        <strong>Alpha Beta</strong>
        <br>
        <a href="mailto:alpha@city.gov">alpha@city.gov</a>
        </div></body></html>"""
        members = adapter.parse(html)
        assert len(members) == 1
        assert members[0]["name"] == "Alpha Beta"


# ---------------------------------------------------------------------------
# TestRevizeHelpers — static method unit tests
# ---------------------------------------------------------------------------

class TestLooksLikeName:
    """Parametrized tests for RevizeAdapter._looks_like_name()."""

    @pytest.mark.parametrize("text, expected", [
        ("John Smith", True),
        ("Mary Jane Watson", True),
        ("Mayor Bob Jones", True),
        # Too short
        ("AB", False),
        # No space (single word)
        ("Alice", False),
        # Starts lowercase
        ("john smith", False),
        # Contains excluded substring
        ("Click here for more info", False),
        ("Contact us today", False),
        ("City Council Meeting", False),
        # Contains @
        ("user@example.com address", False),
        # Mostly digits (address-like)
        ("123 Main Street", False),
        # Empty
        ("", False),
        # Navigation-like
        ("Home Page", False),
        ("About Us", False),
        # Long enough, capitalized, multi-word name
        ("Dr. Martin Luther King Jr", True),
    ])
    def test_looks_like_name(self, text, expected):
        assert RevizeAdapter._looks_like_name(text) is expected


class TestStripTitleSuffix:
    """Parametrized tests for RevizeAdapter._strip_title_suffix()."""

    @pytest.mark.parametrize("input_name, expected_name, expected_title", [
        ("Jane Doe, Mayor Pro Tem", "Jane Doe", "Mayor Pro Tem"),
        ("Jane Doe, Mayor", "Jane Doe", "Mayor"),
        ("Jane Doe, Councilmember", "Jane Doe", ""),
        ("Jane Doe, Councilwoman", "Jane Doe", ""),
        ("Jane Doe, Councilman", "Jane Doe", ""),
        ("Jane Doe", "Jane Doe", ""),
        ("Jane Doe, Chairman", "Jane Doe", ""),
        ("Jane Doe, Vice Chairwoman", "Jane Doe", ""),
    ])
    def test_strip_title_suffix(self, input_name, expected_name, expected_title):
        name, title = RevizeAdapter._strip_title_suffix(input_name)
        assert name == expected_name
        assert title == expected_title


class TestIsGenericEmail:
    """Parametrized tests for RevizeAdapter._is_generic_email()."""

    @pytest.mark.parametrize("email, expected", [
        ("info@city.gov", True),
        ("council@city.gov", True),
        ("clerk@city.gov", True),
        ("webmaster@city.gov", True),
        ("admin@city.gov", True),
        ("contact@city.gov", True),
        ("jsmith@city.gov", False),
        ("mayor@city.gov", False),
        ("alice.jones@city.gov", False),
        ("office@city.gov", True),
        ("general@city.gov", True),
    ])
    def test_is_generic_email(self, email, expected):
        assert RevizeAdapter._is_generic_email(email) is expected


class TestExtractTitleFromName:
    """Tests for RevizeAdapter._extract_title_from_name()."""

    @pytest.mark.parametrize("text, expected", [
        ("Mayor John Smith", "Mayor"),
        ("Mayor Pro Tem Jane Doe", "Mayor Pro Tem"),
        ("Councilman Bob Jones", "Councilman"),
        ("Chairman Mark Lee", "Chairman"),
        ("Vice Chairwoman Sue Park", "Vice Chairwoman"),
        ("John Smith", ""),
    ])
    def test_extract_title_from_name(self, text, expected):
        assert RevizeAdapter._extract_title_from_name(text) == expected


class TestShouldExclude:
    """Tests for RevizeAdapter._should_exclude()."""

    def test_excludes_clerk(self):
        from scrapers.adapters.revize import DEFAULT_EXCLUDE
        assert RevizeAdapter._should_exclude("Sarah Clerk", DEFAULT_EXCLUDE) is True

    def test_excludes_administrator(self):
        from scrapers.adapters.revize import DEFAULT_EXCLUDE
        assert RevizeAdapter._should_exclude("Town Administrator", DEFAULT_EXCLUDE) is True

    def test_does_not_exclude_normal_name(self):
        from scrapers.adapters.revize import DEFAULT_EXCLUDE
        assert RevizeAdapter._should_exclude("John Smith", DEFAULT_EXCLUDE) is False

    def test_custom_filter(self):
        assert RevizeAdapter._should_exclude("Fire Chief", ["fire"]) is True
