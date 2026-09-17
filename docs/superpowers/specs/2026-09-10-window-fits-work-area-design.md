# Main Window Fits The Work Area — Design

**Date:** 2026-09-10
**Status:** Approved

## Problem

On some screens the bottom strip of the Care Manager window sits under the
Windows taskbar, hiding the Info tab's Save Changes / Discard Changes /
Customize Layout row. Staff see it "sometimes", on certain machines, when the
app is opened large.

Cause: `MainWindow._apply_default_geometry` (`gui/main_window.py`) asks for
an 1800×920 window, clamps it to the screen's available (work-area) size,
and centers it. `QWidget.resize()` sets the *client* size; the Windows title
bar and borders add roughly 30 px on top. On any screen whose work area is
920 px tall or shorter, the client area is clamped to the full work-area
height, the frame overshoots by the title-bar height, and the last ~30 px of
the window land under the taskbar. A 1080p monitor at 100 % scaling has a
~1040 px work area and is unaffected; laptops and 125 %/150 % scaling are
affected.

The window's own minimum height is ~478 px (measured with a member open and
every tab built), so content size is not a factor; only the startup
geometry is.

## Decision

Fix the geometry; leave the buttons where they are. Button relocation was
considered (header row, sticky bar under the tab strip, floating pill) and
rejected in favour of fixing the cause, which also un-hides anything else at
the bottom of every tab.

## Design

### Pure decision function — `gui/main_window.py`

```python
FRAME_ALLOWANCE_W = 16   # left + right borders (logical px)
FRAME_ALLOWANCE_H = 40   # title bar + top/bottom borders (logical px)

def choose_startup_geometry(desired: QSize, avail: QRect) -> QRect | None:
    """Return the centered client rect to apply, or None meaning 'maximize'.

    None when the desired client size plus the frame allowance does not fit
    the work area in either dimension."""
```

- Fits: return `QRect` of `desired` size centered inside `avail` (the
  current behaviour).
- Does not fit (width *or* height): return `None`.

Qt cannot know the real frame size before the window is shown, so the
allowance is a constant chosen to cover the Windows 10/11 frame. If the
work area is short by less than the allowance the window still maximizes,
which is the safe direction.

### `_apply_default_geometry`

```python
screen = QApplication.primaryScreen()
if screen is None:
    self.resize(desired); return
rect = choose_startup_geometry(desired, screen.availableGeometry())
if rect is None:
    self.setWindowState(self.windowState() | Qt.WindowState.WindowMaximized)
else:
    self.resize(rect.size()); self.move(rect.topLeft())
```

**Addendum (2026-09-14):** the maximize branch first does `self.resize(avail.size())`. `show()` maximizes asynchronously, so until the event loop runs the widget still reports its pre-show size; when the text-size rebuild reopened a member right after `show()`, the grown minimum exceeded that stale size and Qt resized the maximized native window down to the minimum (a window stuck in the top-left corner on every screen). Pre-sizing to the work area makes any minimum that fits a no-op. Test: `test_maximized_window_is_presized_to_the_work_area`.

Setting the maximized state before `show()` (called by `member_manager.py`)
makes Windows size the frame to the work area, so the bottom edge is always
above the taskbar. No change to `member_manager.py`.

### Not changing

- Primary-screen choice, the 1800×920 target, and centering on large screens.
- Remembering window position/size between runs (out of scope).
- Any button placement.

## Testing (TDD)

Headless tests for `choose_startup_geometry` (no screen needed):

- large work area (e.g. 2560×1400) → rect of 1800×920 centered in it;
- work area exactly 1800×920 → `None` (no room for the frame);
- tall but too narrow work area → `None`;
- wide but too short work area → `None`;
- work area `desired + allowance` → fits (boundary honoured).

Widget test: under the offscreen platform (800×600 screen) a freshly
constructed `MainWindow` has `WindowMaximized` in its window state.

No existing test asserts on main-window geometry.
