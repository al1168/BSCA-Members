# Working Events Log Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Events log record every add/edit/delete of member data, refresh the member's Events tab live, show a clear empty state when unconfigured, and let the user return from All Events to the member they were viewing.

**Architecture:** A single `MemberTabsWidget._log_event(type, description)` helper writes to the local SQLite events DB (when a path is set) and refreshes the member's Events tab; all member-tab mutations route through it. Delete handlers gain logging. `EventsTableWidget` shows an empty-state message. `MainWindow` remembers the last member and the global view gets a "← Back" button.

**Tech Stack:** Python 3.11, PyQt6, SQLite (`db/events.py`), pytest. No new dependencies.

---

## File Map

```
gui/events_view.py     modify — empty-state message; GlobalEventsWidget on_back + "← Back"
gui/member_tabs.py     modify — _log_event helper; route all event writes through it
                                (uncapped EDIT); log the four delete handlers
gui/main_window.py     modify — remember last member; _back_from_events; pass on_back
tests/test_db_events.py     modify — delete-style description round-trip
```

No `db/events.py` code change (its text storage already supports any description).

---

## Task 1: Events layer — delete-description coverage

**Files:**
- Test: `tests/test_db_events.py`

- [ ] **Step 1: Add the test**

Append to `tests/test_db_events.py`:

```python
def test_delete_style_description_round_trips(tmp_path):
    from db.events import open_db, insert_event, query_events
    conn = open_db(str(tmp_path / "ev.db"))
    insert_event(conn, "AUTH", 25049, "Lee, Mary",
                 "Authorization deleted: 2025-01-01 – 2025-12-31 [Mon Wed Fri] · HF")
    rows = query_events(conn, center_id=25049)
    conn.close()
    assert len(rows) == 1
    assert rows[0]["event_type"] == "AUTH"
    assert "Authorization deleted" in rows[0]["description"]
    assert "[Mon Wed Fri]" in rows[0]["description"]
```

- [ ] **Step 2: Run it**

Run: `.venv\Scripts\pytest tests/test_db_events.py::test_delete_style_description_round_trips -v`
Expected: PASS (the events layer stores arbitrary text; this guards the
delete-event shape used by Task 4).

- [ ] **Step 3: Commit**

```bash
git add tests/test_db_events.py
git commit -m "test: cover delete-style event descriptions round-tripping"
```
End the commit message with the trailer:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Task 2: Empty-state message in EventsTableWidget

**Files:**
- Modify: `gui/events_view.py`

- [ ] **Step 1: Show a message when no events path is set**

In `gui/events_view.py`, replace the start of `_load`:

```python
    def _load(self):
        if not self._events_path:
            return
        from db.events import open_db, query_events, purge_old_events
```

with:

```python
    def _load(self):
        if not self._events_path:
            self._table.clearSpans()
            self._table.setRowCount(1)
            self._table.setSpan(0, 0, 1, 4)
            msg = QTableWidgetItem(
                "No events log configured. Set an Events log path in "
                "Settings to start recording changes."
            )
            msg.setForeground(QColor("#888"))
            self._table.setItem(0, 0, msg)
            return
        from db.events import open_db, query_events, purge_old_events
```

Then, in the same method, right after the existing `self._table.setRowCount(len(rows))` line, add a `clearSpans()` so a prior empty-state span never lingers:

```python
        self._table.setRowCount(len(rows))
        self._table.clearSpans()
```

(`QTableWidgetItem` and `QColor` are already imported at the top of the file.)

- [ ] **Step 2: Verify the import + a no-path widget builds**

Run:
```
set QT_QPA_PLATFORM=offscreen && .venv\Scripts\python -c "from PyQt6.QtWidgets import QApplication; from gui.events_view import EventsTableWidget; a=QApplication([]); w=EventsTableWidget('', center_id=None); print(w._table.item(0,0).text()[:20])"
```
Expected: prints `No events log config`

- [ ] **Step 3: Run the full suite**

Run: `.venv\Scripts\pytest -q`
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add gui/events_view.py
git commit -m "feat: events table shows a prompt when no log path is configured"
```
End with:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Task 3: `_log_event` helper + route all writes through it

**Files:**
- Modify: `gui/member_tabs.py`

- [ ] **Step 1: Add the `_log_event` helper**

Add this method to `MemberTabsWidget` immediately after `_load_data` (before
`_make_photo_label`):

```python
    def _log_event(self, event_type: str, description: str) -> None:
        """Record an event for this member (when an events log is configured)
        and refresh the member's Events tab."""
        if self._events_path:
            from db.events import open_db, insert_event
            m = self._member
            conn = open_db(self._events_path)
            try:
                insert_event(
                    conn, event_type, self._center_id,
                    f"{m.get('last_name', '')}, {m.get('first_name', '')}",
                    description,
                )
            finally:
                conn.close()
        if hasattr(self, "_tab_events"):
            self._tab_events.refresh()
```

- [ ] **Step 2: `_save_info` — uncapped EDIT via the helper**

In `_save_info`, replace:

```python
            if self._events_path:
                conn = open_db(self._events_path)
                try:
                    insert_event(
                        conn, "EDIT", self._center_id,
                        f"{fields['last_name']}, {fields['first_name']}",
                        "; ".join(summary[:5]),
                    )
                finally:
                    conn.close()
```

with:

```python
            self._log_event("EDIT", "; ".join(summary))
```

Then delete the now-unused `from db.events import open_db, insert_event` line near
the top of `_save_info`.

- [ ] **Step 3: `_add_enrollment` — via the helper**

In `_add_enrollment`, replace:

```python
                if self._events_path:
                    conn = open_db(self._events_path)
                    try:
                        m = self._member
                        insert_event(conn, "ENROLL", self._center_id,
                            f"{m.get('last_name')}, {m.get('first_name')}",
                            f"Enrollment added: {s} – {e or 'ongoing'}")
                    finally:
                        conn.close()
```

with:

```python
                self._log_event("ENROLL", f"Enrollment added: {s} – {e or 'ongoing'}")
```

Delete the now-unused `from db.events import open_db, insert_event` line near the
top of `_add_enrollment`.

- [ ] **Step 4: `_terminate_enrollment` — via the helper**

Replace:

```python
            if self._events_path:
                conn = open_db(self._events_path)
                try:
                    m = self._member
                    insert_event(conn, "ENROLL", self._center_id,
                        f"{m.get('last_name')}, {m.get('first_name')}",
                        f"Enrollment terminated: end set to {today.isoformat()}")
                finally:
                    conn.close()
```

with:

```python
            self._log_event("ENROLL",
                            f"Enrollment terminated: end set to {today.isoformat()}")
```

Delete the now-unused `from db.events import open_db, insert_event` line near the
top of `_terminate_enrollment`.

- [ ] **Step 5: `_after_auth_change` — via the helper**

Replace:

```python
        from db.members import get_authorizations, sync_health_plan_from_latest_auth
        from db.events import open_db, insert_event

        synced = sync_health_plan_from_latest_auth(self._center_id, self._db_path)
        if synced:
            self._member["health_plan"] = synced
            if hasattr(self, "_info_plan"):
                self._info_plan.setText(synced)
        self._authorizations = get_authorizations(self._center_id, self._db_path)
        self._refresh_tab(2, self._make_auths_tab())
        if description and self._events_path:
            m = self._member
            conn = open_db(self._events_path)
            try:
                insert_event(conn, "AUTH", self._center_id,
                    f"{m.get('last_name')}, {m.get('first_name')}", description)
            finally:
                conn.close()
```

with:

```python
        from db.members import get_authorizations, sync_health_plan_from_latest_auth

        synced = sync_health_plan_from_latest_auth(self._center_id, self._db_path)
        if synced:
            self._member["health_plan"] = synced
            if hasattr(self, "_info_plan"):
                self._info_plan.setText(synced)
        self._authorizations = get_authorizations(self._center_id, self._db_path)
        self._refresh_tab(2, self._make_auths_tab())
        if description:
            self._log_event("AUTH", description)
```

- [ ] **Step 6: `_add_avail` — via the helper**

Replace:

```python
                if self._events_path:
                    conn = open_db(self._events_path)
                    try:
                        m = self._member
                        insert_event(conn, "AVAIL", self._center_id,
                            f"{m.get('last_name')}, {m.get('first_name')}",
                            f"Availability added: {day_name} {ts}–{te}")
                    finally:
                        conn.close()
```

with:

```python
                self._log_event("AVAIL", f"Availability added: {day_name} {ts}–{te}")
```

Delete the now-unused `from db.events import open_db, insert_event` line near the
top of `_add_avail`.

- [ ] **Step 7: `_edit_avail` — via the helper**

Replace:

```python
            if self._events_path:
                conn = open_db(self._events_path)
                try:
                    m = self._member
                    insert_event(conn, "AVAIL", self._center_id,
                        f"{m.get('last_name')}, {m.get('first_name')}",
                        f"Availability edited: {day_name} {ts}–{te}")
                finally:
                    conn.close()
```

with:

```python
            self._log_event("AVAIL", f"Availability edited: {day_name} {ts}–{te}")
```

Delete the now-unused `from db.events import open_db, insert_event` line near the
top of `_edit_avail`.

- [ ] **Step 8: `_add_absence` — via the helper**

Replace:

```python
                if self._events_path:
                    conn = open_db(self._events_path)
                    try:
                        m = self._member
                        insert_event(conn, "ABS", self._center_id,
                            f"{m.get('last_name')}, {m.get('first_name')}",
                            f"Absence added: {lt} · {s} – {e}")
                    finally:
                        conn.close()
```

with:

```python
                self._log_event("ABS", f"Absence added: {lt} · {s} – {e}")
```

Delete the now-unused `from db.events import open_db, insert_event` line near the
top of `_add_absence`.

- [ ] **Step 9: Verify import + grep for leftover inline event writes**

Run: `.venv\Scripts\python -c "from gui.member_tabs import MemberTabsWidget; print('OK')"`
Expected: `OK`

Grep `gui/member_tabs.py` for `insert_event(` — it should appear only inside
`_log_event`. Grep for `from db.events import` — only inside `_log_event`.

- [ ] **Step 10: Run the full suite**

Run: `.venv\Scripts\pytest -q`
Expected: all pass.

- [ ] **Step 11: Commit**

```bash
git add gui/member_tabs.py
git commit -m "feat: route member events through _log_event (live refresh, uncapped edit)"
```
End with:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Task 4: Log deletions

**Files:**
- Modify: `gui/member_tabs.py`

- [ ] **Step 1: `_delete_enrollment` — log the removed row**

Replace the whole method:

```python
    def _delete_enrollment(self, table):
        row = table.currentRow()
        if row < 0:
            return
        record_id = int(table.item(row, 0).text())
        if QMessageBox.question(self, "Confirm", "Delete this enrollment record?") \
                == QMessageBox.StandardButton.Yes:
            from db.members import delete_enrollment
            from monthly_schedule.db import get_enrollments
            entry = next((e for e in self._enrollments if e["id"] == record_id), None)
            try:
                delete_enrollment(record_id, self._db_path)
                self._enrollments = get_enrollments(self._center_id, self._db_path)
                self._refresh_tab(1, self._make_enrollments_tab())
                if entry:
                    self._log_event(
                        "ENROLL",
                        f"Enrollment deleted: {entry['start_date']} – "
                        f"{entry['end_date'] or 'ongoing'}")
            except Exception as exc:
                QMessageBox.critical(self, "Error", str(exc))
```

- [ ] **Step 2: `_delete_auth` — log the removed row**

Replace the whole method:

```python
    def _delete_auth(self, table):
        row = table.currentRow()
        if row < 0:
            return
        record_id = int(table.item(row, 0).text())
        if QMessageBox.question(self, "Confirm", "Delete this authorization?") \
                == QMessageBox.StandardButton.Yes:
            from db.members import delete_authorization
            entry = next((a for a in self._authorizations if a["id"] == record_id), None)
            try:
                delete_authorization(record_id, self._db_path)
                self._after_auth_change(None)
                if entry:
                    self._log_event(
                        "AUTH",
                        f"Authorization deleted: {entry['auth_start']} – "
                        f"{entry['auth_end']} "
                        f"[{format_auth_days(entry.get('auth_days', '') or '')}] · "
                        f"{entry.get('health_plan', '')}")
            except Exception as exc:
                QMessageBox.critical(self, "Error", str(exc))
```

- [ ] **Step 3: `_delete_avail` — log the removed row**

Replace the whole method:

```python
    def _delete_avail(self, table):
        row = table.currentRow()
        if row < 0:
            return
        record_id = int(table.item(row, 0).text())
        if QMessageBox.question(self, "Confirm", "Delete this availability row?") \
                == QMessageBox.StandardButton.Yes:
            from db.members import delete_availability
            from monthly_schedule.db import get_availability
            entry = next((a for a in self._availability if a["id"] == record_id), None)
            try:
                delete_availability(record_id, self._db_path)
                self._availability = get_availability(self._center_id, self._db_path)
                self._refresh_tab(3, self._make_avail_tab())
                if entry:
                    day = WEEKDAY_NAMES.get(entry["day_of_week"],
                                            str(entry["day_of_week"]))
                    self._log_event(
                        "AVAIL",
                        f"Availability deleted: {day} "
                        f"{entry['avail_start']}–{entry['avail_end']}")
            except Exception as exc:
                QMessageBox.critical(self, "Error", str(exc))
```

- [ ] **Step 4: `_delete_absence` — log the removed row**

Replace the whole method (its current body ends by refreshing tab 4):

```python
    def _delete_absence(self, table):
        row = table.currentRow()
        if row < 0:
            return
        record_id = int(table.item(row, 0).text())
        if QMessageBox.question(self, "Confirm", "Delete this absence?") \
                == QMessageBox.StandardButton.Yes:
            from db.members import delete_absence
            from monthly_schedule.db import get_absences
            entry = next((a for a in self._absences if a["id"] == record_id), None)
            try:
                delete_absence(record_id, self._db_path)
                self._absences = get_absences(self._center_id, self._db_path)
                self._refresh_tab(4, self._make_absences_tab())
                if entry:
                    self._log_event(
                        "ABS",
                        f"Absence deleted: {entry['leave_type']} "
                        f"{entry['start_date']} – {entry['end_date']}")
            except Exception as exc:
                QMessageBox.critical(self, "Error", str(exc))
```

- [ ] **Step 5: Verify import**

Run: `.venv\Scripts\python -c "from gui.member_tabs import MemberTabsWidget; print('OK')"`
Expected: `OK`

- [ ] **Step 6: Run the full suite**

Run: `.venv\Scripts\pytest -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add gui/member_tabs.py
git commit -m "feat: record deletions of enrollments, auths, availability, absences"
```
End with:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Task 5: Return from All Events

**Files:**
- Modify: `gui/main_window.py`, `gui/events_view.py`

- [ ] **Step 1: Track the last-viewed member in `MainWindow.__init__`**

Find:

```python
        self._settings = settings
        self._settings_path = settings_path
```

Replace with:

```python
        self._settings = settings
        self._settings_path = settings_path
        self._last_center_id = None
```

- [ ] **Step 2: Record it in `_show_member`**

In `_show_member`, after `db_path = self._settings.get("db_path", "")` (anywhere
before `self._set_detail(widget)`), set the last member. Replace:

```python
    def _show_member(self, center_id: int):
        from gui.member_tabs import MemberTabsWidget
        db_path = self._settings.get("db_path", "")
        events_path = self._settings.get("events_db_path", "")
        api_key = self._settings.get("google_api_key", "")
        widget = MemberTabsWidget(center_id, db_path, events_path, api_key)
        self._set_detail(widget)
```

with:

```python
    def _show_member(self, center_id: int):
        from gui.member_tabs import MemberTabsWidget
        self._last_center_id = center_id
        db_path = self._settings.get("db_path", "")
        events_path = self._settings.get("events_db_path", "")
        api_key = self._settings.get("google_api_key", "")
        widget = MemberTabsWidget(center_id, db_path, events_path, api_key)
        self._set_detail(widget)
```

- [ ] **Step 3: Pass a back callback + add `_back_from_events`**

Replace `_show_global_events`:

```python
    def _show_global_events(self):
        from gui.events_view import GlobalEventsWidget
        events_path = self._settings.get("events_db_path", "")
        widget = GlobalEventsWidget(events_path)
        self._set_detail(widget)
```

with:

```python
    def _show_global_events(self):
        from gui.events_view import GlobalEventsWidget
        events_path = self._settings.get("events_db_path", "")
        widget = GlobalEventsWidget(events_path, on_back=self._back_from_events)
        self._set_detail(widget)

    def _back_from_events(self):
        if self._last_center_id is not None:
            self._show_member(self._last_center_id)
        else:
            while self._detail_stack.count() > 1:
                w = self._detail_stack.widget(1)
                self._detail_stack.removeWidget(w)
                w.deleteLater()
            self._detail_stack.setCurrentIndex(0)
```

- [ ] **Step 4: Add the "← Back" button to `GlobalEventsWidget`**

In `gui/events_view.py`, replace `GlobalEventsWidget`:

```python
class GlobalEventsWidget(QWidget):
    def __init__(self, events_path: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 12)
        layout.addWidget(EventsTableWidget(events_path, center_id=None))
```

with:

```python
class GlobalEventsWidget(QWidget):
    def __init__(self, events_path: str, on_back=None, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 12)
        if on_back is not None:
            from PyQt6.QtWidgets import QPushButton
            back_row = QHBoxLayout()
            btn_back = QPushButton("← Back")
            btn_back.clicked.connect(on_back)
            back_row.addWidget(btn_back)
            back_row.addStretch()
            layout.addLayout(back_row)
        layout.addWidget(EventsTableWidget(events_path, center_id=None))
```

(`QHBoxLayout` is already imported at the top of `events_view.py`.)

- [ ] **Step 5: Verify imports**

Run: `.venv\Scripts\python -c "from gui.main_window import MainWindow; from gui.events_view import GlobalEventsWidget; print('OK')"`
Expected: `OK`

- [ ] **Step 6: Run the full suite**

Run: `.venv\Scripts\pytest -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add gui/main_window.py gui/events_view.py
git commit -m "feat: '← Back' from All Events returns to the last member profile"
```
End with:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Task 6: Full suite + exe rebuild + manual smoke test

**Files:** none changed

- [ ] **Step 1: Run the full test suite**

Run: `.venv\Scripts\pytest -q`
Expected: all pass (prior 91 + the new events test).

- [ ] **Step 2: Rebuild the exe**

Stop any running instance (it locks the output file), then build:

```
powershell -Command "try { Stop-Process -Name MemberManager -Force -ErrorAction Stop } catch {}"
.venv\Scripts\pyinstaller MemberManager.spec
```

Expected: `Build complete! The results are available in: ...\dist`

- [ ] **Step 3: Manual smoke test**

Launch `dist\MemberManager.exe`:
- With **no** Events log path set (Settings): the member **Events** tab and
  **All Events** both show "No events log configured. Set an Events log path in
  Settings…". Add/edit/delete still work.
- Set an **Events log path** in Settings (e.g. a local `events.db`). Then on a
  member: edit several fields → Save → the **Events** tab immediately shows one
  `EDIT` row listing every changed field; it also appears in **All Events**.
- Add then delete an enrollment, an authorization, an availability row, and an
  absence → each **add and each delete** appears (correct badge + description) in
  both the member tab and All Events, updating live.
- Open a member → click **All Events** → click **← Back** → returns to that
  member's profile. From the empty placeholder (no member opened) → All Events →
  ← Back → returns to the placeholder.

---

## Self-Review Notes

- **Spec coverage:** Empty state → Task 2. `_log_event` + live refresh → Task 3.
  Member edit logs every field (drop `[:5]`) → Task 3 Step 2. Delete logging for
  the four entity types → Task 4. "← Back" from All Events → Task 5. Retention
  unchanged (30-day purge in `purge_old_events`, untouched). Manual-only path
  unchanged (no auto-default). Testing → Task 1 + Task 6.
- **Type consistency:** `_log_event(event_type, description)`, `GlobalEventsWidget(
  events_path, on_back=None, parent=None)`, `MainWindow._back_from_events`,
  `self._last_center_id`. Delete descriptions reuse the existing entity badges
  (ENROLL/AUTH/AVAIL/ABS). `WEEKDAY_NAMES` and `format_auth_days` already exist at
  module level in `gui/member_tabs.py`. Entity dict keys used: enrollment
  `start_date`/`end_date`/`id`; auth `auth_start`/`auth_end`/`auth_days`/
  `health_plan`/`id`; availability `day_of_week`/`avail_start`/`avail_end`/`id`;
  absence `leave_type`/`start_date`/`end_date`/`id`.
- **No placeholders:** every code step shows full code; commands list expected
  output. The `db/events.py` layer is unchanged (its storage already supports the
  new descriptions, guarded by Task 1).
