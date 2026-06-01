"""Integration tests against the real populate_real_members.accdb test fixture.

These tests require the Microsoft Access ODBC driver and the test DB file.
They are skipped automatically if the file is not found.

Test DB: BSCA/scripts/test_dbs/populate_real_members.accdb
  - Contains the real Contacts table (including rows with NULL Center IDs)
  - Supporting tables (Enrollment, Authorization, etc.) are empty
"""
import os
import pytest

TEST_DB = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..", "..", "BSCA", "scripts", "test_dbs", "populate_real_members.accdb",
    )
)

pytestmark = pytest.mark.skipif(
    not os.path.exists(TEST_DB),
    reason=f"Test DB not found: {TEST_DB}",
)


# ── get_all_members ────────────────────────────────────────────────────

def test_get_all_members_returns_list():
    from db.members import get_all_members
    members = get_all_members(TEST_DB)
    assert isinstance(members, list)
    assert len(members) > 0


def test_get_all_members_no_none_center_ids():
    """NULL Center IDs in Contacts must be silently skipped."""
    from db.members import get_all_members
    members = get_all_members(TEST_DB)
    for m in members:
        assert m["center_id"] is not None
        assert isinstance(m["center_id"], int)


def test_get_all_members_no_none_strings():
    """last_name, first_name, health_plan must never be None (empty string ok)."""
    from db.members import get_all_members
    members = get_all_members(TEST_DB)
    for m in members:
        assert m["last_name"] is not None
        assert m["first_name"] is not None
        assert m["health_plan"] is not None


def test_get_all_members_sorted_by_last_name():
    from db.members import get_all_members
    members = get_all_members(TEST_DB)
    last_names = [m["last_name"].lower() for m in members]
    assert last_names == sorted(last_names)


def test_get_all_members_required_keys():
    from db.members import get_all_members
    members = get_all_members(TEST_DB)
    for m in members:
        assert set(m.keys()) == {"center_id", "last_name", "first_name", "health_plan"}


# ── center_id_exists ───────────────────────────────────────────────────

def test_center_id_exists_returns_true_for_real_member():
    from db.members import get_all_members, center_id_exists
    members = get_all_members(TEST_DB)
    first_id = members[0]["center_id"]
    assert center_id_exists(first_id, TEST_DB) is True


def test_center_id_exists_returns_false_for_missing():
    from db.members import center_id_exists
    # Use an implausibly large ID that won't exist
    assert center_id_exists(999999999, TEST_DB) is False


# ── bsca-core read functions ───────────────────────────────────────────

def test_get_member_returns_dict_for_valid_id():
    from db.members import get_all_members
    from monthly_schedule.db import get_member
    members = get_all_members(TEST_DB)
    first = members[0]
    result = get_member(first["center_id"], TEST_DB)
    assert result is not None
    assert result["center_id"] == first["center_id"]
    assert result["last_name"] == first["last_name"]


def test_get_member_returns_none_for_missing_id():
    from monthly_schedule.db import get_member
    result = get_member(999999999, TEST_DB)
    assert result is None


def test_get_enrollments_returns_list():
    """Supporting tables are empty in this fixture — list should be empty, not crash."""
    from db.members import get_all_members
    from monthly_schedule.db import get_enrollments
    members = get_all_members(TEST_DB)
    result = get_enrollments(members[0]["center_id"], TEST_DB)
    assert isinstance(result, list)


def test_get_authorizations_returns_list():
    from db.members import get_all_members
    from monthly_schedule.db import get_authorizations
    members = get_all_members(TEST_DB)
    result = get_authorizations(members[0]["center_id"], TEST_DB)
    assert isinstance(result, list)


def test_get_availability_returns_list():
    from db.members import get_all_members
    from monthly_schedule.db import get_availability
    members = get_all_members(TEST_DB)
    result = get_availability(members[0]["center_id"], TEST_DB)
    assert isinstance(result, list)


def test_get_absences_returns_list():
    from db.members import get_all_members
    from monthly_schedule.db import get_absences
    members = get_all_members(TEST_DB)
    result = get_absences(members[0]["center_id"], TEST_DB)
    assert isinstance(result, list)


# ── get_member_photo ──────────────────────────────────────────────────

def test_get_member_photo_returns_bytes_or_none():
    from db.members import get_all_members, get_member_photo
    members = get_all_members(TEST_DB)
    first = members[0]
    result = get_member_photo(first["center_id"], TEST_DB)
    assert result is None or isinstance(result, bytes)


def test_get_member_photo_bytes_start_with_jpeg_header():
    """If a photo exists it must be a valid JPEG (starts with FF D8)."""
    from db.members import get_all_members, get_member_photo
    members = get_all_members(TEST_DB)
    for m in members[:20]:
        data = get_member_photo(m["center_id"], TEST_DB)
        if data is not None:
            assert data[:2] == b'\xff\xd8', f"Not a JPEG for center_id={m['center_id']}"
            return


def test_get_member_photo_missing_id_returns_none():
    from db.members import get_member_photo
    result = get_member_photo(999999999, TEST_DB)
    assert result is None


def test_get_member_context_returns_all_contact_fields():
    from db.members import get_all_members, get_member_context
    members = get_all_members(TEST_DB)
    ctx = get_member_context(members[0]["center_id"], TEST_DB)
    m = ctx["member"]
    for key in (
        "center_id", "last_name", "first_name", "chinese_name",
        "gender", "dob", "member_id", "health_plan",
        "medicaid", "medicare", "ssn", "language",
        "case_manager", "home_tell", "cell", "address",
        "emergency", "pcp", "hospital", "hha",
        "admission_date", "notes",
    ):
        assert key in m, f"Missing key in member context: {key}"
        assert m[key] is not None, f"Key {key!r} is None (should be '' for missing)"
