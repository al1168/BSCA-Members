"""Toolbar popups (Bookmarks, Notifications) must land on screen: anchored
under their button, right-aligned, clamped to the screen's work area — and,
when the button sits in the toolbar's "…" overflow menu (Large / Extra Large
text), anchored under the toolbar itself, since an overflowed button has no
on-screen position of its own."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QPoint


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _bar_and_button(qapp, bar_x=100, bar_y=100, bar_w=600, btn_x=500):
    """A shown 'toolbar' at (bar_x, bar_y) with a button near its right end."""
    from PyQt6.QtWidgets import QWidget, QPushButton
    bar = QWidget()
    bar.setGeometry(bar_x, bar_y, bar_w, 50)
    btn = QPushButton("Bookmarks", bar)
    btn.setGeometry(btn_x, 10, 80, 30)
    bar.show()
    qapp.processEvents()
    return bar, btn


def _popup(w=380, h=300):
    from PyQt6.QtWidgets import QWidget
    p = QWidget()
    p.setFixedSize(w, h)
    return p


def test_right_aligned_under_a_visible_button(qapp):
    from gui.popup_placement import place_popup_under
    bar, btn = _bar_and_button(qapp)
    p = _popup()
    place_popup_under(p, btn)
    br = btn.mapToGlobal(btn.rect().bottomRight())
    assert p.pos() == QPoint(br.x() - p.width(), br.y() + 6)


def test_overflowed_button_anchors_under_its_toolbar(qapp):
    from gui.popup_placement import place_popup_under
    bar, btn = _bar_and_button(qapp)
    btn.hide()                                   # what the "…" overflow does
    p = _popup()
    place_popup_under(p, btn)
    br = bar.mapToGlobal(bar.rect().bottomRight())
    assert p.pos() == QPoint(br.x() - p.width(), br.y() + 6)


def test_popup_is_clamped_inside_the_work_area(qapp):
    from PyQt6.QtWidgets import QApplication
    from gui.popup_placement import place_popup_under
    avail = QApplication.primaryScreen().availableGeometry()
    # Button flush with the bottom-left of the (800x600 offscreen) screen: the
    # right-aligned popup would start left of the screen and run off the
    # bottom.
    bar, btn = _bar_and_button(qapp, bar_x=0, bar_y=avail.bottom() - 60,
                               bar_w=300, btn_x=0)
    p = _popup(380, 300)
    place_popup_under(p, btn)
    assert p.x() >= avail.left()
    assert p.y() + p.height() - 1 <= avail.bottom()
    assert p.x() + p.width() - 1 <= avail.right()
