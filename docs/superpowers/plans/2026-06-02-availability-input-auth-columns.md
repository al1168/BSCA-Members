# Availability Time Input & Authorizations Column Widths Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Add Availability time spinners with a typed `h:mm` box + AM/PM dropdown, and fix the Authorizations table so the Days header renders and the Action/Edit column is compact.

**Architecture:** A pure, unit-tested `time_12h_to_24h` helper in `db/members.py` converts 12-hour input to the stored 24-hour `"HH:mm"` string; the `_add_avail` dialog in `gui/member_tabs.py` collects the new widgets, validates on OK, and calls the unchanged `insert_availability`. The `_make_auths_tab` table swaps `setStretchLastSection(True)` for explicit `QHeaderView` resize modes and shortens the Days header (legend moved to a tooltip).

**Tech Stack:** Python 3.11, PyQt6, pyodbc (Access), pytest. No new dependencies.

---

## File Map

```
db/members.py        modify — add pure helper time_12h_to_24h()
gui/member_tabs.py   modify — rewrite _add_avail() dialog; adjust _make_auths_tab() columns
tests/test_db_members.py  modify — unit tests for time_12h_to_24h()
```

No DB schema or storage change: `insert_availability` still receives 24-hour `"HH:mm"` strings.

---

## Task 1: time_12h_to_24h pure helper (DB layer)

**Files:**
- Modify: `db/members.py`
- Test: `tests/test_db_members.py`

- [ ] **Step 1: Write the failing unit tests**

Add to `tests/test_db_members.py` (the file already imports `pytest` at the top):

```python
@pytest.mark.parametrize("text,period,expected", [
    ("8:00", "AM", "08:00"),
    ("12:00", "AM", "00:00"),
    ("12:00", "PM", "12:00"),
    ("4:30", "PM", "16:30"),
    ("11:59", "PM", "23:59"),
    ("8:05", "am", "08:05"),
])
def test_time_12h_to_24h_valid(text, period, expected):
    from db.members import time_12h_to_24h
    assert time_12h_to_24h(text, period) == expected


@pytest.mark.parametrize("text,period", [
    ("8", "AM"),       # no colon
    ("13:00", "AM"),   # hour > 12
    ("0:00", "AM"),    # hour < 1
    ("8:60", "AM"),    # minute > 59
    ("abc", "AM"),     # non-numeric
    ("8:", "AM"),      # empty minute
    ("8:00", "XM"),    # bad period
])
def test_time_12h_to_24h_invalid(text, period):
    from db.members import time_12h_to_24h
    with pytest.raises(ValueError):
        time_12h_to_24h(text, period)
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv\Scripts\pytest tests/test_db_members.py -k time_12h_to_24h -v`
Expected: FAIL — `ImportError: cannot import name 'time_12h_to_24h'`

- [ ] **Step 3: Implement in `db/members.py`**

Add this function immediately after the existing `_hhmm_to_datetime` function (which ends around line 91):

```python
def time_12h_to_24h(text: str, period: str) -> str:
    """Convert a typed 12-hour time + AM/PM to 24-hour 'HH:mm'.

    '8:00','AM'  -> '08:00'
    '12:00','AM' -> '00:00'
    '12:00','PM' -> '12:00'
    '4:30','PM'  -> '16:30'

    Raises ValueError if the text is not 'h:mm', hour not in 1..12,
    minute not in 0..59, or period not 'AM'/'PM' (case-insensitive).
    """
    parts = text.strip().split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid time: {text!r}")
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError:
        raise ValueError(f"Invalid time: {text!r}")
    if not (1 <= hour <= 12) or not (0 <= minute <= 59):
        raise ValueError(f"Time out of range: {text!r}")
    p = period.strip().upper()
    if p not in ("AM", "PM"):
        raise ValueError(f"Invalid period: {period!r}")
    h24 = hour % 12 if p == "AM" else (hour % 12) + 12
    return f"{h24:02d}:{minute:02d}"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv\Scripts\pytest tests/test_db_members.py -k time_12h_to_24h -v`
Expected: 13 passed (6 valid + 7 invalid)

- [ ] **Step 5: Run the full suite**

Run: `.venv\Scripts\pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add db/members.py tests/test_db_members.py
git commit -m "feat: add time_12h_to_24h() helper for 12-hour time input"
```
End the commit message with the trailer:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Task 2: Rewrite the Add Availability dialog (GUI)

**Files:**
- Modify: `gui/member_tabs.py`

The current `_add_avail()` uses two `QTimeEdit` spinners. Replace the whole method so each time is a typed `h:mm` `QLineEdit` + an AM/PM `QComboBox`, validated on OK via `time_12h_to_24h`.

- [ ] **Step 1: Replace the entire `_add_avail()` method**

```python
    def _add_avail(self):
        from PyQt6.QtWidgets import (
            QDialog, QFormLayout, QComboBox, QLineEdit, QDateEdit,
            QDialogButtonBox, QWidget, QHBoxLayout,
        )
        from PyQt6.QtCore import QDate
        from db.members import insert_availability, time_12h_to_24h
        from db.events import open_db, insert_event
        from monthly_schedule.db import get_availability

        dlg = QDialog(self)
        dlg.setWindowTitle("Add Availability")
        form = QFormLayout(dlg)

        day_combo = QComboBox()
        for num, name in [(1, "Mon"), (2, "Tue"), (3, "Wed"), (4, "Thu"), (5, "Fri")]:
            day_combo.addItem(name, num)

        def time_row(default_text: str, default_period: str):
            container = QWidget()
            hl = QHBoxLayout(container)
            hl.setContentsMargins(0, 0, 0, 0)
            edit = QLineEdit(default_text)
            edit.setPlaceholderText("h:mm")
            period = QComboBox()
            period.addItems(["AM", "PM"])
            period.setCurrentText(default_period)
            hl.addWidget(edit)
            hl.addWidget(period)
            return container, edit, period

        start_row, start_edit, start_period = time_row("8:00", "AM")
        end_row, end_edit, end_period = time_row("4:00", "PM")
        eff_start = QDateEdit(QDate.currentDate())
        eff_start.setCalendarPopup(True)

        form.addRow("Day:", day_combo)
        form.addRow("Start Time:", start_row)
        form.addRow("End Time:", end_row)
        form.addRow("Effective From:", eff_start)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)

        def on_accept():
            try:
                time_12h_to_24h(start_edit.text(), start_period.currentText())
                time_12h_to_24h(end_edit.text(), end_period.currentText())
            except ValueError:
                QMessageBox.warning(dlg, "Validation",
                    "Enter times as h:mm with hour 1-12 and minute 00-59.")
                return
            dlg.accept()

        btns.accepted.connect(on_accept)

        if dlg.exec():
            day = day_combo.currentData()
            day_name = day_combo.currentText()
            ts = time_12h_to_24h(start_edit.text(), start_period.currentText())
            te = time_12h_to_24h(end_edit.text(), end_period.currentText())
            try:
                insert_availability(
                    self._center_id, day, ts, te,
                    eff_start.date().toPyDate(), None, self._db_path,
                )
                self._availability = get_availability(self._center_id, self._db_path)
                self._refresh_tab(3, self._make_avail_tab())
                if self._events_path:
                    conn = open_db(self._events_path)
                    try:
                        m = self._member
                        insert_event(conn, "AVAIL", self._center_id,
                            f"{m.get('last_name')}, {m.get('first_name')}",
                            f"Availability added: {day_name} {ts}–{te}")
                    finally:
                        conn.close()
            except Exception as exc:
                QMessageBox.critical(self, "Error", str(exc))
```

Notes for the implementer:
- `on_accept` validates and only calls `dlg.accept()` when both times parse; otherwise it warns and the dialog stays open (same idiom as `_open_auth_dialog`'s day validation).
- After `dlg.exec()` the recompute of `ts`/`te` is safe because accept only happens on valid input.
- `insert_availability` is unchanged — it still gets 24-hour `"HH:mm"` strings, so the table continues to display 24-hour times.

- [ ] **Step 2: Verify the import works**

Run: `.venv\Scripts\python -c "from gui.member_tabs import MemberTabsWidget; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Run the full suite (unaffected)**

Run: `.venv\Scripts\pytest -q`
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add gui/member_tabs.py
git commit -m "feat: type h:mm + AM/PM dropdown for availability times (no spinners)"
```
End with:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Task 3: Authorizations table column sizing + Days header (GUI)

**Files:**
- Modify: `gui/member_tabs.py`

Adjust `_make_auths_tab()`: shorten the Days header (legend → tooltip), and replace `setStretchLastSection(True)` with explicit resize modes so the Action column is compact and Health Plan absorbs slack.

- [ ] **Step 1: Update the imports + header + sizing in `_make_auths_tab()`**

Find the top of `_make_auths_tab()`:

```python
    def _make_auths_tab(self) -> QWidget:
        from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QAbstractItemView
        from db.members import latest_authorization

        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 12, 0, 0)

        columns = ["ID", "Auth Start", "Auth End", "Days (1=Mon…5=Fri)",
                   "Health Plan", "Action"]
        table = QTableWidget(len(self._authorizations), len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setVisible(False)
```

Replace it with:

```python
    def _make_auths_tab(self) -> QWidget:
        from PyQt6.QtWidgets import (
            QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView,
        )
        from db.members import latest_authorization

        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 12, 0, 0)

        columns = ["ID", "Auth Start", "Auth End", "Days", "Health Plan", "Action"]
        table = QTableWidget(len(self._authorizations), len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.horizontalHeaderItem(3).setToolTip("1=Mon  2=Tue  3=Wed  4=Thu  5=Fri")
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        hdr = table.horizontalHeader()
        hdr.setStretchLastSection(False)
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)        # Health Plan absorbs slack
        hdr.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # Action fits the Edit button
        table.verticalHeader().setVisible(False)
```

Leave the rest of the method (row population, the Edit button on the latest row, the Add/Delete button row, `return w`) exactly as-is.

- [ ] **Step 2: Verify the import works**

Run: `.venv\Scripts\python -c "from gui.member_tabs import MemberTabsWidget; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Run the full suite (unaffected)**

Run: `.venv\Scripts\pytest -q`
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add gui/member_tabs.py
git commit -m "fix: compact Authorizations Action column; short Days header with tooltip"
```
End with:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Task 4: Full suite + exe rebuild + manual smoke test

**Files:** none changed

- [ ] **Step 1: Run the full test suite**

Run: `.venv\Scripts\pytest -q`
Expected: all pass (the prior 50 plus the 13 new `time_12h_to_24h` cases).

- [ ] **Step 2: Rebuild the exe**

Stop any running instance (it locks the output file), then build:

```
powershell -Command "try { Stop-Process -Name MemberManager -Force -ErrorAction Stop } catch {}"
.venv\Scripts\pyinstaller MemberManager.spec
```

Expected: `Build complete! The results are available in: ...\dist`

- [ ] **Step 3: Manual smoke test**

Launch `dist\MemberManager.exe`, set the DB path if needed, click a member:
- **Availability → + Add:** Start/End are a typed `h:mm` box + AM/PM dropdown (no spinner arrows); defaults `8:00 AM` / `4:00 PM`. Saving adds a row showing `08:00` / `16:00`. Entering bad input (e.g. `13:99`) shows a validation warning and the dialog stays open.
- **Authorizations tab:** the `Days` header renders fully (hover shows `1=Mon … 5=Fri`); the Action column is compact and the **Edit** button text is fully visible; Health Plan fills the remaining width.

---

## Self-Review Notes

- **Spec coverage:** Part 1 (availability input) → Tasks 1 (helper) + 2 (dialog). Part 2 (table display stays 24-hour) → no change needed (the dialog passes 24-hour strings to the unchanged `insert_availability`). Part 3 (auth columns) → Task 3. Testing → Task 1 unit tests + Task 4 manual.
- **Type consistency:** `time_12h_to_24h(text: str, period: str) -> str` is defined in Task 1 and called in Task 2 with `(QLineEdit.text(), QComboBox.currentText())`. Resize-mode enum is `QHeaderView.ResizeMode.{ResizeToContents,Stretch}`.
- **No placeholders:** every code step shows full code; commands have expected output.
