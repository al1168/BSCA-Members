# Terminated-Member Indicator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make terminated members unmistakable — a dimmed name + red "⊘ TERMINATED" tag in the member list, and a red "⊘ Terminated" badge in the profile header. Terminated = the member's latest enrollment (by start date) has an end date on file.

**Architecture:** Pure detection helpers in `db/members.py` (`is_terminated`, `terminated_ids_from_rows`, `get_terminated_center_ids`). A `terminated_badge` QSS style + a header badge in `gui/member_tabs.py`. In `gui/main_window.py`, a `QStyledItemDelegate` paints terminated list rows (dimmed name + red tag), fed by a per-item role and the terminated id set.

**Tech Stack:** Python 3.11, PyQt6, pytest. No new dependencies.

---

## File Map

```
db/members.py             modify — is_terminated, terminated_ids_from_rows,
                                   get_terminated_center_ids
gui/theme.py              modify — QLabel#terminated_badge (DARK + LIGHT)
gui/member_tabs.py        modify — header terminated badge
gui/main_window.py        modify — delegate + role + load/populate/theme wiring
tests/test_terminated.py  create — detection + theme unit tests
```

---

## Task 1: Detection helpers in `db/members.py` (TDD)

**Files:**
- Create: `tests/test_terminated.py`
- Modify: `db/members.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_terminated.py`:

```python
from datetime import date

from db.members import is_terminated, terminated_ids_from_rows


def test_is_terminated_no_enrollments():
    assert is_terminated([]) is False


def test_is_terminated_latest_ongoing():
    enrs = [
        {"start_date": date(2025, 1, 1), "end_date": date(2025, 6, 1)},
        {"start_date": date(2025, 7, 1), "end_date": None},
    ]
    assert is_terminated(enrs) is False


def test_is_terminated_latest_ended_past():
    enrs = [{"start_date": date(2025, 1, 1), "end_date": date(2025, 12, 1)}]
    assert is_terminated(enrs) is True


def test_is_terminated_latest_ended_future():
    enrs = [{"start_date": date(2026, 1, 1), "end_date": date(2099, 1, 1)}]
    assert is_terminated(enrs) is True


def test_terminated_ids_from_rows():
    rows = [
        (100, date(2025, 1, 1), date(2025, 6, 1)),   # only enrollment, ended
        (200, date(2025, 1, 1), None),               # ongoing
        (300, date(2025, 1, 1), date(2025, 3, 1)),   # old ended
        (300, date(2025, 9, 1), None),               # newer ongoing (re-enroll)
        (None, date(2025, 1, 1), date(2025, 2, 1)),  # null center id -> skipped
    ]
    assert terminated_ids_from_rows(rows) == {100}
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv\Scripts\pytest tests/test_terminated.py -v`
Expected: FAIL (`cannot import name 'is_terminated'`).

- [ ] **Step 3: Add the helpers**

In `db/members.py`, add near the other enrollment helpers (e.g. just before
`terminate_enrollment`, or after the module-level mappers — anywhere at module
scope; `date` and `_access_date` are already defined in this file):

```python
def is_terminated(enrollments: list[dict]) -> bool:
    """True when the member's latest enrollment (by start date) has an end date.
    No enrollments -> False; a latest ongoing enrollment -> False."""
    if not enrollments:
        return False
    latest = max(enrollments, key=lambda e: e.get("start_date") or date.min)
    return latest.get("end_date") is not None


def terminated_ids_from_rows(rows) -> set[int]:
    """Group raw (center_id, start_date, end_date) rows by member and return the
    set of terminated center ids. Pure (no DB) so it is unit-testable."""
    from collections import defaultdict
    by_member: dict[int, list[dict]] = defaultdict(list)
    for cid, start, end in rows:
        if cid is None:
            continue
        by_member[int(cid)].append(
            {"start_date": _access_date(start), "end_date": _access_date(end)}
        )
    return {cid for cid, enrs in by_member.items() if is_terminated(enrs)}


def get_terminated_center_ids(db_path: str) -> set[int]:
    """Center ids of terminated members, from all Enrollment rows in one query
    (mirrors get_all_members' connection handling)."""
    conn = _connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT [Center ID], [start_date], [end_date] FROM [Enrollment]"
        )
        return terminated_ids_from_rows(cur.fetchall())
    finally:
        conn.close()
```

- [ ] **Step 4: Run to verify they pass**

Run: `.venv\Scripts\pytest tests/test_terminated.py -v`
Expected: the 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add db/members.py tests/test_terminated.py
git commit -m "feat: add terminated-member detection helpers"
```
End the commit message with a blank line then:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Task 2: `terminated_badge` style + profile header badge

**Files:**
- Modify: `gui/theme.py`, `gui/member_tabs.py`, `tests/test_terminated.py`

- [ ] **Step 1: Write the failing theme test**

Append to `tests/test_terminated.py`:

```python
def test_theme_has_terminated_badge():
    from gui.theme import build_qss, DARK, LIGHT
    for tokens in (DARK, LIGHT):
        assert "QLabel#terminated_badge" in build_qss(tokens)
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\pytest tests/test_terminated.py::test_theme_has_terminated_badge -v`
Expected: FAIL.

- [ ] **Step 3: Add the QSS rule**

In `gui/theme.py`, inside `build_qss(t)`, immediately AFTER the
`QLabel#warning_badge {{ ... }}` block, add:

```python
QLabel#terminated_badge {{
    background-color: {t['error']};
    color: #f4f6fd;
    border: none;
    border-radius: 10px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 700;
}}
```

- [ ] **Step 4: Add the header badge**

In `gui/member_tabs.py` `_build_ui`, after the plan-badge `if plan:` block and
BEFORE `top_row.addStretch()`, add:

```python
        from db.members import is_terminated
        if is_terminated(self._enrollments):
            term_badge = QLabel("⊘ Terminated")
            term_badge.setObjectName("terminated_badge")
            term_badge.setMaximumHeight(26)
            top_row.addWidget(term_badge, alignment=Qt.AlignmentFlag.AlignVCenter)
```

(Read the header region first to place this exactly after the plan badge and
before the stretch. `QLabel` and `Qt` are already imported.)

- [ ] **Step 5: Run the theme test + verify import**

Run: `.venv\Scripts\pytest tests/test_terminated.py -v` → all PASS.
Run: `.venv\Scripts\python -c "from gui.theme import build_qss, DARK; build_qss(DARK); from gui.member_tabs import MemberTabsWidget; print('OK')"` → `OK`.

- [ ] **Step 6: Run the full suite**

Run: `.venv\Scripts\pytest -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add gui/theme.py gui/member_tabs.py tests/test_terminated.py
git commit -m "feat: red 'Terminated' badge in the member profile header"
```
End with a blank line then:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Task 3: Member-list delegate + wiring (`gui/main_window.py`)

**Files:**
- Modify: `gui/main_window.py`

- [ ] **Step 1: Add imports**

The current top imports are:

```python
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QListWidget, QListWidgetItem, QPushButton, QLineEdit, QLabel,
    QStackedWidget, QApplication, QMessageBox, QSizePolicy,
)
from PyQt6.QtCore import Qt
```

Replace with (add the delegate/style classes and `QTextDocument`/layout):

```python
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QListWidget, QListWidgetItem, QPushButton, QLineEdit, QLabel,
    QStackedWidget, QApplication, QMessageBox, QSizePolicy,
    QStyledItemDelegate, QStyle, QStyleOptionViewItem,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextDocument, QAbstractTextDocumentLayout
```

- [ ] **Step 2: Add the role constant and delegate (module scope)**

In `gui/main_window.py`, after the imports and before `class MainWindow`, add:

```python
TERMINATED_ROLE = Qt.ItemDataRole.UserRole + 1


class _MemberItemDelegate(QStyledItemDelegate):
    """Paints terminated member rows with a dimmed name and a red TERMINATED tag.
    Active rows fall through to the default rendering."""

    def __init__(self, parent=None, muted="#888888", tag="#d05555"):
        super().__init__(parent)
        self._muted = muted
        self._tag = tag

    def set_colors(self, muted: str, tag: str) -> None:
        self._muted = muted
        self._tag = tag

    def paint(self, painter, option, index):
        if not index.data(TERMINATED_ROLE):
            super().paint(painter, option, index)
            return
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        name, _, sub = opt.text.partition("\n")
        opt.text = ""
        style = opt.widget.style() if opt.widget else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)
        html = (
            f"<span style='color:{self._muted}'>{name}<br>{sub}</span>"
            f"&nbsp;&nbsp;<span style='color:{self._tag}; font-weight:700'>"
            f"⊘ TERMINATED</span>"
        )
        doc = QTextDocument()
        doc.setDefaultFont(opt.font)
        doc.setHtml(html)
        doc.setTextWidth(opt.rect.width() - 12)
        painter.save()
        painter.translate(opt.rect.left() + 6, opt.rect.top() + 3)
        doc.documentLayout().draw(painter, QAbstractTextDocumentLayout.PaintContext())
        painter.restore()
```

- [ ] **Step 3: Initialize state in `__init__`**

The current `__init__` head is:

```python
    def __init__(self, settings: dict, settings_path: str):
        super().__init__()
        self._settings = settings
        self._settings_path = settings_path
        self._last_center_id = None
```

Add the terminated-id set:

```python
    def __init__(self, settings: dict, settings_path: str):
        super().__init__()
        self._settings = settings
        self._settings_path = settings_path
        self._last_center_id = None
        self._terminated_ids = set()
```

- [ ] **Step 4: Install the delegate in `_build_ui`**

The current list creation is:

```python
        self._member_list = QListWidget()
        self._member_list.currentRowChanged.connect(self._on_member_selected)
```

Replace with:

```python
        self._member_list = QListWidget()
        self._member_list.currentRowChanged.connect(self._on_member_selected)
        self._member_delegate = _MemberItemDelegate(self._member_list)
        self._member_list.setItemDelegate(self._member_delegate)
        self._refresh_list_theme()
```

- [ ] **Step 5: Add `_refresh_list_theme` and load the terminated set**

Add this method to `MainWindow` (near `_load_members`):

```python
    def _refresh_list_theme(self):
        from gui.theme import DARK, LIGHT
        tokens = DARK if self._settings.get("theme") == "dark" else LIGHT
        self._member_delegate.set_colors(tokens["text2"], tokens["error"])
        self._member_list.viewport().update()
```

In `_load_members`, after `self._all_members = get_all_members(db_path)` (inside the
`try`), also load the terminated set:

```python
        try:
            from db.members import get_all_members, get_terminated_center_ids
            self._all_members = get_all_members(db_path)
            try:
                self._terminated_ids = get_terminated_center_ids(db_path)
            except Exception:
                self._terminated_ids = set()
        except Exception as exc:
            QMessageBox.critical(self, "Database Error",
                f"Could not load members:\n{exc}\n\nCheck Settings.")
```

(Replace the existing `from db.members import get_all_members` /
`self._all_members = get_all_members(db_path)` lines with the block above.)

- [ ] **Step 6: Flag terminated items in `_populate_list`**

The current method:

```python
    def _populate_list(self, members: list[dict]):
        self._member_list.clear()
        for m in members:
            label = f"{m['last_name']}, {m['first_name']}\n{m['center_id']} · {m['health_plan']}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, m["center_id"])
            self._member_list.addItem(item)
```

Add the terminated flag:

```python
    def _populate_list(self, members: list[dict]):
        self._member_list.clear()
        for m in members:
            label = f"{m['last_name']}, {m['first_name']}\n{m['center_id']} · {m['health_plan']}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, m["center_id"])
            item.setData(TERMINATED_ROLE, m["center_id"] in self._terminated_ids)
            self._member_list.addItem(item)
```

- [ ] **Step 7: Refresh delegate colors on theme toggle**

In `_open_settings`, the current theme block is:

```python
            from gui.theme import apply_theme
            apply_theme(QApplication.instance(), self._settings["theme"])
            self._update_db_indicator()
            self._load_members()
```

Add the list-theme refresh:

```python
            from gui.theme import apply_theme
            apply_theme(QApplication.instance(), self._settings["theme"])
            self._refresh_list_theme()
            self._update_db_indicator()
            self._load_members()
```

- [ ] **Step 8: Verify import**

Run: `.venv\Scripts\python -c "from gui.main_window import MainWindow, _MemberItemDelegate; print('OK')"`
Expected: `OK`

- [ ] **Step 9: Run the full suite**

Run: `.venv\Scripts\pytest -q`
Expected: all pass.

- [ ] **Step 10: Commit**

```bash
git add gui/main_window.py
git commit -m "feat: mark terminated members in the list (dimmed name + red tag)"
```
End with a blank line then:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Task 4: Full suite + exe rebuild + manual smoke test

**Files:** none changed

- [ ] **Step 1: Run the full test suite**

Run: `.venv\Scripts\pytest -q`
Expected: all pass.

- [ ] **Step 2: Rebuild the exe**

```
powershell -Command "try { Stop-Process -Name MemberManager -Force -ErrorAction Stop } catch {}"
.venv\Scripts\pyinstaller MemberManager.spec
```
Expected: `Build complete! ... dist`

- [ ] **Step 3: Manual smoke test**

Launch `dist\MemberManager.exe`:
- A member whose latest enrollment has an end date shows in the **list** with a
  dimmed name and a red **"⊘ TERMINATED"** tag; active members look normal.
- Opening that member shows a red **"⊘ Terminated"** badge in the header (beside the
  plan badge); active members show no such badge.
- Terminating an active member (Enrollments → Terminate) and reloading marks them
  terminated; re-adding an ongoing enrollment clears it.
- Search filtering still works and keeps the terminated styling.
- Toggle light/dark (Settings) — terminated rows and the badge read in both.

---

## Self-Review Notes

- **Spec coverage:** `is_terminated` (latest-enrollment-has-end-date) +
  `terminated_ids_from_rows` + `get_terminated_center_ids` → Task 1. Header badge +
  `terminated_badge` QSS → Task 2. List delegate (dimmed name + red tag), role flag,
  load/populate/theme wiring → Task 3. Suite/exe/manual → Task 4.
- **Type consistency:** `is_terminated(list[dict]) -> bool`;
  `terminated_ids_from_rows(rows) -> set[int]`;
  `get_terminated_center_ids(db_path) -> set[int]`; `TERMINATED_ROLE =
  Qt.ItemDataRole.UserRole + 1`; delegate `set_colors(muted, tag)` fed from
  `tokens['text2']`/`tokens['error']`; header object name `terminated_badge`.
- **No placeholders:** every step shows full code and exact commands/expected
  output. The delegate rendering and header badge are verified manually; detection
  and the theme style are unit-tested.
