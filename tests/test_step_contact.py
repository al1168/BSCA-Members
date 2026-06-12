import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _make_filled():
    """A StepContact with every required field set to a valid value."""
    from PyQt6.QtCore import QDate
    from gui.wizard.step_contact import StepContact
    w = StepContact()
    w.first_name.setText("Jane")
    w.last_name.setText("Doe")
    w.center_id.setText("999001")
    w.member_id.setText("M12345")
    w.dob.setDate(QDate(1950, 6, 15))
    w.health_plan.setCurrentText("HF")
    w.home_tell.setText("212-555-0100")
    w.cell.setText("")
    w.address.setText("1 Main St, New York, NY")
    return w


@pytest.fixture(autouse=True)
def _no_db(monkeypatch):
    """validate() ends with a Center ID uniqueness DB lookup; stub it out so the
    presence-rule tests never touch a database."""
    import db.members as dbm
    monkeypatch.setattr(dbm, "center_id_exists", lambda cid, db_path: False)


def test_validate_rejects_missing_member_id(qapp):
    w = _make_filled()
    w.member_id.setText("")
    assert w.validate("dummy.accdb") is False
    assert "Member ID" in w._error_label.text()


def test_validate_rejects_missing_both_phones(qapp):
    w = _make_filled()
    w.home_tell.setText("")
    w.cell.setText("")
    assert w.validate("dummy.accdb") is False
    assert "phone" in w._error_label.text().lower()


def test_validate_accepts_when_only_cell_filled(qapp):
    w = _make_filled()
    w.home_tell.setText("")
    w.cell.setText("646-555-0199")
    assert w.validate("dummy.accdb") is True


def test_validate_rejects_missing_address(qapp):
    w = _make_filled()
    w.address.setText("")
    assert w.validate("dummy.accdb") is False
    assert "Address" in w._error_label.text()


def test_validate_happy_path(qapp):
    w = _make_filled()
    assert w.validate("dummy.accdb") is True


def test_collect_includes_new_fields(qapp):
    w = _make_filled()
    d = w.collect()
    assert d["member_id"] == "M12345"
    assert d["home_tell"] == "212-555-0100"
    assert d["cell"] == ""


def test_validate_rejects_unset_dob(qapp):
    w = _make_filled()
    w.dob.setDate(w.dob.minimumDate())  # the "Select date of birth" sentinel
    assert w.validate("dummy.accdb") is False
    assert "Date of Birth" in w._error_label.text()


def test_collect_returns_dob_as_date(qapp):
    # Production Contacts.[DOB] is an Access Date/Time column, so collect()
    # yields a datetime.date that pyodbc binds straight to it.
    from datetime import date
    w = _make_filled()
    assert w.collect()["dob"] == date(1950, 6, 15)
