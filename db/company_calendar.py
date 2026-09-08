"""Center-wide calendar tables: Holidays (closed dates) and OperatingDays
(weekly hours, one row per OPEN weekday — a weekday with no row is
closed). Both are created and seeded by the BSCA Setup chain; this
module is the Members app's only reader/writer of them.

Kept apart from db/members.py (already ~1,850 lines); it reuses that
module's connection helpers and Access time/date encoders.
"""
from db.members import (
    _access_date, _access_hhmm, _drop_read_connection, _hhmm_to_datetime,
    _read_connection, write_conn,
)

DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
             "Saturday", "Sunday")          # index 0 == Day Of Week 1

DEFAULT_OPENING = "08:00"
DEFAULT_CLOSING = "16:00"

HOLIDAYS_SELECT = "SELECT [ID], [holiday_name], [date] FROM [Holidays]"
INSERT_HOLIDAY = "INSERT INTO [Holidays] ([holiday_name], [date]) VALUES (?, ?)"
DELETE_HOLIDAY = "DELETE FROM [Holidays] WHERE [ID]=?"

OPERATING_DAYS_SELECT = (
    "SELECT [ID], [day_name], [Day Of Week], [opening_time], [closing_time] "
    "FROM [OperatingDays]"
)
DELETE_ALL_OPERATING_DAYS = "DELETE FROM [OperatingDays]"
INSERT_OPERATING_DAY = (
    "INSERT INTO [OperatingDays] "
    "([day_name], [Day Of Week], [opening_time], [closing_time]) "
    "VALUES (?, ?, ?, ?)"
)


# ── pure helpers ─────────────────────────────────────────────────────────

def hhmm_to_12h(hhmm: str) -> tuple[str, str]:
    """'16:30' -> ('4:30', 'PM'); '00:15' -> ('12:15', 'AM')."""
    h, m = (int(p) for p in hhmm.split(":"))
    period = "AM" if h < 12 else "PM"
    h12 = h % 12 or 12
    return f"{h12}:{m:02d}", period


def validate_hours(rows) -> list[str]:
    """Problems with a list of {day_of_week, opening_time, closing_time}
    ('HH:MM' or None). Empty list when every row is fine."""
    problems = []
    for row in rows:
        name = DAY_NAMES[row["day_of_week"] - 1]
        opening, closing = row.get("opening_time"), row.get("closing_time")
        if not opening or not closing:
            problems.append(
                f"{name}: enter both times as h:mm (hour 1-12, minute 00-59)")
            continue
        if closing <= opening:          # zero-padded 'HH:MM' sorts correctly
            problems.append(f"{name}: closing time must be after opening time")
    return problems


def map_holiday_row(row) -> dict:
    return {"id": int(row[0]), "name": str(row[1] or "").strip(),
            "date": _access_date(row[2])}


def map_operating_day_row(row) -> dict:
    return {"id": int(row[0]), "day_name": str(row[1] or ""),
            "day_of_week": int(row[2]),
            "opening_time": _access_hhmm(row[3]),
            "closing_time": _access_hhmm(row[4])}


def pick_latest_per_weekday(rows) -> dict[int, dict]:
    """{day_of_week: row}; when a weekday has several rows (hand edits in
    Access) the largest ID wins."""
    picked: dict[int, dict] = {}
    for row in rows:
        current = picked.get(row["day_of_week"])
        if current is None or row["id"] > current["id"]:
            picked[row["day_of_week"]] = row
    return picked


# ── reads ────────────────────────────────────────────────────────────────

def _read_rows(db_path: str, sql: str, mapper, _retry: bool = True) -> list:
    """Run an unparameterized SELECT on the cached read connection, with
    the same stale-connection retry as db.members.get_absences."""
    import pyodbc
    conn = _read_connection(db_path)
    try:
        c = conn.cursor()
        c.execute(sql)
        return [mapper(r) for r in c.fetchall()]
    except pyodbc.Error:
        _drop_read_connection(db_path)
        if _retry:
            return _read_rows(db_path, sql, mapper, _retry=False)
        raise


def get_holidays(db_path: str) -> list[dict]:
    """Every holiday with a date, sorted by date then ID."""
    rows = [r for r in _read_rows(db_path, HOLIDAYS_SELECT, map_holiday_row)
            if r["date"] is not None]
    return sorted(rows, key=lambda r: (r["date"], r["id"]))


def get_operating_days(db_path: str) -> dict[int, dict]:
    """{day_of_week: row} for every open weekday."""
    rows = [r for r in _read_rows(db_path, OPERATING_DAYS_SELECT,
                                  map_operating_day_row)
            if r["day_of_week"] in range(1, 8)]
    return pick_latest_per_weekday(rows)


# ── writes ───────────────────────────────────────────────────────────────

def insert_holiday(name: str, day, db_path: str) -> None:
    with write_conn(db_path) as c:
        c.execute(INSERT_HOLIDAY, (name.strip(), day))


def delete_holiday(record_id: int, db_path: str) -> None:
    with write_conn(db_path) as c:
        c.execute(DELETE_HOLIDAY, (record_id,))


def save_operating_days(rows, db_path: str) -> None:
    """Replace the whole table with `rows` ({day_of_week, opening_time,
    closing_time} with 'HH:MM' times) in one transaction. Weekdays not
    in `rows` end up with no row, i.e. closed."""
    with write_conn(db_path) as c:
        c.execute(DELETE_ALL_OPERATING_DAYS)
        for row in sorted(rows, key=lambda r: r["day_of_week"]):
            dow = row["day_of_week"]
            c.execute(INSERT_OPERATING_DAY, (
                DAY_NAMES[dow - 1], dow,
                _hhmm_to_datetime(row["opening_time"]),
                _hhmm_to_datetime(row["closing_time"]),
            ))
