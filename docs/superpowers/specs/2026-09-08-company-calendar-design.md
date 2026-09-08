# Company Calendar (holidays and operating days)

Date: 2026-09-08

## Goal

Give staff one place in BSCA Member Manager to record company holidays
and the center's weekly operating hours. The monthly scheduler (the
sibling `BSCA` repo) reads both tables and skips closed days; that side,
including the table DDL and the Setup step that creates and seeds the
tables, is specified in
`BSCA/docs/superpowers/specs/2026-09-08-holidays-operating-days-design.md`.

## Tables (created by the BSCA Setup chain, not by this app)

- `Holidays`: `ID` autonumber, `holiday_name` TEXT(255), `date` DATETIME
  (date only). One row per closed date.
- `OperatingDays`: `ID` autonumber, `day_name` TEXT(20), `Day Of Week`
  LONG (1 = Monday … 7 = Sunday), `opening_time` / `closing_time`
  DATETIME holding a time-of-day (`1899-12-30 HH:MM`, like
  `Availability.avail_start`). A weekday with no row is closed. Setup
  seeds seven rows at 08:00–16:00 when the table is empty.

Both join `REQUIRED_SCHEMA` in `db/members.py`:
`"Holidays": ["holiday_name", "date"]` and
`"OperatingDays": ["day_name", "Day Of Week", "opening_time",
"closing_time"]`, so an old database triggers the existing startup
warning telling staff to re-run Setup. `docs/database-schema.md` gets a
section for each table.

## DB layer: new module `db/company_calendar.py`

Kept out of `db/members.py`, which is already 1,850 lines. It reuses
`write_conn`, `_read_connection`, `_hhmm_to_datetime`, `_access_date`,
and `_access_hhmm` from `db.members`.

```python
DAY_NAMES = ("Monday", ..., "Sunday")          # index 0 = Day Of Week 1

def get_holidays(db_path) -> list[dict]        # {id, name, date}, sorted by date
def insert_holiday(name: str, day: date, db_path) -> None
def delete_holiday(record_id: int, db_path) -> None

def get_operating_days(db_path) -> dict[int, dict]
    # {day_of_week: {id, day_name, opening_time 'HH:MM', closing_time 'HH:MM'}}
    # duplicate weekday rows: largest ID wins
def save_operating_days(rows: list[dict], db_path) -> None
    # rows = [{day_of_week, opening_time 'HH:MM', closing_time 'HH:MM'}, ...]
    # one transaction: DELETE FROM [OperatingDays]; then INSERT each row
    # with day_name = DAY_NAMES[day_of_week - 1]
```

Pure validation helpers, unit-testable without Access:

```python
def validate_hours(rows) -> list[str]
    # per-row: closing must be after opening; returns messages like
    # "Tuesday: closing time must be after opening time"
```

## GUI: `gui/company_calendar.py`, `CompanyCalendarDialog`

Opened from a new toolbar button `🏢  Company Calendar`
(`objectName="btn_company_calendar"`, styled like `btn_absence_report`),
placed right after the Absences button. `MainWindow._open_company_calendar`
mirrors `_open_absence_report` (reads `db_path` from settings, shows
`show_db_error` on failure).

The dialog is modal, titled "Company Calendar", minimum width 520, and
has two group boxes stacked vertically.

### Holidays group

- A read-only `QTableWidget` with columns **Holiday** and **Date**
  (M/D/YYYY, weekday shown in a tooltip), sorted by date ascending,
  all rows including past ones. Row selection is whole-row, single.
- Below it an add row: name `QLineEdit` (placeholder "Holiday name"),
  date `QLineEdit` using the existing `format_mdy_live` / `parse_mdy`
  helpers (placeholder "M/D/YYYY"), and an **Add** button
  (`btn_row_add`). Add is enabled only when the name is non-blank and
  the date parses. On click: `insert_holiday`, clear the inputs, reload
  the table, select the new row.
- A **Delete** button (`btn_row_delete`), enabled when a row is
  selected. Confirmation: "Delete holiday 'Labor Day' on 9/7/2026?"
  Yes/No, then `delete_holiday` and reload.
- Adds and deletes write immediately, like the per-member tabs.

### Operating days group

- Seven fixed rows, Monday to Sunday, in a `QGridLayout`:
  `QCheckBox("Monday")` labelled **Open**, then an opening-time entry
  and a closing-time entry. Each time entry is the app's existing
  pattern: a `QLineEdit` with `format_time_live` plus an AM/PM
  `QComboBox`, converted with `time_12h_to_24h` on save and shown with
  the 12-hour formatter on load.
- Loading: for each weekday, checked iff a row exists; times from the
  row, else the 08:00 AM / 04:00 PM defaults (so re-checking a closed
  day starts from the defaults).
- Unchecking disables that row's time entries. Any edit or toggle
  marks the section dirty and enables **Save Hours**.
- **Save Hours** (`btn_row_add` style): collect checked rows, run
  `validate_hours`; on messages show a warning box listing them and
  stop. If zero rows are checked, ask "No days are marked open, so the
  scheduler will produce no times for anyone. Save anyway?" Then
  `save_operating_days`, reload, clear dirty.
- Closing the dialog with unsaved hour changes asks "Discard unsaved
  operating hours?" (Discard / Keep Editing), matching the app's
  non-destructive default.

No events-log entries: events are keyed by member and these records
are center-wide.

## Testing (pytest, existing fixtures)

- `tests/test_company_calendar_db.py`: `validate_hours` cases (good,
  closing before opening, closing equal to opening); `get_operating_days`
  picks the largest ID on duplicates (mocked rows); an insert/read/delete
  round-trip against `BSCA/scripts/test_dbs/populate_real_members.accdb`,
  skipped when that file is absent (the pattern in
  `tests/test_db_members_integration.py`; `tests/conftest.py`'s
  `ensure_optional_tables` fixture creates and later drops the two
  tables so the shared test DB stays clean).
- `tests/test_company_calendar_dialog.py` (with the `qapp` fixture and
  `db.company_calendar` monkeypatched): Add button gating; Add calls
  `insert_holiday` and reloads; Delete confirms then calls
  `delete_holiday`; unchecking Wednesday and saving calls
  `save_operating_days` with six rows; invalid hours block the save;
  zero open days prompts.
- `tests/test_company_calendar_dialog.py` also checks the main window
  toolbar: a button with `objectName == "btn_company_calendar"` exists
  and sits immediately after `btn_absence_report`.
- `tests/test_db_members.py`: `REQUIRED_SCHEMA` includes both tables.

After the code lands, rebuild the packaged exe per `docs/deployment.md`.
