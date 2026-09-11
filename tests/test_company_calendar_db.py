"""Company calendar DB module: pure helpers, row mapping, and (when the
shared test DB exists) an Access round-trip."""
import os
from datetime import date, datetime

import pytest

from db import company_calendar as cal


def test_day_names_mon_to_sun():
    assert cal.DAY_NAMES[0] == "Monday"
    assert cal.DAY_NAMES[6] == "Sunday"
    assert len(cal.DAY_NAMES) == 7


def test_hhmm_to_12h():
    assert cal.hhmm_to_12h("08:00") == ("8:00", "AM")
    assert cal.hhmm_to_12h("16:30") == ("4:30", "PM")
    assert cal.hhmm_to_12h("12:00") == ("12:00", "PM")
    assert cal.hhmm_to_12h("00:15") == ("12:15", "AM")


def test_validate_hours_ok():
    rows = [{"day_of_week": 1, "opening_time": "08:00", "closing_time": "16:00"}]
    assert cal.validate_hours(rows) == []


def test_validate_hours_closing_not_after_opening():
    rows = [
        {"day_of_week": 2, "opening_time": "09:00", "closing_time": "09:00"},
        {"day_of_week": 3, "opening_time": "10:00", "closing_time": "08:00"},
    ]
    assert cal.validate_hours(rows) == [
        "Tuesday: closing time must be after opening time",
        "Wednesday: closing time must be after opening time",
    ]


def test_validate_hours_missing_time():
    rows = [{"day_of_week": 5, "opening_time": None, "closing_time": "16:00"}]
    assert cal.validate_hours(rows) == [
        "Friday: enter both times as h:mm (hour 1-12, minute 00-59)",
    ]


def test_map_holiday_row():
    row = (7, " Labor Day ", datetime(2026, 9, 7, 0, 0))
    assert cal.map_holiday_row(row) == {
        "id": 7, "name": "Labor Day", "date": date(2026, 9, 7)}


def test_map_operating_day_row():
    row = (2, "Monday", 1, datetime(1899, 12, 30, 8, 0),
           datetime(1899, 12, 30, 16, 0))
    assert cal.map_operating_day_row(row) == {
        "id": 2, "day_name": "Monday", "day_of_week": 1,
        "opening_time": "08:00", "closing_time": "16:00"}


def test_pick_latest_per_weekday_largest_id_wins():
    rows = [
        {"id": 1, "day_name": "Monday", "day_of_week": 1,
         "opening_time": "08:00", "closing_time": "16:00"},
        {"id": 9, "day_name": "Monday", "day_of_week": 1,
         "opening_time": "10:00", "closing_time": "15:00"},
        {"id": 3, "day_name": "Tuesday", "day_of_week": 2,
         "opening_time": "08:00", "closing_time": "16:00"},
    ]
    picked = cal.pick_latest_per_weekday(rows)
    assert set(picked) == {1, 2}
    assert picked[1]["id"] == 9


def test_statements_shape():
    assert cal.INSERT_HOLIDAY.startswith("INSERT INTO [Holidays]")
    assert cal.DELETE_HOLIDAY == "DELETE FROM [Holidays] WHERE [ID]=?"
    assert cal.DELETE_ALL_OPERATING_DAYS == "DELETE FROM [OperatingDays]"
    for col in ("[day_name]", "[Day Of Week]", "[opening_time]",
                "[closing_time]"):
        assert col in cal.INSERT_OPERATING_DAY


# -- Access round-trip (skipped when the shared test DB is absent) --------
_TEST_DB = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "test_dbs", "DBM_test_cathay.accdb"))

needs_db = pytest.mark.skipif(not os.path.exists(_TEST_DB),
                              reason="shared test DB not present")


@needs_db
def test_holiday_round_trip():
    cal.insert_holiday("Round Trip Day", date(2031, 1, 2), _TEST_DB)
    try:
        rows = [r for r in cal.get_holidays(_TEST_DB)
                if r["name"] == "Round Trip Day"]
        assert len(rows) == 1
        assert rows[0]["date"] == date(2031, 1, 2)
    finally:
        for r in cal.get_holidays(_TEST_DB):
            if r["name"] == "Round Trip Day":
                cal.delete_holiday(r["id"], _TEST_DB)
    assert not [r for r in cal.get_holidays(_TEST_DB)
                if r["name"] == "Round Trip Day"]


@needs_db
def test_operating_days_round_trip():
    before = cal.get_operating_days(_TEST_DB)
    try:
        cal.save_operating_days(
            [{"day_of_week": 2, "opening_time": "09:00",
              "closing_time": "15:00"}], _TEST_DB)
        days = cal.get_operating_days(_TEST_DB)
        assert set(days) == {2}
        assert days[2]["day_name"] == "Tuesday"
        assert (days[2]["opening_time"], days[2]["closing_time"]) == (
            "09:00", "15:00")
    finally:
        cal.save_operating_days(
            [{"day_of_week": d, "opening_time": r["opening_time"],
              "closing_time": r["closing_time"]}
             for d, r in before.items()], _TEST_DB)
