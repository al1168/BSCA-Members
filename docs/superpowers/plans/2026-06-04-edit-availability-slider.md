# Edit Availability — Range Slider + Manual Entry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an "Edit" button to each availability row that opens a modal dialog with a custom two-handle range slider and synced manual time fields, then persists the new Start/End window.

**Architecture:** A new `gui/time_range_editor.py` holds pure value/range helpers (unit-tested), a hand-built `RangeSlider` `QWidget` (two handles, snap-on-drag), and a `TimeRangeEditor` composite (slider + manual `h:mm`/AM-PM fields kept in two-way sync). The Availability tab in `gui/member_tabs.py` becomes a bespoke table with per-row Edit → modal dialog. `db/members.py` gains `update_availability`.

**Tech Stack:** Python 3.11, PyQt6, pyodbc (Access), pytest. No new dependencies.

---

## File Map

```
db/members.py                    modify — UPDATE_AVAILABILITY + update_availability()
gui/time_range_editor.py         create — pure helpers + RangeSlider + TimeRangeEditor
gui/member_tabs.py               modify — bespoke Availability tab + _edit_avail() modal
tests/test_time_range_editor.py  create — unit tests for the pure helpers
tests/test_db_members.py             modify — UPDATE_AVAILABILITY column test
tests/test_db_members_integration.py modify — update_availability round-trip test
```

Domain constants (defined once in `gui/time_range_editor.py`): `MIN_MINUTES=480` (08:00), `MAX_MINUTES=960` (16:00), `SNAP_MINUTES=15`, `MIN_WINDOW=15`. Times are 24-hour `"HH:mm"` strings at the boundaries, consistent with `insert_availability`/`get_availability`.

---

## Task 1: update_availability (DB layer)

**Files:**
- Modify: `db/members.py`
- Test: `tests/test_db_members.py`, `tests/test_db_members_integration.py`

- [ ] **Step 1: Add the failing unit test to `tests/test_db_members.py`**

```python
def test_update_availability_targets_correct_columns():
    from db.members import UPDATE_AVAILABILITY
    assert "UPDATE [Availability]" in UPDATE_AVAILABILITY
    assert "[avail_start]=?" in UPDATE_AVAILABILITY
    assert "[avail_end]=?" in UPDATE_AVAILABILITY
    assert "WHERE [ID]=?" in UPDATE_AVAILABILITY
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv\Scripts\pytest tests/test_db_members.py::test_update_availability_targets_correct_columns -v`
Expected: FAIL — `ImportError: cannot import name 'UPDATE_AVAILABILITY'`

- [ ] **Step 3: Add the failing integration test to the BOTTOM of `tests/test_db_members_integration.py`**

```python
def test_update_availability_round_trips_changes():
    from datetime import date
    from db.members import (
        get_all_members, insert_availability, update_availability,
        delete_availability,
    )
    from monthly_schedule.db import get_availability

    cid = get_all_members(TEST_DB)[0]["center_id"]
    before = {a["id"] for a in get_availability(cid, TEST_DB)}
    insert_availability(cid, 1, "08:00", "16:00", date(2026, 1, 1), None, TEST_DB)
    new_id = ({a["id"] for a in get_availability(cid, TEST_DB)} - before).pop()
    try:
        update_availability(new_id, "09:30", "14:45", TEST_DB)
        row = next(a for a in get_availability(cid, TEST_DB) if a["id"] == new_id)
        assert row["avail_start"] == "09:30"
        assert row["avail_end"] == "14:45"
    finally:
        delete_availability(new_id, TEST_DB)
```

- [ ] **Step 4: Run it to verify it fails**

Run: `.venv\Scripts\pytest tests/test_db_members_integration.py::test_update_availability_round_trips_changes -v`
Expected: FAIL — `ImportError: cannot import name 'update_availability'`

- [ ] **Step 5: Implement in `db/members.py`**

Add the constant right after `DELETE_AVAILABILITY` (near line 65):

```python
UPDATE_AVAILABILITY = (
    "UPDATE [Availability] SET [avail_start]=?, [avail_end]=? WHERE [ID]=?"
)
```

Add the function right after `insert_availability` (after its `finally: conn.close()` block):

```python
def update_availability(record_id: int, avail_start: str, avail_end: str,
                        db_path: str) -> None:
    """Update an availability row's start/end times (24-hour 'HH:mm')."""
    conn = _connect(db_path)
    try:
        conn.cursor().execute(
            UPDATE_AVAILABILITY,
            (_hhmm_to_datetime(avail_start), _hhmm_to_datetime(avail_end), record_id),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

(`_hhmm_to_datetime` already exists and is used by `insert_availability`.)

- [ ] **Step 6: Run both new tests to verify they pass**

Run: `.venv\Scripts\pytest tests/test_db_members.py::test_update_availability_targets_correct_columns tests/test_db_members_integration.py::test_update_availability_round_trips_changes -v`
Expected: 2 passed

- [ ] **Step 7: Commit**

```bash
git add db/members.py tests/test_db_members.py tests/test_db_members_integration.py
git commit -m "feat: add update_availability() for editing an availability window"
```
End the commit message with the trailer:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Task 2: Pure time/range helpers

**Files:**
- Create: `gui/time_range_editor.py`
- Test: `tests/test_time_range_editor.py`

- [ ] **Step 1: Create `tests/test_time_range_editor.py`**

```python
import pytest


def test_hhmm_minutes_round_trip():
    from gui.time_range_editor import hhmm_to_minutes, minutes_to_hhmm
    assert hhmm_to_minutes("08:00") == 480
    assert hhmm_to_minutes("16:00") == 960
    assert hhmm_to_minutes("08:07") == 487
    assert minutes_to_hhmm(480) == "08:00"
    assert minutes_to_hhmm(960) == "16:00"
    assert minutes_to_hhmm(487) == "08:07"


@pytest.mark.parametrize("bad", ["8", "8:00:00", "abc", "8:"])
def test_hhmm_to_minutes_invalid(bad):
    from gui.time_range_editor import hhmm_to_minutes
    with pytest.raises(ValueError):
        hhmm_to_minutes(bad)


def test_clamp_minutes():
    from gui.time_range_editor import clamp_minutes
    assert clamp_minutes(470) == 480
    assert clamp_minutes(970) == 960
    assert clamp_minutes(600) == 600


def test_snap_minutes():
    from gui.time_range_editor import snap_minutes
    assert snap_minutes(487) == 480
    assert snap_minutes(488) == 495
    assert snap_minutes(953) == 960   # snaps to 960, within bounds
    assert snap_minutes(470) == 480   # clamped up first/after


def test_minutes_to_12h():
    from gui.time_range_editor import minutes_to_12h
    assert minutes_to_12h(480) == ("8:00", "AM")
    assert minutes_to_12h(487) == ("8:07", "AM")
    assert minutes_to_12h(720) == ("12:00", "PM")
    assert minutes_to_12h(960) == ("4:00", "PM")
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv\Scripts\pytest tests/test_time_range_editor.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gui.time_range_editor'`

- [ ] **Step 3: Create `gui/time_range_editor.py` with the constants + pure helpers**

```python
"""Time-range editor: a two-handle range slider synced with manual h:mm fields.

Pure helpers (minutes <-> 'HH:mm', clamp, snap, 12-hour formatting) are unit
tested; the RangeSlider/TimeRangeEditor widgets are verified manually.
"""

MIN_MINUTES = 480   # 08:00
MAX_MINUTES = 960   # 16:00
SNAP_MINUTES = 15
MIN_WINDOW = 15


def hhmm_to_minutes(hhmm: str) -> int:
    """'08:00' -> 480. Raises ValueError on malformed input."""
    parts = hhmm.strip().split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid time: {hhmm!r}")
    return int(parts[0]) * 60 + int(parts[1])


def minutes_to_hhmm(m: int) -> str:
    """480 -> '08:00' (24-hour, zero-padded)."""
    return f"{m // 60:02d}:{m % 60:02d}"


def clamp_minutes(m: int) -> int:
    """Clamp to [MIN_MINUTES, MAX_MINUTES]."""
    return max(MIN_MINUTES, min(MAX_MINUTES, m))


def snap_minutes(m: int) -> int:
    """Round to the nearest SNAP_MINUTES, then clamp to bounds."""
    return clamp_minutes(round(m / SNAP_MINUTES) * SNAP_MINUTES)


def minutes_to_12h(m: int) -> tuple[str, str]:
    """480 -> ('8:00','AM'); 487 -> ('8:07','AM'); 720 -> ('12:00','PM')."""
    h24, mm = divmod(m, 60)
    period = "AM" if h24 < 12 else "PM"
    h12 = h24 % 12 or 12
    return f"{h12}:{mm:02d}", period
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv\Scripts\pytest tests/test_time_range_editor.py -v`
Expected: 8 passed

- [ ] **Step 5: Run the full suite**

Run: `.venv\Scripts\pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add gui/time_range_editor.py tests/test_time_range_editor.py
git commit -m "feat: add pure time/range helpers for the availability editor"
```
End with:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Task 3: RangeSlider custom widget

**Files:**
- Modify: `gui/time_range_editor.py`

- [ ] **Step 1: Append the `RangeSlider` widget to `gui/time_range_editor.py`**

Add these imports at the top of the file (below the docstring, above the constants):

```python
from PyQt6.QtWidgets import QWidget, QSizePolicy
from PyQt6.QtCore import Qt, pyqtSignal, QRectF
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QFont
```

Append the widget at the end of the file:

```python
class RangeSlider(QWidget):
    """A horizontal two-handle range slider over MIN_MINUTES..MAX_MINUTES.

    Dragging a handle snaps to SNAP_MINUTES and cannot cross the other handle
    (min gap MIN_WINDOW). Emits windowChanged(start_min, end_min) while dragging.
    set_window() accepts any minute (no snap) so typed values render off-tick.
    """
    windowChanged = pyqtSignal(int, int)

    _MARGIN = 18      # px padding so handles aren't clipped
    _TRACK_Y = 22     # track top
    _TRACK_H = 8
    _HANDLE_R = 9

    def __init__(self, parent=None):
        super().__init__(parent)
        self._start = MIN_MINUTES
        self._end = MAX_MINUTES
        self._drag = None  # 'start' | 'end' | None
        self.setMinimumHeight(60)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    # ── state ────────────────────────────────────────────────────────────
    def set_window(self, start_min: int, end_min: int) -> None:
        start = clamp_minutes(int(start_min))
        end = clamp_minutes(int(end_min))
        if end < start + MIN_WINDOW:
            end = clamp_minutes(start + MIN_WINDOW)
        self._start, self._end = start, end
        self.update()

    def window(self) -> tuple[int, int]:
        return self._start, self._end

    # ── geometry ─────────────────────────────────────────────────────────
    def _track_left_width(self):
        w = max(self.width() - 2 * self._MARGIN, 1)
        return self._MARGIN, w

    def _x_for(self, minutes: int) -> float:
        left, w = self._track_left_width()
        frac = (minutes - MIN_MINUTES) / (MAX_MINUTES - MIN_MINUTES)
        return left + frac * w

    def _minutes_for(self, x: float) -> int:
        left, w = self._track_left_width()
        frac = (x - left) / w
        return int(round(MIN_MINUTES + frac * (MAX_MINUTES - MIN_MINUTES)))

    # ── painting ─────────────────────────────────────────────────────────
    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        left, w = self._track_left_width()
        cy = self._TRACK_Y + self._TRACK_H / 2

        # base track
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor("#2a2e3a")))
        p.drawRoundedRect(QRectF(left, self._TRACK_Y, w, self._TRACK_H), 4, 4)

        # filled band
        xs, xe = self._x_for(self._start), self._x_for(self._end)
        p.setBrush(QBrush(QColor("#5b7cf4")))
        p.drawRoundedRect(QRectF(xs, self._TRACK_Y, max(xe - xs, 1), self._TRACK_H), 4, 4)

        # hour ticks + labels (8a..4p)
        p.setFont(QFont("Segoe UI", 7))
        p.setPen(QPen(QColor("#757a98")))
        for hour in range(8, 17):
            mx = self._x_for(hour * 60)
            p.drawLine(int(mx), self._TRACK_Y + self._TRACK_H + 2,
                       int(mx), self._TRACK_Y + self._TRACK_H + 6)
            label = f"{hour}a" if hour < 12 else ("12p" if hour == 12 else f"{hour - 12}p")
            p.drawText(QRectF(mx - 12, self._TRACK_Y + self._TRACK_H + 7, 24, 12),
                       Qt.AlignmentFlag.AlignHCenter, label)

        # handles
        p.setPen(QPen(QColor("#5b7cf4"), 2))
        p.setBrush(QBrush(QColor("#ffffff")))
        for mx in (xs, xe):
            p.drawEllipse(QRectF(mx - self._HANDLE_R, cy - self._HANDLE_R,
                                 self._HANDLE_R * 2, self._HANDLE_R * 2))
        p.end()

    # ── interaction ──────────────────────────────────────────────────────
    def mousePressEvent(self, ev):
        x = ev.position().x()
        self._drag = ("start" if abs(x - self._x_for(self._start))
                      <= abs(x - self._x_for(self._end)) else "end")
        self._drag_to(x)

    def mouseMoveEvent(self, ev):
        if self._drag:
            self._drag_to(ev.position().x())

    def mouseReleaseEvent(self, ev):
        self._drag = None

    def _drag_to(self, x: float) -> None:
        m = snap_minutes(self._minutes_for(x))
        if self._drag == "start":
            self._start = clamp_minutes(min(m, self._end - MIN_WINDOW))
        else:
            self._end = clamp_minutes(max(m, self._start + MIN_WINDOW))
        self.update()
        self.windowChanged.emit(self._start, self._end)

    def keyPressEvent(self, ev):
        step = SNAP_MINUTES
        if ev.key() == Qt.Key.Key_Left:
            self._end = clamp_minutes(max(self._end - step, self._start + MIN_WINDOW))
        elif ev.key() == Qt.Key.Key_Right:
            self._end = clamp_minutes(self._end + step)
        else:
            super().keyPressEvent(ev)
            return
        self.update()
        self.windowChanged.emit(self._start, self._end)
```

- [ ] **Step 2: Verify the module imports**

Run: `.venv\Scripts\python -c "from gui.time_range_editor import RangeSlider; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Run the full suite (pure-helper tests still pass; widget import is exercised)**

Run: `.venv\Scripts\pytest -q`
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add gui/time_range_editor.py
git commit -m "feat: hand-built RangeSlider widget (two handles, snap-on-drag)"
```
End with:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Task 4: TimeRangeEditor composite widget

**Files:**
- Modify: `gui/time_range_editor.py`

- [ ] **Step 1: Append the `TimeRangeEditor` widget to `gui/time_range_editor.py`**

Extend the top-of-file PyQt imports to include the extra widgets/QMessageBox:

```python
from PyQt6.QtWidgets import (
    QWidget, QSizePolicy, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QComboBox, QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, QRectF
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QFont
```

(Replace the three import lines added in Task 3 with this expanded block.)

Append at the end of the file:

```python
def _format_duration(minutes: int) -> str:
    h, m = divmod(minutes, 60)
    return f"{h}h {m}m"


class TimeRangeEditor(QWidget):
    """Range slider + manual Start/End (h:mm + AM/PM) kept in two-way sync.

    Drag snaps to 15 min; typing accepts any minute in 08:00–16:00 and clamps
    to bounds / enforces the 15-min minimum window. start_hhmm()/end_hhmm()
    return 24-hour 'HH:mm' for saving.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        from db.members import time_12h_to_24h  # reuse existing parser
        self._parse_12h = time_12h_to_24h
        self._start = MIN_MINUTES
        self._end = MAX_MINUTES

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._readout = QLabel()
        self._readout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._readout.setStyleSheet("font-size:16px; font-weight:700;")
        layout.addWidget(self._readout)

        self._slider = RangeSlider()
        self._slider.windowChanged.connect(self._on_slider)
        layout.addWidget(self._slider)

        self._start_edit, self._start_period = self._time_field(layout, "Start")
        self._end_edit, self._end_period = self._time_field(layout, "End")

        self._refresh()

    def _time_field(self, layout, label):
        row = QHBoxLayout()
        row.addWidget(QLabel(f"{label}:"))
        edit = QLineEdit()
        edit.setPlaceholderText("h:mm")
        period = QComboBox()
        period.addItems(["AM", "PM"])
        row.addWidget(edit)
        row.addWidget(period)
        row.addStretch()
        layout.addLayout(row)
        commit = self._commit_start if label == "Start" else self._commit_end
        edit.editingFinished.connect(commit)
        period.currentIndexChanged.connect(commit)
        return edit, period

    # ── public API ───────────────────────────────────────────────────────
    def set_window(self, start_hhmm: str, end_hhmm: str) -> None:
        self._start = clamp_minutes(hhmm_to_minutes(start_hhmm))
        self._end = clamp_minutes(hhmm_to_minutes(end_hhmm))
        if self._end < self._start + MIN_WINDOW:
            self._end = clamp_minutes(self._start + MIN_WINDOW)
        self._refresh()

    def start_hhmm(self) -> str:
        return minutes_to_hhmm(self._start)

    def end_hhmm(self) -> str:
        return minutes_to_hhmm(self._end)

    # ── sync ─────────────────────────────────────────────────────────────
    def _on_slider(self, start_min: int, end_min: int) -> None:
        self._start, self._end = start_min, end_min
        self._refresh()

    def _commit_start(self) -> None:
        m = self._parse_field(self._start_edit, self._start_period)
        if m is None:
            return
        self._start = clamp_minutes(min(m, self._end - MIN_WINDOW))
        self._refresh()

    def _commit_end(self) -> None:
        m = self._parse_field(self._end_edit, self._end_period)
        if m is None:
            return
        self._end = clamp_minutes(max(m, self._start + MIN_WINDOW))
        self._refresh()

    def _parse_field(self, edit: QLineEdit, period: QComboBox):
        try:
            hhmm = self._parse_12h(edit.text(), period.currentText())
            return clamp_minutes(hhmm_to_minutes(hhmm))
        except ValueError:
            QMessageBox.warning(self, "Validation",
                "Enter times as h:mm with hour 1-12 and minute 00-59.")
            self._refresh()  # revert field to last valid value
            return None

    def _refresh(self) -> None:
        """Push current state to the slider, both fields, and the readout."""
        self._slider.set_window(self._start, self._end)
        st, sp = minutes_to_12h(self._start)
        et, ep = minutes_to_12h(self._end)
        for edit, period, text, per in (
            (self._start_edit, self._start_period, st, sp),
            (self._end_edit, self._end_period, et, ep),
        ):
            edit.blockSignals(True)
            period.blockSignals(True)
            edit.setText(text)
            period.setCurrentText(per)
            edit.blockSignals(False)
            period.blockSignals(False)
        self._readout.setText(
            f"{st} {sp}  –  {et} {ep}   ·   {_format_duration(self._end - self._start)}"
        )
```

- [ ] **Step 2: Verify the module imports**

Run: `.venv\Scripts\python -c "from gui.time_range_editor import TimeRangeEditor; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Smoke-test the sync logic headlessly**

Run:
```
set QT_QPA_PLATFORM=offscreen && .venv\Scripts\python -c "from PyQt6.QtWidgets import QApplication; from gui.time_range_editor import TimeRangeEditor; app=QApplication([]); e=TimeRangeEditor(); e.set_window('09:30','14:45'); print(e.start_hhmm(), e.end_hhmm())"
```
Expected: `09:30 14:45`

- [ ] **Step 4: Run the full suite**

Run: `.venv\Scripts\pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add gui/time_range_editor.py
git commit -m "feat: TimeRangeEditor — slider + manual fields with two-way sync"
```
End with:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Task 5: Availability tab Edit button + modal dialog

**Files:**
- Modify: `gui/member_tabs.py`

- [ ] **Step 1: Replace `_make_avail_tab()` with a bespoke table**

Replace the entire `_make_avail_tab()` method:

```python
    def _make_avail_tab(self) -> QWidget:
        from PyQt6.QtWidgets import (
            QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView,
        )
        day_names = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri"}

        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 12, 0, 0)

        columns = ["ID", "Day", "Start", "End", "Effective From", "Action"]
        table = QTableWidget(len(self._availability), len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        hdr = table.horizontalHeader()
        hdr.setStretchLastSection(False)
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        table.verticalHeader().setVisible(False)

        for r, a in enumerate(self._availability):
            table.setItem(r, 0, QTableWidgetItem(str(a["id"])))
            table.setItem(r, 1, QTableWidgetItem(
                day_names.get(a["day_of_week"], str(a["day_of_week"]))))
            table.setItem(r, 2, QTableWidgetItem(a["avail_start"] or ""))
            table.setItem(r, 3, QTableWidgetItem(a["avail_end"] or ""))
            table.setItem(r, 4, QTableWidgetItem(str(a["effective_start_date"])))
            btn = QPushButton("Edit")
            btn.setObjectName("btn_edit")
            btn.clicked.connect(lambda _=False, av=a: self._edit_avail(av))
            table.setCellWidget(r, 5, btn)

        self._avail_table = table
        layout.addWidget(table)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("+ Add")
        btn_add.clicked.connect(self._add_avail)
        btn_del = QPushButton("Delete Selected")
        btn_del.clicked.connect(lambda: self._delete_avail(table))
        btn_row.addWidget(btn_add)
        btn_row.addStretch()
        btn_row.addWidget(btn_del)
        layout.addLayout(btn_row)
        return w
```

- [ ] **Step 2: Add the `_edit_avail()` handler**

Add this method immediately after `_make_avail_tab()` (before `_add_avail`):

```python
    def _edit_avail(self, avail: dict):
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QDialogButtonBox
        from gui.time_range_editor import TimeRangeEditor
        from db.members import update_availability
        from db.events import open_db, insert_event
        from monthly_schedule.db import get_availability

        day_names = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri"}
        day_name = day_names.get(avail["day_of_week"], str(avail["day_of_week"]))

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Edit Availability — {day_name}")
        v = QVBoxLayout(dlg)
        v.addWidget(QLabel(f"Day: {day_name}"))

        editor = TimeRangeEditor()
        editor.set_window(avail["avail_start"] or "08:00", avail["avail_end"] or "16:00")
        v.addWidget(editor)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        v.addWidget(btns)

        if not dlg.exec():
            return
        ts, te = editor.start_hhmm(), editor.end_hhmm()
        try:
            update_availability(avail["id"], ts, te, self._db_path)
            self._availability = get_availability(self._center_id, self._db_path)
            self._refresh_tab(3, self._make_avail_tab())
            if self._events_path:
                conn = open_db(self._events_path)
                try:
                    m = self._member
                    insert_event(conn, "AVAIL", self._center_id,
                        f"{m.get('last_name')}, {m.get('first_name')}",
                        f"Availability edited: {day_name} {ts}–{te}")
                finally:
                    conn.close()
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
```

- [ ] **Step 3: Verify the import works**

Run: `.venv\Scripts\python -c "from gui.member_tabs import MemberTabsWidget; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Run the full suite (unaffected)**

Run: `.venv\Scripts\pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add gui/member_tabs.py
git commit -m "feat: edit availability via per-row Edit button + range-slider dialog"
```
End with:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Task 6: Full suite + exe rebuild + manual smoke test

**Files:** none changed

- [ ] **Step 1: Run the full test suite**

Run: `.venv\Scripts\pytest -q`
Expected: all pass (prior 70 + ~11 new: update_availability unit + integration, and the 8 time_range_editor unit cases).

- [ ] **Step 2: Rebuild the exe**

Stop any running instance (it locks the output file), then build:

```
powershell -Command "try { Stop-Process -Name MemberManager -Force -ErrorAction Stop } catch {}"
.venv\Scripts\pyinstaller MemberManager.spec
```

Expected: `Build complete! The results are available in: ...\dist`

- [ ] **Step 3: Manual smoke test**

Launch `dist\MemberManager.exe`, set the DB path if needed, click a member → Availability tab:
- Each row has an **Edit** button. Click one → a modal "Edit Availability — <Day>" dialog shows the range slider + Start/End fields + a live readout, seeded to the row's window.
- **Drag** a handle → snaps to 15 min; readout and fields update live; handles can't cross (min 15 min).
- **Type** `8:07` in Start → the start handle moves off-tick to 8:07; type a time outside 8 AM–4 PM → a warning shows and the field reverts.
- **Save** → the table row updates to the new Start/End and an AVAIL event is logged; **Cancel** discards.

---

## Self-Review Notes

- **Spec coverage:** DB `update_availability` → Task 1. Pure helpers (minutes/hhmm/clamp/snap/12h) → Task 2. Custom two-handle `RangeSlider` (paint, drag-snap, min-window, keyboard) → Task 3. `TimeRangeEditor` composite + two-way sync + readout → Task 4. Bespoke Availability tab + per-row Edit + modal dialog wiring `update_availability` + AVAIL event → Task 5. Testing → Tasks 1–2 (unit/integration) + Task 6 (full run + manual). Bounds 8 AM–4 PM, 15-min snap, manual any-minute, 15-min min window are encoded in the constants and helpers.
- **Type consistency:** `hhmm_to_minutes`, `minutes_to_hhmm`, `clamp_minutes`, `snap_minutes`, `minutes_to_12h`, `RangeSlider.set_window/window/windowChanged`, `TimeRangeEditor.set_window/start_hhmm/end_hhmm`, `update_availability(record_id, avail_start, avail_end, db_path)` are used consistently across tasks. The editor reuses `db.members.time_12h_to_24h`. Avail dicts expose `avail_start`/`avail_end` as `"HH:mm"` and `day_of_week`/`effective_start_date` (from `map_availability_row`).
- **No placeholders:** every code step is complete; commands have expected output.
- **Note:** Add Availability is intentionally left unchanged (per spec). The `btn_edit` style already exists in `gui/theme.py` from earlier work, so no theme change is needed.
