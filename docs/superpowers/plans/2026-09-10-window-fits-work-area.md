# Main Window Fits The Work Area — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep the Care Manager main window's bottom edge above the Windows taskbar on every screen, so the Info tab's Save / Discard / Customize Layout row is never hidden.

**Architecture:** A pure function `choose_startup_geometry(desired, avail)` in `gui/main_window.py` decides between a centered rect (screen big enough) and "maximize" (screen too small for the desired client size plus a fixed frame allowance). `MainWindow._apply_default_geometry` applies that answer: resize+move, or set the maximized window state before `show()`. Spec: `docs/superpowers/specs/2026-09-10-window-fits-work-area-design.md`.

**Tech Stack:** Python 3.11, PyQt6, pytest (offscreen platform). Run everything from the repo root `C:\Users\luald\OneDrive\Desktop\BSCA-Members` with `.venv\Scripts\python.exe`. Prefix runs with `PYTHONUTF8=1` (some window text is non-ASCII).

---

## Background for the engineer

- `gui/main_window.py` line 207 (`_apply_default_geometry`) currently does:

  ```python
  desired_w, desired_h = 1800, 920
  screen = QApplication.primaryScreen()
  avail = screen.availableGeometry() if screen else None
  if avail is not None:
      w = min(desired_w, avail.width())
      h = min(desired_h, avail.height())
      self.resize(w, h)
      self.move(avail.x() + (avail.width() - w) // 2,
                avail.y() + (avail.height() - h) // 2)
  else:
      self.resize(desired_w, desired_h)
  ```

  `resize()` sets the client size; the title bar (~30 px) is added on top, so on
  a work area of 920 px or less the window overshoots below the taskbar.
- `member_manager.py` lines 67-68 construct `MainWindow(settings, SETTINGS_PATH)`
  then call `window.show()`. Do not change it.
- Tests build the window headlessly with `MainWindow({"db_path": "", "theme": "dark"}, str(tmp_path / "settings.json"))` (see `tests/test_bookmark_button.py`); an empty `db_path` is handled silently.
- Under `QT_QPA_PLATFORM=offscreen` the primary screen is 800x600.

## File structure

- Modify: `gui/main_window.py` — add `FRAME_ALLOWANCE_W`, `FRAME_ALLOWANCE_H`, `choose_startup_geometry()` near the top (after `TERMINATED_ROLE`), rewrite `_apply_default_geometry`.
- Create: `tests/test_startup_geometry.py` — pure-function tests plus one widget test.

---

### Task 0: Branch

- [ ] **Step 1: Create the working branch**

```bash
git checkout -b fix/window-fits-work-area
```

Expected: `Switched to a new branch 'fix/window-fits-work-area'`

---

### Task 1: `choose_startup_geometry` (pure decision)

**Files:**
- Modify: `gui/main_window.py` (add after line 20, `TERMINATED_ROLE = ...`)
- Create: `tests/test_startup_geometry.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_startup_geometry.py`:

```python
"""Startup geometry: the main window must never hang below the taskbar.

choose_startup_geometry decides between a centered 1800x920 client rect and
'maximize' (None) using a fixed frame allowance, because Qt cannot know the
real frame size before the window is shown."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QRect, QSize


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


DESIRED = QSize(1800, 920)


def _choose(avail):
    from gui.main_window import choose_startup_geometry
    return choose_startup_geometry(DESIRED, avail)


def test_large_screen_centers_desired_size():
    # 2560x1400 work area starting at (0, 0): plenty of room.
    rect = _choose(QRect(0, 0, 2560, 1400))
    assert rect.size() == DESIRED
    assert rect.x() == (2560 - 1800) // 2
    assert rect.y() == (1400 - 920) // 2


def test_centering_respects_work_area_origin():
    # Second monitor to the right, taskbar at the top: origin (2560, 40).
    rect = _choose(QRect(2560, 40, 2560, 1400))
    assert rect.x() == 2560 + (2560 - 1800) // 2
    assert rect.y() == 40 + (1400 - 920) // 2


def test_exactly_desired_size_maximizes():
    # No room for the frame -> maximize.
    assert _choose(QRect(0, 0, 1800, 920)) is None


def test_too_short_maximizes():
    # 1080p at 125% scaling minus a taskbar is ~824 tall: wide enough, too short.
    assert _choose(QRect(0, 0, 2560, 824)) is None


def test_too_narrow_maximizes():
    assert _choose(QRect(0, 0, 1600, 1400)) is None


def test_boundary_with_frame_allowance_fits():
    from gui.main_window import FRAME_ALLOWANCE_W, FRAME_ALLOWANCE_H
    avail = QRect(0, 0, 1800 + FRAME_ALLOWANCE_W, 920 + FRAME_ALLOWANCE_H)
    rect = _choose(avail)
    assert rect is not None
    assert rect.size() == DESIRED


def test_one_pixel_under_allowance_maximizes():
    from gui.main_window import FRAME_ALLOWANCE_W, FRAME_ALLOWANCE_H
    assert _choose(QRect(0, 0, 1800 + FRAME_ALLOWANCE_W,
                         920 + FRAME_ALLOWANCE_H - 1)) is None
    assert _choose(QRect(0, 0, 1800 + FRAME_ALLOWANCE_W - 1,
                         920 + FRAME_ALLOWANCE_H)) is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONUTF8=1 .venv/Scripts/python.exe -m pytest tests/test_startup_geometry.py -q`

Expected: 7 failures, each `ImportError: cannot import name 'choose_startup_geometry' from 'gui.main_window'`.

- [ ] **Step 3: Implement the function**

In `gui/main_window.py`, change the QtCore import (line 10) to:

```python
from PyQt6.QtCore import Qt, QEvent, QObject, QRect, QSize
```

Then add directly after `TERMINATED_ROLE = Qt.ItemDataRole.UserRole + 1` (line 20):

```python
# Room the OS window frame needs around the client area, in logical pixels.
# Qt cannot report the real frame before the window is shown, so these are
# fixed allowances sized for the Windows 10/11 title bar and borders. Erring
# high is safe: it only makes a borderline screen open maximized.
FRAME_ALLOWANCE_W = 16
FRAME_ALLOWANCE_H = 40


def choose_startup_geometry(desired: QSize, avail: QRect) -> QRect | None:
    """Where to open the main window on a screen whose work area is `avail`.

    Returns the client rect of size `desired` centered in `avail` when the
    window plus its frame fits, or None meaning "open maximized" when it does
    not fit in either dimension. Maximizing lets the OS size the frame to the
    work area, so the bottom edge never lands under the taskbar (which is
    what happened when the client size was merely clamped: resize() ignores
    the title bar, so the window overshot by its height)."""
    if (desired.width() + FRAME_ALLOWANCE_W > avail.width()
            or desired.height() + FRAME_ALLOWANCE_H > avail.height()):
        return None
    x = avail.x() + (avail.width() - desired.width()) // 2
    y = avail.y() + (avail.height() - desired.height()) // 2
    return QRect(x, y, desired.width(), desired.height())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `PYTHONUTF8=1 .venv/Scripts/python.exe -m pytest tests/test_startup_geometry.py -q`

Expected: `7 passed`.

- [ ] **Step 5: Commit**

```bash
git add gui/main_window.py tests/test_startup_geometry.py
git commit -m "feat(gui): choose_startup_geometry decides centered vs maximized

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Apply it in `_apply_default_geometry`

**Files:**
- Modify: `gui/main_window.py:_apply_default_geometry` (currently lines ~207-224; shifted down by Task 1's insert)
- Test: `tests/test_startup_geometry.py` (append)

- [ ] **Step 1: Write the failing widget test**

Append to `tests/test_startup_geometry.py`:

```python
def test_main_window_maximizes_on_small_offscreen_screen(qapp, tmp_path):
    """The offscreen platform's primary screen is 800x600, far below the
    1800x920 target, so the window must ask to open maximized rather than
    clamp its client size to the work area."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication
    avail = QApplication.primaryScreen().availableGeometry()
    assert avail.height() < 920, "precondition: offscreen screen is small"
    from gui.main_window import MainWindow
    w = MainWindow({"db_path": "", "theme": "dark"},
                   str(tmp_path / "settings.json"))
    assert w.windowState() & Qt.WindowState.WindowMaximized
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `PYTHONUTF8=1 .venv/Scripts/python.exe -m pytest tests/test_startup_geometry.py::test_main_window_maximizes_on_small_offscreen_screen -q`

Expected: `1 failed` on the final `assert` (window state is `WindowNoState`; the old code clamps to 800x600 instead).

- [ ] **Step 3: Rewrite `_apply_default_geometry`**

Replace the whole method with:

```python
    def _apply_default_geometry(self):
        """Open at 1800x920 (wide enough for the Authorizations table with
        the sidebar) centered on the primary screen when the window plus
        its frame fits the work area; otherwise open maximized so the OS
        keeps the bottom edge — and the Info tab's Save/Discard row on it —
        above the taskbar. See choose_startup_geometry."""
        desired = QSize(1800, 920)
        screen = QApplication.primaryScreen()
        if screen is None:
            self.resize(desired)
            return
        rect = choose_startup_geometry(desired, screen.availableGeometry())
        if rect is None:
            self.setWindowState(self.windowState()
                                | Qt.WindowState.WindowMaximized)
        else:
            self.resize(rect.size())
            self.move(rect.topLeft())
```

- [ ] **Step 4: Run the whole new test file**

Run: `PYTHONUTF8=1 .venv/Scripts/python.exe -m pytest tests/test_startup_geometry.py -q`

Expected: `8 passed`.

- [ ] **Step 5: Run the GUI test files that construct MainWindow**

Run: `PYTHONUTF8=1 .venv/Scripts/python.exe -m pytest tests/test_bookmark_button.py tests/test_company_calendar_dialog.py tests/test_startup_geometry.py -q`

Expected: all pass (nothing asserts on main-window size).

- [ ] **Step 6: Commit**

```bash
git add gui/main_window.py tests/test_startup_geometry.py
git commit -m "fix(gui): open maximized when the window would not fit above the taskbar

resize() sets the client size only; on work areas of 920px or less the
title bar pushed the frame under the taskbar and hid the Info tab's
Save/Discard/Customize Layout row. Small or scaled screens now open
maximized; large screens are unchanged.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Full test run and merge

- [ ] **Step 1: Run the whole suite**

Run: `PYTHONUTF8=1 .venv/Scripts/python.exe -m pytest -q`

Expected: all pass (about 2 minutes; the DB integration tests skip when the test DB is absent).

- [ ] **Step 2: Merge to main and push**

```bash
git checkout main
git merge --ff-only fix/window-fits-work-area
git push origin main
git branch -d fix/window-fits-work-area
```

Expected: fast-forward, then `main -> main` on the push.

- [ ] **Step 3: Rebuild the packaged exe**

Per `docs/deployment.md`, rebuild `CareManager` so staff get the fix; the frozen build is what runs on the small-screen machines.
