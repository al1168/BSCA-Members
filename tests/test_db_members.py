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
    for col in ("[Center ID]", "[Last Name]", "[First Name]", "[Health Plan]",
                "[Address]", "[Member ID]", "[Home Tell]", "[Cell]", "[DOB]"):
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


def test_update_availability_targets_correct_columns():
    from db.members import UPDATE_AVAILABILITY
    assert "UPDATE [Availability]" in UPDATE_AVAILABILITY
    assert "[avail_start]=?" in UPDATE_AVAILABILITY
    assert "[avail_end]=?" in UPDATE_AVAILABILITY
    assert "WHERE [ID]=?" in UPDATE_AVAILABILITY


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


def test_update_enrollment_end_targets_correct_columns():
    from db.members import UPDATE_ENROLLMENT_END
    assert "UPDATE [Enrollment]" in UPDATE_ENROLLMENT_END
    assert "[end_date]=?" in UPDATE_ENROLLMENT_END
    assert "WHERE [ID]=?" in UPDATE_ENROLLMENT_END


def test_insert_authorization_includes_health_plan_created_at_member_id():
    from db.members import INSERT_AUTHORIZATION
    assert "[Health Plan]" in INSERT_AUTHORIZATION
    assert "[created_at]" in INSERT_AUTHORIZATION
    assert "[Member ID]" in INSERT_AUTHORIZATION
    assert INSERT_AUTHORIZATION.count("?") == 9


def test_latest_authorization_picks_latest_start_then_id():
    from datetime import date
    from db.members import latest_authorization
    auths = [
        {"id": 1, "auth_start": date(2025, 1, 1), "health_plan": "AE"},
        {"id": 2, "auth_start": date(2026, 1, 1), "health_plan": "Aetna"},
        {"id": 3, "auth_start": date(2026, 1, 1), "health_plan": "BCBS"},
    ]
    assert latest_authorization(auths)["id"] == 3  # same start -> highest id


def test_latest_authorization_empty_returns_none():
    from db.members import latest_authorization
    assert latest_authorization([]) is None
    assert latest_authorization([{"id": 1, "auth_start": None}]) is None


def test_update_authorization_targets_correct_columns():
    from db.members import UPDATE_AUTHORIZATION
    assert "UPDATE [Authorization]" in UPDATE_AUTHORIZATION
    for col in ("[auth_start]=?", "[auth_end]=?", "[auth_days]=?", "[Health Plan]=?"):
        assert col in UPDATE_AUTHORIZATION
    assert "WHERE [ID]=?" in UPDATE_AUTHORIZATION


@pytest.mark.parametrize("text,period,expected", [
    ("8:00", "AM", "08:00"),
    ("12:00", "AM", "00:00"),
    ("12:00", "PM", "12:00"),
    ("4:30", "PM", "16:30"),
    ("11:59", "PM", "23:59"),
    ("8:05", "am", "08:05"),
])
def test_time_12h_to_24h_valid(text, period, expected):
    from db.members import time_12h_to_24h
    assert time_12h_to_24h(text, period) == expected


@pytest.mark.parametrize("text,period", [
    ("8", "AM"),       # no colon
    ("13:00", "AM"),   # hour > 12
    ("0:00", "AM"),    # hour < 1
    ("8:60", "AM"),    # minute > 59
    ("abc", "AM"),     # non-numeric
    ("8:", "AM"),      # empty minute
    ("8:00", "XM"),    # bad period
])
def test_time_12h_to_24h_invalid(text, period):
    from db.members import time_12h_to_24h
    with pytest.raises(ValueError):
        time_12h_to_24h(text, period)


def test_insert_contact_includes_long_lat():
    from db.members import INSERT_CONTACT
    assert "[Long Lat]" in INSERT_CONTACT
    # Center ID, Last Name, First Name, Health Plan, Address, Long Lat,
    # Member ID, Home Tell, Cell, DOB
    assert INSERT_CONTACT.count("?") == 10


def test_set_long_lat_targets_correct_columns():
    from db.members import SET_LONG_LAT
    assert "UPDATE [Contacts]" in SET_LONG_LAT
    assert "[Long Lat]=?" in SET_LONG_LAT
    assert "WHERE [Center ID]=?" in SET_LONG_LAT
