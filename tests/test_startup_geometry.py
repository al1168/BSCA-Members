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
