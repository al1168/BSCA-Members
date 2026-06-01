import pytest
from db.members import (
    ALL_MEMBERS_QUERY,
    INSERT_CONTACT,
    INSERT_ENROLLMENT,
    INSERT_AUTHORIZATION,
    INSERT_AVAILABILITY,
    INSERT_ABSENCE,
    encode_auth_days,
    decode_auth_days,
    get_all_members,
)


def test_all_members_query_selects_required_columns():
    for col in ("[Center ID]", "[Last Name]", "[First Name]", "[Health Plan]"):
        assert col in ALL_MEMBERS_QUERY
    assert "ORDER BY [Last Name]" in ALL_MEMBERS_QUERY


def test_insert_contact_targets_correct_table():
    assert "INSERT INTO [Contacts]" in INSERT_CONTACT
    for col in ("[Center ID]", "[Last Name]", "[First Name]", "[Health Plan]", "[Address]"):
        assert col in INSERT_CONTACT


def test_insert_enrollment_targets_correct_table():
    assert "INSERT INTO [Enrollment]" in INSERT_ENROLLMENT
    for col in ("[Center ID]", "[start_date]", "[end_date]"):
        assert col in INSERT_ENROLLMENT


def test_insert_authorization_targets_correct_table():
    assert "INSERT INTO [Authorization]" in INSERT_AUTHORIZATION
    for col in ("[Center ID]", "[auth_start]", "[auth_end]", "[auth_days]"):
        assert col in INSERT_AUTHORIZATION


def test_insert_availability_targets_correct_table():
    assert "INSERT INTO [Availability]" in INSERT_AVAILABILITY
    for col in ("[Center ID]", "[Day Of Week]", "[avail_start]", "[avail_end]"):
        assert col in INSERT_AVAILABILITY


def test_insert_absence_targets_correct_table():
    assert "INSERT INTO [Absences]" in INSERT_ABSENCE
    for col in ("[Center ID]", "[Leave Type]", "[Start_Date]", "[End_Date]"):
        assert col in INSERT_ABSENCE


def test_encode_auth_days_sorted():
    assert encode_auth_days({3, 1, 5}) == "1,3,5"


def test_encode_auth_days_empty():
    assert encode_auth_days(set()) == ""


def test_decode_auth_days_returns_set():
    assert decode_auth_days("1,3,5") == {1, 3, 5}


def test_decode_auth_days_empty_string():
    assert decode_auth_days("") == set()


def test_get_all_members_missing_db_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        get_all_members(str(tmp_path / "nope.accdb"))


def test_update_contact_targets_all_editable_fields():
    from db.members import UPDATE_CONTACT
    for col in (
        "[Last Name]", "[First Name]", "[Chinese Name]", "[Gender]", "[DOB]",
        "[Member ID]", "[Health Plan]", "[Medicaid]", "[Medicare]", "[SSN]",
        "[Language]", "[Case Manager]", "[Home Tell]", "[Cell]", "[Address]",
        "[Emergency]", "[PCP]", "[Hospital]", "[HHA]", "[Admission Date]", "[Notes]",
    ):
        assert col in UPDATE_CONTACT, f"Missing column in UPDATE_CONTACT: {col}"
    assert "WHERE [Center ID]=?" in UPDATE_CONTACT
