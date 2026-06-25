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


def test_dob_autoformats_8_digits_on_blur(qapp):
    from gui.wizard.step_contact import DobLineEdit
    d = DobLineEdit()
    d.setText("01012000")              # just digits
    _focus_out(d)
    assert d.text() == "01-01-2000"
    assert d.property("error") in (False, None)


def test_dob_formats_as_you_type(qapp):
    from gui.wizard.step_contact import DobLineEdit
    d = DobLineEdit()
    d.setText("0101")
    d._on_edited()                     # simulate a keystroke
    assert d.text() == "01-01"
    d.setText("01-012000")
    d._on_edited()
    assert d.text() == "01-01-2000"


def test_dob_input_is_numbers_only(qapp):
    from gui.wizard.step_contact import DobLineEdit
    d = DobLineEdit()
    val = d.validator()
    from PyQt6.QtGui import QValidator
    # letters and slashes are rejected by the validator; digits pass
    assert val.validate("12/34", 0)[0] == QValidator.State.Invalid
    assert val.validate("ab", 0)[0] == QValidator.State.Invalid
    assert val.validate("01012000", 0)[0] == QValidator.State.Acceptable


def test_dob_flags_invalid_on_blur(qapp):
    from gui.wizard.step_contact import DobLineEdit
    d = DobLineEdit()
    d.setText("99999999")              # formats to 99-99-9999 -> not a real date
    _focus_out(d)
    assert d.property("error") is True


def test_dob_empty_no_error(qapp):
    from gui.wizard.step_contact import DobLineEdit
    d = DobLineEdit()
    _focus_out(d)
    assert d.property("error") in (False, None)


def test_editing_clears_dob_error(qapp):
    from gui.wizard.step_contact import DobLineEdit
    from gui.address_autocomplete import set_widget_error
    d = DobLineEdit()
    set_widget_error(d, True)
    d.textEdited.emit("0")
    assert d.property("error") is False
