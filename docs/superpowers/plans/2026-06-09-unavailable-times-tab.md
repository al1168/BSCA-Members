# Unavailable Times Tab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an "Unavailable Times" member tab (between Availability and Absences) that records one-off date-specific windows when a member is busy/unavailable, with add / edit / delete, backed by the Access `OneOffAvailability` table.

**Architecture:** Write/read helpers go in `db/members.py` (SQL constants, a row mapper, insert/update/delete, plus a new `one_off_availability` key in `get_member_context` and a standalone `get_one_off_availability` reload). The tab UI in `gui/member_tabs.py` mirrors the Availability tab and reuses `TimeRangeEditor`. Inserting the tab at index 4 shifts Absences to 5, so the absence handlers' refresh index is bumped.

**Tech Stack:** Python 3.11, PyQt6, pyodbc/Access, pytest. No new dependencies.

---

## File Map

```
db/members.py                     modify — SQL, mapper, CRUD, context key, reload fn
gui/member_tabs.py                modify — Unavailable Times tab + handlers; index bump
tests/test_one_off_availability.py create — row-mapper unit tests
```

`monthly_schedule` (site-packages) is NOT touched.

---

## Task 1: Data layer in `db/members.py` (TDD on the mapper)

**Files:**
- Create: `tests/test_one_off_availability.py`
- Modify: `db/members.py`

- [ ] **Step 1: Write the failing mapper tests**

Create `tests/test_one_off_availability.py`:

```python
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
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv\Scripts\pytest tests/test_one_off_availability.py -v`
Expected: FAIL with `cannot import name 'map_one_off_availability_row'`.

- [ ] **Step 3: Add SQL constants**

In `db/members.py`, immediately after `DELETE_ABSENCE = "..."` (around line 91),
add:

```python
INSERT_ONE_OFF_AVAILABILITY = (
    "INSERT INTO [OneOffAvailability] ([Center ID], [date], "
    "[avail_start], [avail_end], [Notes]) VALUES (?, ?, ?, ?, ?)"
)

UPDATE_ONE_OFF_AVAILABILITY = (
    "UPDATE [OneOffAvailability] SET [date]=?, [avail_start]=?, "
    "[avail_end]=?, [Notes]=? WHERE [ID]=?"
)

DELETE_ONE_OFF_AVAILABILITY = "DELETE FROM [OneOffAvailability] WHERE [ID]=?"

ONE_OFF_AVAILABILITY_SELECT = (
    "SELECT [ID],[Center ID],[date],[avail_start],[avail_end],[Notes] "
    "FROM [OneOffAvailability] WHERE [Center ID]=?"
)
```

- [ ] **Step 4: Add the converters and row mapper**

In `db/members.py`, immediately after `_hhmm_to_datetime` (ends around line 109),
add:

```python
def _access_date(value):
    """Access Date/Time -> datetime.date (a date passes through; None -> None)."""
    if value is None:
        return None
    return value.date() if isinstance(value, datetime) else value


def _access_hhmm(value):
    """Access time-only DATETIME -> 'HH:mm' (None -> None)."""
    if value is None:
        return None
    return value.strftime("%H:%M") if hasattr(value, "strftime") else value


def map_one_off_availability_row(row) -> dict:
    """Map a OneOffAvailability row: [date] -> date; [avail_start]/[avail_end]
    are time-only DATETIMEs -> 'HH:mm'; [Notes] -> str."""
    return {
        "id": int(row[0]),
        "center_id": int(row[1]),
        "date": _access_date(row[2]),
        "avail_start": _access_hhmm(row[3]),
        "avail_end": _access_hhmm(row[4]),
        "notes": row[5] or "",
    }
```

- [ ] **Step 5: Run to verify the mapper tests pass**

Run: `.venv\Scripts\pytest tests/test_one_off_availability.py -v`
Expected: 3 PASS.

- [ ] **Step 6: Add the write functions**

In `db/members.py`, after `delete_availability` (ends around line 713), add:

```python
def insert_one_off_availability(
    center_id: int,
    on_date: date,
    avail_start: str,
    avail_end: str,
    notes: str,
    db_path: str,
) -> None:
    conn = _connect(db_path)
    try:
        conn.cursor().execute(
            INSERT_ONE_OFF_AVAILABILITY,
            (center_id, on_date, _hhmm_to_datetime(avail_start),
             _hhmm_to_datetime(avail_end), notes),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def update_one_off_availability(
    record_id: int,
    on_date: date,
    avail_start: str,
    avail_end: str,
    notes: str,
    db_path: str,
) -> None:
    conn = _connect(db_path)
    try:
        conn.cursor().execute(
            UPDATE_ONE_OFF_AVAILABILITY,
            (on_date, _hhmm_to_datetime(avail_start),
             _hhmm_to_datetime(avail_end), notes, record_id),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_one_off_availability(record_id: int, db_path: str) -> None:
    conn = _connect(db_path)
    try:
        conn.cursor().execute(DELETE_ONE_OFF_AVAILABILITY, (record_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

- [ ] **Step 7: Add the one-off fetch to `get_member_context`**

In `get_member_context`, immediately after the absences block:

```python
        c.execute(
            "SELECT [ID],[Center ID],[Leave Type],[Start_Date],[End_Date] "
            "FROM [Absences] WHERE [Center ID]=?",
            center_id,
        )
        absences = [map_absence_row(r) for r in c.fetchall()]
```

add:

```python
        c.execute(ONE_OFF_AVAILABILITY_SELECT, center_id)
        one_off_availability = [
            map_one_off_availability_row(r) for r in c.fetchall()
        ]
```

Then add the key to the returned dict (currently ends with `"absences": absences,`):

```python
        return {
            "member": member,
            "enrollments": enrollments,
            "authorizations": authorizations,
            "availability": availability,
            "absences": absences,
            "one_off_availability": one_off_availability,
        }
```

- [ ] **Step 8: Add the standalone reload function**

In `db/members.py`, after `get_authorizations` (around line 410), add (mirrors its
cached-connection + stale-retry pattern):

```python
def get_one_off_availability(center_id: int, db_path: str,
                             _retry: bool = True) -> list[dict]:
    """One-off unavailable windows for a member (cached read connection).
    Mirrors get_member_context's stale-connection retry."""
    import pyodbc
    conn = _read_connection(db_path)
    try:
        c = conn.cursor()
        c.execute(ONE_OFF_AVAILABILITY_SELECT, center_id)
        return [map_one_off_availability_row(r) for r in c.fetchall()]
    except pyodbc.Error:
        _drop_read_connection(db_path)
        if _retry:
            return get_one_off_availability(center_id, db_path, _retry=False)
        raise
```

(Confirm `_read_connection` and `_drop_read_connection` exist — they are used by
`get_member_context`/`get_authorizations`.)

- [ ] **Step 9: Verify import + run the full suite**

Run: `.venv\Scripts\python -c "from db.members import insert_one_off_availability, update_one_off_availability, delete_one_off_availability, get_one_off_availability, map_one_off_availability_row; print('OK')"`
Expected: `OK`

Run: `.venv\Scripts\pytest -q`
Expected: all pass.

- [ ] **Step 10: Commit**

```bash
git add db/members.py tests/test_one_off_availability.py
git commit -m "feat: data layer for OneOffAvailability (CRUD, mapper, context key)"
```
End the commit message with a blank line then:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Task 2: Unavailable Times tab UI in `gui/member_tabs.py`

**Files:**
- Modify: `gui/member_tabs.py`

- [ ] **Step 1: Load the one-off rows in `_load_data`**

The current method:

```python
    def _load_data(self):
        self._member = {}
        self._enrollments = []
        self._authorizations = []
        self._availability = []
        self._absences = []
        try:
            ctx = get_member_context(self._center_id, self._db_path)
            self._member = ctx["member"]
            self._enrollments = ctx["enrollments"]
            self._authorizations = ctx["authorizations"]
            self._availability = ctx["availability"]
            self._absences = ctx["absences"]
        except Exception as exc:
            QMessageBox.critical(self, "Load Error", str(exc))
```

Add the `_one_off` init and assignment:

```python
    def _load_data(self):
        self._member = {}
        self._enrollments = []
        self._authorizations = []
        self._availability = []
        self._absences = []
        self._one_off = []
        try:
            ctx = get_member_context(self._center_id, self._db_path)
            self._member = ctx["member"]
            self._enrollments = ctx["enrollments"]
            self._authorizations = ctx["authorizations"]
            self._availability = ctx["availability"]
            self._absences = ctx["absences"]
            self._one_off = ctx.get("one_off_availability", [])
        except Exception as exc:
            QMessageBox.critical(self, "Load Error", str(exc))
```

- [ ] **Step 2: Build and insert the tab in `_build_ui`**

The current block:

```python
        self._tab_info = self._make_info_tab()
        self._tab_enrollments = self._make_enrollments_tab()
        self._tab_auths = self._make_auths_tab()
        self._tab_avail = self._make_avail_tab()
        self._tab_absences = self._make_absences_tab()

        self._tabs.addTab(self._tab_info, "Info")
        self._tabs.addTab(self._tab_enrollments, "Enrollments")
        self._tabs.addTab(self._tab_auths,
            "Auths ⚠" if warn else "Authorizations")
        self._tabs.addTab(self._tab_avail, "Availability")
        self._tabs.addTab(self._tab_absences, "Absences")
```

Replace with (build `_tab_unavail`, add it between Availability and Absences):

```python
        self._tab_info = self._make_info_tab()
        self._tab_enrollments = self._make_enrollments_tab()
        self._tab_auths = self._make_auths_tab()
        self._tab_avail = self._make_avail_tab()
        self._tab_unavail = self._make_unavailable_tab()
        self._tab_absences = self._make_absences_tab()

        self._tabs.addTab(self._tab_info, "Info")
        self._tabs.addTab(self._tab_enrollments, "Enrollments")
        self._tabs.addTab(self._tab_auths,
            "Auths ⚠" if warn else "Authorizations")
        self._tabs.addTab(self._tab_avail, "Availability")
        self._tabs.addTab(self._tab_unavail, "Unavailable Times")
        self._tabs.addTab(self._tab_absences, "Absences")
```

- [ ] **Step 3: Add the tab + handlers**

In `gui/member_tabs.py`, insert this block immediately after `_delete_avail`
(ends around line 1162) and before the `# ── Absences tab ──` comment:

```python
    # ── Unavailable Times tab (one-off) ──────────────────────────────────────

    def _make_unavailable_tab(self) -> QWidget:
        from PyQt6.QtWidgets import (
            QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView,
        )
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 12, 0, 0)

        caption = QLabel("Times the member is unavailable on a specific date.")
        caption.setObjectName("field_label")
        layout.addWidget(caption)

        columns = ["ID", "Date", "Start", "End", "Notes", "Action"]
        table = QTableWidget(len(self._one_off), len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        hdr = table.horizontalHeader()
        hdr.setStretchLastSection(False)
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(34)

        for r, a in enumerate(self._one_off):
            table.setItem(r, 0, QTableWidgetItem(str(a["id"])))
            table.setItem(r, 1, QTableWidgetItem(str(a["date"]) if a["date"] else ""))
            table.setItem(r, 2, QTableWidgetItem(a["avail_start"] or ""))
            table.setItem(r, 3, QTableWidgetItem(a["avail_end"] or ""))
            table.setItem(r, 4, QTableWidgetItem(a.get("notes", "") or ""))
            btn = QPushButton("Edit")
            btn.setObjectName("btn_edit")
            btn.clicked.connect(lambda _=False, uv=a: self._edit_unavailable(uv))
            table.setCellWidget(r, 5, btn)

        self._unavail_table = table
        layout.addWidget(table)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("+ Add")
        btn_add.clicked.connect(self._add_unavailable)
        btn_del = QPushButton("Delete Selected")
        btn_del.clicked.connect(lambda: self._delete_unavailable(table))
        btn_row.addWidget(btn_add)
        btn_row.addStretch()
        btn_row.addWidget(btn_del)
        layout.addLayout(btn_row)
        return w

    def _open_one_off_dialog(self, existing: dict | None = None):
        """Add/Edit dialog: date + time window + notes. Returns a dict with
        date, avail_start, avail_end, notes — or None if cancelled."""
        from PyQt6.QtWidgets import (
            QDialog, QFormLayout, QDateEdit, QPlainTextEdit, QDialogButtonBox,
        )
        from PyQt6.QtCore import QDate
        from gui.time_range_editor import TimeRangeEditor

        dlg = QDialog(self)
        dlg.setWindowTitle("Edit Unavailable Time" if existing
                           else "Add Unavailable Time")
        form = QFormLayout(dlg)

        date_edit = QDateEdit()
        date_edit.setCalendarPopup(True)
        editor = TimeRangeEditor()
        notes_edit = QPlainTextEdit()
        notes_edit.setFixedHeight(60)

        if existing:
            d = existing.get("date")
            date_edit.setDate(QDate(d.year, d.month, d.day) if d
                              else QDate.currentDate())
            editor.set_window(existing.get("avail_start") or "09:00",
                              existing.get("avail_end") or "12:00")
            notes_edit.setPlainText(existing.get("notes", "") or "")
        else:
            date_edit.setDate(QDate.currentDate())
            editor.set_window("09:00", "12:00")

        form.addRow("Date:", date_edit)
        form.addRow("Time:", editor)
        form.addRow("Notes:", notes_edit)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)

        if not dlg.exec():
            return None
        return {
            "date": date_edit.date().toPyDate(),
            "avail_start": editor.start_hhmm(),
            "avail_end": editor.end_hhmm(),
            "notes": notes_edit.toPlainText().strip(),
        }

    def _add_unavailable(self):
        from db.members import (
            insert_one_off_availability, get_one_off_availability,
        )
        result = self._open_one_off_dialog()
        if not result:
            return
        try:
            insert_one_off_availability(
                self._center_id, result["date"], result["avail_start"],
                result["avail_end"], result["notes"], self._db_path,
            )
            self._one_off = get_one_off_availability(self._center_id, self._db_path)
            self._refresh_tab(4, self._make_unavailable_tab())
            self._log_event(
                "AVAIL",
                f"One-off unavailable added: {result['date']} "
                f"{result['avail_start']}–{result['avail_end']}")
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _edit_unavailable(self, entry: dict):
        from db.members import (
            update_one_off_availability, get_one_off_availability,
        )
        result = self._open_one_off_dialog(existing=entry)
        if not result:
            return
        try:
            update_one_off_availability(
                entry["id"], result["date"], result["avail_start"],
                result["avail_end"], result["notes"], self._db_path,
            )
            self._one_off = get_one_off_availability(self._center_id, self._db_path)
            self._refresh_tab(4, self._make_unavailable_tab())
            self._log_event(
                "AVAIL",
                f"One-off unavailable edited: {result['date']} "
                f"{result['avail_start']}–{result['avail_end']}")
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _delete_unavailable(self, table):
        row = table.currentRow()
        if row < 0:
            return
        record_id = int(table.item(row, 0).text())
        if QMessageBox.question(self, "Confirm", "Delete this unavailable time?") \
                == QMessageBox.StandardButton.Yes:
            from db.members import (
                delete_one_off_availability, get_one_off_availability,
            )
            entry = next((a for a in self._one_off if a["id"] == record_id), None)
            try:
                delete_one_off_availability(record_id, self._db_path)
                self._one_off = get_one_off_availability(
                    self._center_id, self._db_path)
                self._refresh_tab(4, self._make_unavailable_tab())
                if entry:
                    self._log_event(
                        "AVAIL",
                        f"One-off unavailable deleted: {entry['date']} "
                        f"{entry['avail_start']}–{entry['avail_end']}")
            except Exception as exc:
                QMessageBox.critical(self, "Error", str(exc))
```

- [ ] **Step 4: Bump the Absences refresh index from 4 to 5**

Absences moved from tab index 4 to 5. In `_add_absence`, change:

```python
                self._refresh_tab(4, self._make_absences_tab())
```
to:
```python
                self._refresh_tab(5, self._make_absences_tab())
```

And in `_delete_absence`, change the same `self._refresh_tab(4, self._make_absences_tab())`
to `self._refresh_tab(5, self._make_absences_tab())`.

(Availability handlers stay at index 3; the new Unavailable Times handlers use 4.)

- [ ] **Step 5: Verify import + grep the indices**

Run: `.venv\Scripts\python -c "from gui.member_tabs import MemberTabsWidget; print('OK')"`
Expected: `OK`

Grep `gui/member_tabs.py` for `_make_absences_tab())` — both occurrences should now
be `_refresh_tab(5, ...)`. Grep for `_make_unavailable_tab())` — the three handler
refreshes should be `_refresh_tab(4, ...)`.

- [ ] **Step 6: Run the full suite**

Run: `.venv\Scripts\pytest -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add gui/member_tabs.py
git commit -m "feat: add Unavailable Times tab with add/edit/delete"
```
End with a blank line then:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Task 3: Full suite + exe rebuild + manual smoke test

**Files:** none changed

- [ ] **Step 1: Run the full test suite**

Run: `.venv\Scripts\pytest -q`
Expected: all pass.

- [ ] **Step 2: Rebuild the exe**

Stop any running instance, then build:

```
powershell -Command "try { Stop-Process -Name MemberManager -Force -ErrorAction Stop } catch {}"
.venv\Scripts\pyinstaller MemberManager.spec
```

Expected: `Build complete! ... dist`

- [ ] **Step 3: Manual smoke test** (requires the real Access DB configured in Settings)

Launch `dist\MemberManager.exe`, open a member:
- An **Unavailable Times** tab sits between Availability and Absences, with the
  caption and an empty table (for a member with no rows).
- **+ Add** → pick a date, set a 9:00 AM–12:00 PM window, type a note, OK → the row
  appears (Date · Start · End · Notes) and persists after reopening the member.
- **Edit** (per-row button) → change the date/time/note → the row updates.
- **Delete Selected** → confirm → the row is removed.
- The **Absences** tab still adds/deletes correctly (index bump verified), and the
  **Events** tab shows the "One-off unavailable added/edited/deleted" entries.

---

## Self-Review Notes

- **Spec coverage:** SQL + mapper + CRUD + `one_off_availability` context key +
  `get_one_off_availability` → Task 1. Tab between Availability and Absences,
  add/edit/delete, caption, `TimeRangeEditor`, AVAIL audit logging, Absences index
  bump → Task 2. Suite/exe/manual → Task 3.
- **Type consistency:** `insert_one_off_availability(center_id, on_date,
  avail_start, avail_end, notes, db_path)` and `update_one_off_availability(
  record_id, on_date, avail_start, avail_end, notes, db_path)` match their call
  sites; `get_one_off_availability(center_id, db_path)` matches; the dialog returns
  `{date, avail_start, avail_end, notes}`; the mapper returns `{id, center_id,
  date, avail_start, avail_end, notes}`; `self._one_off` is the loaded list.
  New tab index 4 (handlers refresh 4), Absences index 5 (handlers refresh 5),
  Availability stays 3.
- **No placeholders:** every step shows full code and exact commands/expected
  output. DB CRUD is verified manually (the integration harness auto-skips without
  the Access fixture); the row mapper is unit-tested.
