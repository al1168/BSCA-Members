import os
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _focus_out(w):
    from PyQt6.QtGui import QFocusEvent
    from PyQt6.QtCore import QEvent
    w.focusOutEvent(QFocusEvent(QEvent.Type.FocusOut))


# ── pure parse/format ──────────────────────────────────────────────────────
def test_parse_mdy():
    from db.members import parse_mdy
    assert parse_mdy("1/5/2026") == date(2026, 1, 5)
    assert parse_mdy("01/05/2026") == date(2026, 1, 5)
    assert parse_mdy("13/01/2026") is None      # bad month
    assert parse_mdy("2026-01-05") is None       # wrong separators
    assert parse_mdy("") is None


def test_format_mdy():
    from db.members import format_mdy
    assert format_mdy("01052026") == "01/05/2026"
    assert format_mdy("1/5/2026") == "1/5/2026"  # already slashed -> untouched
    assert format_mdy("123") == "123"
    assert format_mdy("") == ""


# ── DateLineEdit widget ────────────────────────────────────────────────────
def test_datelineedit_autoformats_and_reads(qapp):
    from gui.address_autocomplete import DateLineEdit
    d = DateLineEdit()
    d.setText("01052026")
    _focus_out(d)
    assert d.text() == "01/05/2026"
    assert d.to_pydate() == date(2026, 1, 5)
    assert d.property("error") in (False, None)


def test_datelineedit_flags_invalid(qapp):
    from gui.address_autocomplete import DateLineEdit
    d = DateLineEdit()
    d.setText("13/40/2026")
    _focus_out(d)
    assert d.to_pydate() is None
    assert d.property("error") is True


def test_datelineedit_empty_optional_vs_required(qapp):
    from gui.address_autocomplete import DateLineEdit
    d = DateLineEdit()
    assert d.is_valid() is True
    assert d.is_valid(required=True) is False


def test_datelineedit_minimum(qapp):
    from gui.address_autocomplete import DateLineEdit
    d = DateLineEdit(minimum=date(2026, 6, 20))
    d.set_pydate(date(2026, 6, 19))
    assert d.is_valid() is False
    d.set_pydate(date(2026, 6, 21))
    assert d.is_valid() is True


def test_datelineedit_set_pydate(qapp):
    from gui.address_autocomplete import DateLineEdit
    d = DateLineEdit()
    d.set_pydate(date(2026, 7, 1))
    assert d.text() == "07/01/2026"
    d.set_pydate(None)
    assert d.text() == ""
