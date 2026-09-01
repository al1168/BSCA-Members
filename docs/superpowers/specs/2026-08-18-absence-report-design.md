# Absences Report — Design

**Date:** 2026-08-18
**Status:** Approved (dialog choices confirmed by Alden)

## Purpose

A monthly report, launched from the toolbar like Birthdays and Expiring,
that saves a spreadsheet of every absence overlapping a chosen month/year.
Used to review who was out (hospital stays, vacations, leaves) in a given
month.

## Confirmed decisions

- **Month match:** an absence appears in every month its date range
  overlaps — a Jan 28 → Feb 10 stay shows in both January and February.
  A missing end date means the absence is still ongoing, so it matches
  the selected month whenever its start date is on or before the month's
  last day.
- **Members:** active members only (same terminated-exclusion rule as the
  Birthdays and Expiring reports).
- **Style:** ruled printable record sheet via the existing
  `_write_record_sheet` helper — bordered cells, shaded header, print
  setup, MM/DD/YYYY date cells.

## Components

### db/members.py — bulk absences query

`ABSENCES_ALL_SELECT`: `SELECT [Center ID],[Leave Type],[Start_Date],
[End_Date],[Notes] FROM [Absences]` and
`get_all_absences(db_path) -> list[tuple]`, following the
`get_member_auth_ends` pattern exactly: cached read connection, one bulk
SELECT, stale-connection retry. Returns raw tuples; date/None handling
happens in the pure filter function.

### db/export.py — pure filter + writer

- `ABSENCE_COLUMNS = ["Center Id", "Name", "Leave Type", "Start Date",
  "End Date", "Notes"]`
- `member_absences_in_month(members, terminated_ids, absence_rows, year,
  month) -> list[dict]` — pure, unit-testable:
  - one output row per absence (a member with two absences in the month
    yields two rows)
  - skips rows whose Center ID is missing, terminated members, and rows
    with no parseable start date
  - overlap rule: `start <= last_day_of_month` and
    `(end is None or end >= first_day_of_month)`
  - sort: start date, then name (case-insensitive)
  - row dict: `center_id`, `name` ("Last, First"), `leave_type`,
    `start`, `end` (None when open-ended), `notes`
- `write_absence_xlsx(path, rows, month_label)` — `_write_record_sheet`
  with sheet title `Absences {month_label}`, widths sized so the sheet
  fits the printable width at 100% scale, Center Id and dates centered.
  Open-ended absences show an empty End Date cell.

### gui/absence_report.py — dialog

`AbsenceReportDialog(db_path, members, terminated_ids, parent, today)`,
modeled on `ExpiringReportDialog` minus the health-plan filter:

- month combo + year spinbox (2000–2100), defaulting to the **current**
  month (absences are reviewed for the month in progress or just past,
  unlike expiring auths which look ahead)
- live count label: "N absences in {Month} {Year}"; Save button disabled
  at zero
- Save Spreadsheet… → default filename `Absences {Month} {Year}.xlsx` in
  Documents; PermissionError → "may be open in Excel" message; success →
  saved-count dialog with an Open Spreadsheet button
- DB errors during count/save surfaced via `gui.errors.show_db_error`

### gui/main_window.py — toolbar button

"🏥  Absences" button between Expiring Report and Export, tooltip
describing the report, opening `AbsenceReportDialog` with the same
arguments the Expiring report gets (db path, members, terminated ids).

## Testing

`tests/test_absence_report.py`, mirroring `test_birthday_report.py`:

- overlap edge cases: starts before/ends inside, spans the whole month,
  starts inside/ends after, open-ended (no end date), entirely outside
  the month, datetime vs date values from Access
- terminated members and null Center IDs excluded; missing start date
  skipped
- one row per absence for a member with two absences in the month
- xlsx round-trip: columns, sheet title, ruled borders, date format,
  empty End Date for open-ended rows, print setup
- dialog: defaults to current month/year, live count across month/year
  changes, Save disabled at zero rows

## Out of scope

- Leave-type filter checkboxes (add later if needed, following the
  Expiring dialog's health-plan filter)
- Editing absences from the report (the member's Absences tab already
  does this)
