import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


# ── parse_dob (pure) ──────────────────────────────────────────────────────

def test_parse_dob_accepts_m_d_yyyy():
    from datetime import date
    from gui.wizard.step_contact import parse_dob
    assert parse_dob("5/14/1948") == date(1948, 5, 14)
    assert parse_dob("05/14/1948") == date(1948, 5, 14)


def test_parse_dob_accepts_dashes():
    from datetime import date
    from gui.wizard.step_contact import parse_dob
    assert parse_dob("5-14-1948") == date(1948, 5, 14)


def test_parse_dob_rejects_garbage_and_empty():
    from gui.wizard.step_contact import parse_dob
    assert parse_dob("not a date") is None
    assert parse_dob("13/40/2020") is None
    assert parse_dob("") is None
    assert parse_dob("   ") is None


def _make_filled():
    """A StepContact with every required field set to a valid value."""
    from gui.wizard.step_contact import StepContact
    w = StepContact()
    w.first_name.setText("Jane")
    w.last_name.setText("Doe")
    w.center_id.setText("999001")
    w.member_id.setText("M12345")
    w.dob.setText("6/15/1950")
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


def test_validate_rejects_empty_dob(qapp):
    w = _make_filled()
    w.dob.setText("")  # empty -> the gray placeholder shows; not a value
    assert w.validate("dummy.accdb") is False
    assert "Date of Birth is required" in w._error_label.text()


def test_validate_rejects_unparseable_dob(qapp):
    w = _make_filled()
    w.dob.setText("not a date")
    assert w.validate("dummy.accdb") is False
    assert "valid date" in w._error_label.text()


def test_validate_rejects_future_dob(qapp):
    from datetime import date, timedelta
    w = _make_filled()
    future = date.today() + timedelta(days=1)
    w.dob.setText(f"{future.month}/{future.day}/{future.year}")
    assert w.validate("dummy.accdb") is False
    assert "future" in w._error_label.text().lower()


def test_dob_is_a_typeable_field_with_placeholder(qapp):
    from PyQt6.QtWidgets import QLineEdit
    from gui.wizard.step_contact import StepContact
    w = StepContact()
    assert isinstance(w.dob, QLineEdit)          # typeable, not a dropdown
    assert not w.dob.text()                       # empty by default
    assert "birth" in w.dob.placeholderText().lower()  # gray placeholder hint


def test_collect_returns_dob_as_date(qapp):
    # Production Contacts.[DOB] is an Access Date/Time column, so collect()
    # yields a datetime.date that pyodbc binds straight to it.
    from datetime import date
    w = _make_filled()
    assert w.collect()["dob"] == date(1950, 6, 15)


def test_center_id_prefilled_and_locked_when_suggested(qapp):
    from gui.wizard.step_contact import StepContact
    w = StepContact(center_id=10056)
    assert w.center_id.text() == "10056"
    assert w.center_id.isReadOnly() is True


def test_center_id_editable_when_no_suggestion(qapp):
    from gui.wizard.step_contact import StepContact
    w = StepContact()
    assert w.center_id.isReadOnly() is False
