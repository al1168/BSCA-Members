import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _field():
    from gui.member_tabs import _ViewEditLineEdit
    from db.members import (
        format_medicaid, is_valid_medicaid, format_medicaid_live,
    )
    return _ViewEditLineEdit(
        "", formatter=format_medicaid, validator=is_valid_medicaid,
        live_formatter=format_medicaid_live)


def test_partial_value_flags_error_live(qapp):
    w = _field()
    w.setText("AB123")
    w._on_edited()                      # simulate a keystroke handler
    assert w.property("error") is True  # incomplete -> red outline as you type


def test_complete_value_clears_error_live(qapp):
    w = _field()
    w.setText("AB12345C")
    w._on_edited()
    assert w.property("error") is False


def test_empty_is_valid(qapp):
    w = _field()
    w.setText("")
    w._on_edited()
    assert w.property("error") is False


def test_live_formatter_uppercases_as_you_type(qapp):
    w = _field()
    w.setText("ab12345c")
    w._on_edited()
    assert w.text() == "AB12345C"       # letters uppercased live
    assert w.property("error") is False
