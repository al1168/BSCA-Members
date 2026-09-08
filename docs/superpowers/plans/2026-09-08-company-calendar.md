# Company Calendar Implementation Plan (BSCA-Members repo)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "🏢 Company Calendar" toolbar button that opens a dialog for adding/deleting company holidays and editing the seven weekly operating-day rows (open checkbox + opening/closing times).

**Architecture:** A new `db/company_calendar.py` module owns all reads/writes to the `Holidays` and `OperatingDays` tables (reusing `db.members`' connection helpers), plus pure validation/formatting helpers. A new `gui/company_calendar.py` holds `CompanyCalendarDialog`, opened from `MainWindow`. Both tables join `REQUIRED_SCHEMA` so an old database gets the existing startup warning.

**Tech Stack:** Python 3.11, PyQt6, pyodbc against Microsoft Access, pytest. Run tests with `.venv\Scripts\python.exe -m pytest` from `C:\Users\luald\OneDrive\Desktop\BSCA-Members`. Qt tests use `os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")` and a module-scoped `qapp` fixture, as in `tests/test_absence_report.py`.

**Spec:** `docs/superpowers/specs/2026-09-08-company-calendar-design.md`. The tables themselves are created by the BSCA repo's Setup chain (`BSCA/docs/superpowers/plans/2026-09-08-holidays-operating-days.md`, Tasks 1–2). Run that Setup on the target database before exercising this dialog.

---

## File map

| File | Change |
| --- | --- |
| `db/company_calendar.py` | **New.** Reads/writes + `validate_hours`, `hhmm_to_12h`, `pick_latest_per_weekday` |
| `db/members.py` | `REQUIRED_SCHEMA` gains both tables |
| `gui/company_calendar.py` | **New.** `CompanyCalendarDialog`, `_TimeEntry` |
| `gui/main_window.py` | Toolbar button + `_open_company_calendar` |
| `gui/theme.py` | `btn_company_calendar` joins the outline-button selectors |
| `tests/conftest.py` | `_CREATE_SQL` gains both tables |
| `docs/database-schema.md` | Two new sections |
| Tests | `tests/test_company_calendar_db.py` (new), `tests/test_company_calendar_dialog.py` (new), `tests/test_db_members.py` |

---

### Task 1: `db/company_calendar.py`

**Files:**
- Create: `db/company_calendar.py`
- Test: `tests/test_company_calendar_db.py` (new)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_company_calendar_db.py`:

```python
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


# ── Access round-trip (skipped when the shared test DB is absent) ─────────
_TEST_DB = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "BSCA", "scripts", "test_dbs",
    "populate_real_members.accdb"))

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
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_company_calendar_db.py -q`
Expected: `ModuleNotFoundError: No module named 'db.company_calendar'`.

- [ ] **Step 3: Write the module**

Create `db/company_calendar.py`:

```python
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
```

- [ ] **Step 4: Run the tests**

Run: `.venv\Scripts\python.exe -m pytest tests/test_company_calendar_db.py -q`
Expected: pure tests pass; the two round-trip tests pass if the shared DB exists and has the tables (see Task 2's conftest change), otherwise skip.

- [ ] **Step 5: Commit**

```bash
git add db/company_calendar.py tests/test_company_calendar_db.py
git commit -m "feat(db): company_calendar module for Holidays and OperatingDays"
```

---

### Task 2: Schema requirement, test fixture, schema doc

**Files:**
- Modify: `db/members.py` (`REQUIRED_SCHEMA`)
- Modify: `tests/conftest.py`
- Modify: `docs/database-schema.md`
- Test: `tests/test_db_members.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_db_members.py`:

```python
def test_required_schema_includes_calendar_tables():
    from db.members import REQUIRED_SCHEMA
    assert REQUIRED_SCHEMA["Holidays"] == ["holiday_name", "date"]
    assert REQUIRED_SCHEMA["OperatingDays"] == [
        "day_name", "Day Of Week", "opening_time", "closing_time"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest tests/test_db_members.py -q -k calendar_tables`
Expected: `KeyError: 'Holidays'`.

- [ ] **Step 3: Implement**

In `db/members.py`, add to the end of `REQUIRED_SCHEMA`:

```python
    "Holidays": ["holiday_name", "date"],
    "OperatingDays": ["day_name", "Day Of Week", "opening_time",
                      "closing_time"],
```

In `tests/conftest.py`, add to `_CREATE_SQL`:

```python
    "Holidays": """
        CREATE TABLE [Holidays] (
            [ID] AUTOINCREMENT PRIMARY KEY,
            [holiday_name] TEXT(255),
            [date] DATETIME
        )
    """,
    "OperatingDays": """
        CREATE TABLE [OperatingDays] (
            [ID] AUTOINCREMENT PRIMARY KEY,
            [day_name] TEXT(20),
            [Day Of Week] LONG,
            [opening_time] DATETIME,
            [closing_time] DATETIME
        )
    """,
```

(The fixture already drops any table it created at session end, so the shared DB stays clean.)

In `docs/database-schema.md`, after the `EmergencyContact` section and before the `---` that precedes "SQLite events log", add:

```markdown
### Holidays — company-wide closed dates

Created by the BSCA Setup chain (`scripts/create_supporting_tables.py`).
Edited here through **🏢 Company Calendar**.

| Field | Type | Notes |
|---|---|---|
| ID | AUTOINCREMENT PK | |
| holiday_name | TEXT(255) | Required at startup. |
| date | DATETIME | Date only. One row per closed date. Required at startup. |

The scheduler generates no times on a holiday (blank day, not an absence).

### OperatingDays — weekly hours, one row per open weekday

Created by the BSCA Setup chain and seeded Monday–Sunday 08:00–16:00 by
`scripts/seed_operating_days.py` when empty. Edited here through
**🏢 Company Calendar**; "Save Hours" rewrites the whole table.

| Field | Type | Notes |
|---|---|---|
| ID | AUTOINCREMENT PK | |
| day_name | TEXT(20) | `Monday` … `Sunday`. Required at startup. |
| Day Of Week | LONG | 1 = Monday … 7 = Sunday (Availability's convention). The scheduler matches on this, not on `day_name`. Required at startup. |
| opening_time | DATETIME | Time-only on 1899-12-30, same as Availability. Required at startup. |
| closing_time | DATETIME | Same; later than `opening_time`. Required at startup. |

A weekday with no row is **closed**. On an open day these times are the
scheduler's day bounds (earliest Time-In / latest Time-Out).
```

- [ ] **Step 4: Run the tests**

Run: `.venv\Scripts\python.exe -m pytest tests/test_db_members.py tests/test_company_calendar_db.py -q`
Expected: all pass (round-trip tests now run when the shared DB is present).

- [ ] **Step 5: Commit**

```bash
git add db/members.py tests/conftest.py tests/test_db_members.py docs/database-schema.md
git commit -m "feat: Holidays and OperatingDays join the required schema"
```

---

### Task 3: `CompanyCalendarDialog`

**Files:**
- Create: `gui/company_calendar.py`
- Test: `tests/test_company_calendar_dialog.py` (new)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_company_calendar_dialog.py`:

```python
"""Company Calendar dialog: holiday add/delete gating and the weekly
hours editor, with db.company_calendar stubbed."""
import os
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


HOLIDAYS = [
    {"id": 1, "name": "New Year's Day", "date": date(2026, 1, 1)},
    {"id": 2, "name": "Labor Day", "date": date(2026, 9, 7)},
]


def _open_days(*days, opening="08:00", closing="16:00"):
    return {d: {"id": d, "day_name": "", "day_of_week": d,
                "opening_time": opening, "closing_time": closing}
            for d in days}


@pytest.fixture
def stubs(monkeypatch):
    """Stub every db call; record writes."""
    calls = {"insert": [], "delete": [], "save": []}
    state = {"holidays": list(HOLIDAYS),
             "days": _open_days(1, 2, 3, 4, 5, 6, 7)}
    monkeypatch.setattr("db.company_calendar.get_holidays",
                        lambda db: list(state["holidays"]))
    monkeypatch.setattr("db.company_calendar.get_operating_days",
                        lambda db: dict(state["days"]))

    def insert(name, day, db):
        calls["insert"].append((name, day))
        state["holidays"].append(
            {"id": 99, "name": name, "date": day})

    def delete(record_id, db):
        calls["delete"].append(record_id)
        state["holidays"] = [h for h in state["holidays"]
                             if h["id"] != record_id]

    def save(rows, db):
        calls["save"].append(rows)

    monkeypatch.setattr("db.company_calendar.insert_holiday", insert)
    monkeypatch.setattr("db.company_calendar.delete_holiday", delete)
    monkeypatch.setattr("db.company_calendar.save_operating_days", save)
    # Auto-answer every confirmation with "Yes"/the first (accept) button.
    from PyQt6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "warning",
                        lambda *a, **k: QMessageBox.StandardButton.Ok)
    return calls, state


def _dialog():
    from gui.company_calendar import CompanyCalendarDialog
    return CompanyCalendarDialog("fake.accdb")


def test_holidays_listed_sorted_and_add_gated(qapp, stubs):
    dlg = _dialog()
    assert dlg._table.rowCount() == 2
    assert dlg._table.item(0, 0).text() == "New Year's Day"
    assert dlg._table.item(1, 1).text() == "09/07/2026"
    assert not dlg._btn_add.isEnabled()
    dlg._name_edit.setText("Thanksgiving")
    assert not dlg._btn_add.isEnabled()          # no date yet
    dlg._date_edit.setText("11/26/2026")
    assert dlg._btn_add.isEnabled()
    dlg._date_edit.setText("13/40/2026")
    assert not dlg._btn_add.isEnabled()          # invalid date


def test_add_holiday_writes_and_reloads(qapp, stubs):
    calls, _state = stubs
    dlg = _dialog()
    dlg._name_edit.setText("Thanksgiving")
    dlg._date_edit.setText("11/26/2026")
    dlg._btn_add.click()
    assert calls["insert"] == [("Thanksgiving", date(2026, 11, 26))]
    assert dlg._table.rowCount() == 3
    assert dlg._name_edit.text() == ""
    assert dlg._date_edit.text() == ""


def test_delete_holiday_needs_selection_then_deletes(qapp, stubs):
    calls, _state = stubs
    dlg = _dialog()
    assert not dlg._btn_delete.isEnabled()
    dlg._table.selectRow(1)
    assert dlg._btn_delete.isEnabled()
    dlg._btn_delete.click()
    assert calls["delete"] == [2]
    assert dlg._table.rowCount() == 1


def test_hours_loaded_from_table(qapp, stubs):
    _calls, state = stubs
    state["days"] = _open_days(1, 2, 3, 4, 5, opening="09:00", closing="15:30")
    dlg = _dialog()
    check, opening, closing = dlg._day_rows[1]
    assert check.isChecked()
    assert (opening.edit.text(), opening.period.currentText()) == ("9:00", "AM")
    assert (closing.edit.text(), closing.period.currentText()) == ("3:30", "PM")
    sat_check, sat_open, _ = dlg._day_rows[6]
    assert not sat_check.isChecked()
    assert not sat_open.isEnabled()
    assert sat_open.edit.text() == "8:00"        # default shown for a closed day
    assert not dlg._btn_save.isEnabled()         # nothing dirty yet


def test_uncheck_day_and_save_writes_six_rows(qapp, stubs):
    calls, _state = stubs
    dlg = _dialog()
    dlg._day_rows[3][0].setChecked(False)        # close Wednesday
    assert dlg._btn_save.isEnabled()
    dlg._btn_save.click()
    assert len(calls["save"]) == 1
    rows = calls["save"][0]
    assert [r["day_of_week"] for r in rows] == [1, 2, 4, 5, 6, 7]
    assert rows[0] == {"day_of_week": 1, "opening_time": "08:00",
                       "closing_time": "16:00"}
    assert not dlg._btn_save.isEnabled()


def test_invalid_hours_block_save(qapp, stubs):
    calls, _state = stubs
    dlg = _dialog()
    _check, opening, _closing = dlg._day_rows[2]
    opening.edit.setText("5:00")
    opening.period.setCurrentText("PM")          # opens after it closes
    dlg._btn_save.click()
    assert calls["save"] == []


def test_zero_open_days_asks_then_saves(qapp, stubs, monkeypatch):
    calls, _state = stubs
    from PyQt6.QtWidgets import QMessageBox
    asked = []
    monkeypatch.setattr(
        QMessageBox, "question",
        lambda *a, **k: (asked.append(True), QMessageBox.StandardButton.Yes)[1])
    dlg = _dialog()
    for d in range(1, 8):
        dlg._day_rows[d][0].setChecked(False)
    dlg._btn_save.click()
    assert asked == [True]
    assert calls["save"] == [[]]


def test_close_with_dirty_hours_asks_first(qapp, stubs, monkeypatch):
    from PyQt6.QtWidgets import QDialog
    closed = []
    monkeypatch.setattr(QDialog, "reject", lambda self: closed.append(True))
    dlg = _dialog()
    dlg._day_rows[1][0].setChecked(False)
    dlg._confirm_discard = lambda: False          # "Keep Editing"
    dlg.reject()
    assert closed == []                           # stayed open
    dlg._confirm_discard = lambda: True           # "Discard"
    dlg.reject()
    assert closed == [True]


def test_close_when_clean_does_not_ask(qapp, stubs, monkeypatch):
    from PyQt6.QtWidgets import QDialog
    closed = []
    monkeypatch.setattr(QDialog, "reject", lambda self: closed.append(True))
    dlg = _dialog()
    dlg._confirm_discard = lambda: (_ for _ in ()).throw(AssertionError("asked"))
    dlg.reject()
    assert closed == [True]
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_company_calendar_dialog.py -q`
Expected: `ModuleNotFoundError: No module named 'gui.company_calendar'`.

- [ ] **Step 3: Write the dialog**

Create `gui/company_calendar.py`:

```python
"""Company Calendar dialog: company holidays (add / delete, written
immediately) and the weekly operating hours (seven rows — Open
checkbox plus opening / closing time — saved together).

Reads and writes go through db.company_calendar; the tables themselves
are created by the BSCA Setup chain.
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget,
)

from db import company_calendar as cal
from gui.address_autocomplete import DateLineEdit


class _TimeEntry(QWidget):
    """'h:mm' box + AM/PM combo, the app's usual 12-hour time entry."""

    def __init__(self, hhmm: str, on_change, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("h:mm")
        self.edit.setFixedWidth(64)
        self.period = QComboBox()
        self.period.addItems(["AM", "PM"])
        layout.addWidget(self.edit)
        layout.addWidget(self.period)
        self.set_hhmm(hhmm)
        self.edit.textEdited.connect(self._live_format)
        self.edit.textEdited.connect(lambda _t: on_change())
        self.period.currentIndexChanged.connect(lambda _i: on_change())

    def _live_format(self, text: str) -> None:
        from db.members import format_time_live
        formatted = format_time_live(text)
        if formatted != text:
            self.edit.setText(formatted)

    def set_hhmm(self, hhmm: str) -> None:
        text, period = cal.hhmm_to_12h(hhmm)
        self.edit.setText(text)
        self.period.setCurrentText(period)

    def hhmm(self):
        """24-hour 'HH:MM', or None when the text isn't a valid time."""
        from db.members import time_12h_to_24h
        try:
            return time_12h_to_24h(self.edit.text(), self.period.currentText())
        except ValueError:
            return None


class CompanyCalendarDialog(QDialog):
    def __init__(self, db_path: str, parent=None):
        super().__init__(parent)
        self._db_path = db_path
        self._dirty = False
        self._loading = False
        self.setWindowTitle("Company Calendar")
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.addWidget(self._build_holidays_group())
        layout.addWidget(self._build_hours_group())
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        layout.addWidget(close)

        self._load_holidays()
        self._load_hours()

    # ── holidays ──────────────────────────────────────────────────────
    def _build_holidays_group(self) -> QGroupBox:
        group = QGroupBox("Holidays")
        v = QVBoxLayout(group)
        v.addWidget(QLabel("Days the center is closed for everyone. "
                           "The scheduler leaves these days blank."))

        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["Holiday", "Date"])
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.itemSelectionChanged.connect(self._refresh_delete_enabled)
        v.addWidget(self._table)

        add_row = QHBoxLayout()
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Holiday name")
        self._date_edit = DateLineEdit()
        self._date_edit.setFixedWidth(110)
        self._btn_add = QPushButton("Add")
        self._btn_add.setObjectName("btn_row_add")
        self._btn_add.setEnabled(False)
        self._btn_add.clicked.connect(self._add_holiday)
        self._btn_delete = QPushButton("Delete")
        self._btn_delete.setObjectName("btn_row_delete")
        self._btn_delete.setEnabled(False)
        self._btn_delete.clicked.connect(self._delete_holiday)
        add_row.addWidget(self._name_edit)
        add_row.addWidget(self._date_edit)
        add_row.addWidget(self._btn_add)
        add_row.addStretch()
        add_row.addWidget(self._btn_delete)
        v.addLayout(add_row)

        self._name_edit.textChanged.connect(self._refresh_add_enabled)
        self._date_edit.textChanged.connect(self._refresh_add_enabled)
        return group

    def _load_holidays(self, select_id=None) -> None:
        try:
            rows = cal.get_holidays(self._db_path)
        except Exception as exc:
            from gui.errors import show_db_error
            show_db_error(self, exc)
            rows = []
        self._table.setRowCount(0)
        for row in rows:
            r = self._table.rowCount()
            self._table.insertRow(r)
            name_item = QTableWidgetItem(row["name"])
            name_item.setData(Qt.ItemDataRole.UserRole, row["id"])
            date_item = QTableWidgetItem(row["date"].strftime("%m/%d/%Y"))
            date_item.setToolTip(row["date"].strftime("%A"))
            self._table.setItem(r, 0, name_item)
            self._table.setItem(r, 1, date_item)
            if row["id"] == select_id:
                self._table.selectRow(r)
        self._refresh_delete_enabled()

    def _refresh_add_enabled(self) -> None:
        ok = bool(self._name_edit.text().strip()) and \
            self._date_edit.to_pydate() is not None
        self._btn_add.setEnabled(ok)

    def _refresh_delete_enabled(self) -> None:
        self._btn_delete.setEnabled(self._table.currentRow() >= 0
                                    and bool(self._table.selectedItems()))

    def _add_holiday(self) -> None:
        name = self._name_edit.text().strip()
        day = self._date_edit.to_pydate()
        if not name or day is None:
            return
        try:
            cal.insert_holiday(name, day, self._db_path)
        except Exception as exc:
            from gui.errors import show_db_error
            show_db_error(self, exc)
            return
        self._name_edit.clear()
        self._date_edit.clear()
        self._load_holidays()
        # Select the row we just added (newest row for that name+date).
        for r in range(self._table.rowCount() - 1, -1, -1):
            if (self._table.item(r, 0).text() == name
                    and self._table.item(r, 1).text()
                    == day.strftime("%m/%d/%Y")):
                self._table.selectRow(r)
                break

    def _delete_holiday(self) -> None:
        r = self._table.currentRow()
        if r < 0:
            return
        record_id = self._table.item(r, 0).data(Qt.ItemDataRole.UserRole)
        name = self._table.item(r, 0).text()
        when = self._table.item(r, 1).text()
        answer = QMessageBox.question(
            self, "Delete Holiday",
            f"Delete holiday '{name}' on {when}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            cal.delete_holiday(record_id, self._db_path)
        except Exception as exc:
            from gui.errors import show_db_error
            show_db_error(self, exc)
            return
        self._load_holidays()

    # ── operating days ────────────────────────────────────────────────
    def _build_hours_group(self) -> QGroupBox:
        group = QGroupBox("Operating Days")
        v = QVBoxLayout(group)
        v.addWidget(QLabel("Uncheck a day to close the center that day. "
                           "Opening and closing times are the earliest "
                           "Time-In and latest Time-Out on the schedule."))
        grid = QGridLayout()
        grid.addWidget(QLabel("Open"), 0, 0)
        grid.addWidget(QLabel("Opens"), 0, 1)
        grid.addWidget(QLabel("Closes"), 0, 2)
        self._day_rows: dict[int, tuple] = {}
        for dow, name in enumerate(cal.DAY_NAMES, start=1):
            check = QCheckBox(name)
            opening = _TimeEntry(cal.DEFAULT_OPENING, self._mark_dirty)
            closing = _TimeEntry(cal.DEFAULT_CLOSING, self._mark_dirty)
            check.toggled.connect(
                lambda on, o=opening, c=closing: self._toggle_day(on, o, c))
            grid.addWidget(check, dow, 0)
            grid.addWidget(opening, dow, 1)
            grid.addWidget(closing, dow, 2)
            self._day_rows[dow] = (check, opening, closing)
        grid.setColumnStretch(3, 1)
        v.addLayout(grid)

        buttons = QHBoxLayout()
        self._btn_save = QPushButton("Save Hours")
        self._btn_save.setObjectName("btn_row_add")
        self._btn_save.setEnabled(False)
        self._btn_save.clicked.connect(self._save_hours)
        buttons.addWidget(self._btn_save)
        buttons.addStretch()
        v.addLayout(buttons)
        return group

    def _toggle_day(self, on: bool, opening, closing) -> None:
        opening.setEnabled(on)
        closing.setEnabled(on)
        self._mark_dirty()

    def _mark_dirty(self) -> None:
        if self._loading:
            return
        self._dirty = True
        self._btn_save.setEnabled(True)

    def _load_hours(self) -> None:
        try:
            days = cal.get_operating_days(self._db_path)
        except Exception as exc:
            from gui.errors import show_db_error
            show_db_error(self, exc)
            days = {}
        self._loading = True
        try:
            for dow, (check, opening, closing) in self._day_rows.items():
                row = days.get(dow)
                check.setChecked(row is not None)
                opening.set_hhmm(row["opening_time"] if row
                                 else cal.DEFAULT_OPENING)
                closing.set_hhmm(row["closing_time"] if row
                                 else cal.DEFAULT_CLOSING)
                opening.setEnabled(row is not None)
                closing.setEnabled(row is not None)
        finally:
            self._loading = False
        self._dirty = False
        self._btn_save.setEnabled(False)

    def _collect_rows(self) -> list[dict]:
        rows = []
        for dow, (check, opening, closing) in self._day_rows.items():
            if check.isChecked():
                rows.append({"day_of_week": dow,
                             "opening_time": opening.hhmm(),
                             "closing_time": closing.hhmm()})
        return rows

    def _save_hours(self) -> None:
        rows = self._collect_rows()
        problems = cal.validate_hours(rows)
        if problems:
            QMessageBox.warning(self, "Check the Hours",
                                "\n".join(problems))
            return
        if not rows:
            answer = QMessageBox.question(
                self, "No Open Days",
                "No days are marked open, so the scheduler will produce "
                "no times for anyone. Save anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                return
        try:
            cal.save_operating_days(rows, self._db_path)
        except Exception as exc:
            from gui.errors import show_db_error
            show_db_error(self, exc)
            return
        self._load_hours()

    # ── closing ───────────────────────────────────────────────────────
    def _confirm_discard(self) -> bool:
        box = QMessageBox(self)
        box.setWindowTitle("Unsaved Hours")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText("Discard unsaved operating hours?")
        discard = box.addButton("Discard", QMessageBox.ButtonRole.DestructiveRole)
        box.addButton("Keep Editing", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        return box.clickedButton() is discard

    def reject(self) -> None:
        if self._dirty and not self._confirm_discard():
            return
        super().reject()

    def closeEvent(self, event) -> None:
        if self._dirty and not self._confirm_discard():
            event.ignore()
            return
        super().closeEvent(event)
```

- [ ] **Step 4: Run the tests**

Run: `.venv\Scripts\python.exe -m pytest tests/test_company_calendar_dialog.py -q`
Expected: all pass. If `test_holidays_listed_sorted_and_add_gated` fails on the date column, remember `DateLineEdit` reformats digits on `textEdited` only (not `setText`), so the test types the slashed form directly — keep it that way.

- [ ] **Step 5: Commit**

```bash
git add gui/company_calendar.py tests/test_company_calendar_dialog.py
git commit -m "feat(gui): Company Calendar dialog for holidays and operating days"
```

---

### Task 4: Toolbar button, handler, theme

**Files:**
- Modify: `gui/main_window.py`
- Modify: `gui/theme.py`
- Test: `tests/test_company_calendar_dialog.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_company_calendar_dialog.py`:

```python
def test_toolbar_button_sits_after_absences(qapp, tmp_path):
    from PyQt6.QtWidgets import QToolBar
    from gui.main_window import MainWindow
    w = MainWindow({"db_path": "", "theme": "dark"},
                   str(tmp_path / "settings.json"))
    toolbar = w.findChild(QToolBar, "main_toolbar")
    names = [toolbar.widgetForAction(a).objectName()
             for a in toolbar.actions()
             if toolbar.widgetForAction(a) is not None]
    i = names.index("btn_absence_report")
    assert names[i + 1] == "btn_company_calendar"


def test_open_company_calendar_without_db_warns(qapp, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    from gui.main_window import MainWindow
    warned = []
    monkeypatch.setattr(QMessageBox, "warning",
                        lambda *a, **k: warned.append(a[1]))
    w = MainWindow({"db_path": "", "theme": "dark"},
                   str(tmp_path / "settings.json"))
    w._open_company_calendar()
    assert warned == ["No Database"]
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest tests/test_company_calendar_dialog.py -q -k "toolbar or without_db"`
Expected: `ValueError: 'btn_company_calendar' is not in list` and `AttributeError: _open_company_calendar`.

- [ ] **Step 3: Implement**

In `gui/main_window.py`, in `_build_ui`, directly after `toolbar.addWidget(btn_absences)`:

```python
        btn_calendar = QPushButton("🏢  Company Calendar")
        btn_calendar.setObjectName("btn_company_calendar")
        btn_calendar.setToolTip(
            "Company holidays and weekly operating hours used by the "
            "monthly scheduler")
        btn_calendar.clicked.connect(self._open_company_calendar)
        toolbar.addWidget(btn_calendar)
```

After `_open_absence_report`, add:

```python
    def _open_company_calendar(self):
        """Company holidays and the weekly operating hours (Holidays /
        OperatingDays tables) that the monthly scheduler honors."""
        db_path = self._settings.get("db_path", "")
        if not db_path:
            QMessageBox.warning(self, "No Database",
                "Set a database path in Settings before editing the "
                "company calendar.")
            return
        from gui.company_calendar import CompanyCalendarDialog
        CompanyCalendarDialog(db_path, self).exec()
```

In `gui/theme.py`, add `QPushButton#btn_company_calendar` to both selector lists that currently read `QPushButton#btn_export, QPushButton#btn_expiring_report, QPushButton#btn_birthday_report, QPushButton#btn_absence_report, QPushButton#btn_bookmarks` (the base rule and the `:hover` rule), e.g.:

```
QPushButton#btn_export, QPushButton#btn_expiring_report,
QPushButton#btn_birthday_report, QPushButton#btn_absence_report,
QPushButton#btn_company_calendar, QPushButton#btn_bookmarks {{
```

and the same with `:hover` suffixes in the hover rule.

- [ ] **Step 4: Run the tests**

Run: `.venv\Scripts\python.exe -m pytest tests/test_company_calendar_dialog.py tests/test_bookmark_button.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add gui/main_window.py gui/theme.py tests/test_company_calendar_dialog.py
git commit -m "feat(gui): Company Calendar toolbar button"
```

---

### Task 5: Full run, manual check, exe

- [ ] **Step 1: Run the whole suite**

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: all pass.

- [ ] **Step 2: Manual check against a database that has been through the new BSCA Setup**

Run `.venv\Scripts\python.exe main.py`, open **🏢 Company Calendar**:
- Add a holiday, confirm it appears sorted by date; delete it with the confirmation.
- Uncheck Wednesday, change Monday to 9:00 AM – 3:00 PM, Save Hours; reopen the dialog and confirm both persisted. Re-check Wednesday and save to restore.
- Set Tuesday closing before opening and confirm the warning names Tuesday.
- Open the dialog against a database without the tables: the startup schema warning should list `table Holidays` and `table OperatingDays`.

- [ ] **Step 3: Update PRODUCT.md and rebuild**

In `PRODUCT.md` under **Key Surfaces**, add `- Company Calendar dialog (holidays + weekly operating hours)`.

Build per `docs/deployment.md`: `.venv\Scripts\pyinstaller CareManager.spec --noconfirm` (or `deploy\deploy.ps1` for a release).

- [ ] **Step 4: Commit**

```bash
git add PRODUCT.md
git commit -m "docs: Company Calendar surface"
```
