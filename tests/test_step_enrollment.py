import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QDate


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_end_date_minimum_is_sentinel(qapp):
    from gui.wizard.step_enrollment import StepEnrollment
    w = StepEnrollment()
    assert w.end_date.minimumDate() == QDate(2000, 1, 1)
    assert w.end_date.specialValueText() == "Ongoing (leave blank)"


def test_collect_end_none_by_default(qapp):
    from gui.wizard.step_enrollment import StepEnrollment
    w = StepEnrollment()
    assert w.collect()["enrollment_end"] is None
