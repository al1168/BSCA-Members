# Meal Sheet Report — Design

**Date:** 2026-09-10
**Status:** Approved (decisions confirmed by Alden)

## Purpose

A monthly report, launched from the toolbar like Birthdays, Expiring, and
Absences, that saves a **blank** meal-sheet workbook for a chosen month.
Staff previously hand-built this workbook every month from a copy of the
previous one (`2026 Sept meal sheet -template.xlsm`); the member list
drifted from the database and the bottom SUM ranges went stale.

The workbook lists only members who are **enrolled on some day of the
month and hold at least one authorization overlapping the month**, one
column per day, with each day cell pre-shaded by whether the member is
authorized that weekday. Staff fill in meal counts by hand.

## What the hand-made template looks like (verified with openpyxl)

- Three member sheets with identical layout, titled `会员早餐统计-B`
  (breakfast), `会员餐券统计-B` (meal ticket), `会员午餐统计-B` (lunch).
  Header: `ID | Alt Id | Name | Health plan | <one column per date, m/d> |
  Total | Location`. Calibri 14, thin borders on every cell, header row
  ~44pt, data rows ~26pt, landscape at 79%, margins 0.25/0.75. Rows sorted
  by Center ID ascending. Total = `SUM` of the row's day cells.
- Day-cell fills (theme colours): orange (accent2, tint 0.4) = authorized
  weekday; blue (accent5, tint 0.8) = not authorized; yellow (accent4,
  tint 0.8) = closed. The template marks only Sundays as closed.
- Bottom rows `Total`, `Authorized`, `Not_Authorized`; the last two used a
  VBA `SumCellsByColor` macro.
- Staff and anniversary-tea sheets are not member-driven and are out of
  scope.

## Confirmed decisions

- **Members:** enrollment overlaps the month AND at least one
  Authorization overlaps the month. Overlap: `start <= last_day and (end
  is None or end >= first_day)`. A missing enrollment start disqualifies;
  a missing auth start does not (as in `pick_active_auth`). The report
  does **not** use the "terminated today" set the other reports use, so a
  past month still lists members terminated since.
- **Sheets:** all three member sheets, identical; no staff/tea sheets; no
  extra fixed rows (the template's 孙老师 / 公司 rows).
- **Location:** `Contacts.[Group]` as-is; blank when NULL. (The test
  database has it NULL everywhere; production is expected to hold B / C.)
- **Closed days:** company holidays plus any weekday without an
  `OperatingDays` row (Company Calendar). Closed wins over authorized. An
  empty OperatingDays table closes the whole month, by that table's
  definition.
- **Shading is per day:** a date is authorized when some auth covers that
  exact date and its `auth_days` includes the date's weekday (union across
  overlapping auths). Malformed `auth_days` text counts as no days.
- **Plain .xlsx, no VBA.** `Authorized` / `Not_Authorized` rows use
  `SUMPRODUCT` against a hidden `_mask` sheet holding 1 in authorized day
  cells and 0 elsewhere (closed days count as not authorized).
- **Alt ID:** filled only when the session alt-id password is unlocked
  (the corpus is already decrypted in place then); otherwise blank.
- **Fills** as concrete RGB: authorized `F4B183`, closed `FFF2CC`, not
  authorized `DEEBF7`.

## Components

### db/members.py — bulk Group query

`CONTACT_GROUPS_QUERY = "SELECT [Center ID],[Group] FROM [Contacts]"` and
`get_member_groups(db_path) -> dict[int, str]` (NULL Group → `""`),
following `get_member_auth_ends` exactly. A separate query rather than an
extension of `ALL_MEMBERS_QUERY` because that query runs at startup and
its dict shape is pinned by the integration tests.

### db/export.py — pure functions, loader, writer

- `members_for_meal_sheet(members, groups, enrollment_rows, auth_rows,
  year, month, alt_ids_unlocked) -> list[dict]` — row dict: `center_id`,
  `alt_id`, `name` ("Last, First"), `health_plan`, `location`, `auths`
  (list of `(start, end, auth_days)` overlapping the month). Sorted by
  `center_id`.
- `closed_days_in_month(year, month, holidays, operating_days) -> set[int]`
- `meal_day_states(auths, year, month, closed_days) -> list[str]` — one
  of `DAY_AUTHORIZED / DAY_CLOSED / DAY_NOT_AUTHORIZED` per day.
- `load_meal_sheet_inputs(db_path) -> dict` — the five bulk reads
  (enrollments, auths, groups, holidays, operating_days), fetched once per
  dialog.
- `write_meal_sheet_xlsx(path, rows, year, month, closed_days)` — three
  sheets + hidden `_mask`, created last with the breakfast sheet active.
  Day `d` sits at column `4 + d`; Total and Location follow the last day.
  Widths A16 B16 C29 D18, days 9, Total 9, Location 10. `freeze_panes =
  "E2"`, landscape, scale 79, `print_title_rows = "1:1"`,
  `print_title_cols = "A:D"` so names repeat on overflow pages. With no
  rows only the header is written.

### gui/meal_sheet.py — dialog

`MealSheetDialog(db_path, members, parent, today, alt_ids_unlocked)`,
modeled on `AbsenceReportDialog`: month combo + year spinbox defaulting to
the current month, live "N members in {Month} {Year}" count, Save disabled
at zero, default filename `Meal Sheet {Month} {Year}.xlsx` in Documents,
PermissionError → "may be open in Excel" message, success → "Open
Spreadsheet" button. DB errors via `gui.errors.show_db_error`.

### gui/main_window.py — toolbar button

"🍱  Meal Sheet" between Company Calendar and Export (an existing test pins
Company Calendar directly after Absences). `_open_meal_sheet` guards on
the database path and passes `alt_ids_unlocked=bool(self._alt_id_password)`.

## Testing

`tests/test_meal_sheet.py`: member filter edge cases (no enrollment, no
auth, ranges ending before the month, open-ended ranges, datetime values,
NULL Center ID, missing enrollment start), sorting and row fields, alt-id
locked/unlocked, closed days (weekends + Labor Day, other-month holidays
ignored, empty operating days), per-day states (range, weekday, closed
wins, union of auths, malformed days), workbook round-trip (sheet names,
hidden mask, header/format/font/heights/widths, freeze, print setup,
fills, mask values, formulas, three sheets identical, zero rows), dialog
counts with the loader called once, save path, and toolbar wiring.

## Out of scope

- Staff meal sheet and anniversary-tea sheet.
- Marking one-off availability or absences on the sheet.
- A remembered output folder (all reports default to Documents).
