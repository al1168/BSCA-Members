import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _data():
    from datetime import date
    return {
        "contact": {
            "first_name": "Jane",
            "last_name": "Doe",
            "center_id": 999001,
            "member_id": "M12345",
            "dob": date(1950, 6, 15),
            "health_plan": "HF",
            "home_tell": "212-555-0100",
            "cell": "646-555-0199",
            "address": "1 Main St, New York, NY",
        },
        "enrollment_start": "2026-01-01",
        "enrollment_end": None,
    }


def test_review_shows_member_id(qapp):
    from gui.wizard.step_review import StepReview
    w = StepReview()
    w.populate(_data())
    assert "M12345" in w._body.text()


def test_review_shows_both_phones(qapp):
    from gui.wizard.step_review import StepReview
    w = StepReview()
    w.populate(_data())
    body = w._body.text()
    assert "212-555-0100" in body
    assert "646-555-0199" in body


def test_review_shows_dob(qapp):
    from gui.wizard.step_review import StepReview
    w = StepReview()
    w.populate(_data())
    assert "1950-06-15" in w._body.text()
