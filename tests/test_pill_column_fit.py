import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_fit_pill_column_is_wide_enough_for_widest_pill(qapp):
    from gui.member_tabs import _fit_pill_column
    from PyQt6.QtWidgets import QTableWidget, QLabel, QHeaderView
    t = QTableWidget(2, 2)
    pills = [QLabel("Active"), QLabel("Expired-and-longer")]
    _fit_pill_column(t, 1, pills, floor=40)
    widest = max(p.sizeHint().width() for p in pills)
    # Column must leave room for the pill plus the centered-cell margins so the
    # pill is never squeezed below its content (which is what clipped the text).
    assert t.columnWidth(1) >= widest + 12
    assert t.horizontalHeader().sectionResizeMode(1) == QHeaderView.ResizeMode.Fixed


def test_fit_pill_column_uses_floor_when_no_pills(qapp):
    from gui.member_tabs import _fit_pill_column
    from PyQt6.QtWidgets import QTableWidget
    t = QTableWidget(1, 2)
    _fit_pill_column(t, 1, [], floor=90)
    assert t.columnWidth(1) == 90


def test_centered_cell_pins_widget_minimum_width(qapp):
    from gui.member_tabs import _centered_cell, make_plan_badge
    badge = make_plan_badge("HF")
    cell = _centered_cell(badge)   # keep a ref so the cell/badge aren't GC'd
    assert cell is not None
    # The pill can't be shrunk below its own content width.
    assert badge.minimumWidth() >= badge.sizeHint().width()
