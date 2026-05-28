# BSCA Member Manager Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone PyQt6 desktop app for non-technical staff to manage BSCA member records (contacts, enrollments, authorizations, availability, absences) with a full audit log.

**Architecture:** Side-by-side main window (sidebar list + tabbed detail panel), 4-step add-member wizard, SQLite events log with 30-day TTL. Reads the same Access `.accdb` used by the schedule generator via the `bsca-core` package; write functions live in this repo's `db/members.py`.

**Tech Stack:** Python 3.11, PyQt6, pyodbc (Access via bsca-core), sqlite3 (stdlib, events), pytest

---

## File Map

```
BSCA-Members/
├── conftest.py                     create
├── settings.py                     create  — read/write bsca_members_settings.json
├── member_manager.py               modify  — wire MainWindow + settings + theme
├── gui/
│   ├── theme.py                    create  — hex token dicts, build_qss(), apply_theme()
│   ├── main_window.py              modify  — full MainWindow: sidebar + detail panel
│   ├── member_tabs.py              create  — 6-tab widget: Info/Enroll/Auth/Avail/Abs/Events
│   ├── settings_dialog.py          create  — db path, theme toggle, events path
│   └── events_view.py              create  — global events log widget
│   └── wizard/
│       ├── __init__.py             create
│       ├── wizard.py               create  — QDialog + QStackedWidget, progress bar
│       ├── step_contact.py         create  — Step 1: contact info
│       ├── step_enrollment.py      create  — Step 2: enrollment dates
│       ├── step_auths.py           create  — Step 3: auths & availability (skippable)
│       └── step_review.py         create  — Step 4: review + DB write transaction
├── db/
│   ├── __init__.py                 create
│   ├── members.py                  create  — get_all_members + INSERT/UPDATE/DELETE
│   └── events.py                   create  — SQLite schema, insert_event, query, TTL purge
└── tests/
    ├── test_settings.py            create
    ├── test_db_members.py          create
    └── test_db_events.py           create
```

**Note:** The spec calls for `QWizard`; this plan uses `QDialog + QStackedWidget` instead because QWizard's native rendering on Windows ignores QSS on navigation buttons and the titlebar area. The custom progress bar design requires full styling control.

---

## Task 1: Project Setup

**Files:**
- Create: `conftest.py`
- Create: `tests/__init__.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Add pytest and pytest-qt to requirements**

Edit `requirements.txt`:
```
PyQt6>=6.6.0
pyodbc>=5.0
pytest>=8.0
pytest-qt>=4.4
# install bsca-core locally:
# pip install -e "C:\Users\luald\OneDrive\Desktop\BSCA"
```

- [ ] **Step 2: Install pytest into the venv**

```
.venv\Scripts\pip install pytest pytest-qt
```

Expected: `Successfully installed pytest-...`

- [ ] **Step 3: Create conftest.py**

```python
# anchors pytest rootdir at the repo root
```

- [ ] **Step 4: Create tests/__init__.py**

```python
```

- [ ] **Step 5: Verify pytest discovers no tests yet**

```
.venv\Scripts\pytest --collect-only
```

Expected: `no tests ran`

- [ ] **Step 6: Commit**

```bash
git add conftest.py tests/ requirements.txt
git commit -m "chore: add pytest + pytest-qt, scaffold tests dir"
```

---

## Task 2: Settings Module

**Files:**
- Create: `settings.py`
- Create: `tests/test_settings.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_settings.py`:
```python
import json
from settings import load_settings, save_settings, DEFAULT_SETTINGS


def test_defaults_returned_when_file_missing(tmp_path):
    path = tmp_path / "settings.json"
    result = load_settings(str(path))
    assert result["db_path"] == ""
    assert result["theme"] == "dark"
    assert result["events_db_path"] == ""


def test_save_and_reload(tmp_path):
    path = tmp_path / "settings.json"
    data = {"db_path": "C:/data/test.accdb", "theme": "light", "events_db_path": ""}
    save_settings(data, str(path))
    result = load_settings(str(path))
    assert result["db_path"] == "C:/data/test.accdb"
    assert result["theme"] == "light"


def test_missing_keys_filled_with_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"theme": "light"}))
    result = load_settings(str(path))
    assert result["db_path"] == DEFAULT_SETTINGS["db_path"]
    assert result["theme"] == "light"
```

- [ ] **Step 2: Run to verify failure**

```
.venv\Scripts\pytest tests/test_settings.py -v
```

Expected: `ImportError: No module named 'settings'`

- [ ] **Step 3: Implement settings.py**

```python
import json
import os

DEFAULT_SETTINGS = {
    "db_path": "",
    "theme": "dark",
    "events_db_path": "",
}


def load_settings(path: str) -> dict:
    if not os.path.exists(path):
        return dict(DEFAULT_SETTINGS)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {**DEFAULT_SETTINGS, **data}


def save_settings(data: dict, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
```

- [ ] **Step 4: Run tests to verify pass**

```
.venv\Scripts\pytest tests/test_settings.py -v
```

Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add settings.py tests/test_settings.py requirements.txt
git commit -m "feat: add settings load/save module"
```

---

## Task 3: Events Database

**Files:**
- Create: `db/__init__.py`
- Create: `db/events.py`
- Create: `tests/test_db_events.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_db_events.py`:
```python
import sqlite3
from datetime import date, timedelta
from db.events import init_db, insert_event, query_events, purge_old_events, EVENT_TYPES


def make_db():
    conn = sqlite3.connect(":memory:")
    init_db(conn)
    return conn


def test_init_creates_table():
    conn = make_db()
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='events'")
    assert cursor.fetchone() is not None


def test_insert_and_query_all(tmp_path):
    conn = make_db()
    insert_event(conn, "NEW", 1001, "Smith, John", "Member added to system")
    rows = query_events(conn)
    assert len(rows) == 1
    assert rows[0]["event_type"] == "NEW"
    assert rows[0]["center_id"] == 1001
    assert rows[0]["member_name"] == "Smith, John"
    assert rows[0]["description"] == "Member added to system"


def test_query_by_center_id(tmp_path):
    conn = make_db()
    insert_event(conn, "AUTH", 1001, "Smith, John", "Auth added")
    insert_event(conn, "ABS",  1002, "Doe, Jane",  "Absence added")
    rows = query_events(conn, center_id=1001)
    assert len(rows) == 1
    assert rows[0]["center_id"] == 1001


def test_query_filter_text(tmp_path):
    conn = make_db()
    insert_event(conn, "EDIT", 1001, "Smith, John", "Health Plan changed: HOF → Anthem")
    insert_event(conn, "ABS",  1002, "Doe, Jane",   "Absence added: Medical")
    rows = query_events(conn, filter_text="Medical")
    assert len(rows) == 1
    assert rows[0]["center_id"] == 1002


def test_purge_deletes_old_rows():
    conn = make_db()
    old_ts = (date.today() - timedelta(days=31)).isoformat() + "T00:00:00"
    conn.execute(
        "INSERT INTO events (ts, event_type, center_id, member_name, description) VALUES (?,?,?,?,?)",
        (old_ts, "NEW", 999, "Old, Member", "old event"),
    )
    conn.commit()
    insert_event(conn, "NEW", 1001, "Smith, John", "recent event")
    purge_old_events(conn)
    rows = query_events(conn)
    assert len(rows) == 1
    assert rows[0]["center_id"] == 1001


def test_event_types_constants():
    for t in ("NEW", "EDIT", "AUTH", "ABS", "AVAIL", "ENROLL"):
        assert t in EVENT_TYPES
```

- [ ] **Step 2: Run to verify failure**

```
.venv\Scripts\pytest tests/test_db_events.py -v
```

Expected: `ImportError: No module named 'db'`

- [ ] **Step 3: Create db/__init__.py**

```python
```

- [ ] **Step 4: Implement db/events.py**

```python
import sqlite3
from datetime import date, datetime, timedelta

EVENT_TYPES = ("NEW", "EDIT", "AUTH", "ABS", "AVAIL", "ENROLL")

_CREATE = """
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    event_type  TEXT NOT NULL,
    center_id   INTEGER NOT NULL,
    member_name TEXT NOT NULL,
    description TEXT NOT NULL
)
"""


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(_CREATE)
    conn.commit()


def open_db(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def insert_event(
    conn: sqlite3.Connection,
    event_type: str,
    center_id: int,
    member_name: str,
    description: str,
) -> None:
    ts = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        "INSERT INTO events (ts, event_type, center_id, member_name, description) "
        "VALUES (?, ?, ?, ?, ?)",
        (ts, event_type, center_id, member_name, description),
    )
    conn.commit()


def query_events(
    conn: sqlite3.Connection,
    center_id: int | None = None,
    filter_text: str | None = None,
) -> list[dict]:
    sql = "SELECT id, ts, event_type, center_id, member_name, description FROM events"
    params: list = []
    clauses: list[str] = []
    if center_id is not None:
        clauses.append("center_id = ?")
        params.append(center_id)
    if filter_text:
        clauses.append("(member_name LIKE ? OR description LIKE ?)")
        like = f"%{filter_text}%"
        params += [like, like]
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY ts DESC"
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def purge_old_events(conn: sqlite3.Connection) -> None:
    cutoff = (date.today() - timedelta(days=30)).isoformat()
    conn.execute("DELETE FROM events WHERE ts < ?", (cutoff,))
    conn.commit()
```

- [ ] **Step 5: Run tests**

```
.venv\Scripts\pytest tests/test_db_events.py -v
```

Expected: `6 passed`

- [ ] **Step 6: Commit**

```bash
git add db/ tests/test_db_events.py
git commit -m "feat: add SQLite events DB with TTL purge"
```

---

## Task 4: Members DB Write Layer

**Files:**
- Create: `db/members.py`
- Create: `tests/test_db_members.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_db_members.py`:
```python
import pytest
from db.members import (
    ALL_MEMBERS_QUERY,
    INSERT_CONTACT,
    INSERT_ENROLLMENT,
    INSERT_AUTHORIZATION,
    INSERT_AVAILABILITY,
    INSERT_ABSENCE,
    encode_auth_days,
    decode_auth_days,
    get_all_members,
)


def test_all_members_query_selects_required_columns():
    for col in ("[Center ID]", "[Last Name]", "[First Name]", "[Health Plan]"):
        assert col in ALL_MEMBERS_QUERY
    assert "ORDER BY [Last Name]" in ALL_MEMBERS_QUERY


def test_insert_contact_targets_correct_table():
    assert "INSERT INTO [Contacts]" in INSERT_CONTACT
    for col in ("[Center ID]", "[Last Name]", "[First Name]", "[Health Plan]", "[Address]"):
        assert col in INSERT_CONTACT


def test_insert_enrollment_targets_correct_table():
    assert "INSERT INTO [Enrollment]" in INSERT_ENROLLMENT
    for col in ("[Center ID]", "[start_date]", "[end_date]"):
        assert col in INSERT_ENROLLMENT


def test_insert_authorization_targets_correct_table():
    assert "INSERT INTO [Authorization]" in INSERT_AUTHORIZATION
    for col in ("[Center ID]", "[auth_start]", "[auth_end]", "[auth_days]"):
        assert col in INSERT_AUTHORIZATION


def test_insert_availability_targets_correct_table():
    assert "INSERT INTO [Availability]" in INSERT_AVAILABILITY
    for col in ("[Center ID]", "[Day Of Week]", "[avail_start]", "[avail_end]"):
        assert col in INSERT_AVAILABILITY


def test_insert_absence_targets_correct_table():
    assert "INSERT INTO [Absences]" in INSERT_ABSENCE
    for col in ("[Center ID]", "[Leave Type]", "[Start_Date]", "[End_Date]"):
        assert col in INSERT_ABSENCE


def test_encode_auth_days_sorted():
    assert encode_auth_days({3, 1, 5}) == "1,3,5"


def test_encode_auth_days_empty():
    assert encode_auth_days(set()) == ""


def test_decode_auth_days_returns_set():
    assert decode_auth_days("1,3,5") == {1, 3, 5}


def test_decode_auth_days_empty_string():
    assert decode_auth_days("") == set()


def test_get_all_members_missing_db_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        get_all_members(str(tmp_path / "nope.accdb"))
```

- [ ] **Step 2: Run to verify failure**

```
.venv\Scripts\pytest tests/test_db_members.py -v
```

Expected: `ImportError: cannot import name 'ALL_MEMBERS_QUERY'`

- [ ] **Step 3: Implement db/members.py**

```python
"""Read/write helpers for the BSCA Access database.

Read connections reuse bsca-core's build_connection_string.
Write operations open their own connection with autocommit=False
so multiple INSERTs can be wrapped in a single transaction.
"""
import os
from datetime import date, datetime

from monthly_schedule.db import build_connection_string

HEALTH_PLANS = ("AE", "Aetna", "Anthem", "BCBS", "ES", "HC", "HF", "HOF", "VCM")

LEAVE_TYPES = (
    "Vacation", "Medical", "Hospitalization",
    "Family Emergency", "Holiday", "Other",
)

ALL_MEMBERS_QUERY = (
    "SELECT [Center ID], [Last Name], [First Name], [Health Plan] "
    "FROM [Contacts] ORDER BY [Last Name], [First Name]"
)

INSERT_CONTACT = (
    "INSERT INTO [Contacts] ([Center ID], [Last Name], [First Name], "
    "[Health Plan], [Address]) VALUES (?, ?, ?, ?, ?)"
)

UPDATE_CONTACT = (
    "UPDATE [Contacts] SET [Last Name]=?, [First Name]=?, "
    "[Health Plan]=?, [Address]=? WHERE [Center ID]=?"
)

INSERT_ENROLLMENT = (
    "INSERT INTO [Enrollment] ([Center ID], [start_date], [end_date]) "
    "VALUES (?, ?, ?)"
)

DELETE_ENROLLMENT = "DELETE FROM [Enrollment] WHERE [ID]=?"

INSERT_AUTHORIZATION = (
    "INSERT INTO [Authorization] ([Center ID], [auth_start], [auth_end], "
    "[effective_start], [effective_end], [auth_days]) VALUES (?, ?, ?, ?, ?, ?)"
)

DELETE_AUTHORIZATION = "DELETE FROM [Authorization] WHERE [ID]=?"

INSERT_AVAILABILITY = (
    "INSERT INTO [Availability] ([Center ID], [effective_start_date], "
    "[effective_end_date], [Day Of Week], [avail_start], [avail_end]) "
    "VALUES (?, ?, ?, ?, ?, ?)"
)

DELETE_AVAILABILITY = "DELETE FROM [Availability] WHERE [ID]=?"

INSERT_ABSENCE = (
    "INSERT INTO [Absences] ([Center ID], [Leave Type], [Start_Date], [End_Date]) "
    "VALUES (?, ?, ?, ?)"
)

DELETE_ABSENCE = "DELETE FROM [Absences] WHERE [ID]=?"


def encode_auth_days(days: set[int]) -> str:
    """Convert {1, 3, 5} → '1,3,5'. Empty set → ''."""
    return ",".join(str(d) for d in sorted(days))


def decode_auth_days(value: str) -> set[int]:
    """Convert '1,3,5' → {1, 3, 5}. Empty string → set()."""
    if not value:
        return set()
    return {int(x) for x in value.split(",") if x.strip()}


def _hhmm_to_datetime(hhmm: str) -> datetime:
    """'08:30' → datetime(1899, 12, 30, 8, 30) for Access DATETIME storage."""
    h, m = map(int, hhmm.split(":"))
    return datetime(1899, 12, 30, h, m)


def _connect(db_path: str):
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found: {db_path}")
    import pyodbc
    try:
        return pyodbc.connect(build_connection_string(db_path), autocommit=False)
    except pyodbc.Error as exc:
        raise RuntimeError(f"Could not open Access database: {exc}") from exc


def get_all_members(db_path: str) -> list[dict]:
    """Return all members as dicts with center_id, last_name, first_name, health_plan."""
    conn = _connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(ALL_MEMBERS_QUERY)
        return [
            {
                "center_id": int(row[0]),
                "last_name": row[1],
                "first_name": row[2],
                "health_plan": row[3],
            }
            for row in cursor.fetchall()
        ]
    finally:
        conn.close()


def center_id_exists(center_id: int, db_path: str) -> bool:
    conn = _connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM [Contacts] WHERE [Center ID]=?", center_id)
        return cursor.fetchone()[0] > 0
    finally:
        conn.close()


def insert_member(
    center_id: int,
    last_name: str,
    first_name: str,
    health_plan: str,
    address: str,
    enrollment_start: date,
    enrollment_end: date | None,
    authorization: dict | None,
    availability_rows: list[dict],
    db_path: str,
) -> None:
    """Insert a new member and all related records in one transaction.

    authorization dict keys: auth_start, auth_end, effective_start (opt),
        effective_end (opt), auth_days (set[int]).
    availability_rows list item keys: day_of_week (int), avail_start (str HH:MM),
        avail_end (str HH:MM), effective_start_date (date), effective_end_date (date|None).
    """
    conn = _connect(db_path)
    try:
        c = conn.cursor()
        c.execute(INSERT_CONTACT, (center_id, last_name, first_name, health_plan, address))
        c.execute(INSERT_ENROLLMENT, (center_id, enrollment_start, enrollment_end))
        if authorization:
            c.execute(
                INSERT_AUTHORIZATION,
                (
                    center_id,
                    authorization["auth_start"],
                    authorization["auth_end"],
                    authorization.get("effective_start"),
                    authorization.get("effective_end"),
                    encode_auth_days(authorization["auth_days"]),
                ),
            )
        for row in availability_rows:
            c.execute(
                INSERT_AVAILABILITY,
                (
                    center_id,
                    row["effective_start_date"],
                    row.get("effective_end_date"),
                    row["day_of_week"],
                    _hhmm_to_datetime(row["avail_start"]),
                    _hhmm_to_datetime(row["avail_end"]),
                ),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def update_contact(
    center_id: int,
    last_name: str,
    first_name: str,
    health_plan: str,
    address: str,
    db_path: str,
) -> None:
    conn = _connect(db_path)
    try:
        conn.cursor().execute(
            UPDATE_CONTACT, (last_name, first_name, health_plan, address, center_id)
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def insert_enrollment(center_id: int, start: date, end: date | None, db_path: str) -> None:
    conn = _connect(db_path)
    try:
        conn.cursor().execute(INSERT_ENROLLMENT, (center_id, start, end))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_enrollment(record_id: int, db_path: str) -> None:
    conn = _connect(db_path)
    try:
        conn.cursor().execute(DELETE_ENROLLMENT, (record_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def insert_authorization(
    center_id: int,
    auth_start: date,
    auth_end: date,
    auth_days: set[int],
    effective_start: date | None,
    effective_end: date | None,
    db_path: str,
) -> None:
    conn = _connect(db_path)
    try:
        conn.cursor().execute(
            INSERT_AUTHORIZATION,
            (center_id, auth_start, auth_end, effective_start, effective_end,
             encode_auth_days(auth_days)),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_authorization(record_id: int, db_path: str) -> None:
    conn = _connect(db_path)
    try:
        conn.cursor().execute(DELETE_AUTHORIZATION, (record_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def insert_availability(
    center_id: int,
    day_of_week: int,
    avail_start: str,
    avail_end: str,
    effective_start: date,
    effective_end: date | None,
    db_path: str,
) -> None:
    conn = _connect(db_path)
    try:
        conn.cursor().execute(
            INSERT_AVAILABILITY,
            (center_id, effective_start, effective_end, day_of_week,
             _hhmm_to_datetime(avail_start), _hhmm_to_datetime(avail_end)),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_availability(record_id: int, db_path: str) -> None:
    conn = _connect(db_path)
    try:
        conn.cursor().execute(DELETE_AVAILABILITY, (record_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def insert_absence(
    center_id: int,
    leave_type: str,
    start: date,
    end: date,
    db_path: str,
) -> None:
    conn = _connect(db_path)
    try:
        conn.cursor().execute(INSERT_ABSENCE, (center_id, leave_type, start, end))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_absence(record_id: int, db_path: str) -> None:
    conn = _connect(db_path)
    try:
        conn.cursor().execute(DELETE_ABSENCE, (record_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

- [ ] **Step 4: Run tests**

```
.venv\Scripts\pytest tests/test_db_members.py -v
```

Expected: `10 passed`

- [ ] **Step 5: Commit**

```bash
git add db/members.py tests/test_db_members.py
git commit -m "feat: add Access DB write layer (members, enrollments, auths, availability, absences)"
```

---

## Task 5: Theme System

**Files:**
- Create: `gui/theme.py`

- [ ] **Step 1: Create gui/theme.py**

```python
"""Dark/light theme tokens and QSS generator.

Colors are pre-converted from OKLCH to sRGB hex. Call apply_theme(app, "dark")
or apply_theme(app, "light") to swap at runtime.
"""

DARK = {
    "bg":           "#141519",
    "surface":      "#181b20",
    "raised":       "#1e2128",
    "border":       "#282c38",
    "border_mid":   "#232730",
    "text":         "#dde0f2",
    "text2":        "#757a98",
    "text3":        "#434760",
    "text4":        "#31354a",
    "accent":       "#5b7cf4",
    "accent_hover": "#6e8cf6",
    "accent_bg":    "#1c2040",
    "accent_text":  "#92b4ff",
    "success":      "#3d9e6e",
    "success_bg":   "#182e22",
    "warning":      "#c08a2a",
    "warning_bg":   "#281f0a",
    "error":        "#d05555",
    "error_bg":     "#2e1515",
    "error_text":   "#e08080",
}

LIGHT = {
    "bg":           "#f5f6fa",
    "surface":      "#eaebf0",
    "raised":       "#fdfefe",
    "border":       "#ced1e0",
    "border_mid":   "#dfe0e8",
    "text":         "#252838",
    "text2":        "#515670",
    "text3":        "#7e8090",
    "text4":        "#a8aab8",
    "accent":       "#3b5ce0",
    "accent_hover": "#2e4ec2",
    "accent_bg":    "#e5eafc",
    "accent_text":  "#2c47b8",
    "success":      "#1e7a4e",
    "success_bg":   "#e8f5ee",
    "warning":      "#876010",
    "warning_bg":   "#f5f0e0",
    "error":        "#b83a3a",
    "error_bg":     "#f5e8e8",
    "error_text":   "#902a2a",
}


def build_qss(t: dict) -> str:
    return f"""
QMainWindow, QDialog, QWidget {{
    background-color: {t['bg']};
    color: {t['text']};
    font-family: "Segoe UI", system-ui, sans-serif;
    font-size: 13px;
}}
QWidget#sidebar {{
    background-color: {t['surface']};
    border-right: 1px solid {t['border_mid']};
}}
QWidget#detail {{
    background-color: {t['bg']};
}}
QPushButton {{
    background-color: {t['raised']};
    color: {t['text2']};
    border: 1px solid {t['border']};
    border-radius: 7px;
    padding: 7px 16px;
    font-size: 12px;
    font-weight: 500;
}}
QPushButton:hover {{
    background-color: {t['border']};
    color: {t['text']};
}}
QPushButton:pressed {{
    background-color: {t['border_mid']};
}}
QPushButton:disabled {{
    color: {t['text4']};
    background-color: {t['surface']};
    border-color: {t['border_mid']};
}}
QPushButton#btn_primary {{
    background-color: {t['accent']};
    color: #ffffff;
    border: none;
    font-weight: 600;
}}
QPushButton#btn_primary:hover {{
    background-color: {t['accent_hover']};
}}
QPushButton#btn_add {{
    background-color: {t['accent']};
    color: #ffffff;
    border: none;
    font-weight: 600;
    border-radius: 7px;
    padding: 8px 12px;
    font-size: 12px;
}}
QPushButton#btn_add:hover {{
    background-color: {t['accent_hover']};
}}
QPushButton#btn_save {{
    background-color: {t['success']};
    color: #ffffff;
    border: none;
    font-weight: 600;
}}
QPushButton#btn_save:hover {{
    background-color: {t['success']};
    opacity: 0.9;
}}
QLineEdit, QComboBox, QDateEdit, QTimeEdit, QSpinBox {{
    background-color: {t['raised']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: 5px;
    padding: 7px 10px;
    font-size: 12px;
    selection-background-color: {t['accent_bg']};
    selection-color: {t['text']};
}}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QTimeEdit:focus {{
    border-color: {t['accent']};
}}
QLineEdit:read-only {{
    background-color: {t['surface']};
    color: {t['text3']};
    border-style: dashed;
}}
QComboBox::drop-down {{
    border: none;
    padding-right: 8px;
}}
QComboBox QAbstractItemView {{
    background-color: {t['raised']};
    color: {t['text']};
    border: 1px solid {t['border']};
    selection-background-color: {t['accent_bg']};
}}
QListWidget {{
    background-color: transparent;
    border: none;
    outline: none;
}}
QListWidget::item {{
    border-radius: 5px;
    padding: 7px 9px;
    color: {t['text2']};
}}
QListWidget::item:hover {{
    background-color: {t['raised']};
}}
QListWidget::item:selected {{
    background-color: {t['accent_bg']};
    color: {t['accent_text']};
}}
QTabWidget::pane {{
    border-top: 1px solid {t['border_mid']};
    background-color: {t['bg']};
}}
QTabBar::tab {{
    background-color: transparent;
    color: {t['text3']};
    padding: 6px 14px;
    border-bottom: 2px solid transparent;
    font-size: 11px;
    font-weight: 500;
}}
QTabBar::tab:selected {{
    color: {t['accent_text']};
    border-bottom-color: {t['accent']};
}}
QTabBar::tab:hover:!selected {{
    color: {t['text2']};
}}
QLabel {{
    background-color: transparent;
    color: {t['text']};
}}
QLabel#label_field {{
    color: {t['text3']};
    font-size: 10px;
    font-weight: 600;
}}
QLabel#warning_badge {{
    background-color: {t['error_bg']};
    color: {t['error_text']};
    border: 1px solid {t['error']};
    border-radius: 10px;
    padding: 3px 10px;
    font-size: 10px;
    font-weight: 500;
}}
QScrollBar:vertical {{
    background: {t['surface']};
    width: 6px;
    border: none;
}}
QScrollBar::handle:vertical {{
    background: {t['border']};
    border-radius: 3px;
    min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QTableWidget {{
    background-color: {t['bg']};
    color: {t['text']};
    border: 1px solid {t['border_mid']};
    border-radius: 7px;
    gridline-color: {t['border_mid']};
    font-size: 12px;
}}
QTableWidget::item {{
    padding: 6px 10px;
}}
QTableWidget::item:selected {{
    background-color: {t['accent_bg']};
    color: {t['text']};
}}
QHeaderView::section {{
    background-color: {t['surface']};
    color: {t['text3']};
    border: none;
    border-bottom: 1px solid {t['border_mid']};
    padding: 6px 10px;
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}}
"""


def apply_theme(app, theme_name: str) -> None:
    """Apply 'dark' or 'light' QSS to the entire application."""
    tokens = DARK if theme_name == "dark" else LIGHT
    app.setStyleSheet(build_qss(tokens))
```

- [ ] **Step 2: Verify QSS syntax by importing**

```
.venv\Scripts\python -c "from gui.theme import build_qss, DARK; print(len(build_qss(DARK)), 'chars')"
```

Expected: prints a char count > 2000

- [ ] **Step 3: Commit**

```bash
git add gui/theme.py
git commit -m "feat: add dark/light theme QSS system"
```

---

## Task 6: Main Window Shell

**Files:**
- Modify: `member_manager.py`
- Modify: `gui/main_window.py`

- [ ] **Step 1: Rewrite member_manager.py**

```python
import sys
import os
from PyQt6.QtWidgets import QApplication, QMessageBox
from gui.main_window import MainWindow
from gui.theme import apply_theme
from settings import load_settings

SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "bsca_members_settings.json")


def main():
    app = QApplication(sys.argv)
    settings = load_settings(SETTINGS_PATH)
    apply_theme(app, settings.get("theme", "dark"))
    window = MainWindow(settings, SETTINGS_PATH)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Rewrite gui/main_window.py**

```python
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter,
    QListWidget, QListWidgetItem, QPushButton, QLineEdit, QLabel,
    QStackedWidget, QApplication, QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon

from settings import save_settings
from gui.settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    def __init__(self, settings: dict, settings_path: str):
        super().__init__()
        self._settings = settings
        self._settings_path = settings_path
        self.setWindowTitle("BSCA Member Manager")
        self.resize(1000, 640)
        self._build_ui()
        self._load_members()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Sidebar ──────────────────────────────────────────
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(10, 10, 10, 10)
        sidebar_layout.setSpacing(6)

        self._btn_add = QPushButton("+ Add New Member")
        self._btn_add.setObjectName("btn_add")
        self._btn_add.clicked.connect(self._open_wizard)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search members…")
        self._search.textChanged.connect(self._filter_members)

        self._member_list = QListWidget()
        self._member_list.currentRowChanged.connect(self._on_member_selected)

        self._btn_events = QPushButton("All Events")
        self._btn_events.clicked.connect(self._show_global_events)

        sidebar_layout.addWidget(self._btn_add)
        sidebar_layout.addWidget(self._search)
        sidebar_layout.addWidget(self._member_list)
        sidebar_layout.addWidget(self._btn_events)

        # ── Detail panel ─────────────────────────────────────
        self._detail_stack = QStackedWidget()
        self._detail_stack.setObjectName("detail")

        self._placeholder = QLabel("Select a member to view details.")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._detail_stack.addWidget(self._placeholder)  # index 0

        # ── Titlebar gear ─────────────────────────────────────
        toolbar = self.addToolBar("Main")
        toolbar.setMovable(False)
        btn_settings = QPushButton("⚙")
        btn_settings.setFixedSize(32, 32)
        btn_settings.clicked.connect(self._open_settings)
        toolbar.addWidget(btn_settings)

        root.addWidget(sidebar)
        root.addWidget(self._detail_stack)

    def _load_members(self):
        self._all_members = []
        db_path = self._settings.get("db_path", "")
        if not db_path:
            return
        try:
            from db.members import get_all_members
            self._all_members = get_all_members(db_path)
        except Exception as exc:
            QMessageBox.critical(self, "Database Error",
                f"Could not load members:\n{exc}\n\nCheck Settings.")
        self._populate_list(self._all_members)

    def _populate_list(self, members: list[dict]):
        self._member_list.clear()
        for m in members:
            label = f"{m['last_name']}, {m['first_name']}\n{m['center_id']} · {m['health_plan']}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, m["center_id"])
            self._member_list.addItem(item)

    def _filter_members(self, text: str):
        q = text.lower()
        filtered = [
            m for m in self._all_members
            if q in m["last_name"].lower()
            or q in m["first_name"].lower()
            or q in str(m["center_id"])
        ]
        self._populate_list(filtered)

    def _on_member_selected(self, row: int):
        if row < 0:
            return
        item = self._member_list.item(row)
        if item is None:
            return
        center_id = item.data(Qt.ItemDataRole.UserRole)
        self._show_member(center_id)

    def _show_member(self, center_id: int):
        # Lazy import to avoid circular; MemberTabs added in Task 9
        from gui.member_tabs import MemberTabsWidget
        db_path = self._settings.get("db_path", "")
        events_path = self._settings.get("events_db_path", "")
        widget = MemberTabsWidget(center_id, db_path, events_path)
        self._set_detail(widget)

    def _set_detail(self, widget: QWidget):
        # Replace current detail widget (index >0) if present
        while self._detail_stack.count() > 1:
            w = self._detail_stack.widget(1)
            self._detail_stack.removeWidget(w)
            w.deleteLater()
        self._detail_stack.addWidget(widget)
        self._detail_stack.setCurrentIndex(1)

    def _show_global_events(self):
        from gui.events_view import GlobalEventsWidget
        events_path = self._settings.get("events_db_path", "")
        widget = GlobalEventsWidget(events_path)
        self._set_detail(widget)

    def _open_wizard(self):
        db_path = self._settings.get("db_path", "")
        if not db_path:
            QMessageBox.warning(self, "No Database",
                "Set a database path in Settings before adding members.")
            return
        from gui.wizard.wizard import AddMemberWizard
        events_path = self._settings.get("events_db_path", "")
        dlg = AddMemberWizard(db_path, events_path, self)
        if dlg.exec():
            self._load_members()

    def _open_settings(self):
        dlg = SettingsDialog(self._settings, self)
        if dlg.exec():
            self._settings.update(dlg.result_settings())
            save_settings(self._settings, self._settings_path)
            from gui.theme import apply_theme
            apply_theme(QApplication.instance(), self._settings["theme"])
            self._load_members()
```

- [ ] **Step 3: Run the app to verify it launches without crashing**

```
.venv\Scripts\python member_manager.py
```

Expected: Window opens with empty sidebar and "Select a member" placeholder. No exceptions.

- [ ] **Step 4: Commit**

```bash
git add member_manager.py gui/main_window.py
git commit -m "feat: wire MainWindow shell with sidebar, theme, and settings hook"
```

---

## Task 7: Settings Dialog

**Files:**
- Create: `gui/settings_dialog.py`

- [ ] **Step 1: Create gui/settings_dialog.py**

```python
from PyQt6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QPushButton, QHBoxLayout,
    QVBoxLayout, QRadioButton, QButtonGroup, QFileDialog, QDialogButtonBox,
    QLabel, QWidget,
)
from PyQt6.QtCore import Qt


class SettingsDialog(QDialog):
    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(480)
        self._settings = dict(settings)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)

        # DB path
        db_row = QWidget()
        db_hl = QHBoxLayout(db_row)
        db_hl.setContentsMargins(0, 0, 0, 0)
        self._db_path = QLineEdit(self._settings.get("db_path", ""))
        btn_browse_db = QPushButton("Browse…")
        btn_browse_db.clicked.connect(self._browse_db)
        db_hl.addWidget(self._db_path)
        db_hl.addWidget(btn_browse_db)
        form.addRow("Database path:", db_row)

        # Events DB path
        ev_row = QWidget()
        ev_hl = QHBoxLayout(ev_row)
        ev_hl.setContentsMargins(0, 0, 0, 0)
        self._events_path = QLineEdit(self._settings.get("events_db_path", ""))
        btn_browse_ev = QPushButton("Browse…")
        btn_browse_ev.clicked.connect(self._browse_events)
        ev_hl.addWidget(self._events_path)
        ev_hl.addWidget(btn_browse_ev)
        form.addRow("Events log path:", ev_row)

        # Theme
        theme_row = QWidget()
        theme_hl = QHBoxLayout(theme_row)
        theme_hl.setContentsMargins(0, 0, 0, 0)
        self._radio_dark = QRadioButton("Dark")
        self._radio_light = QRadioButton("Light")
        self._theme_group = QButtonGroup()
        self._theme_group.addButton(self._radio_dark)
        self._theme_group.addButton(self._radio_light)
        if self._settings.get("theme", "dark") == "light":
            self._radio_light.setChecked(True)
        else:
            self._radio_dark.setChecked(True)
        theme_hl.addWidget(self._radio_dark)
        theme_hl.addWidget(self._radio_light)
        form.addRow("Theme:", theme_row)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse_db(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Database", "", "Access Databases (*.accdb *.mdb)"
        )
        if path:
            self._db_path.setText(path)

    def _browse_events(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Events Log Location", "events.db", "SQLite (*.db)"
        )
        if path:
            self._events_path.setText(path)

    def result_settings(self) -> dict:
        return {
            "db_path": self._db_path.text().strip(),
            "events_db_path": self._events_path.text().strip(),
            "theme": "light" if self._radio_light.isChecked() else "dark",
        }
```

- [ ] **Step 2: Smoke-test by opening settings from the running app**

```
.venv\Scripts\python member_manager.py
```

Click ⚙. Verify the Settings dialog opens with all three fields. Click Cancel.

- [ ] **Step 3: Commit**

```bash
git add gui/settings_dialog.py
git commit -m "feat: add settings dialog (db path, events path, theme toggle)"
```

---

## Task 8: Member Tabs Shell + Warning Badge

**Files:**
- Create: `gui/member_tabs.py`

- [ ] **Step 1: Create gui/member_tabs.py skeleton**

```python
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel,
    QPushButton, QMessageBox,
)
from PyQt6.QtCore import Qt

from monthly_schedule.db import (
    get_member, get_enrollments, get_authorizations,
    get_availability, get_absences,
)


class MemberTabsWidget(QWidget):
    def __init__(self, center_id: int, db_path: str, events_path: str, parent=None):
        super().__init__(parent)
        self._center_id = center_id
        self._db_path = db_path
        self._events_path = events_path
        self._member = None
        self._load_data()
        self._build_ui()

    def _load_data(self):
        try:
            self._member = get_member(self._center_id, self._db_path)
            self._enrollments = get_enrollments(self._center_id, self._db_path)
            self._authorizations = get_authorizations(self._center_id, self._db_path)
            self._availability = get_availability(self._center_id, self._db_path)
            self._absences = get_absences(self._center_id, self._db_path)
        except Exception as exc:
            QMessageBox.critical(self, "Load Error", str(exc))
            self._member = {}
            self._enrollments = self._authorizations = []
            self._availability = self._absences = []

    def _missing(self) -> list[str]:
        missing = []
        if not self._authorizations:
            missing.append("Authorizations")
        if not self._availability:
            missing.append("Availability")
        return missing

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 12)
        layout.setSpacing(12)

        # Header row
        header = QHBoxLayout()
        name = f"{self._member.get('last_name', '')}, {self._member.get('first_name', '')}"
        cid = str(self._center_id)
        name_label = QLabel(f"<b style='font-size:15px'>{name}</b>"
                            f"<span style='color:gray;font-size:12px'> &nbsp;ID {cid}</span>")
        name_label.setTextFormat(Qt.TextFormat.RichText)
        header.addWidget(name_label)
        header.addStretch()

        missing = self._missing()
        if missing:
            badge = QLabel("⚠ Missing: " + ", ".join(missing))
            badge.setObjectName("warning_badge")
            header.addWidget(badge)

        layout.addLayout(header)

        # Tabs
        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        self._tab_info = self._make_info_tab()
        self._tab_enrollments = self._make_placeholder_tab("Enrollments")
        self._tab_auths = self._make_placeholder_tab("Authorizations")
        self._tab_avail = self._make_placeholder_tab("Availability")
        self._tab_absences = self._make_placeholder_tab("Absences")
        self._tab_events = self._make_placeholder_tab("Events")

        self._tabs.addTab(self._tab_info, "Info")
        self._tabs.addTab(self._tab_enrollments, "Enrollments")
        self._tabs.addTab(self._tab_auths,
            "Auths ⚠" if "Authorizations" in missing else "Authorizations")
        self._tabs.addTab(self._tab_avail,
            "Availability ⚠" if "Availability" in missing else "Availability")
        self._tabs.addTab(self._tab_absences, "Absences")
        self._tabs.addTab(self._tab_events, "Events")

    def _make_placeholder_tab(self, name: str) -> QWidget:
        w = QWidget()
        lbl = QLabel(f"{name} — coming soon")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        QVBoxLayout(w).addWidget(lbl)
        return w

    def _make_info_tab(self) -> QWidget:
        # Filled in Task 9
        return self._make_placeholder_tab("Info")
```

- [ ] **Step 2: Run app, set a valid DB path in Settings, click a member**

```
.venv\Scripts\python member_manager.py
```

Expected: clicking a member shows the tab shell with name header. Warning badge visible if auths/availability missing.

- [ ] **Step 3: Commit**

```bash
git add gui/member_tabs.py
git commit -m "feat: member tabs shell with warning badge"
```

---

## Task 9: Info Tab

**Files:**
- Modify: `gui/member_tabs.py`

- [ ] **Step 1: Replace `_make_info_tab` in MemberTabsWidget**

Replace the `_make_info_tab` method:
```python
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QComboBox, QPushButton, QLabel, QSizePolicy,
)
from db.members import HEALTH_PLANS, update_contact
```

Add the import at the top of `member_tabs.py`, then replace the method:

```python
def _make_info_tab(self) -> QWidget:
    from db.members import HEALTH_PLANS, update_contact
    w = QWidget()
    outer = QVBoxLayout(w)
    outer.setContentsMargins(0, 12, 0, 0)

    form = QFormLayout()
    form.setSpacing(12)
    form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

    self._info_first = QLineEdit(self._member.get("first_name", ""))
    self._info_last = QLineEdit(self._member.get("last_name", ""))
    self._info_plan = QComboBox()
    self._info_plan.addItems(HEALTH_PLANS)
    current_plan = self._member.get("health_plan", "")
    idx = self._info_plan.findText(current_plan)
    if idx >= 0:
        self._info_plan.setCurrentIndex(idx)
    self._info_cid = QLineEdit(str(self._center_id))
    self._info_cid.setReadOnly(True)
    self._info_address = QLineEdit(self._member.get("address", "") or "")

    for lbl, widget in [
        ("First Name", self._info_first),
        ("Last Name", self._info_last),
        ("Health Plan", self._info_plan),
        ("Center ID", self._info_cid),
        ("Address", self._info_address),
    ]:
        form.addRow(lbl, widget)

    outer.addLayout(form)
    outer.addStretch()

    btn_row = QHBoxLayout()
    btn_row.addStretch()
    btn_discard = QPushButton("Discard")
    btn_discard.clicked.connect(self._discard_info)
    btn_save = QPushButton("Save Changes")
    btn_save.setObjectName("btn_save")
    btn_save.clicked.connect(self._save_info)
    btn_row.addWidget(btn_discard)
    btn_row.addWidget(btn_save)
    outer.addLayout(btn_row)
    return w


def _discard_info(self):
    self._info_first.setText(self._member.get("first_name", ""))
    self._info_last.setText(self._member.get("last_name", ""))
    self._info_address.setText(self._member.get("address", "") or "")
    plan = self._member.get("health_plan", "")
    idx = self._info_plan.findText(plan)
    if idx >= 0:
        self._info_plan.setCurrentIndex(idx)


def _save_info(self):
    from db.members import update_contact
    from db.events import open_db, insert_event
    old = self._member
    new_first = self._info_first.text().strip()
    new_last = self._info_last.text().strip()
    new_plan = self._info_plan.currentText()
    new_address = self._info_address.text().strip()

    changes = []
    if new_first != (old.get("first_name") or ""):
        changes.append(f"First Name: {old.get('first_name')} → {new_first}")
    if new_last != (old.get("last_name") or ""):
        changes.append(f"Last Name: {old.get('last_name')} → {new_last}")
    if new_plan != (old.get("health_plan") or ""):
        changes.append(f"Health Plan: {old.get('health_plan')} → {new_plan}")
    if new_address != (old.get("address") or ""):
        changes.append("Address updated")

    if not changes:
        return

    try:
        update_contact(self._center_id, new_last, new_first, new_plan,
                       new_address, self._db_path)
        self._member["first_name"] = new_first
        self._member["last_name"] = new_last
        self._member["health_plan"] = new_plan
        self._member["address"] = new_address
        if self._events_path:
            conn = open_db(self._events_path)
            insert_event(conn, "EDIT", self._center_id,
                f"{new_last}, {new_first}", "; ".join(changes))
            conn.close()
    except Exception as exc:
        QMessageBox.critical(self, "Save Error", str(exc))
```

- [ ] **Step 2: Smoke-test info tab**

```
.venv\Scripts\python member_manager.py
```

Select a member → Info tab shows fields. Change a value → Save Changes → no error.

- [ ] **Step 3: Commit**

```bash
git add gui/member_tabs.py
git commit -m "feat: info tab with save/discard and EDIT event logging"
```

---

## Task 10: Enrollments, Authorizations, Availability, Absences Tabs

**Files:**
- Modify: `gui/member_tabs.py`

All four tabs follow the same pattern: a `QTableWidget` showing existing rows, an "Add" button that opens an inline row or small dialog, and a "Delete" button for the selected row.

- [ ] **Step 1: Add table tab helper to MemberTabsWidget**

Add this helper method to `MemberTabsWidget`:

```python
def _make_table_tab(
    self,
    columns: list[str],
    rows: list[list],
    on_add,
    on_delete,
) -> QWidget:
    from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QAbstractItemView
    w = QWidget()
    layout = QVBoxLayout(w)
    layout.setContentsMargins(0, 12, 0, 0)

    table = QTableWidget(len(rows), len(columns))
    table.setHorizontalHeaderLabels(columns)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.horizontalHeader().setStretchLastSection(True)
    table.verticalHeader().setVisible(False)

    for r, row_data in enumerate(rows):
        for c, val in enumerate(row_data):
            table.setItem(r, c, QTableWidgetItem(str(val) if val is not None else ""))

    layout.addWidget(table)

    btn_row = QHBoxLayout()
    btn_add = QPushButton("+ Add")
    btn_add.clicked.connect(on_add)
    btn_del = QPushButton("Delete Selected")
    btn_del.clicked.connect(lambda: on_delete(table))
    btn_row.addWidget(btn_add)
    btn_row.addStretch()
    btn_row.addWidget(btn_del)
    layout.addLayout(btn_row)
    return w, table
```

- [ ] **Step 2: Replace Enrollments placeholder tab**

Replace `_make_placeholder_tab("Enrollments")` call with `_make_enrollments_tab()` and add:

```python
def _make_enrollments_tab(self) -> QWidget:
    rows = [
        [e["id"], str(e["start_date"]), str(e["end_date"]) if e["end_date"] else "ongoing"]
        for e in self._enrollments
    ]
    w, self._enroll_table = self._make_table_tab(
        ["ID", "Start Date", "End Date"],
        rows,
        self._add_enrollment,
        self._delete_enrollment,
    )
    return w


def _add_enrollment(self):
    from PyQt6.QtWidgets import QDialog, QFormLayout, QDateEdit, QDialogButtonBox
    from PyQt6.QtCore import QDate
    from db.members import insert_enrollment
    from db.events import open_db, insert_event

    dlg = QDialog(self)
    dlg.setWindowTitle("Add Enrollment")
    form = QFormLayout(dlg)
    start = QDateEdit(QDate.currentDate())
    start.setCalendarPopup(True)
    end = QDateEdit()
    end.setCalendarPopup(True)
    end.setSpecialValueText("Ongoing")
    end.setDate(QDate(2000, 1, 1))
    form.addRow("Start Date:", start)
    form.addRow("End Date (optional):", end)
    btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                            QDialogButtonBox.StandardButton.Cancel)
    btns.accepted.connect(dlg.accept)
    btns.rejected.connect(dlg.reject)
    form.addRow(btns)
    if dlg.exec():
        from datetime import date
        s = start.date().toPyDate()
        e = end.date().toPyDate() if end.date() != QDate(2000, 1, 1) else None
        try:
            insert_enrollment(self._center_id, s, e, self._db_path)
            self._enrollments = __import__(
                "monthly_schedule.db", fromlist=["get_enrollments"]
            ).get_enrollments(self._center_id, self._db_path)
            self._refresh_tab(1, self._make_enrollments_tab())
            if self._events_path:
                conn = open_db(self._events_path)
                member = self._member
                insert_event(conn, "ENROLL", self._center_id,
                    f"{member.get('last_name')}, {member.get('first_name')}",
                    f"Enrollment added: {s} – {e or 'ongoing'}")
                conn.close()
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))


def _delete_enrollment(self, table):
    row = table.currentRow()
    if row < 0:
        return
    record_id = int(table.item(row, 0).text())
    if QMessageBox.question(self, "Confirm", "Delete this enrollment record?") \
            == QMessageBox.StandardButton.Yes:
        from db.members import delete_enrollment
        try:
            delete_enrollment(record_id, self._db_path)
            self._enrollments = [e for e in self._enrollments if e["id"] != record_id]
            self._refresh_tab(1, self._make_enrollments_tab())
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))


def _refresh_tab(self, index: int, new_widget: QWidget):
    old = self._tabs.widget(index)
    label = self._tabs.tabText(index)
    self._tabs.removeTab(index)
    self._tabs.insertTab(index, new_widget, label)
    self._tabs.setCurrentIndex(index)
    if old:
        old.deleteLater()
```

- [ ] **Step 3: Replace Authorizations placeholder tab**

```python
def _make_auths_tab(self) -> QWidget:
    rows = [
        [
            a["id"],
            str(a["auth_start"]), str(a["auth_end"]),
            a["auth_days"] or "",
        ]
        for a in self._authorizations
    ]
    w, self._auth_table = self._make_table_tab(
        ["ID", "Auth Start", "Auth End", "Days (1=Mon…5=Fri)"],
        rows,
        self._add_auth,
        self._delete_auth,
    )
    return w


def _add_auth(self):
    from PyQt6.QtWidgets import (
        QDialog, QFormLayout, QDateEdit, QCheckBox,
        QHBoxLayout, QDialogButtonBox, QWidget,
    )
    from PyQt6.QtCore import QDate
    from db.members import insert_authorization, encode_auth_days
    from db.events import open_db, insert_event

    dlg = QDialog(self)
    dlg.setWindowTitle("Add Authorization")
    form = QFormLayout(dlg)

    auth_start = QDateEdit(QDate.currentDate())
    auth_start.setCalendarPopup(True)
    auth_end = QDateEdit(QDate.currentDate().addYears(1))
    auth_end.setCalendarPopup(True)

    day_checks = {}
    days_widget = QWidget()
    days_hl = QHBoxLayout(days_widget)
    days_hl.setContentsMargins(0, 0, 0, 0)
    for num, label in [(1, "Mon"), (2, "Tue"), (3, "Wed"), (4, "Thu"), (5, "Fri")]:
        cb = QCheckBox(label)
        day_checks[num] = cb
        days_hl.addWidget(cb)

    form.addRow("Auth Start:", auth_start)
    form.addRow("Auth End:", auth_end)
    form.addRow("Days:", days_widget)

    btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                            QDialogButtonBox.StandardButton.Cancel)
    btns.accepted.connect(dlg.accept)
    btns.rejected.connect(dlg.reject)
    form.addRow(btns)

    if dlg.exec():
        selected_days = {n for n, cb in day_checks.items() if cb.isChecked()}
        if not selected_days:
            QMessageBox.warning(self, "Validation", "Select at least one day.")
            return
        try:
            insert_authorization(
                self._center_id,
                auth_start.date().toPyDate(),
                auth_end.date().toPyDate(),
                selected_days, None, None, self._db_path,
            )
            self._authorizations = __import__(
                "monthly_schedule.db", fromlist=["get_authorizations"]
            ).get_authorizations(self._center_id, self._db_path)
            self._refresh_tab(2, self._make_auths_tab())
            if self._events_path:
                conn = open_db(self._events_path)
                m = self._member
                insert_event(conn, "AUTH", self._center_id,
                    f"{m.get('last_name')}, {m.get('first_name')}",
                    f"Auth added: {auth_start.date().toString('MM/dd/yyyy')} – "
                    f"{auth_end.date().toString('MM/dd/yyyy')} · "
                    f"{encode_auth_days(selected_days)}")
                conn.close()
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))


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
            self._authorizations = [a for a in self._authorizations if a["id"] != record_id]
            self._refresh_tab(2, self._make_auths_tab())
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
```

- [ ] **Step 4: Replace Availability placeholder tab**

```python
def _make_avail_tab(self) -> QWidget:
    day_names = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri"}
    rows = [
        [
            a["id"],
            day_names.get(a["day_of_week"], str(a["day_of_week"])),
            a["avail_start"] or "", a["avail_end"] or "",
            str(a["effective_start_date"]),
        ]
        for a in self._availability
    ]
    w, self._avail_table = self._make_table_tab(
        ["ID", "Day", "Start", "End", "Effective From"],
        rows,
        self._add_avail,
        self._delete_avail,
    )
    return w


def _add_avail(self):
    from PyQt6.QtWidgets import (
        QDialog, QFormLayout, QComboBox, QTimeEdit, QDateEdit, QDialogButtonBox,
    )
    from PyQt6.QtCore import QDate, QTime
    from db.members import insert_availability
    from db.events import open_db, insert_event

    dlg = QDialog(self)
    dlg.setWindowTitle("Add Availability")
    form = QFormLayout(dlg)

    day_combo = QComboBox()
    for num, name in [(1, "Mon"), (2, "Tue"), (3, "Wed"), (4, "Thu"), (5, "Fri")]:
        day_combo.addItem(name, num)

    t_start = QTimeEdit(QTime(8, 0))
    t_end = QTimeEdit(QTime(16, 0))
    eff_start = QDateEdit(QDate.currentDate())
    eff_start.setCalendarPopup(True)

    form.addRow("Day:", day_combo)
    form.addRow("Start Time:", t_start)
    form.addRow("End Time:", t_end)
    form.addRow("Effective From:", eff_start)

    btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                            QDialogButtonBox.StandardButton.Cancel)
    btns.accepted.connect(dlg.accept)
    btns.rejected.connect(dlg.reject)
    form.addRow(btns)

    if dlg.exec():
        day = day_combo.currentData()
        day_name = day_combo.currentText()
        ts = t_start.time().toString("HH:mm")
        te = t_end.time().toString("HH:mm")
        try:
            insert_availability(
                self._center_id, day, ts, te,
                eff_start.date().toPyDate(), None, self._db_path,
            )
            self._availability = __import__(
                "monthly_schedule.db", fromlist=["get_availability"]
            ).get_availability(self._center_id, self._db_path)
            self._refresh_tab(3, self._make_avail_tab())
            if self._events_path:
                conn = open_db(self._events_path)
                m = self._member
                insert_event(conn, "AVAIL", self._center_id,
                    f"{m.get('last_name')}, {m.get('first_name')}",
                    f"Availability added: {day_name} {ts}–{te}")
                conn.close()
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))


def _delete_avail(self, table):
    row = table.currentRow()
    if row < 0:
        return
    record_id = int(table.item(row, 0).text())
    if QMessageBox.question(self, "Confirm", "Delete this availability row?") \
            == QMessageBox.StandardButton.Yes:
        from db.members import delete_availability
        try:
            delete_availability(record_id, self._db_path)
            self._availability = [a for a in self._availability if a["id"] != record_id]
            self._refresh_tab(3, self._make_avail_tab())
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
```

- [ ] **Step 5: Replace Absences placeholder tab**

```python
def _make_absences_tab(self) -> QWidget:
    rows = [
        [a["id"], a["leave_type"], str(a["start_date"]), str(a["end_date"])]
        for a in self._absences
    ]
    w, self._abs_table = self._make_table_tab(
        ["ID", "Leave Type", "Start", "End"],
        rows,
        self._add_absence,
        self._delete_absence,
    )
    return w


def _add_absence(self):
    from PyQt6.QtWidgets import (
        QDialog, QFormLayout, QComboBox, QDateEdit, QDialogButtonBox,
    )
    from PyQt6.QtCore import QDate
    from db.members import insert_absence, LEAVE_TYPES
    from db.events import open_db, insert_event

    dlg = QDialog(self)
    dlg.setWindowTitle("Add Absence")
    form = QFormLayout(dlg)

    leave_combo = QComboBox()
    leave_combo.addItems(LEAVE_TYPES)
    start = QDateEdit(QDate.currentDate())
    start.setCalendarPopup(True)
    end = QDateEdit(QDate.currentDate())
    end.setCalendarPopup(True)

    form.addRow("Leave Type:", leave_combo)
    form.addRow("Start Date:", start)
    form.addRow("End Date:", end)

    btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                            QDialogButtonBox.StandardButton.Cancel)
    btns.accepted.connect(dlg.accept)
    btns.rejected.connect(dlg.reject)
    form.addRow(btns)

    if dlg.exec():
        lt = leave_combo.currentText()
        s = start.date().toPyDate()
        e = end.date().toPyDate()
        try:
            insert_absence(self._center_id, lt, s, e, self._db_path)
            self._absences = __import__(
                "monthly_schedule.db", fromlist=["get_absences"]
            ).get_absences(self._center_id, self._db_path)
            self._refresh_tab(4, self._make_absences_tab())
            if self._events_path:
                conn = open_db(self._events_path)
                m = self._member
                insert_event(conn, "ABS", self._center_id,
                    f"{m.get('last_name')}, {m.get('first_name')}",
                    f"Absence added: {lt} · {s} – {e}")
                conn.close()
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))


def _delete_absence(self, table):
    row = table.currentRow()
    if row < 0:
        return
    record_id = int(table.item(row, 0).text())
    if QMessageBox.question(self, "Confirm", "Delete this absence?") \
            == QMessageBox.StandardButton.Yes:
        from db.members import delete_absence
        try:
            delete_absence(record_id, self._db_path)
            self._absences = [a for a in self._absences if a["id"] != record_id]
            self._refresh_tab(4, self._make_absences_tab())
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
```

- [ ] **Step 6: Wire all tabs in `_build_ui` — replace the four placeholder calls**

In `_build_ui`, replace:
```python
self._tab_enrollments = self._make_placeholder_tab("Enrollments")
self._tab_auths = self._make_placeholder_tab("Authorizations")
self._tab_avail = self._make_placeholder_tab("Availability")
self._tab_absences = self._make_placeholder_tab("Absences")
```
With:
```python
self._tab_enrollments = self._make_enrollments_tab()
self._tab_auths = self._make_auths_tab()
self._tab_avail = self._make_avail_tab()
self._tab_absences = self._make_absences_tab()
```

- [ ] **Step 7: Smoke-test all tabs**

```
.venv\Scripts\python member_manager.py
```

Select a member. Verify each tab shows data table. Try Add and Delete on each tab.

- [ ] **Step 8: Commit**

```bash
git add gui/member_tabs.py
git commit -m "feat: enrollments, authorizations, availability, absences tabs with add/delete"
```

---

## Task 11: Events Views

**Files:**
- Create: `gui/events_view.py`
- Modify: `gui/member_tabs.py`

- [ ] **Step 1: Create gui/events_view.py**

```python
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView,
)
from PyQt6.QtCore import Qt

BADGE_COLORS = {
    "NEW":    ("#182e22", "#3d9e6e"),
    "EDIT":   ("#281f0a", "#c08a2a"),
    "AUTH":   ("#1c2040", "#92b4ff"),
    "ABS":    ("#1e1530", "#b090e8"),
    "AVAIL":  ("#0e2028", "#5eead4"),
    "ENROLL": ("#1a2030", "#80b0e8"),
}


class EventsTableWidget(QWidget):
    """Reusable events log table. Pass center_id=None for global view."""

    def __init__(self, events_path: str, center_id: int | None = None,
                 show_header: bool = True, parent=None):
        super().__init__(parent)
        self._events_path = events_path
        self._center_id = center_id
        self._show_header = show_header
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        if self._show_header:
            header_row = QHBoxLayout()
            title = QLabel("All Events" if self._center_id is None else "Events")
            title.setStyleSheet("font-size:15px; font-weight:600;")
            ttl_lbl = QLabel("Auto-deletes after 30 days")
            ttl_lbl.setStyleSheet("font-size:10px; color: gray;")
            header_row.addWidget(title)
            header_row.addStretch()
            header_row.addWidget(ttl_lbl)
            layout.addLayout(header_row)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter by member or action…")
        self._search.textChanged.connect(self._load)
        layout.addWidget(self._search)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Time", "Type", "Member", "Description"])
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self._table)

    def _load(self):
        if not self._events_path:
            return
        from db.events import open_db, query_events, purge_old_events
        try:
            conn = open_db(self._events_path)
            purge_old_events(conn)
            rows = query_events(
                conn,
                center_id=self._center_id,
                filter_text=self._search.text().strip() or None,
            )
            conn.close()
        except Exception:
            return

        self._table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            ts_item = QTableWidgetItem(row["ts"].replace("T", "  "))
            ts_item.setFont(__import__("PyQt6.QtGui", fromlist=["QFont"]).QFont(
                "Cascadia Mono, Consolas", 10))
            self._table.setItem(r, 0, ts_item)

            badge = QTableWidgetItem(row["event_type"])
            badge.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            bg, fg = BADGE_COLORS.get(row["event_type"], ("#333", "#ccc"))
            from PyQt6.QtGui import QColor
            badge.setBackground(QColor(bg))
            badge.setForeground(QColor(fg))
            self._table.setItem(r, 1, badge)

            self._table.setItem(r, 2, QTableWidgetItem(row["member_name"]))
            self._table.setItem(r, 3, QTableWidgetItem(row["description"]))


class GlobalEventsWidget(QWidget):
    def __init__(self, events_path: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 12)
        layout.addWidget(EventsTableWidget(events_path, center_id=None))
```

- [ ] **Step 2: Replace Events placeholder tab in member_tabs.py**

In `_build_ui`, replace:
```python
self._tab_events = self._make_placeholder_tab("Events")
```
With:
```python
from gui.events_view import EventsTableWidget
self._tab_events = EventsTableWidget(
    self._events_path, center_id=self._center_id, show_header=False
)
```

- [ ] **Step 3: Smoke-test events views**

```
.venv\Scripts\python member_manager.py
```

Add a member or edit info. Open Events tab on that member — event row appears. Click "All Events" — global log shows.

- [ ] **Step 4: Commit**

```bash
git add gui/events_view.py gui/member_tabs.py
git commit -m "feat: per-member and global events log views"
```

---

## Task 12: Add Member Wizard

**Files:**
- Create: `gui/wizard/__init__.py`
- Create: `gui/wizard/wizard.py`
- Create: `gui/wizard/step_contact.py`
- Create: `gui/wizard/step_enrollment.py`
- Create: `gui/wizard/step_auths.py`
- Create: `gui/wizard/step_review.py`

- [ ] **Step 1: Create gui/wizard/__init__.py**

```python
```

- [ ] **Step 2: Create gui/wizard/step_contact.py**

```python
from PyQt6.QtWidgets import (
    QWidget, QFormLayout, QLineEdit, QComboBox, QLabel, QVBoxLayout,
)
from PyQt6.QtCore import Qt
from db.members import HEALTH_PLANS


class StepContact(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._error_label = QLabel("")
        self._error_label.setStyleSheet("color: #d05555; font-size: 11px;")
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(12)

        self.first_name = QLineEdit()
        self.first_name.setPlaceholderText("First name")
        self.last_name = QLineEdit()
        self.last_name.setPlaceholderText("Last name")
        self.center_id = QLineEdit()
        self.center_id.setPlaceholderText("e.g. 10042")
        self.health_plan = QComboBox()
        self.health_plan.addItem("")
        self.health_plan.addItems(HEALTH_PLANS)
        self.address = QLineEdit()
        self.address.setPlaceholderText("Street, City, State ZIP")

        form.addRow("First Name *", self.first_name)
        form.addRow("Last Name *", self.last_name)
        form.addRow("Center ID *", self.center_id)
        form.addRow("Health Plan *", self.health_plan)
        form.addRow("Address", self.address)

        layout.addLayout(form)
        layout.addWidget(self._error_label)
        layout.addStretch()

    def validate(self, db_path: str) -> bool:
        self._error_label.setText("")
        fn = self.first_name.text().strip()
        ln = self.last_name.text().strip()
        cid_text = self.center_id.text().strip()
        plan = self.health_plan.currentText()

        if not fn or not ln:
            self._error_label.setText("First and Last Name are required.")
            return False
        if not plan:
            self._error_label.setText("Health Plan is required.")
            return False
        try:
            cid = int(cid_text)
            if cid <= 0:
                raise ValueError
        except ValueError:
            self._error_label.setText("Center ID must be a positive integer.")
            return False
        from db.members import center_id_exists
        if center_id_exists(cid, db_path):
            self._error_label.setText(f"Center ID {cid} already exists in the database.")
            return False
        return True

    def collect(self) -> dict:
        return {
            "first_name": self.first_name.text().strip(),
            "last_name": self.last_name.text().strip(),
            "center_id": int(self.center_id.text().strip()),
            "health_plan": self.health_plan.currentText(),
            "address": self.address.text().strip(),
        }
```

- [ ] **Step 3: Create gui/wizard/step_enrollment.py**

```python
from PyQt6.QtWidgets import QWidget, QFormLayout, QDateEdit, QLabel, QVBoxLayout, QCheckBox
from PyQt6.QtCore import QDate


class StepEnrollment(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(12)

        self.start_date = QDateEdit(QDate.currentDate())
        self.start_date.setCalendarPopup(True)

        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setSpecialValueText("Ongoing (leave blank)")
        self.end_date.setDate(QDate(2000, 1, 1))

        form.addRow("Enrollment Start *", self.start_date)
        form.addRow("Enrollment End (optional)", self.end_date)

        note = QLabel("Enrollment begins on the start date. Leave End blank for ongoing enrollment.")
        note.setWordWrap(True)
        note.setStyleSheet("color: gray; font-size: 11px;")

        layout.addLayout(form)
        layout.addWidget(note)
        layout.addStretch()

    def collect(self) -> dict:
        end = self.end_date.date()
        return {
            "enrollment_start": self.start_date.date().toPyDate(),
            "enrollment_end": end.toPyDate() if end != QDate(2000, 1, 1) else None,
        }
```

- [ ] **Step 4: Create gui/wizard/step_auths.py**

```python
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QDateEdit, QCheckBox, QTimeEdit, QPushButton, QScrollArea,
)
from PyQt6.QtCore import QDate, QTime


class StepAuths(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._avail_rows: list[dict] = []
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)

        warning = QLabel(
            "⚠  This step is optional. You can skip it and add authorizations "
            "and availability later, but the member won't appear on schedules "
            "until this information is filled in."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet(
            "background: #281f0a; color: #c08a2a; border: 1px solid #4a3810;"
            "border-radius: 7px; padding: 10px; font-size: 11px;"
        )
        layout.addWidget(warning)

        panels = QHBoxLayout()

        # Auth panel
        auth_box = QWidget()
        auth_box.setStyleSheet(
            "background: #181b20; border: 1px solid #232730; border-radius: 10px;"
        )
        auth_layout = QFormLayout(auth_box)
        auth_layout.setContentsMargins(14, 14, 14, 14)
        auth_layout.setSpacing(10)

        title_auth = QLabel("Authorization")
        title_auth.setStyleSheet("font-weight:600; font-size:11px;")
        auth_layout.addRow(title_auth)

        self.auth_start = QDateEdit(QDate.currentDate())
        self.auth_start.setCalendarPopup(True)
        self.auth_end = QDateEdit(QDate.currentDate().addYears(1))
        self.auth_end.setCalendarPopup(True)
        auth_layout.addRow("Auth Start:", self.auth_start)
        auth_layout.addRow("Auth End:", self.auth_end)

        days_widget = QWidget()
        days_hl = QHBoxLayout(days_widget)
        days_hl.setContentsMargins(0, 0, 0, 0)
        self._day_checks: dict[int, QCheckBox] = {}
        for num, lbl in [(1, "Mon"), (2, "Tue"), (3, "Wed"), (4, "Thu"), (5, "Fri")]:
            cb = QCheckBox(lbl)
            self._day_checks[num] = cb
            days_hl.addWidget(cb)
        auth_layout.addRow("Days:", days_widget)

        panels.addWidget(auth_box)

        # Avail panel
        avail_box = QWidget()
        avail_box.setStyleSheet(
            "background: #181b20; border: 1px solid #232730; border-radius: 10px;"
        )
        avail_layout = QVBoxLayout(avail_box)
        avail_layout.setContentsMargins(14, 14, 14, 14)

        title_avail = QLabel("Availability")
        title_avail.setStyleSheet("font-weight:600; font-size:11px;")
        avail_layout.addWidget(title_avail)

        self._avail_container = QVBoxLayout()
        avail_layout.addLayout(self._avail_container)

        btn_add_day = QPushButton("+ Add day")
        btn_add_day.setFlat(True)
        btn_add_day.setStyleSheet("color: #5b7cf4; font-size:10px; text-align:left;")
        btn_add_day.clicked.connect(self._add_avail_row)
        avail_layout.addWidget(btn_add_day)
        avail_layout.addStretch()

        panels.addWidget(avail_box)
        layout.addLayout(panels)
        layout.addStretch()

    def _add_avail_row(self):
        from PyQt6.QtWidgets import QComboBox
        row_widget = QWidget()
        hl = QHBoxLayout(row_widget)
        hl.setContentsMargins(0, 0, 0, 0)

        day_combo = QComboBox()
        for num, name in [(1, "Mon"), (2, "Tue"), (3, "Wed"), (4, "Thu"), (5, "Fri")]:
            day_combo.addItem(name, num)
        day_combo.setFixedWidth(60)

        t_start = QTimeEdit(QTime(8, 0))
        t_end = QTimeEdit(QTime(16, 0))

        hl.addWidget(day_combo)
        hl.addWidget(t_start)
        hl.addWidget(QLabel("–"))
        hl.addWidget(t_end)

        self._avail_container.addWidget(row_widget)
        self._avail_rows.append({
            "combo": day_combo, "t_start": t_start, "t_end": t_end,
        })

    def is_skipped(self) -> bool:
        return not any(cb.isChecked() for cb in self._day_checks.values())

    def collect(self) -> dict:
        from datetime import date
        if self.is_skipped():
            return {"authorization": None, "availability_rows": []}

        selected_days = {n for n, cb in self._day_checks.items() if cb.isChecked()}
        auth = {
            "auth_start": self.auth_start.date().toPyDate(),
            "auth_end": self.auth_end.date().toPyDate(),
            "auth_days": selected_days,
        }
        avail = [
            {
                "day_of_week": r["combo"].currentData(),
                "avail_start": r["t_start"].time().toString("HH:mm"),
                "avail_end":   r["t_end"].time().toString("HH:mm"),
                "effective_start_date": date.today(),
                "effective_end_date": None,
            }
            for r in self._avail_rows
        ]
        return {"authorization": auth, "availability_rows": avail}
```

- [ ] **Step 5: Create gui/wizard/step_review.py**

```python
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea
from PyQt6.QtCore import Qt


class StepReview(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        title = QLabel("Review your entries before saving.")
        title.setStyleSheet("font-size:12px; color:gray;")
        layout.addWidget(title)
        self._body = QLabel("")
        self._body.setWordWrap(True)
        self._body.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll = QScrollArea()
        scroll.setWidget(self._body)
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)

    def populate(self, data: dict):
        m = data.get("contact", {})
        e = data.get("enrollment", {})
        auth = data.get("authorization")
        avail = data.get("availability_rows", [])
        lines = [
            "<b>Contact Info</b>",
            f"Name: {m.get('last_name')}, {m.get('first_name')}",
            f"Center ID: {m.get('center_id')}",
            f"Health Plan: {m.get('health_plan')}",
            f"Address: {m.get('address') or '—'}",
            "",
            "<b>Enrollment</b>",
            f"Start: {e.get('enrollment_start')}",
            f"End: {e.get('enrollment_end') or 'Ongoing'}",
        ]
        if auth:
            from db.members import encode_auth_days
            lines += [
                "",
                "<b>Authorization</b>",
                f"Period: {auth['auth_start']} – {auth['auth_end']}",
                f"Days: {encode_auth_days(auth['auth_days'])}",
            ]
        if avail:
            day_names = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri"}
            lines += ["", "<b>Availability</b>"]
            for row in avail:
                lines.append(
                    f"{day_names.get(row['day_of_week'], '?')}: "
                    f"{row['avail_start']} – {row['avail_end']}"
                )
        self._body.setText("<br>".join(lines))
```

- [ ] **Step 6: Create gui/wizard/wizard.py**

```python
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QStackedWidget,
    QLabel, QWidget, QMessageBox,
)
from PyQt6.QtCore import Qt
from gui.wizard.step_contact import StepContact
from gui.wizard.step_enrollment import StepEnrollment
from gui.wizard.step_auths import StepAuths
from gui.wizard.step_review import StepReview

STEP_LABELS = ["Contact Info", "Enrollment", "Auths & Availability", "Review & Save"]


class AddMemberWizard(QDialog):
    def __init__(self, db_path: str, events_path: str, parent=None):
        super().__init__(parent)
        self._db_path = db_path
        self._events_path = events_path
        self.setWindowTitle("Add New Member")
        self.setMinimumSize(560, 520)
        self._current = 0
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 20)
        layout.setSpacing(16)

        # Progress bar
        self._progress_widget = self._build_progress()
        layout.addWidget(self._progress_widget)

        # Step pages
        self._stack = QStackedWidget()
        self._step_contact = StepContact()
        self._step_enrollment = StepEnrollment()
        self._step_auths = StepAuths()
        self._step_review = StepReview()
        for step in (self._step_contact, self._step_enrollment,
                     self._step_auths, self._step_review):
            self._stack.addWidget(step)
        layout.addWidget(self._stack)

        # Navigation buttons
        nav = QHBoxLayout()
        self._btn_cancel = QPushButton("Cancel")
        self._btn_cancel.clicked.connect(self.reject)
        self._btn_back = QPushButton("← Back")
        self._btn_back.clicked.connect(self._go_back)
        self._btn_back.setEnabled(False)
        self._btn_next = QPushButton("Next →")
        self._btn_next.setObjectName("btn_primary")
        self._btn_next.clicked.connect(self._go_next)
        nav.addWidget(self._btn_cancel)
        nav.addStretch()
        nav.addWidget(self._btn_back)
        nav.addWidget(self._btn_next)
        layout.addLayout(nav)

    def _build_progress(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(6)

        dot_row = QHBoxLayout()
        dot_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._dots: list[QLabel] = []
        for i in range(4):
            dot = QLabel(str(i + 1))
            dot.setFixedSize(28, 28)
            dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            dot.setStyleSheet(self._dot_style(i, 0))
            self._dots.append(dot)
            dot_row.addWidget(dot)
            if i < 3:
                line = QLabel()
                line.setFixedHeight(1)
                line.setFixedWidth(64)
                line.setObjectName(f"progress_line_{i}")
                line.setStyleSheet("background: #282c38;")
                dot_row.addWidget(line)

        lbl_row = QHBoxLayout()
        for label in STEP_LABELS:
            lbl = QLabel(label)
            lbl.setFixedWidth(84)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setWordWrap(True)
            lbl.setStyleSheet("font-size:10px; color:#31354a;")
            lbl_row.addWidget(lbl)

        layout.addLayout(dot_row)
        layout.addLayout(lbl_row)
        return widget

    def _dot_style(self, dot_index: int, current: int) -> str:
        if dot_index < current:
            return ("background:#3d9e6e; color:white; border-radius:14px;"
                    "font-weight:700; font-size:11px;")
        if dot_index == current:
            return ("background:#5b7cf4; color:white; border-radius:14px;"
                    "font-weight:700; font-size:11px; border:3px solid #1c2040;")
        return ("background:#1e2128; color:#31354a; border-radius:14px;"
                "border:1px solid #282c38; font-size:11px;")

    def _update_progress(self):
        for i, dot in enumerate(self._dots):
            dot.setStyleSheet(self._dot_style(i, self._current))

    def _go_next(self):
        if self._current == 0:
            if not self._step_contact.validate(self._db_path):
                return
        if self._current == 2:
            data = self._collect_all()
            self._step_review.populate(data)
        if self._current == 3:
            self._save()
            return
        self._current += 1
        self._stack.setCurrentIndex(self._current)
        self._btn_back.setEnabled(True)
        if self._current == 3:
            self._btn_next.setText("Create Member")
        self._update_progress()

    def _go_back(self):
        self._current -= 1
        self._stack.setCurrentIndex(self._current)
        self._btn_next.setText("Next →")
        self._btn_back.setEnabled(self._current > 0)
        self._update_progress()

    def _collect_all(self) -> dict:
        data = {}
        data["contact"] = self._step_contact.collect()
        data.update(self._step_enrollment.collect())
        data.update(self._step_auths.collect())
        return data

    def _save(self):
        data = self._collect_all()
        c = data["contact"]
        try:
            from db.members import insert_member
            from db.events import open_db, insert_event
            insert_member(
                center_id=c["center_id"],
                last_name=c["last_name"],
                first_name=c["first_name"],
                health_plan=c["health_plan"],
                address=c["address"],
                enrollment_start=data["enrollment_start"],
                enrollment_end=data["enrollment_end"],
                authorization=data.get("authorization"),
                availability_rows=data.get("availability_rows", []),
                db_path=self._db_path,
            )
            if self._events_path:
                conn = open_db(self._events_path)
                insert_event(
                    conn, "NEW", c["center_id"],
                    f"{c['last_name']}, {c['first_name']}",
                    "Member added to system",
                )
                conn.close()
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Save Failed",
                f"Could not create member:\n{exc}")
```

- [ ] **Step 7: Smoke-test the full wizard**

```
.venv\Scripts\python member_manager.py
```

Click "+ Add New Member". Walk through all 4 steps. On Step 4 click "Create Member". Verify the new member appears in the sidebar list.

- [ ] **Step 8: Commit**

```bash
git add gui/wizard/
git commit -m "feat: 4-step add-member wizard with progress bar and DB write transaction"
```

---

## Task 13: Unsaved Changes Guard + Launch Error Handling

**Files:**
- Modify: `gui/member_tabs.py`
- Modify: `gui/main_window.py`

- [ ] **Step 1: Add dirty tracking to MemberTabsWidget**

Add to `MemberTabsWidget.__init__` after `self._build_ui()`:
```python
self._dirty = False
# Mark dirty on any field change in info tab
for widget in (self._info_first, self._info_last, self._info_address):
    widget.textChanged.connect(lambda: setattr(self, '_dirty', True))
self._info_plan.currentIndexChanged.connect(lambda: setattr(self, '_dirty', True))
```

Add method:
```python
def is_dirty(self) -> bool:
    return self._dirty
```

- [ ] **Step 2: Guard member selection in MainWindow**

In `MainWindow._on_member_selected`, before calling `_show_member`:
```python
def _on_member_selected(self, row: int):
    if row < 0:
        return
    # Guard: check if current detail widget has unsaved changes
    if self._detail_stack.count() > 1:
        current = self._detail_stack.widget(1)
        if hasattr(current, "is_dirty") and current.is_dirty():
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved changes. Discard them?",
                QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            )
            if reply != QMessageBox.StandardButton.Discard:
                # Revert list selection to previous member
                self._member_list.blockSignals(True)
                self._member_list.setCurrentRow(-1)
                self._member_list.blockSignals(False)
                return
    item = self._member_list.item(row)
    if item is None:
        return
    center_id = item.data(Qt.ItemDataRole.UserRole)
    self._show_member(center_id)
```

- [ ] **Step 3: Show launch error when DB path is missing**

In `MainWindow._load_members`, after the empty `db_path` early return, add a status label to the placeholder:
```python
if not db_path:
    self._placeholder.setText(
        "No database configured.\nOpen ⚙ Settings to set the database path."
    )
    return
```

- [ ] **Step 4: Smoke-test guard**

```
.venv\Scripts\python member_manager.py
```

Select a member, change the first name without saving, click a different member. Confirm dialog appears. Click Cancel — stays on original member. Click Discard — switches member.

- [ ] **Step 5: Commit**

```bash
git add gui/member_tabs.py gui/main_window.py
git commit -m "feat: unsaved changes guard and no-db launch message"
```

---

## Task 14: Final Wiring + .gitignore Updates

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Update .gitignore**

Add to `.gitignore`:
```
.superpowers/
*.db
bsca_members_settings.json
```

- [ ] **Step 2: Run full test suite**

```
.venv\Scripts\pytest -v
```

Expected: all tests pass.

- [ ] **Step 3: Full end-to-end smoke test**

```
.venv\Scripts\python member_manager.py
```

Verify:
1. Launch with no settings → placeholder message shown
2. Open Settings → set DB path → save → member list populates
3. Click member → all 6 tabs load
4. Info tab: edit + save → Events tab shows EDIT entry
5. Auths tab: add auth → Events tab shows AUTH entry
6. Availability tab: add row → Events tab shows AVAIL entry
7. Absences tab: add absence → Events tab shows ABS entry
8. "All Events" → global log shows all entries
9. "+ Add New Member" → wizard completes → new member in list
10. Toggle theme in Settings → UI repaints immediately

- [ ] **Step 4: Final commit**

```bash
git add .gitignore
git commit -m "chore: update gitignore for db files and superpowers dir"
```
