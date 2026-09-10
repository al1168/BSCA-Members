# Meal Sheet Report Implementation Plan (BSCA-Members repo)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add a "🍱 Meal Sheet" toolbar button that saves a blank monthly meal-sheet workbook (three identical sheets: breakfast, meal ticket, lunch) listing every member enrolled and authorized at some point in the chosen month, with day cells shaded by authorization / closed days.

**Architecture:** Pure functions and the xlsx writer live in `db/export.py` beside the other reports; one new bulk read (`get_member_groups`) joins `db/members.py`; `gui/meal_sheet.py` holds `MealSheetDialog`, opened from `MainWindow`. Company Calendar reads (`db/company_calendar.py`) supply closed days.

**Tech Stack:** Python 3.11, PyQt6, pyodbc against Microsoft Access, openpyxl, pytest. Run tests with `.venv\Scripts\python.exe -m pytest` from `C:\Users\luald\OneDrive\Desktop\BSCA-Members`. Qt tests use `os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")` and a module-scoped `qapp` fixture, as in `tests/test_absence_report.py`.

**Spec:** `docs/superpowers/specs/2026-09-10-meal-sheet-design.md`.

---

## File map

| File | Change |
| --- | --- |
| `db/members.py` | `CONTACT_GROUPS_QUERY`, `get_member_groups` |
| `db/export.py` | Meal-sheet constants, `members_for_meal_sheet`, `closed_days_in_month`, `meal_day_states`, `load_meal_sheet_inputs`, `write_meal_sheet_xlsx` |
| `gui/meal_sheet.py` | **New.** `MealSheetDialog` |
| `gui/main_window.py` | Toolbar button between Company Calendar and Export + `_open_meal_sheet` |
| `gui/theme.py` | `btn_meal_sheet` joins the outline-button selectors |
| Tests | `tests/test_meal_sheet.py` (new), `tests/test_db_members.py` |

---

### Task 1: bulk Group query — `db/members.py`

- [x] Test: `test_contact_groups_query_shape` in `tests/test_db_members.py`.
- [x] `CONTACT_GROUPS_QUERY` + `get_member_groups(db_path) -> dict[int, str]`, modeled on `get_member_auth_ends`.

### Task 2: pure functions — `db/export.py`

- [x] Tests: member filter (both overlaps required, open-ended ranges, datetimes, NULL Center ID, missing enrollment start), sort + fields, alt-id locked/unlocked, other months.
- [x] Tests: `closed_days_in_month` (weekends + holiday, other-month holiday ignored, empty operating days).
- [x] Tests: `meal_day_states` (range + weekday, closed wins, union, open-ended, malformed days, empty).
- [x] Implement `members_for_meal_sheet`, `closed_days_in_month`, `_safe_auth_days`, `meal_day_states`, `load_meal_sheet_inputs`.

### Task 3: writer — `db/export.py`

- [x] Tests: sheet names + hidden mask + active sheet, header values/format/font/heights/widths, freeze/print setup/margins/borders, member rows, fills + mask values, summary-row formulas, three sheets identical, zero rows.
- [x] Implement `write_meal_sheet_xlsx` (three sheets via one `fill_sheet` closure, `_mask` created last, `wb.active = 0`).

### Task 4: dialog — `gui/meal_sheet.py`

- [x] Tests: defaults + live counts with the loader called once, load error disables Save, save writes the workbook.
- [x] Implement `MealSheetDialog` (copy of `AbsenceReportDialog`; inputs cached per dialog).

### Task 5: wiring — `gui/main_window.py`, `gui/theme.py`

- [x] Tests: button sits between Company Calendar and Export; no-DB warning.
- [x] Button + tooltip + `_open_meal_sheet` passing `alt_ids_unlocked=bool(self._alt_id_password)`; theme selectors.

### Verification

- [x] `.venv\Scripts\python.exe -m pytest -q` — 751 passed.
- [x] Headless run against the September 2026 test database: 433 members, member 14's shading pattern matches the hand-made template (plus Labor Day closed).
- [ ] In Excel: open the saved file, type `1` into an orange cell and a blue cell, confirm the Total / Authorized / Not_Authorized rows update; compare colours and widths with the template.
- [ ] Run BSCA Setup on the target database first if the Company Calendar tables are missing (the dialog shows the existing "Run BSCA Setup" message otherwise).
