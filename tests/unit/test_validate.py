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

def _make_member(**overrides):
    """Build a local council member with all required normalized fields.

    Defaults to a numbered council seat. Pass overrides to customize.
    """
    member = {
        "name": "Council Person",
        "title": "Council Member, District 1",
        "email": "person@city.gov",
        "phone": "(555) 123-4567",
        "office": "council-member",
        "leadership": None,
        "seatClass": "numbered",
        "seatLabel": "district",
        "seatId": "1",
        "seatSource": "parsed-title",
        "vacant": False,
        "partisan": False,
    }
    member.update(overrides)
    return member


def _make_mayor(**overrides):
    """Build a valid mayor member (at-large)."""
    return _make_member(**{
        "name": "Mayor Person",
        "title": "Mayor",
        "office": "mayor",
        "seatClass": "at-large",
        "seatLabel": None,
        "seatId": None,
        **overrides,
    })


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
            _make_mayor(name="Alice", email="alice@city.gov", phone="(555) 123-4567"),
            _make_member(name="Bob", title="Council Member, District 2", seatId="2",
                         email="bob@city.gov", phone="(555) 987-6543"),
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
            "office": "state-senator",
            "leadership": None,
            "seatClass": "numbered",
            "seatLabel": "district",
            "seatId": str(i),
            "seatSource": "source",
            "vacant": False,
            "partisan": True,
        }

    house = {}
    for i in range(1, house_count + 1):
        house[str(i)] = {
            "name": f"Rep {i}",
            "district": str(i),
            "email": f"rep{i}@house.gov",
            "phone": "(803) 555-0002",
            "party": "D",
            "office": "state-representative",
            "leadership": None,
            "seatClass": "numbered",
            "seatLabel": "district",
            "seatId": str(i),
            "seatSource": "source",
            "vacant": False,
            "partisan": True,
        }

    data = {"meta": meta, "senate": senate, "house": house}
    if executive is not None:
        data["executive"] = executive
    return data


def _make_executive(**overrides):
    """Build a valid executive (governor) record."""
    member = {
        "name": "Gov Smith",
        "title": "Governor",
        "email": "gov@sc.gov",
        "phone": "(803) 555-0000",
        "office": "governor",
        "leadership": None,
        "seatClass": "at-large",
        "seatLabel": None,
        "seatId": None,
        "seatSource": "source",
        "vacant": False,
        "partisan": True,
    }
    member.update(overrides)
    return member


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
        data = _make_state_data(executive=[_make_executive()])
        val.validate_state_json(data, "SC", "state.json")
        assert len(val.errors) == 0

    def test_executive_missing_name_is_error(self):
        exec_member = _make_executive()
        del exec_member["name"]
        data = _make_state_data(executive=[exec_member])
        val.validate_state_json(data, "SC", "state.json")
        assert any("missing 'name'" in e for e in val.errors)

    def test_executive_missing_title_is_error(self):
        exec_member = _make_executive()
        del exec_member["title"]
        data = _make_state_data(executive=[exec_member])
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


# ---------------------------------------------------------------------------
# Normalized seat fields (validate_local_file + validate_state_json)
# ---------------------------------------------------------------------------

class TestNormalizedFieldsLocal:
    """Verify _validate_normalized_fields runs against local council members."""

    def test_valid_normalized_record_no_errors(self):
        data = _make_local_data()
        val.validate_local_file(data, "test.json")
        assert len(val.errors) == 0

    def test_missing_office_is_error(self):
        m = _make_member()
        del m["office"]
        data = _make_local_data(members=[m])
        val.validate_local_file(data, "test.json")
        assert any("office" in e and "not in" in e for e in val.errors)

    def test_invalid_office_is_error(self):
        m = _make_member(office="dogcatcher")
        data = _make_local_data(members=[m])
        val.validate_local_file(data, "test.json")
        assert any("office 'dogcatcher'" in e for e in val.errors)

    def test_missing_leadership_is_error(self):
        m = _make_member()
        del m["leadership"]
        data = _make_local_data(members=[m])
        val.validate_local_file(data, "test.json")
        assert any("missing 'leadership'" in e for e in val.errors)

    def test_null_leadership_is_valid(self):
        m = _make_member(leadership=None)
        data = _make_local_data(members=[m])
        val.validate_local_file(data, "test.json")
        assert len(val.errors) == 0

    def test_invalid_leadership_is_error(self):
        m = _make_member(leadership="president")
        data = _make_local_data(members=[m])
        val.validate_local_file(data, "test.json")
        assert any("leadership 'president'" in e for e in val.errors)

    def test_invalid_seat_class_is_error(self):
        m = _make_member(seatClass="ranked")
        data = _make_local_data(members=[m])
        val.validate_local_file(data, "test.json")
        assert any("seatClass 'ranked'" in e for e in val.errors)

    def test_missing_seat_label_is_error(self):
        m = _make_member()
        del m["seatLabel"]
        data = _make_local_data(members=[m])
        val.validate_local_file(data, "test.json")
        assert any("missing 'seatLabel'" in e for e in val.errors)

    def test_invalid_seat_label_is_error(self):
        m = _make_member(seatLabel="zone")
        data = _make_local_data(members=[m])
        val.validate_local_file(data, "test.json")
        assert any("seatLabel 'zone'" in e for e in val.errors)

    def test_missing_seat_id_is_error(self):
        m = _make_member()
        del m["seatId"]
        data = _make_local_data(members=[m])
        val.validate_local_file(data, "test.json")
        assert any("missing 'seatId'" in e for e in val.errors)

    def test_invalid_seat_source_is_error(self):
        m = _make_member(seatSource="guessed")
        data = _make_local_data(members=[m])
        val.validate_local_file(data, "test.json")
        assert any("seatSource 'guessed'" in e for e in val.errors)

    def test_vacant_not_bool_is_error(self):
        m = _make_member(vacant="yes")
        data = _make_local_data(members=[m])
        val.validate_local_file(data, "test.json")
        assert any("vacant must be boolean" in e for e in val.errors)

    def test_missing_partisan_is_error(self):
        m = _make_member()
        del m["partisan"]
        data = _make_local_data(members=[m])
        val.validate_local_file(data, "test.json")
        assert any("missing 'partisan'" in e for e in val.errors)

    def test_partisan_false_does_not_require_party(self):
        """A non-partisan member without a 'party' field should validate clean."""
        m = _make_member(partisan=False)
        assert "party" not in m
        data = _make_local_data(members=[m])
        val.validate_local_file(data, "test.json")
        assert len(val.errors) == 0


class TestSeatInvariants:
    """Cross-field invariants on seatClass / seatLabel / seatId / office / leadership."""

    def test_at_large_must_have_null_seat_label(self):
        m = _make_member(seatClass="at-large", seatLabel="district", seatId=None)
        data = _make_local_data(members=[m])
        val.validate_local_file(data, "test.json")
        assert any("at-large" in e and "null seatLabel" in e for e in val.errors)

    def test_at_large_must_have_null_seat_id(self):
        m = _make_member(seatClass="at-large", seatLabel=None, seatId="1")
        data = _make_local_data(members=[m])
        val.validate_local_file(data, "test.json")
        assert any("at-large" in e for e in val.errors)

    def test_at_large_with_nulls_is_valid(self):
        m = _make_member(seatClass="at-large", seatLabel=None, seatId=None)
        data = _make_local_data(members=[m])
        val.validate_local_file(data, "test.json")
        assert len(val.errors) == 0

    def test_numbered_must_have_seat_label(self):
        m = _make_member(seatClass="numbered", seatLabel=None, seatId="1")
        data = _make_local_data(members=[m])
        val.validate_local_file(data, "test.json")
        assert any("numbered" in e for e in val.errors)

    def test_numbered_must_have_seat_id(self):
        m = _make_member(seatClass="numbered", seatLabel="district", seatId=None)
        data = _make_local_data(members=[m])
        val.validate_local_file(data, "test.json")
        assert any("numbered" in e for e in val.errors)

    def test_unknown_must_have_null_seat_id(self):
        m = _make_member(seatClass="unknown", seatLabel=None, seatId="1")
        data = _make_local_data(members=[m])
        val.validate_local_file(data, "test.json")
        assert any("unknown" in e and "seatId" in e for e in val.errors)

    def test_unknown_with_null_seat_id_is_valid(self):
        m = _make_member(seatClass="unknown", seatLabel=None, seatId=None,
                         leadership="chair", seatSource="parsed-title")
        data = _make_local_data(members=[m])
        val.validate_local_file(data, "test.json")
        assert len(val.errors) == 0

    def test_mayor_pro_tem_requires_council_member_office(self):
        m = _make_member(office="mayor", seatClass="at-large", seatLabel=None,
                         seatId=None, leadership="mayor-pro-tem")
        data = _make_local_data(members=[m])
        val.validate_local_file(data, "test.json")
        assert any("mayor-pro-tem" in e and "council-member" in e for e in val.errors)

    def test_mayor_pro_tem_on_council_member_is_valid(self):
        m = _make_member(office="council-member", leadership="mayor-pro-tem")
        data = _make_local_data(members=[m])
        val.validate_local_file(data, "test.json")
        assert len(val.errors) == 0

    def test_mayor_office_requires_at_large(self):
        m = _make_member(office="mayor", seatClass="numbered",
                         seatLabel="district", seatId="1")
        data = _make_local_data(members=[m])
        val.validate_local_file(data, "test.json")
        assert any("mayor" in e and "at-large" in e for e in val.errors)

    def test_mayor_with_at_large_is_valid(self):
        data = _make_local_data(members=[_make_mayor()])
        val.validate_local_file(data, "test.json")
        assert len(val.errors) == 0

    def test_numbered_with_township_seat_label_is_valid(self):
        """`township` is an accepted seatLabel for numbered seats (Jasper SC hybrid)."""
        m = _make_member(seatClass="numbered", seatLabel="township",
                         seatId="Hardeeville", seatSource="manual")
        data = _make_local_data(members=[m])
        val.validate_local_file(data, "test.json")
        assert len(val.errors) == 0


class TestNormalizedFieldsState:
    """Verify _validate_normalized_fields runs against state legislators and executive."""

    def test_state_legislators_validate_clean(self):
        data = _make_state_data()
        val.validate_state_json(data, "SC", "state.json")
        assert len(val.errors) == 0

    def test_senator_missing_office_is_error(self):
        data = _make_state_data()
        del data["senate"]["1"]["office"]
        val.validate_state_json(data, "SC", "state.json")
        assert any("senate[1]" in e and "office" in e for e in val.errors)

    def test_house_member_invalid_seat_class_is_error(self):
        data = _make_state_data()
        data["house"]["1"]["seatClass"] = "ranked"
        val.validate_state_json(data, "SC", "state.json")
        assert any("house[1]" in e and "seatClass 'ranked'" in e for e in val.errors)

    def test_executive_normalized_fields_validated(self):
        bad_exec = _make_executive(office="dogcatcher")
        data = _make_state_data(executive=[bad_exec])
        val.validate_state_json(data, "SC", "state.json")
        assert any("executive[0]" in e and "office 'dogcatcher'" in e for e in val.errors)

    def test_executive_at_large_governor_is_valid(self):
        data = _make_state_data(executive=[_make_executive()])
        val.validate_state_json(data, "SC", "state.json")
        assert len(val.errors) == 0


class TestLocalSeatCoverage:
    """A jurisdiction registry-marked as districted (atLarge: false, no
    councilDefaults override) should not have every member at seatClass: unknown.
    The check warns rather than errors — a single overrides patch can fix it,
    but a regression should be loud."""

    def _data(self, members):
        return {
            "meta": {"state": "SC", "level": "local", "jurisdiction": "county:test",
                     "label": "Test", "lastUpdated": "2026-05-20", "adapter": "test"},
            "members": members,
        }

    def _member(self, name, seat_class="unknown", seat_label=None, seat_id=None,
                leadership=None, office="council-member"):
        return {
            "name": name, "title": "Council Member", "office": office,
            "leadership": leadership, "seatClass": seat_class,
            "seatLabel": seat_label, "seatId": seat_id,
            "seatSource": "parsed-title", "vacant": False, "partisan": False,
        }

    def test_warns_when_districted_jurisdiction_has_all_unknown_seats(self):
        entry = {"id": "county:test", "type": "county", "atLarge": False}
        data = self._data([self._member("A"), self._member("B")])
        val.validate_local_file(data, "test.json", jurisdiction_entry=entry)
        assert any("districted but all members have seatClass: unknown" in w
                   for w in val.warnings)

    def test_no_warning_when_at_large(self):
        entry = {"id": "place:test", "type": "place", "atLarge": True,
                 "councilDefaults": {"seatClass": "at-large", "partisan": False}}
        data = self._data([self._member("A", seat_class="at-large")])
        val.validate_local_file(data, "test.json", jurisdiction_entry=entry)
        assert not any("seatClass: unknown" in w for w in val.warnings)

    def test_no_warning_when_at_least_one_seat_populated(self):
        entry = {"id": "county:test", "type": "county", "atLarge": False}
        data = self._data([
            self._member("A", seat_class="numbered", seat_label="district", seat_id="1"),
            self._member("B"),
        ])
        val.validate_local_file(data, "test.json", jurisdiction_entry=entry)
        assert not any("seatClass: unknown" in w for w in val.warnings)

    def test_no_warning_when_jurisdiction_entry_missing(self):
        # Defensive: if the lookup fails, don't warn (avoids noise on jurisdictions
        # that were dropped from registry but still have a data file).
        data = self._data([self._member("A"), self._member("B")])
        val.validate_local_file(data, "test.json", jurisdiction_entry=None)
        assert not any("seatClass: unknown" in w for w in val.warnings)

    def test_no_warning_when_council_defaults_pins_at_large(self):
        # Branch coverage: atLarge omitted but councilDefaults pins at-large.
        entry = {"id": "place:test", "type": "place",
                 "councilDefaults": {"seatClass": "at-large", "partisan": False}}
        data = self._data([self._member("A", seat_class="at-large")])
        val.validate_local_file(data, "test.json", jurisdiction_entry=entry)
        assert not any("seatClass: unknown" in w for w in val.warnings)

    def test_no_warning_when_only_leadership_members(self):
        # Branch coverage: filter empties out leadership-only rosters.
        entry = {"id": "county:test", "type": "county", "atLarge": False}
        data = self._data([self._member("A", leadership="chair"),
                           self._member("B", leadership="vice-chair")])
        val.validate_local_file(data, "test.json", jurisdiction_entry=entry)
        assert not any("seatClass: unknown" in w for w in val.warnings)
