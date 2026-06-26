import os
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_no_end_date_field_and_enrollment_is_ongoing(qapp):
    # The Add Member flow has no enrollment end date; it's always ongoing.
    from gui.wizard.step_enrollment import StepEnrollment
    w = StepEnrollment()
    assert not hasattr(w, "end_date")
    assert w.collect()["enrollment_end"] is None


def test_start_defaults_to_today_and_validates(qapp):
    from gui.wizard.step_enrollment import StepEnrollment
    w = StepEnrollment()
    assert w.collect()["enrollment_start"] == date.today()
    assert w.validate() is True
    w.start_date.setText("")            # required
    assert w.validate() is False
