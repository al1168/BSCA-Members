import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _focus_out(widget):
    from PyQt6.QtGui import QFocusEvent
    from PyQt6.QtCore import QEvent
    widget.focusOutEvent(QFocusEvent(QEvent.Type.FocusOut))


def test_phone_autoformats_digits_on_focus_out(qapp):
    from gui.address_autocomplete import PhoneLineEdit
    pe = PhoneLineEdit()
    pe.setText("2125550100")          # just digits
    _focus_out(pe)
    assert pe.text() == "(212)-555-0100"
    assert pe.property("error") in (False, None)


def test_phone_flags_error_when_too_long(qapp):
    from gui.address_autocomplete import PhoneLineEdit
    pe = PhoneLineEdit()
    pe.setText("12345678901234")       # too many digits
    _focus_out(pe)
    assert pe.is_valid() is False
    assert pe.property("error") is True


def test_phone_empty_is_valid(qapp):
    from gui.address_autocomplete import PhoneLineEdit
    pe = PhoneLineEdit()
    assert pe.is_valid() is True


def test_editing_clears_phone_error(qapp):
    from gui.address_autocomplete import PhoneLineEdit, set_widget_error
    pe = PhoneLineEdit()
    set_widget_error(pe, True)
    pe.textEdited.emit("2")            # user types -> error clears
    assert pe.property("error") is False


def test_wizard_highlights_invalid_phone(qapp):
    from gui.wizard.step_contact import StepContact
    s = StepContact(api_key="")        # editable center id (no suggestion)
    s.first_name.setText("Ann")
    s.last_name.setText("Lee")
    s.center_id.setText("12345")
    s.member_id.setText("M-1")
    s.dob.setText("01-01-2000")
    s.health_plan.setCurrentIndex(1)   # a real plan (index 0 is blank)
    s.home_tell.setText("12345")       # only 5 digits -> invalid
    # center_id_exists is not reached (phone check fails first), so db_path is unused.
    assert s.validate(db_path="missing.accdb") is False
    assert s.home_tell.property("error") is True
