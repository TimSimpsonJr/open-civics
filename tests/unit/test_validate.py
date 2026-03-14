"""Tests for validate.py validator functions.

validate.py uses module-level errors and warnings lists. An autouse fixture
clears them between tests so each test starts with a clean slate.
"""

import pytest

import validate as val


@pytest.fixture(autouse=True)
def clear_validation_state():
    """Clear module-level errors/warnings before each test."""
    val.errors.clear()
    val.warnings.clear()
    yield
    val.errors.clear()
    val.warnings.clear()


# ---------------------------------------------------------------------------
# Helper builders
# ---------------------------------------------------------------------------

def _make_local_data(members=None, meta_overrides=None, contact=None):
    """Build a valid local council data dict."""
    meta = {
        "state": "SC",
        "level": "local",
        "jurisdiction": "place:test-city",
        "label": "Test City",
        "lastUpdated": "2025-01-01",
        "adapter": "table",
    }
    if contact is not None:
        meta["contact"] = contact
    if meta_overrides:
        meta.update(meta_overrides)
    if members is None:
        members = [
            {"name": "Alice", "title": "Mayor", "email": "alice@city.gov", "phone": "(555) 123-4567"},
            {"name": "Bob", "title": "Council Member", "email": "bob@city.gov", "phone": "(555) 987-6543"},
        ]
    return {"meta": meta, "members": members}


def _make_state_data(senate_count=46, house_count=124, state_code="SC",
                     executive=None, meta_overrides=None):
    """Build a valid state.json data dict."""
    meta = {
        "state": state_code,
        "level": "state",
        "lastUpdated": "2025-01-01",
        "source": "openstates",
    }
    if meta_overrides:
        meta.update(meta_overrides)

    senate = {}
    for i in range(1, senate_count + 1):
        senate[str(i)] = {
            "name": f"Senator {i}",
            "district": str(i),
            "email": f"senator{i}@senate.gov",
            "phone": "(803) 555-0001",
            "party": "R",
        }

    house = {}
    for i in range(1, house_count + 1):
        house[str(i)] = {
            "name": f"Rep {i}",
            "district": str(i),
            "email": f"rep{i}@house.gov",
            "phone": "(803) 555-0002",
            "party": "D",
        }

    data = {"meta": meta, "senate": senate, "house": house}
    if executive is not None:
        data["executive"] = executive
    return data


# ---------------------------------------------------------------------------
# validate_local_file
# ---------------------------------------------------------------------------

class TestValidateLocalFile:
    def test_valid_data_no_errors(self):
        data = _make_local_data()
        val.validate_local_file(data, "test.json")
        assert len(val.errors) == 0
        assert len(val.warnings) == 0

    def test_missing_meta_is_error(self):
        data = {"members": [{"name": "Alice", "title": "Mayor"}]}
        val.validate_local_file(data, "test.json")
        assert any("Missing 'meta'" in e for e in val.errors)

    def test_non_list_members_is_error(self):
        data = _make_local_data()
        data["members"] = "not a list"
        val.validate_local_file(data, "test.json")
        assert any("'members' must be a list" in e for e in val.errors)

    def test_empty_members_is_warning(self):
        data = _make_local_data(members=[])
        val.validate_local_file(data, "test.json")
        assert len(val.errors) == 0
        assert any("0 members" in w for w in val.warnings)

    def test_admin_title_is_warning(self):
        data = _make_local_data(members=[
            {"name": "Jane", "title": "City Clerk"},
        ])
        val.validate_local_file(data, "test.json")
        assert any("admin staff" in w for w in val.warnings)

    def test_bad_phone_format_is_warning(self):
        data = _make_local_data(members=[
            {"name": "Alice", "title": "Mayor", "phone": "555-1234"},
        ])
        val.validate_local_file(data, "test.json")
        assert any("unexpected phone format" in w for w in val.warnings)

    def test_bad_email_format_is_warning(self):
        data = _make_local_data(members=[
            {"name": "Alice", "title": "Mayor", "email": "not-an-email"},
        ])
        val.validate_local_file(data, "test.json")
        assert any("invalid email format" in w for w in val.warnings)

    def test_valid_contact(self):
        data = _make_local_data(contact={"phone": "(555) 123-4567", "email": "info@city.gov"})
        val.validate_local_file(data, "test.json")
        assert len(val.errors) == 0
        assert len(val.warnings) == 0

    def test_contact_not_a_dict_is_error(self):
        data = _make_local_data(contact="not a dict")
        val.validate_local_file(data, "test.json")
        assert any("meta.contact must be an object" in e for e in val.errors)

    def test_contact_bad_phone_is_warning(self):
        data = _make_local_data(contact={"phone": "bad"})
        val.validate_local_file(data, "test.json")
        assert any("meta.contact.phone" in w for w in val.warnings)

    def test_contact_bad_email_is_warning(self):
        data = _make_local_data(contact={"email": "bad"})
        val.validate_local_file(data, "test.json")
        assert any("meta.contact.email" in w for w in val.warnings)

    def test_missing_member_name_is_error(self):
        data = _make_local_data(members=[{"title": "Mayor"}])
        val.validate_local_file(data, "test.json")
        assert any("missing 'name'" in e for e in val.errors)

    def test_missing_meta_fields(self):
        data = _make_local_data(meta_overrides={"adapter": "", "label": ""})
        val.validate_local_file(data, "test.json")
        assert any("missing 'adapter'" in e for e in val.errors)
        assert any("missing 'label'" in e for e in val.errors)

    def test_non_dict_root_is_error(self):
        val.validate_local_file([], "test.json")
        assert any("Root must be an object" in e for e in val.errors)


# ---------------------------------------------------------------------------
# validate_state_json
# ---------------------------------------------------------------------------

class TestValidateStateJson:
    def test_valid_data_no_errors(self):
        data = _make_state_data()
        val.validate_state_json(data, "SC", "state.json")
        assert len(val.errors) == 0
        assert len(val.warnings) == 0

    def test_senate_member_drop_detection(self):
        """If senate has < 50% of expected count, it's an error."""
        data = _make_state_data(senate_count=20)  # expected 46, 20 < 23
        val.validate_state_json(data, "SC", "state.json")
        assert any(">50% drop" in e for e in val.errors)

    def test_house_member_drop_detection(self):
        data = _make_state_data(house_count=50)  # expected 124, 50 < 62
        val.validate_state_json(data, "SC", "state.json")
        assert any(">50% drop" in e for e in val.errors)

    def test_no_drop_for_unknown_state(self):
        """States not in STATE_EXPECTED_COUNTS don't trigger drop detection."""
        data = _make_state_data(senate_count=5, house_count=5, state_code="XX")
        val.validate_state_json(data, "XX", "state.json")
        drop_errors = [e for e in val.errors if ">50% drop" in e]
        assert len(drop_errors) == 0

    def test_bad_email_is_warning(self):
        data = _make_state_data(senate_count=46, house_count=124)
        data["senate"]["1"]["email"] = "bad-email"
        val.validate_state_json(data, "SC", "state.json")
        assert any("invalid email format" in w for w in val.warnings)

    def test_bad_phone_is_warning(self):
        data = _make_state_data()
        data["house"]["1"]["phone"] = "555-1234"
        val.validate_state_json(data, "SC", "state.json")
        assert any("unexpected phone format" in w for w in val.warnings)

    def test_missing_meta_is_error(self):
        data = _make_state_data()
        del data["meta"]
        val.validate_state_json(data, "SC", "state.json")
        assert any("Missing 'meta'" in e for e in val.errors)

    def test_missing_senate_is_error(self):
        data = _make_state_data()
        del data["senate"]
        val.validate_state_json(data, "SC", "state.json")
        assert any("Missing 'senate'" in e for e in val.errors)

    def test_valid_executive(self):
        data = _make_state_data(executive=[
            {"name": "Gov Smith", "title": "Governor", "email": "gov@sc.gov", "phone": "(803) 555-0000"},
        ])
        val.validate_state_json(data, "SC", "state.json")
        assert len(val.errors) == 0

    def test_executive_missing_name_is_error(self):
        data = _make_state_data(executive=[
            {"title": "Governor"},
        ])
        val.validate_state_json(data, "SC", "state.json")
        assert any("missing 'name'" in e for e in val.errors)

    def test_executive_missing_title_is_error(self):
        data = _make_state_data(executive=[
            {"name": "Gov Smith"},
        ])
        val.validate_state_json(data, "SC", "state.json")
        assert any("missing 'title'" in e for e in val.errors)

    def test_executive_not_a_list_is_error(self):
        data = _make_state_data(executive="not a list")
        val.validate_state_json(data, "SC", "state.json")
        assert any("'executive' must be a list" in e for e in val.errors)

    def test_non_dict_root_is_error(self):
        val.validate_state_json([], "SC", "state.json")
        assert any("Root must be an object" in e for e in val.errors)

    def test_state_code_mismatch_is_error(self):
        data = _make_state_data(state_code="NC")
        val.validate_state_json(data, "SC", "state.json")
        assert any("expected 'SC'" in e for e in val.errors)

    def test_unexpected_party_is_warning(self):
        data = _make_state_data()
        data["senate"]["1"]["party"] = "X"
        val.validate_state_json(data, "SC", "state.json")
        assert any("unexpected party" in w for w in val.warnings)
