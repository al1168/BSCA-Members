"""DOB display: MM/DD/YYYY however the database stores the value."""
from datetime import date, datetime

from db.members import format_dob_display, parse_flexible_date


def test_iso_text():
    assert format_dob_display("1953-08-23") == "08/23/1953"


def test_iso_text_with_midnight_time():
    assert format_dob_display("1941-06-04 00:00:00") == "06/04/1941"


def test_slash_text_gets_zero_padded():
    assert format_dob_display("8/23/1953") == "08/23/1953"


def test_datetime_and_date_objects():
    assert format_dob_display(datetime(1950, 3, 15)) == "03/15/1950"
    assert format_dob_display(date(1950, 3, 15)) == "03/15/1950"


def test_unparseable_passes_through_visibly():
    assert format_dob_display("unknown") == "unknown"
    assert format_dob_display("") == ""
    assert format_dob_display(None) == ""


def test_parse_flexible_date():
    assert parse_flexible_date("8/23/1953") == date(1953, 8, 23)
    assert parse_flexible_date("1953-08-23") == date(1953, 8, 23)
    assert parse_flexible_date("nope") is None


def test_export_coerces_text_dob_to_date():
    from db.export import build_export_rows, COLUMNS
    row = (1, "Chan", "Mei", "", "8/23/1953", "", "", "", "", "", "",
           "", "", "", "", "", "", "", "", "", "")
    rows = build_export_rows([row], [], [], [], date(2026, 7, 9))
    assert dict(zip(COLUMNS, rows[0]))["DOB"] == date(1953, 8, 23)
