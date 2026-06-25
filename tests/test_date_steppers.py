import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_filter_disables_date_and_time_steppers(qapp):
    from PyQt6.QtWidgets import QDateEdit, QTimeEdit, QAbstractSpinBox
    from member_manager import _NoStepButtonsFilter

    f = _NoStepButtonsFilter()
    qapp.installEventFilter(f)
    de = QDateEdit()
    de.setCalendarPopup(True)
    te = QTimeEdit()
    try:
        de.show()
        te.show()
        qapp.processEvents()
        none = QAbstractSpinBox.ButtonSymbols.NoButtons
        assert de.buttonSymbols() == none      # no up/down steppers to click
        assert te.buttonSymbols() == none
        assert de.calendarPopup() is True       # calendar popup still available
    finally:
        qapp.removeEventFilter(f)
        de.deleteLater()
        te.deleteLater()
