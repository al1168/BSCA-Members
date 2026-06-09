from datetime import date, datetime

from db.members import map_one_off_availability_row


def test_map_one_off_row_datetime_date():
    row = (5, 25049, datetime(2026, 7, 1, 0, 0),
           datetime(1899, 12, 30, 9, 0), datetime(1899, 12, 30, 12, 0), "Doctor")
    assert map_one_off_availability_row(row) == {
        "id": 5, "center_id": 25049, "date": date(2026, 7, 1),
        "avail_start": "09:00", "avail_end": "12:00", "notes": "Doctor",
    }


def test_map_one_off_row_plain_date_and_null_notes():
    row = (6, 25049, date(2026, 8, 2),
           datetime(1899, 12, 30, 13, 30), datetime(1899, 12, 30, 17, 0), None)
    d = map_one_off_availability_row(row)
    assert d["date"] == date(2026, 8, 2)
    assert d["avail_start"] == "13:30"
    assert d["avail_end"] == "17:00"
    assert d["notes"] == ""


def test_map_one_off_row_null_times():
    row = (7, 25049, date(2026, 8, 3), None, None, "")
    d = map_one_off_availability_row(row)
    assert d["avail_start"] is None
    assert d["avail_end"] is None
