import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_auth_number_collected_with_auth(qapp):
    from gui.wizard.step_auths import StepAuths
    w = StepAuths()
    w._day_checks[1].setChecked(True)
    w.auth_number.setText("  A-2026-01  ")     # trimmed
    data = w.collect()
    assert data["authorization"] is not None
    assert data["authorization"]["auth_number"] == "A-2026-01"


def test_auth_number_blank_when_unset(qapp):
    from gui.wizard.step_auths import StepAuths
    w = StepAuths()
    w._day_checks[2].setChecked(True)
    data = w.collect()
    assert data["authorization"]["auth_number"] == ""


def test_auth_number_alone_engages_the_step(qapp):
    # Typing an auth number without checking days no longer silently
    # discards it: the step is engaged and must be completed to pass
    # validation (explicit-entry rule, 2026-09-01 spec).
    from gui.wizard.step_auths import StepAuths
    w = StepAuths()
    w.auth_number.setText("A-999")
    assert w.is_skipped() is False
    assert w.validate() is False        # incomplete -> blocked, not dropped


def test_review_shows_auth_number(qapp):
    from gui.wizard.step_review import StepReview
    r = StepReview()
    r.populate({
        "contact": {"last_name": "Doe", "first_name": "J", "center_id": 1,
                    "health_plan": "HF"},
        "enrollment_start": "2026-01-01", "enrollment_end": None,
        "authorization": {"auth_start": "2026-01-01", "auth_end": "2026-12-31",
                          "auth_days": {1, 3}, "auth_number": "A-2026-01"},
    })
    assert "A-2026-01" in r._body.text()
