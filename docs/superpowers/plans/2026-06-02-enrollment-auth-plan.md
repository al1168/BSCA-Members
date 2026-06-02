# Enrollment Termination, Read-Only Plan & Plan-Per-Authorization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Terminate button to enrollments, make the profile Health Plan read-only, attach a Health Plan to each authorization with auto-sync of the member's plan from the latest authorization, and allow editing the latest authorization.

**Architecture:** All business logic (terminate, plan sync, latest-auth selection, auth CRUD) lives in `db/members.py` and is unit/integration tested. The Enrollments and Authorizations tabs in `gui/member_tabs.py` are rebuilt as bespoke `QTableWidget`s so per-row action buttons (Terminate, Edit) can be placed via `setCellWidget`; the other three tabs keep using the shared helper. The "latest authorization wins" rule is a single pure function reused by the sync function and the UI.

**Tech Stack:** Python 3.11, PyQt6, pyodbc (Access), pytest. No new dependencies.

**DB precondition:** the `[Authorization]` table has a text column `[Health Plan]`. This is already present in the integration test DB (`populate_real_members.accdb`). The production database must have it too before this ships.

---

## File Map

```
db/members.py          modify — terminate_enrollment, UPDATE_ENROLLMENT_END;
                                Health Plan on auth insert/read; latest_authorization;
                                sync_health_plan_from_latest_auth; update_authorization
gui/member_tabs.py     modify — read-only plan field; bespoke Enrollments table + Terminate;
                                reusable auth dialog; bespoke Authorizations table + Edit + sync wiring;
                                Schedule Summary plan
gui/theme.py           modify — styles for btn_terminate (red) and btn_edit
tests/test_db_members.py             modify — SQL constant unit tests + latest_authorization
tests/test_db_members_integration.py modify — terminate, auth plan round-trip, sync behavior
```

---

## Task 1: terminate_enrollment (DB layer)

**Files:**
- Modify: `db/members.py`
- Test: `tests/test_db_members.py`, `tests/test_db_members_integration.py`

- [ ] **Step 1: Write the failing unit test**

Add to `tests/test_db_members.py`:

```python
def test_update_enrollment_end_targets_correct_columns():
    from db.members import UPDATE_ENROLLMENT_END
    assert "UPDATE [Enrollment]" in UPDATE_ENROLLMENT_END
    assert "[end_date]=?" in UPDATE_ENROLLMENT_END
    assert "WHERE [ID]=?" in UPDATE_ENROLLMENT_END
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv\Scripts\pytest tests/test_db_members.py::test_update_enrollment_end_targets_correct_columns -v`
Expected: FAIL — `ImportError: cannot import name 'UPDATE_ENROLLMENT_END'`

- [ ] **Step 3: Write the failing integration test**

Add to `tests/test_db_members_integration.py` (at the bottom):

```python
def test_terminate_enrollment_sets_end_to_today():
    from datetime import date
    from db.members import (
        get_all_members, insert_enrollment, terminate_enrollment, delete_enrollment,
    )
    from monthly_schedule.db import get_enrollments

    cid = get_all_members(TEST_DB)[0]["center_id"]
    before = {e["id"] for e in get_enrollments(cid, TEST_DB)}
    insert_enrollment(cid, date(2020, 1, 1), None, TEST_DB)
    new_id = ({e["id"] for e in get_enrollments(cid, TEST_DB)} - before).pop()
    try:
        terminate_enrollment(new_id, TEST_DB)
        row = next(e for e in get_enrollments(cid, TEST_DB) if e["id"] == new_id)
        assert row["end_date"] == date.today()
    finally:
        delete_enrollment(new_id, TEST_DB)
```

- [ ] **Step 4: Run it to verify it fails**

Run: `.venv\Scripts\pytest tests/test_db_members_integration.py::test_terminate_enrollment_sets_end_to_today -v`
Expected: FAIL — `ImportError: cannot import name 'terminate_enrollment'`

- [ ] **Step 5: Implement in `db/members.py`**

Add the constant next to `DELETE_ENROLLMENT` (after line 50):

```python
UPDATE_ENROLLMENT_END = "UPDATE [Enrollment] SET [end_date]=? WHERE [ID]=?"
```

Add the function right after `delete_enrollment` (after its `conn.close()` block):

```python
def terminate_enrollment(record_id: int, db_path: str) -> None:
    """Set an enrollment's end date to today (used by the Terminate button)."""
    conn = _connect(db_path)
    try:
        conn.cursor().execute(UPDATE_ENROLLMENT_END, (date.today(), record_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

(`date` is already imported at the top: `from datetime import date, datetime`.)

- [ ] **Step 6: Run both tests to verify they pass**

Run: `.venv\Scripts\pytest tests/test_db_members.py::test_update_enrollment_end_targets_correct_columns tests/test_db_members_integration.py::test_terminate_enrollment_sets_end_to_today -v`
Expected: 2 passed

- [ ] **Step 7: Commit**

```bash
git add db/members.py tests/test_db_members.py tests/test_db_members_integration.py
git commit -m "feat: add terminate_enrollment() to set enrollment end date to today"
```

---

## Task 2: Health Plan on authorization reads & writes (DB layer)

**Files:**
- Modify: `db/members.py`
- Test: `tests/test_db_members.py`, `tests/test_db_members_integration.py`

- [ ] **Step 1: Write the failing unit test**

Add to `tests/test_db_members.py`:

```python
def test_insert_authorization_includes_health_plan():
    from db.members import INSERT_AUTHORIZATION
    assert "[Health Plan]" in INSERT_AUTHORIZATION
    assert INSERT_AUTHORIZATION.count("?") == 7
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv\Scripts\pytest tests/test_db_members.py::test_insert_authorization_includes_health_plan -v`
Expected: FAIL — `[Health Plan]` not in the (6-placeholder) statement.

- [ ] **Step 3: Write the failing integration test**

Add to `tests/test_db_members_integration.py`:

```python
def test_insert_authorization_persists_health_plan():
    from datetime import date
    from db.members import (
        get_all_members, insert_authorization, get_authorizations,
        delete_authorization,
    )
    cid = get_all_members(TEST_DB)[0]["center_id"]
    before = {a["id"] for a in get_authorizations(cid, TEST_DB)}
    insert_authorization(
        cid, date(2026, 1, 1), date(2026, 12, 31), {1, 3, 5},
        None, None, "Aetna", TEST_DB,
    )
    new_id = ({a["id"] for a in get_authorizations(cid, TEST_DB)} - before).pop()
    try:
        row = next(a for a in get_authorizations(cid, TEST_DB) if a["id"] == new_id)
        assert row["health_plan"] == "Aetna"
    finally:
        delete_authorization(new_id, TEST_DB)
```

- [ ] **Step 4: Run it to verify it fails**

Run: `.venv\Scripts\pytest tests/test_db_members_integration.py::test_insert_authorization_persists_health_plan -v`
Expected: FAIL — `get_authorizations` is still bsca-core's (no `health_plan` key) → `KeyError`, or `insert_authorization` rejects the extra arg → `TypeError`.

- [ ] **Step 5: Extend the INSERT statement in `db/members.py`**

Replace the `INSERT_AUTHORIZATION` constant:

```python
INSERT_AUTHORIZATION = (
    "INSERT INTO [Authorization] ([Center ID], [auth_start], [auth_end], "
    "[effective_start], [effective_end], [auth_days], [Health Plan]) "
    "VALUES (?, ?, ?, ?, ?, ?, ?)"
)
```

- [ ] **Step 6: Update `insert_authorization()` signature & binding**

Replace the existing `insert_authorization` function:

```python
def insert_authorization(
    center_id: int,
    auth_start: date,
    auth_end: date,
    auth_days: set[int],
    effective_start: date | None,
    effective_end: date | None,
    health_plan: str,
    db_path: str,
) -> None:
    conn = _connect(db_path)
    try:
        conn.cursor().execute(
            INSERT_AUTHORIZATION,
            (center_id, auth_start, auth_end, effective_start, effective_end,
             encode_auth_days(auth_days), health_plan),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

- [ ] **Step 7: Add the local auth read layer (with Health Plan)**

Add near the top of `db/members.py`, right after the `INSERT_AUTHORIZATION`/`DELETE_AUTHORIZATION` constants:

```python
AUTHORIZATION_SELECT = (
    "SELECT [ID],[Center ID],[auth_start],[auth_end],"
    "[effective_start],[effective_end],[auth_days],[Health Plan] "
    "FROM [Authorization] WHERE [Center ID]=?"
)
```

Add these functions right after `get_member_context()` (after its closing block). `map_authorization_row` is already imported at the top of the file:

```python
def _map_auth_row(row) -> dict:
    """bsca-core maps 7 columns by index; add the local [Health Plan] (row[7])."""
    d = map_authorization_row(row)
    d["health_plan"] = row[7] or ""
    return d


def get_authorizations(center_id: int, db_path: str, _retry: bool = True) -> list[dict]:
    """Authorizations for a member, including health_plan (cached read connection).

    Replaces monthly_schedule.db.get_authorizations whose query has no
    [Health Plan] column. Mirrors get_member_context's stale-connection retry.
    """
    import pyodbc
    conn = _read_connection(db_path)
    try:
        c = conn.cursor()
        c.execute(AUTHORIZATION_SELECT, center_id)
        return [_map_auth_row(r) for r in c.fetchall()]
    except pyodbc.Error:
        _drop_read_connection(db_path)
        if _retry:
            return get_authorizations(center_id, db_path, _retry=False)
        raise
```

- [ ] **Step 8: Use the new select in `get_member_context()`**

In `get_member_context()`, find the authorizations block:

```python
        c.execute(
            "SELECT [ID],[Center ID],[auth_start],[auth_end],"
            "[effective_start],[effective_end],[auth_days] "
            "FROM [Authorization] WHERE [Center ID]=?",
            center_id,
        )
        authorizations = [map_authorization_row(r) for r in c.fetchall()]
```

Replace it with:

```python
        c.execute(AUTHORIZATION_SELECT, center_id)
        authorizations = [_map_auth_row(r) for r in c.fetchall()]
```

- [ ] **Step 9: Run both tests to verify they pass**

Run: `.venv\Scripts\pytest tests/test_db_members.py::test_insert_authorization_includes_health_plan tests/test_db_members_integration.py::test_insert_authorization_persists_health_plan -v`
Expected: 2 passed

> Note: this changes `insert_authorization`'s signature, so the call site in `gui/member_tabs.py::_add_auth` is now stale and will error **if clicked** until Task 9 rewrites it. Imports and the test suite stay green in the meantime.

- [ ] **Step 10: Commit**

```bash
git add db/members.py tests/test_db_members.py tests/test_db_members_integration.py
git commit -m "feat: attach Health Plan to authorizations (insert + local read layer)"
```

---

## Task 3: latest_authorization helper (DB layer)

**Files:**
- Modify: `db/members.py`
- Test: `tests/test_db_members.py`

- [ ] **Step 1: Write the failing unit test**

Add to `tests/test_db_members.py`:

```python
def test_latest_authorization_picks_latest_start_then_id():
    from datetime import date
    from db.members import latest_authorization
    auths = [
        {"id": 1, "auth_start": date(2025, 1, 1), "health_plan": "AE"},
        {"id": 2, "auth_start": date(2026, 1, 1), "health_plan": "Aetna"},
        {"id": 3, "auth_start": date(2026, 1, 1), "health_plan": "BCBS"},
    ]
    assert latest_authorization(auths)["id"] == 3  # same start → highest id


def test_latest_authorization_empty_returns_none():
    from db.members import latest_authorization
    assert latest_authorization([]) is None
    assert latest_authorization([{"id": 1, "auth_start": None}]) is None
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv\Scripts\pytest tests/test_db_members.py -k latest_authorization -v`
Expected: FAIL — `ImportError: cannot import name 'latest_authorization'`

- [ ] **Step 3: Implement in `db/members.py`**

Add right after `get_authorizations()`:

```python
def latest_authorization(authorizations: list[dict]) -> dict | None:
    """The 'current' authorization: latest by (auth_start, id).

    Returns None if the list is empty or no row has an auth_start.
    """
    candidates = [a for a in authorizations if a.get("auth_start")]
    if not candidates:
        return None
    return max(candidates, key=lambda a: (a["auth_start"], a["id"]))
```

- [ ] **Step 4: Run it to verify it passes**

Run: `.venv\Scripts\pytest tests/test_db_members.py -k latest_authorization -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add db/members.py tests/test_db_members.py
git commit -m "feat: add latest_authorization() helper (latest by auth_start, id)"
```

---

## Task 4: sync_health_plan_from_latest_auth (DB layer)

**Files:**
- Modify: `db/members.py`
- Test: `tests/test_db_members_integration.py`

- [ ] **Step 1: Write the failing integration test**

Add to `tests/test_db_members_integration.py`:

```python
def test_sync_writes_latest_auth_plan_into_contacts():
    from datetime import date
    from db.members import (
        get_all_members, get_member_context, insert_authorization,
        delete_authorization, get_authorizations, update_contact,
        sync_health_plan_from_latest_auth,
    )
    cid = get_all_members(TEST_DB)[0]["center_id"]
    m = get_member_context(cid, TEST_DB)["member"]
    original_plan = m["health_plan"]
    before = {a["id"] for a in get_authorizations(cid, TEST_DB)}
    # Insert an authorization with a far-future start so it is the latest.
    insert_authorization(
        cid, date(2099, 1, 1), date(2099, 12, 31), {1}, None, None, "VCM", TEST_DB,
    )
    new_id = ({a["id"] for a in get_authorizations(cid, TEST_DB)} - before).pop()
    try:
        returned = sync_health_plan_from_latest_auth(cid, TEST_DB)
        assert returned == "VCM"
        assert get_member_context(cid, TEST_DB)["member"]["health_plan"] == "VCM"
    finally:
        delete_authorization(new_id, TEST_DB)
        # Restore the member's original Contacts plan.
        update_contact(
            cid, m["last_name"], m["first_name"], m["chinese_name"], m["gender"],
            m["dob"], m["member_id"], original_plan, m["medicaid"], m["medicare"],
            m["ssn"], m["language"], m["case_manager"], m["home_tell"], m["cell"],
            m["address"], m["emergency"], m["pcp"], m["hospital"], m["hha"],
            m["admission_date"], m["notes"], TEST_DB,
        )


def test_sync_noop_when_no_authorizations():
    from db.members import get_all_members, get_authorizations, sync_health_plan_from_latest_auth
    # Find a member with no authorizations (supporting tables are sparse).
    members = get_all_members(TEST_DB)
    for mem in members:
        if not get_authorizations(mem["center_id"], TEST_DB):
            assert sync_health_plan_from_latest_auth(mem["center_id"], TEST_DB) is None
            return
```

> Note on `update_contact` argument order in the restore call: it is
> `(center_id, last_name, first_name, chinese_name, gender, dob, member_id,
> health_plan, medicaid, medicare, ssn, language, case_manager, home_tell,
> cell, address, emergency, pcp, hospital, hha, admission_date, notes, db_path)`.

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv\Scripts\pytest tests/test_db_members_integration.py -k sync -v`
Expected: FAIL — `ImportError: cannot import name 'sync_health_plan_from_latest_auth'`

- [ ] **Step 3: Implement in `db/members.py`**

Add right after `latest_authorization()`:

```python
def sync_health_plan_from_latest_auth(center_id: int, db_path: str) -> str | None:
    """Set Contacts.[Health Plan] to the latest authorization's plan.

    Returns the plan written, or None when nothing changed. Never blanks an
    existing plan: if there are no authorizations, or the latest one's plan is
    empty, Contacts is left untouched.
    """
    latest = latest_authorization(get_authorizations(center_id, db_path))
    if not latest:
        return None
    plan = (latest.get("health_plan") or "").strip()
    if not plan:
        return None
    conn = _connect(db_path)
    try:
        conn.cursor().execute(
            "UPDATE [Contacts] SET [Health Plan]=? WHERE [Center ID]=?",
            (plan, center_id),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return plan
```

(`_connect` invalidates the cached read connection, so the next `get_member_context` reflects the new plan.)

- [ ] **Step 4: Run it to verify it passes**

Run: `.venv\Scripts\pytest tests/test_db_members_integration.py -k sync -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add db/members.py tests/test_db_members_integration.py
git commit -m "feat: sync_health_plan_from_latest_auth() writes latest auth plan to Contacts"
```

---

## Task 5: update_authorization (DB layer)

**Files:**
- Modify: `db/members.py`
- Test: `tests/test_db_members.py`, `tests/test_db_members_integration.py`

- [ ] **Step 1: Write the failing unit test**

Add to `tests/test_db_members.py`:

```python
def test_update_authorization_targets_correct_columns():
    from db.members import UPDATE_AUTHORIZATION
    assert "UPDATE [Authorization]" in UPDATE_AUTHORIZATION
    for col in ("[auth_start]=?", "[auth_end]=?", "[auth_days]=?", "[Health Plan]=?"):
        assert col in UPDATE_AUTHORIZATION
    assert "WHERE [ID]=?" in UPDATE_AUTHORIZATION
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv\Scripts\pytest tests/test_db_members.py::test_update_authorization_targets_correct_columns -v`
Expected: FAIL — `ImportError: cannot import name 'UPDATE_AUTHORIZATION'`

- [ ] **Step 3: Write the failing integration test**

Add to `tests/test_db_members_integration.py`:

```python
def test_update_authorization_round_trips_changes():
    from datetime import date
    from db.members import (
        get_all_members, insert_authorization, update_authorization,
        get_authorizations, delete_authorization,
    )
    cid = get_all_members(TEST_DB)[0]["center_id"]
    before = {a["id"] for a in get_authorizations(cid, TEST_DB)}
    insert_authorization(
        cid, date(2026, 1, 1), date(2026, 6, 30), {1, 2}, None, None, "AE", TEST_DB,
    )
    new_id = ({a["id"] for a in get_authorizations(cid, TEST_DB)} - before).pop()
    try:
        update_authorization(
            new_id, date(2026, 2, 1), date(2026, 7, 31), {3, 4, 5}, "HF", TEST_DB,
        )
        row = next(a for a in get_authorizations(cid, TEST_DB) if a["id"] == new_id)
        assert row["auth_start"] == date(2026, 2, 1)
        assert row["auth_end"] == date(2026, 7, 31)
        assert row["auth_days"] == "3,4,5"
        assert row["health_plan"] == "HF"
    finally:
        delete_authorization(new_id, TEST_DB)
```

- [ ] **Step 4: Run it to verify it fails**

Run: `.venv\Scripts\pytest tests/test_db_members_integration.py::test_update_authorization_round_trips_changes -v`
Expected: FAIL — `ImportError: cannot import name 'update_authorization'`

- [ ] **Step 5: Implement in `db/members.py`**

Add the constant after `DELETE_AUTHORIZATION`:

```python
UPDATE_AUTHORIZATION = (
    "UPDATE [Authorization] SET [auth_start]=?, [auth_end]=?, "
    "[auth_days]=?, [Health Plan]=? WHERE [ID]=?"
)
```

Add the function right after `insert_authorization`:

```python
def update_authorization(
    record_id: int,
    auth_start: date,
    auth_end: date,
    auth_days: set[int],
    health_plan: str,
    db_path: str,
) -> None:
    """Update an existing authorization's dates, days, and plan."""
    conn = _connect(db_path)
    try:
        conn.cursor().execute(
            UPDATE_AUTHORIZATION,
            (auth_start, auth_end, encode_auth_days(auth_days), health_plan, record_id),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

- [ ] **Step 6: Run both tests to verify they pass**

Run: `.venv\Scripts\pytest tests/test_db_members.py::test_update_authorization_targets_correct_columns tests/test_db_members_integration.py::test_update_authorization_round_trips_changes -v`
Expected: 2 passed

- [ ] **Step 7: Commit**

```bash
git add db/members.py tests/test_db_members.py tests/test_db_members_integration.py
git commit -m "feat: add update_authorization() for editing an existing auth"
```

---

## Task 6: Read-only Health Plan on the Info tab (GUI)

**Files:**
- Modify: `gui/member_tabs.py`

- [ ] **Step 1: Make the plan field a read-only line edit**

In `_make_info_tab()`, change the local import line:

```python
        from PyQt6.QtWidgets import (
            QFormLayout, QLineEdit, QComboBox, QTextEdit,
            QGroupBox, QScrollArea,
        )
        from db.members import HEALTH_PLANS
```

to (drop `QComboBox` and the `HEALTH_PLANS` import — neither is used here anymore):

```python
        from PyQt6.QtWidgets import (
            QFormLayout, QLineEdit, QTextEdit,
            QGroupBox, QScrollArea,
        )
```

Then replace the plan widget creation:

```python
        self._info_plan = QComboBox()
        self._info_plan.addItems(HEALTH_PLANS)
        idx = self._info_plan.findText(m.get("health_plan", ""))
        self._info_plan.setCurrentIndex(idx if idx >= 0 else 0)
```

with:

```python
        self._info_plan = QLineEdit(m.get("health_plan", "") or "")
        self._info_plan.setReadOnly(True)
```

- [ ] **Step 2: Stop resetting the plan in `_discard_info()`**

Remove these two lines from `_discard_info()`:

```python
        idx = self._info_plan.findText(m.get("health_plan", ""))
        self._info_plan.setCurrentIndex(idx if idx >= 0 else 0)
```

- [ ] **Step 3: Preserve (don't edit) the plan in `_save_info()`**

In `_save_info()`, change:

```python
            "health_plan":    self._info_plan.currentText(),
```

to:

```python
            "health_plan":    self._member.get("health_plan", "") or "",
```

- [ ] **Step 4: Remove the plan from dirty tracking**

In `_setup_dirty_tracking()`, delete this line:

```python
        self._info_plan.currentIndexChanged.connect(lambda: setattr(self, '_dirty', True))
```

- [ ] **Step 5: Verify the import still works**

Run: `.venv\Scripts\python -c "from gui.member_tabs import MemberTabsWidget; print('OK')"`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add gui/member_tabs.py
git commit -m "feat: make profile Health Plan read-only (now driven by authorizations)"
```

---

## Task 7: Bespoke Enrollments table with Terminate button (GUI)

**Files:**
- Modify: `gui/member_tabs.py`, `gui/theme.py`

- [ ] **Step 1: Add the red Terminate button style**

In `gui/theme.py`, inside `build_qss(t)`, add these rules right before the `QLabel {{` block:

```python
QPushButton#btn_terminate {{
    background-color: {t['error']};
    color: #ffffff;
    border: none;
    font-weight: 600;
    padding: 4px 12px;
    border-radius: 5px;
}}
QPushButton#btn_terminate:hover {{
    background-color: {t['error_text']};
}}
QPushButton#btn_edit {{
    background-color: {t['accent_bg']};
    color: {t['accent_text']};
    border: 1px solid {t['accent']};
    font-weight: 600;
    padding: 4px 12px;
    border-radius: 5px;
}}
QPushButton#btn_edit:hover {{
    background-color: {t['accent']};
    color: #ffffff;
}}
```

- [ ] **Step 2: Replace `_make_enrollments_tab()`**

Replace the entire `_make_enrollments_tab()` method:

```python
    def _make_enrollments_tab(self) -> QWidget:
        from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QAbstractItemView
        from datetime import date

        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 12, 0, 0)

        columns = ["ID", "Start Date", "End Date", "Status"]
        table = QTableWidget(len(self._enrollments), len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setVisible(False)

        today = date.today()
        for r, e in enumerate(self._enrollments):
            end = e["end_date"]
            table.setItem(r, 0, QTableWidgetItem(str(e["id"])))
            table.setItem(r, 1, QTableWidgetItem(str(e["start_date"])))
            table.setItem(r, 2, QTableWidgetItem(str(end) if end else "ongoing"))
            if end is None or end > today:
                btn = QPushButton("Terminate")
                btn.setObjectName("btn_terminate")
                btn.clicked.connect(
                    lambda _=False, rid=e["id"]: self._terminate_enrollment(rid)
                )
                table.setCellWidget(r, 3, btn)
            else:
                table.setItem(r, 3, QTableWidgetItem("Ended"))

        self._enroll_table = table
        layout.addWidget(table)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("+ Add")
        btn_add.clicked.connect(self._add_enrollment)
        btn_del = QPushButton("Delete Selected")
        btn_del.clicked.connect(lambda: self._delete_enrollment(table))
        btn_row.addWidget(btn_add)
        btn_row.addStretch()
        btn_row.addWidget(btn_del)
        layout.addLayout(btn_row)
        return w
```

- [ ] **Step 3: Add the `_terminate_enrollment()` handler**

Add this method right after `_delete_enrollment()`:

```python
    def _terminate_enrollment(self, record_id: int):
        from datetime import date
        from db.members import terminate_enrollment
        from db.events import open_db, insert_event
        from monthly_schedule.db import get_enrollments

        today = date.today()
        reply = QMessageBox.question(
            self, "Terminate Enrollment",
            f"Terminate this enrollment? The end date will be set to today "
            f"({today.isoformat()}). This can't be undone.",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            terminate_enrollment(record_id, self._db_path)
            self._enrollments = get_enrollments(self._center_id, self._db_path)
            self._refresh_tab(1, self._make_enrollments_tab())
            if self._events_path:
                conn = open_db(self._events_path)
                try:
                    m = self._member
                    insert_event(conn, "ENROLL", self._center_id,
                        f"{m.get('last_name')}, {m.get('first_name')}",
                        f"Enrollment terminated: end set to {today.isoformat()}")
                finally:
                    conn.close()
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
```

- [ ] **Step 4: Verify imports + QSS build**

Run: `.venv\Scripts\python -c "from gui.theme import build_qss, DARK, LIGHT; build_qss(DARK); build_qss(LIGHT); from gui.member_tabs import MemberTabsWidget; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add gui/member_tabs.py gui/theme.py
git commit -m "feat: Enrollments tab Status column with red Terminate button"
```

---

## Task 8: Reusable Add/Edit Authorization dialog (GUI)

**Files:**
- Modify: `gui/member_tabs.py`

- [ ] **Step 1: Add the shared dialog method**

Add this method right before `_add_auth()`:

```python
    def _open_auth_dialog(self, existing: dict | None = None) -> dict | None:
        """Build the Add/Edit Authorization dialog. Returns a dict with
        auth_start, auth_end, days, health_plan — or None if cancelled.
        Pre-fills from `existing` when editing."""
        from PyQt6.QtWidgets import (
            QDialog, QFormLayout, QDateEdit, QCheckBox, QComboBox,
            QHBoxLayout, QDialogButtonBox, QWidget,
        )
        from PyQt6.QtCore import QDate
        from db.members import HEALTH_PLANS

        dlg = QDialog(self)
        dlg.setWindowTitle("Edit Authorization" if existing else "Add Authorization")
        form = QFormLayout(dlg)

        auth_start = QDateEdit()
        auth_start.setCalendarPopup(True)
        auth_end = QDateEdit()
        auth_end.setCalendarPopup(True)
        if existing:
            s, e = existing["auth_start"], existing["auth_end"]
            auth_start.setDate(QDate(s.year, s.month, s.day))
            auth_end.setDate(QDate(e.year, e.month, e.day))
        else:
            auth_start.setDate(QDate.currentDate())
            auth_end.setDate(QDate.currentDate().addYears(1))

        existing_days = (
            self.decode_auth_days_static(existing["auth_days"]) if existing else set()
        )
        day_checks = {}
        days_widget = QWidget()
        days_hl = QHBoxLayout(days_widget)
        days_hl.setContentsMargins(0, 0, 0, 0)
        for num, label in [(1, "Mon"), (2, "Tue"), (3, "Wed"), (4, "Thu"), (5, "Fri")]:
            cb = QCheckBox(label)
            cb.setChecked(num in existing_days)
            day_checks[num] = cb
            days_hl.addWidget(cb)

        plan_combo = QComboBox()
        plan_combo.addItems(HEALTH_PLANS)
        if existing:
            idx = plan_combo.findText(existing.get("health_plan", ""))
            if idx >= 0:
                plan_combo.setCurrentIndex(idx)

        form.addRow("Auth Start:", auth_start)
        form.addRow("Auth End:", auth_end)
        form.addRow("Days:", days_widget)
        form.addRow("Health Plan:", plan_combo)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)
        btns.accepted.connect(
            lambda: dlg.accept() if any(cb.isChecked() for cb in day_checks.values())
            else QMessageBox.warning(dlg, "Validation", "Select at least one day.")
        )

        if not dlg.exec():
            return None
        return {
            "auth_start": auth_start.date().toPyDate(),
            "auth_end": auth_end.date().toPyDate(),
            "days": {n for n, cb in day_checks.items() if cb.isChecked()},
            "health_plan": plan_combo.currentText(),
        }
```

- [ ] **Step 2: Verify the import still works**

Run: `.venv\Scripts\python -c "from gui.member_tabs import MemberTabsWidget; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add gui/member_tabs.py
git commit -m "feat: reusable Add/Edit Authorization dialog with Health Plan field"
```

---

## Task 9: Authorizations tab — Health Plan column, Edit on latest, sync wiring (GUI)

**Files:**
- Modify: `gui/member_tabs.py`

- [ ] **Step 1: Replace `_make_auths_tab()` with a bespoke table**

Replace the entire `_make_auths_tab()` method:

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

        latest = latest_authorization(self._authorizations)
        latest_id = latest["id"] if latest else None
        for r, a in enumerate(self._authorizations):
            table.setItem(r, 0, QTableWidgetItem(str(a["id"])))
            table.setItem(r, 1, QTableWidgetItem(str(a["auth_start"])))
            table.setItem(r, 2, QTableWidgetItem(str(a["auth_end"])))
            table.setItem(r, 3, QTableWidgetItem(a["auth_days"] or ""))
            table.setItem(r, 4, QTableWidgetItem(a.get("health_plan", "") or ""))
            if a["id"] == latest_id:
                btn = QPushButton("Edit")
                btn.setObjectName("btn_edit")
                btn.clicked.connect(lambda _=False, auth=a: self._edit_auth(auth))
                table.setCellWidget(r, 5, btn)

        self._auth_table = table
        layout.addWidget(table)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("+ Add")
        btn_add.clicked.connect(self._add_auth)
        btn_del = QPushButton("Delete Selected")
        btn_del.clicked.connect(lambda: self._delete_auth(table))
        btn_row.addWidget(btn_add)
        btn_row.addStretch()
        btn_row.addWidget(btn_del)
        layout.addLayout(btn_row)
        return w
```

- [ ] **Step 2: Add the shared post-change helper**

Add this method right after `_make_auths_tab()`:

```python
    def _after_auth_change(self, description: str | None):
        """Re-sync the plan, reload auths, refresh the tab, and (optionally)
        log an AUTH event. Called after add/edit/delete of an authorization."""
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

- [ ] **Step 3: Replace `_add_auth()`**

Replace the entire `_add_auth()` method:

```python
    def _add_auth(self):
        from db.members import insert_authorization, encode_auth_days

        result = self._open_auth_dialog()
        if not result:
            return
        try:
            insert_authorization(
                self._center_id, result["auth_start"], result["auth_end"],
                result["days"], None, None, result["health_plan"], self._db_path,
            )
            self._after_auth_change(
                f"Auth added: {result['auth_start']} – {result['auth_end']} · "
                f"{encode_auth_days(result['days'])} · {result['health_plan']}"
            )
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
```

- [ ] **Step 4: Add the `_edit_auth()` handler**

Add this method right after `_add_auth()`:

```python
    def _edit_auth(self, auth: dict):
        from db.members import update_authorization, encode_auth_days

        result = self._open_auth_dialog(existing=auth)
        if not result:
            return
        try:
            update_authorization(
                auth["id"], result["auth_start"], result["auth_end"],
                result["days"], result["health_plan"], self._db_path,
            )
            self._after_auth_change(
                f"Auth edited: {result['auth_start']} – {result['auth_end']} · "
                f"{encode_auth_days(result['days'])} · {result['health_plan']}"
            )
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
```

- [ ] **Step 5: Replace `_delete_auth()` to re-sync the plan**

Replace the entire `_delete_auth()` method:

```python
    def _delete_auth(self, table):
        row = table.currentRow()
        if row < 0:
            return
        record_id = int(table.item(row, 0).text())
        if QMessageBox.question(self, "Confirm", "Delete this authorization?") \
                == QMessageBox.StandardButton.Yes:
            from db.members import delete_authorization
            try:
                delete_authorization(record_id, self._db_path)
                self._after_auth_change(None)
            except Exception as exc:
                QMessageBox.critical(self, "Error", str(exc))
```

- [ ] **Step 6: Verify the import still works**

Run: `.venv\Scripts\python -c "from gui.member_tabs import MemberTabsWidget; print('OK')"`
Expected: `OK`

- [ ] **Step 7: Commit**

```bash
git add gui/member_tabs.py
git commit -m "feat: Authorizations tab Health Plan column, Edit on latest, plan auto-sync"
```

---

## Task 10: Schedule Summary shows the active auth's plan (GUI)

**Files:**
- Modify: `gui/member_tabs.py`

- [ ] **Step 1: Append the plan to the Active Auth line**

In `_make_info_tab()`, find the Schedule Summary block:

```python
            auth_text = (f"{active_auth['effective_start']} – "
                         f"{active_auth['effective_end']}  [{days_str}]")
```

Replace it with:

```python
            plan = active_auth.get("health_plan", "")
            auth_text = (f"{active_auth['effective_start']} – "
                         f"{active_auth['effective_end']}  [{days_str}]"
                         + (f"  ·  {plan}" if plan else ""))
```

- [ ] **Step 2: Verify the import still works**

Run: `.venv\Scripts\python -c "from gui.member_tabs import MemberTabsWidget; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add gui/member_tabs.py
git commit -m "feat: show active authorization's Health Plan in Schedule Summary"
```

---

## Task 11: Full test suite + exe rebuild + manual smoke test

**Files:** none changed

- [ ] **Step 1: Run the full test suite**

Run: `.venv\Scripts\pytest -q`
Expected: all tests pass (the prior 40 plus the new unit/integration tests).

- [ ] **Step 2: Rebuild the exe**

First stop any running instance (it locks the output file), then build:

```
powershell -Command "try { Stop-Process -Name MemberManager -Force -ErrorAction Stop } catch {}"
.venv\Scripts\pyinstaller MemberManager.spec
```

Expected: `Build complete! The results are available in: ...\dist`

- [ ] **Step 3: Manual smoke test**

Launch `dist\MemberManager.exe`, set the DB path in Settings if needed, click a member, and verify:
- **Info tab:** Health Plan is read-only (greyed/dashed), not a dropdown.
- **Enrollments tab:** a Status column sits next to End Date; active rows show a red **Terminate** button, ended rows show "Ended". Clicking Terminate prompts for confirmation; on Yes the end date becomes today and the row flips to "Ended".
- **Authorizations tab:** a Health Plan column is present; only the latest auth row has an **Edit** button. Adding an auth requires a plan and ≥1 day; the member's Health Plan (Info tab + sidebar on next load) updates to the latest auth's plan.
- **Edit** opens the dialog pre-filled; saving a different plan/date updates the row and the displayed plan.
- **Schedule Summary:** the Active Auth line shows the plan after the days.

- [ ] **Step 4: Commit (if any incidental fixes were needed)**

```bash
git add -A
git commit -m "chore: rebuild MemberManager.exe with enrollment/auth/plan features"
```

---

## Self-Review Notes

- **Spec coverage:** Feature 1 → Tasks 1, 7. Feature 2 → Task 6. Feature 3 → Tasks 2, 3, 4, 9, 10. Feature 4 → Tasks 5, 8, 9. Testing section → Tasks 1–5 (unit + integration) and Task 11 (full run + manual GUI checks).
- **Type/name consistency:** `latest_authorization`, `get_authorizations`, `sync_health_plan_from_latest_auth`, `insert_authorization` (7-arg + db_path), `update_authorization`, `terminate_enrollment`, `_open_auth_dialog`, `_after_auth_change`, `_terminate_enrollment`, `_edit_auth` are referenced consistently across tasks. Auth dicts carry keys `id`, `auth_start`, `auth_end`, `auth_days`, `effective_start`, `effective_end`, `health_plan`.
- **Ordering note:** Task 2 changes `insert_authorization`'s signature; the stale call site is rewritten in Task 9. Between them the app imports fine and tests pass; only clicking "Add Authorization" would error, and no task in between exercises that path.
