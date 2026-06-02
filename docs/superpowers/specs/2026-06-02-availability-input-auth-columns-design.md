# Availability Time Input & Authorizations Column Widths — Design Spec

**Date:** 2026-06-02
**Status:** Approved (pending spec review)

## Goal

Two focused UI improvements on the member profile:

1. **Availability time entry** — replace the `QTimeEdit` spinners in the Add Availability dialog with a typed `h:mm` text box plus an AM/PM dropdown for each of Start and End time.
2. **Authorizations table layout** — stop the Action column from stretching wide, give the Days column room by shortening its header (with a tooltip legend), and ensure the Edit button fits.

## Architecture

- The availability time-string conversion (12-hour input → stored 24-hour `"HH:mm"`) is a **pure function** `time_12h_to_24h` in `db/members.py`, alongside the existing time helpers (`_hhmm_to_datetime`, `encode_auth_days`). It is unit-tested.
- The `_add_avail` dialog in `gui/member_tabs.py` builds the new widgets, validates on OK (keeping the dialog open on bad input), and calls the **unchanged** `insert_availability(...)` with `"HH:mm"` 24-hour strings. Storage format and `_hhmm_to_datetime` are untouched.
- The `_make_auths_tab` table in `gui/member_tabs.py` switches from `setStretchLastSection(True)` to explicit per-column `QHeaderView` resize modes.

## Tech Stack

Python 3.11, PyQt6, pyodbc (Access), pytest. No new dependencies.

---

## Part 1 — Availability time input

### Current behavior

`_add_avail` uses:

```python
t_start = QTimeEdit(QTime(8, 0))
t_end = QTimeEdit(QTime(16, 0))
...
ts = t_start.time().toString("HH:mm")  # "08:00"
te = t_end.time().toString("HH:mm")    # "16:00"
insert_availability(self._center_id, day, ts, te, eff_start.date().toPyDate(), None, self._db_path)
```

`QTimeEdit` renders up/down spinner arrows in 24-hour format, which the user finds awkward.

### New behavior

Each of Start Time and End Time becomes a composite row: a `QLineEdit` (typed `h:mm`) + a `QComboBox` with items `["AM", "PM"]`, placed in a `QWidget` with a horizontal layout (mirrors the day-checkbox container in `_open_auth_dialog`).

- **Defaults:** Start = `QLineEdit("8:00")` + period `AM`; End = `QLineEdit("4:00")` + period `PM`.
- **No spinners** — plain text entry.
- **Validation on OK:** override the dialog's accept (same idiom as the auth dialog's "select at least one day"): attempt to convert both times via `time_12h_to_24h`; if either raises `ValueError`, show `QMessageBox.warning(dlg, "Validation", "Enter times as h:mm with hour 1-12 and minute 00-59.")` and do NOT accept (dialog stays open). Otherwise accept.
- On accept, pass the converted 24-hour strings to `insert_availability(...)` exactly as today. The event-log line continues to use the stored 24-hour strings (e.g., `Availability added: Mon 08:00–16:00`).

### Pure helper (in `db/members.py`)

```python
def time_12h_to_24h(text: str, period: str) -> str:
    """Convert a typed 12-hour time + AM/PM to 24-hour 'HH:mm'.

    '8:00','AM'  -> '08:00'
    '12:00','AM' -> '00:00'
    '12:00','PM' -> '12:00'
    '4:30','PM'  -> '16:30'

    Raises ValueError if the text is not 'h:mm', hour not in 1..12,
    minute not in 0..59, or period not 'AM'/'PM'.
    """
```

Behavior:
- Strip whitespace; require exactly one `:`; split into hour/minute integer parts (reject non-numeric).
- Validate `1 <= hour <= 12` and `0 <= minute <= 59`; `period` must be `"AM"` or `"PM"` (case-insensitive).
- Convert: `AM` → `hour % 12`; `PM` → `(hour % 12) + 12`. Return `f"{h24:02d}:{minute:02d}"`.

### Data flow unchanged

`insert_availability(center_id, day, avail_start, avail_end, effective_start, None, db_path)` still receives `"HH:mm"` 24-hour strings; `_hhmm_to_datetime` and Access storage are untouched.

---

## Part 2 — Availability table display

No change. The Availability table's Start/End columns keep showing the stored 24-hour `"HH:MM"` values (e.g., `08:00`, `16:00`). Only the input dialog changes.

---

## Part 3 — Authorizations table column widths

### Current behavior (`_make_auths_tab`)

Columns: `ID, Auth Start, Auth End, Days (1=Mon…5=Fri), Health Plan, Action`. The table sets `table.horizontalHeader().setStretchLastSection(True)`, so the **Action** (last) column stretches to fill all spare width while the long **Days** header is squeezed and clipped.

### New behavior

1. **Header rename + tooltip:** the Days column header label becomes `"Days"`; set a tooltip with the legend on that header section:
   ```python
   table.horizontalHeaderItem(3).setToolTip("1=Mon  2=Tue  3=Wed  4=Thu  5=Fri")
   ```
   (Header items exist after `setHorizontalHeaderLabels`.)

2. **Column sizing** via `QHeaderView` (replace `setStretchLastSection(True)`):
   ```python
   from PyQt6.QtWidgets import QHeaderView
   hdr = table.horizontalHeader()
   hdr.setStretchLastSection(False)
   hdr.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)  # all columns
   hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)        # Health Plan absorbs slack
   hdr.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # Action fits the Edit button
   ```
   - Index 4 (Health Plan) stretches so the table fills its width without bloating Action.
   - Index 5 (Action) sizes to its contents — the Edit button (and empty cells on non-latest rows) — so the **Edit text fits** and the column is no longer oversized.
   - Days (index 3) now renders fully since the header is short.

The column header label list changes from `"Days (1=Mon…5=Fri)"` to `"Days"`; everything else (data population, Edit button on the latest row, Add/Delete buttons) is unchanged.

The Enrollments table is intentionally left unchanged (its Status/Terminate column is wide enough to render).

---

## Testing

Unit tests (`tests/test_db_members.py`):
- `time_12h_to_24h` conversions: `("8:00","AM")=="08:00"`, `("12:00","AM")=="00:00"`, `("12:00","PM")=="12:00"`, `("4:30","PM")=="16:30"`, `("11:59","PM")=="23:59"`.
- `time_12h_to_24h` invalid inputs raise `ValueError`: `"8"` (no colon), `"13:00"`/`"AM"` (hour > 12), `"0:00"`/`"AM"` (hour < 1), `"8:60"`/`"AM"` (minute > 59), `"abc"`, and bad period `("8:00","XM")`.

GUI changes (dialog layout, header rename/tooltip, column resize modes) — verify with:
- Import smoke: `.venv\Scripts\python -c "from gui.member_tabs import MemberTabsWidget; print('OK')"`
- Manual: Add Availability shows two `h:mm` boxes + AM/PM dropdowns, no spinners; typing `8:00`/`AM` and `4:00`/`PM` saves a row showing `08:00`/`16:00`; bad input (e.g. `13:99`) shows a warning and the dialog stays open. Authorizations table shows a short `Days` header (full legend on hover), a compact Action column whose Edit button text is fully visible, and Health Plan filling the remaining width.

## Out of scope

- Changing the Availability table display to 12-hour (stays 24-hour).
- Editing existing availability rows (add/delete only, as today).
- Enrollments table column sizing.
