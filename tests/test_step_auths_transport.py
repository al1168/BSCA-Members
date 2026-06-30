import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_transport_none_when_auth_skipped(qapp):
    # A transport number alone (no care-auth days checked) creates nothing.
    from gui.wizard.step_auths import StepAuths
    w = StepAuths()
    w.transport_number.setText("T-999")
    data = w.collect()
    assert data["authorization"] is None
    assert data["transport_authorization"] is None


def test_transport_none_when_number_blank(qapp):
    from gui.wizard.step_auths import StepAuths
    w = StepAuths()
    w._day_checks[1].setChecked(True)       # care auth present, no transport #
    data = w.collect()
    assert data["authorization"] is not None
    assert data["transport_authorization"] is None


def test_transport_collected_when_number_and_auth(qapp):
    from gui.wizard.step_auths import StepAuths
    w = StepAuths()
    w._day_checks[1].setChecked(True)
    w._day_checks[3].setChecked(True)
    w.transport_number.setText("  T-123  ")  # trimmed
    data = w.collect()
    assert data["transport_authorization"] == {"auth_number": "T-123"}
