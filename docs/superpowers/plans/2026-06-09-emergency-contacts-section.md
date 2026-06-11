# Emergency Contacts Section Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an "Emergency" section at the bottom of the Info tab holding a member's emergency contacts (Full Name · Phone · Relationship) with add/edit/delete, backed by the Access `EmergencyContact` table; remove the old single free-text Emergency field from the form.

**Architecture:** `db/members.py` gains EmergencyContact CRUD + mapper + a `get_member_context` key + a reload (mirrors OneOffAvailability). `gui/member_tabs.py` embeds a self-refreshing CRUD table inside the Info grid and removes the old Emergency cell. The test `conftest.py` creates the table in the integration DB.

**Tech Stack:** Python 3.11, PyQt6, pyodbc/Access, pytest. No new dependencies.

---

## File Map

```
db/members.py             modify — SQL, mapper, CRUD, context key, reload
gui/member_tabs.py        modify — Emergency section + handlers; remove old field
tests/conftest.py         modify — create EmergencyContact in the integration DB
tests/test_emergency.py   create — row-mapper unit tests
```

---

## Task 1: Data layer + conftest (TDD on the mapper)

**Files:**
- Create: `tests/test_emergency.py`
- Modify: `db/members.py`, `tests/conftest.py`

- [ ] **Step 1: Write the failing mapper tests**

Create `tests/test_emergency.py`:

```python
def test_map_emergency_contact_row():
    from db.members import map_emergency_contact_row
    row = (3, 25049, "Jane Doe", "917-555-0100", "Daughter")
    assert map_emergency_contact_row(row) == {
        "id": 3, "center_id": 25049, "full_name": "Jane Doe",
        "phone": "917-555-0100", "relationship": "Daughter",
    }


def test_map_emergency_contact_row_nulls():
    from db.members import map_emergency_contact_row
    d = map_emergency_contact_row((4, 25049, None, None, None))
    assert d["full_name"] == ""
    assert d["phone"] == ""
    assert d["relationship"] == ""
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv\Scripts\pytest tests/test_emergency.py -v`
Expected: FAIL (`cannot import name 'map_emergency_contact_row'`).

- [ ] **Step 3: Add SQL constants**

In `db/members.py`, after the `ONE_OFF_AVAILABILITY_SELECT` constant (around line
105-108), add:

```python
INSERT_EMERGENCY_CONTACT = (
    "INSERT INTO [EmergencyContact] ([Center ID], [Full Name], "
    "[Phone Number], [Relationship]) VALUES (?, ?, ?, ?)"
)

UPDATE_EMERGENCY_CONTACT = (
    "UPDATE [EmergencyContact] SET [Full Name]=?, [Phone Number]=?, "
    "[Relationship]=? WHERE [ID]=?"
)

DELETE_EMERGENCY_CONTACT = "DELETE FROM [EmergencyContact] WHERE [ID]=?"

EMERGENCY_CONTACT_SELECT = (
    "SELECT [ID],[Center ID],[Full Name],[Phone Number],[Relationship] "
    "FROM [EmergencyContact] WHERE [Center ID]=?"
)
```

- [ ] **Step 4: Add the row mapper**

In `db/members.py`, after `map_one_off_availability_row` (around line 143-155), add:

```python
def map_emergency_contact_row(row) -> dict:
    """Map an EmergencyContact row. Null text fields become ''."""
    return {
        "id": int(row[0]),
        "center_id": int(row[1]),
        "full_name": row[2] or "",
        "phone": row[3] or "",
        "relationship": row[4] or "",
    }
```

- [ ] **Step 5: Run the mapper tests**

Run: `.venv\Scripts\pytest tests/test_emergency.py -v`
Expected: 2 PASS.

- [ ] **Step 6: Add the write functions**

In `db/members.py`, after `delete_one_off_availability` (around line 895-905), add:

```python
def insert_emergency_contact(center_id: int, full_name: str, phone: str,
                             relationship: str, db_path: str) -> None:
    conn = _connect(db_path)
    try:
        conn.cursor().execute(
            INSERT_EMERGENCY_CONTACT,
            (center_id, full_name, phone, relationship),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def update_emergency_contact(record_id: int, full_name: str, phone: str,
                             relationship: str, db_path: str) -> None:
    conn = _connect(db_path)
    try:
        conn.cursor().execute(
            UPDATE_EMERGENCY_CONTACT,
            (full_name, phone, relationship, record_id),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_emergency_contact(record_id: int, db_path: str) -> None:
    conn = _connect(db_path)
    try:
        conn.cursor().execute(DELETE_EMERGENCY_CONTACT, (record_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

- [ ] **Step 7: Add the fetch to `get_member_context`**

In `get_member_context`, the current one-off block + return (around lines 438-450)
is:

```python
        c.execute(ONE_OFF_AVAILABILITY_SELECT, center_id)
        one_off_availability = [
            map_one_off_availability_row(r) for r in c.fetchall()
        ]

        return {
            "member": member,
            "enrollments": enrollments,
            "authorizations": authorizations,
            "availability": availability,
            "absences": absences,
            "one_off_availability": one_off_availability,
        }
```

Replace with (add the EmergencyContact fetch + key):

```python
        c.execute(ONE_OFF_AVAILABILITY_SELECT, center_id)
        one_off_availability = [
            map_one_off_availability_row(r) for r in c.fetchall()
        ]

        c.execute(EMERGENCY_CONTACT_SELECT, center_id)
        emergency_contacts = [
            map_emergency_contact_row(r) for r in c.fetchall()
        ]

        return {
            "member": member,
            "enrollments": enrollments,
            "authorizations": authorizations,
            "availability": availability,
            "absences": absences,
            "one_off_availability": one_off_availability,
            "emergency_contacts": emergency_contacts,
        }
```

- [ ] **Step 8: Add the standalone reload**

In `db/members.py`, after `get_one_off_availability` (around line 485-500), add:

```python
def get_emergency_contacts(center_id: int, db_path: str,
                           _retry: bool = True) -> list[dict]:
    """Emergency contacts for a member (cached read connection). Mirrors
    get_member_context's stale-connection retry."""
    import pyodbc
    conn = _read_connection(db_path)
    try:
        c = conn.cursor()
        c.execute(EMERGENCY_CONTACT_SELECT, center_id)
        return [map_emergency_contact_row(r) for r in c.fetchall()]
    except pyodbc.Error:
        _drop_read_connection(db_path)
        if _retry:
            return get_emergency_contacts(center_id, db_path, _retry=False)
        raise
```

- [ ] **Step 9: Create the table in the integration test DB (`tests/conftest.py`)**

The current `conftest.py` creates only `OneOffAvailability`. Generalize it to create
both tables. Replace the whole file body from `_CREATE_ONE_OFF = ...` through the end
of the fixture with:

```python
_CREATE_SQL = {
    "OneOffAvailability": """
        CREATE TABLE [OneOffAvailability] (
            [ID] AUTOINCREMENT PRIMARY KEY,
            [Center ID] LONG,
            [date] DATETIME,
            [avail_start] DATETIME,
            [avail_end] DATETIME,
            [Notes] MEMO
        )
    """,
    "EmergencyContact": """
        CREATE TABLE [EmergencyContact] (
            [ID] AUTOINCREMENT PRIMARY KEY,
            [Center ID] LONG,
            [Full Name] TEXT(255),
            [Phone Number] TEXT(255),
            [Relationship] TEXT(255)
        )
    """,
}


@pytest.fixture(scope="session", autouse=True)
def ensure_optional_tables():
    """Create tables that newer code queries but older test DBs may lack; drop the
    ones we created at session end. No-op when the test DB is absent (integration
    tests skip themselves in that case)."""
    if not os.path.exists(_TEST_DB):
        yield
        return

    import pyodbc
    from monthly_schedule.db import build_connection_string

    conn = pyodbc.connect(build_connection_string(_TEST_DB), autocommit=True)
    c = conn.cursor()
    existing = {row.table_name for row in c.tables(tableType="TABLE")}
    created = []
    for name, sql in _CREATE_SQL.items():
        if name not in existing:
            c.execute(sql)
            created.append(name)
    conn.close()

    yield

    if created:
        conn2 = pyodbc.connect(build_connection_string(_TEST_DB), autocommit=True)
        try:
            for name in created:
                try:
                    conn2.cursor().execute(f"DROP TABLE [{name}]")
                except Exception:
                    pass
        finally:
            conn2.close()
```

(Keep the file's existing imports and the `_TEST_DB` definition at the top.)

- [ ] **Step 10: Verify import + full suite**

Run: `.venv\Scripts\python -c "from db.members import insert_emergency_contact, update_emergency_contact, delete_emergency_contact, get_emergency_contacts, map_emergency_contact_row; print('OK')"`
Expected: `OK`

Run: `.venv\Scripts\pytest -q`
Expected: all pass.

- [ ] **Step 11: Commit**

```bash
git add db/members.py tests/test_emergency.py tests/conftest.py
git commit -m "feat: data layer for EmergencyContact (CRUD, mapper, context key)"
```
End the commit message with a blank line then:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Task 2: Emergency section in the Info tab (`gui/member_tabs.py`)

**Files:**
- Modify: `gui/member_tabs.py`

- [ ] **Step 1: Load emergency contacts in `_load_data`**

The current `_load_data` has (around lines 200-213):

```python
        self._one_off = []
        try:
            ctx = get_member_context(self._center_id, self._db_path)
            self._member = ctx["member"]
            self._enrollments = ctx["enrollments"]
            self._authorizations = ctx["authorizations"]
            self._availability = ctx["availability"]
            self._absences = ctx["absences"]
            self._one_off = ctx.get("one_off_availability", [])
```

Add the emergency list (init + assignment):

```python
        self._one_off = []
        self._emergency_contacts = []
        try:
            ctx = get_member_context(self._center_id, self._db_path)
            self._member = ctx["member"]
            self._enrollments = ctx["enrollments"]
            self._authorizations = ctx["authorizations"]
            self._availability = ctx["availability"]
            self._absences = ctx["absences"]
            self._one_off = ctx.get("one_off_availability", [])
            self._emergency_contacts = ctx.get("emergency_contacts", [])
```

- [ ] **Step 2: Remove the old Emergency field from the Contact section**

In `_make_info_tab`, the Contact block is:

```python
        cell(0, "Home Phone", self._info_home_tell)
        cell(1, "Cell", self._info_cell)
        cell(2, "Emergency", self._info_emergency)
        state["row"] += 1
```

Remove the Emergency cell line (keep the others):

```python
        cell(0, "Home Phone", self._info_home_tell)
        cell(1, "Cell", self._info_cell)
        state["row"] += 1
```

(Do NOT remove `self._info_emergency = field("emergency")` or its use in
`collect`/`_save_info`/`_discard_info` — the unshown widget keeps the existing
value round-tripping to the DB.)

- [ ] **Step 3: Add the Emergency section after Care**

In `_make_info_tab`, the Care section ends and the assemble comment begins:

```python
        section("Care")
        cell(0, "Case Manager", self._info_case_manager)
        cell(1, "Admission Date", self._info_admission_date)
        state["row"] += 1

        # ── Assemble (scroll area is a safety net; content fits unscrolled) ─
```

Insert the Emergency section between them:

```python
        section("Care")
        cell(0, "Case Manager", self._info_case_manager)
        cell(1, "Admission Date", self._info_admission_date)
        state["row"] += 1

        section("Emergency")
        self._emergency_box = QWidget()
        ebox = QVBoxLayout(self._emergency_box)
        ebox.setContentsMargins(0, 0, 0, 0)
        grid.addWidget(self._emergency_box, state["row"], 0, 1, 6)
        state["row"] += 1
        self._fill_emergency_box()

        # ── Assemble (scroll area is a safety net; content fits unscrolled) ─
```

(`QWidget` and `QVBoxLayout` are imported at the top of the file.)

- [ ] **Step 4: Add `_fill_emergency_box` + CRUD handlers**

Add these methods to `MemberTabsWidget` (e.g. right after `_make_info_tab`):

```python
    def _fill_emergency_box(self):
        """(Re)build the embedded emergency-contacts table + buttons in place."""
        from PyQt6.QtWidgets import (
            QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView,
        )
        box = self._emergency_box.layout()
        while box.count():
            item = box.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
            elif item.layout() is not None:
                sub = item.layout()
                while sub.count():
                    sw = sub.takeAt(0).widget()
                    if sw is not None:
                        sw.deleteLater()

        columns = ["Full Name", "Phone", "Relationship", "Action"]
        table = QTableWidget(len(self._emergency_contacts), len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        hdr = table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(34)

        for r, ec in enumerate(self._emergency_contacts):
            name_item = QTableWidgetItem(ec["full_name"])
            name_item.setData(Qt.ItemDataRole.UserRole, ec["id"])
            table.setItem(r, 0, name_item)
            table.setItem(r, 1, QTableWidgetItem(ec["phone"]))
            table.setItem(r, 2, QTableWidgetItem(ec["relationship"]))
            btn = QPushButton("Edit")
            btn.setObjectName("btn_edit")
            btn.clicked.connect(lambda _=False, e=ec: self._edit_emergency(e))
            table.setCellWidget(r, 3, btn)

        self._emergency_table = table
        box.addWidget(table)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("+ Add")
        btn_add.clicked.connect(self._add_emergency)
        btn_del = QPushButton("Delete Selected")
        btn_del.clicked.connect(lambda: self._delete_emergency(table))
        btn_row.addWidget(btn_add)
        btn_row.addStretch()
        btn_row.addWidget(btn_del)
        box.addLayout(btn_row)

    def _open_emergency_dialog(self, existing: dict | None = None):
        from PyQt6.QtWidgets import (
            QDialog, QFormLayout, QLineEdit, QDialogButtonBox,
        )
        e = existing or {}
        dlg = QDialog(self)
        dlg.setWindowTitle("Edit Emergency Contact" if existing
                           else "Add Emergency Contact")
        form = QFormLayout(dlg)
        name_edit = QLineEdit(e.get("full_name", ""))
        phone_edit = QLineEdit(e.get("phone", ""))
        rel_edit = QLineEdit(e.get("relationship", ""))
        form.addRow("Full Name:", name_edit)
        form.addRow("Phone Number:", phone_edit)
        form.addRow("Relationship:", rel_edit)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)

        def on_accept():
            if not name_edit.text().strip():
                QMessageBox.warning(dlg, "Validation", "Full Name is required.")
                return
            dlg.accept()

        btns.accepted.connect(on_accept)
        if not dlg.exec():
            return None
        return {
            "full_name": name_edit.text().strip(),
            "phone": phone_edit.text().strip(),
            "relationship": rel_edit.text().strip(),
        }

    def _add_emergency(self):
        from db.members import insert_emergency_contact, get_emergency_contacts
        result = self._open_emergency_dialog()
        if not result:
            return
        try:
            insert_emergency_contact(
                self._center_id, result["full_name"], result["phone"],
                result["relationship"], self._db_path,
            )
            self._emergency_contacts = get_emergency_contacts(
                self._center_id, self._db_path)
            self._fill_emergency_box()
            self._log_event("EDIT",
                            f"Emergency contact added: {result['full_name']}")
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _edit_emergency(self, entry: dict):
        from db.members import update_emergency_contact, get_emergency_contacts
        result = self._open_emergency_dialog(existing=entry)
        if not result:
            return
        try:
            update_emergency_contact(
                entry["id"], result["full_name"], result["phone"],
                result["relationship"], self._db_path,
            )
            self._emergency_contacts = get_emergency_contacts(
                self._center_id, self._db_path)
            self._fill_emergency_box()
            self._log_event("EDIT",
                            f"Emergency contact edited: {result['full_name']}")
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _delete_emergency(self, table):
        row = table.currentRow()
        if row < 0:
            return
        item = table.item(row, 0)
        record_id = item.data(Qt.ItemDataRole.UserRole) if item else None
        if record_id is None:
            return
        if QMessageBox.question(self, "Confirm", "Delete this emergency contact?") \
                == QMessageBox.StandardButton.Yes:
            from db.members import delete_emergency_contact, get_emergency_contacts
            entry = next((e for e in self._emergency_contacts
                          if e["id"] == record_id), None)
            try:
                delete_emergency_contact(record_id, self._db_path)
                self._emergency_contacts = get_emergency_contacts(
                    self._center_id, self._db_path)
                self._fill_emergency_box()
                if entry:
                    self._log_event(
                        "EDIT",
                        f"Emergency contact deleted: {entry['full_name']}")
            except Exception as exc:
                QMessageBox.critical(self, "Error", str(exc))
```

- [ ] **Step 5: Verify import + grep**

Run: `.venv\Scripts\python -c "from gui.member_tabs import MemberTabsWidget; print('OK')"`
Expected: `OK`

Grep `gui/member_tabs.py` for `cell(2, "Emergency"` → no matches (old field cell
removed). Grep for `_fill_emergency_box` → the definition + the calls in build/CRUD.

- [ ] **Step 6: Run the full suite**

Run: `.venv\Scripts\pytest -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add gui/member_tabs.py
git commit -m "feat: Emergency contacts section in the Info tab (add/edit/delete)"
```
End with a blank line then:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Task 3: Full suite + exe rebuild + manual smoke test

**Files:** none changed

- [ ] **Step 1: Run the full test suite**

Run: `.venv\Scripts\pytest -q` → all pass.

- [ ] **Step 2: Rebuild the exe**

```
powershell -Command "try { Stop-Process -Name MemberManager -Force -ErrorAction Stop } catch {}"
.venv\Scripts\pyinstaller MemberManager.spec
```
Expected: `Build complete! ... dist`

- [ ] **Step 3: Manual smoke test** (requires the real Access DB in Settings)

Launch `dist\MemberManager.exe`, open a member, Info tab:
- The old single **Emergency** field is gone from the Contact section.
- At the bottom, an **Emergency** section shows a table of contacts
  (Full Name · Phone · Relationship) with **+ Add** / **Delete Selected**, empty for
  a member with none.
- **+ Add** → enter Full Name (+ optional Phone/Relationship) → it appears and
  persists after reopening the member; an empty Full Name is rejected.
- **Edit** (per row) → change fields → updates.
- **Delete Selected** → confirm → removed.
- The **Events** tab shows "Emergency contact added/edited/deleted: …".
- Saving the Info form still works (the hidden Emergency value is preserved).

---

## Self-Review Notes

- **Spec coverage:** EmergencyContact SQL + mapper + CRUD + `emergency_contacts`
  context key + `get_emergency_contacts` + conftest table → Task 1. Embedded
  Emergency section (self-refreshing table), dialog, immediate-commit CRUD, audit
  log, old-field removal → Task 2. Suite/exe/manual → Task 3.
- **Type consistency:** `insert_emergency_contact(center_id, full_name, phone,
  relationship, db_path)`, `update_emergency_contact(record_id, full_name, phone,
  relationship, db_path)`, `get_emergency_contacts(center_id, db_path)`, mapper →
  `{id, center_id, full_name, phone, relationship}`; the dialog returns
  `{full_name, phone, relationship}`; the row's id is stored via
  `Qt.ItemDataRole.UserRole` on the Full Name cell; `self._emergency_contacts` is
  the loaded list; `self._emergency_box` is the embedded container.
- **No placeholders:** every step has full code and exact commands/expected output.
  The mapper is unit-tested; the embedded UI + DB writes are verified manually (the
  conftest keeps the integration suite green by creating the table).
