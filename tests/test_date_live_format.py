"""Dates slash themselves as you type (auth dialogs, enrollment, wizard —
every DateLineEdit)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from db.members import format_mdy_live


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_bare_digits_get_slashed_progressively():
    assert format_mdy_live("0") == "0"
    assert format_mdy_live("07") == "07"
    assert format_mdy_live("071") == "07/1"
    assert format_mdy_live("0710") == "07/10"
    assert format_mdy_live("07102") == "07/10/2"
    assert format_mdy_live("07102026") == "07/10/2026"


def test_extra_digits_capped_at_eight():
    assert format_mdy_live("071020269") == "07/10/2026"


def test_canonical_text_keeps_growing():
    # Simulates typing the 5th digit after auto-slashing: '07/10' + '2'.
    assert format_mdy_live("07/102") == "07/10/2"
    assert format_mdy_live("07/10/2026") == "07/10/2026"


def test_hand_typed_shorthand_left_alone():
    assert format_mdy_live("7/1/2026") == "7/1/2026"
    assert format_mdy_live("7/") == "7/"


def test_backspacing_through_a_slash_drops_it():
    assert format_mdy_live("07/") == "07"


def test_empty_and_none():
    assert format_mdy_live("") == ""
    assert format_mdy_live(None) == ""


def test_widget_formats_real_keystrokes(qapp):
    from PyQt6.QtTest import QTest
    from gui.address_autocomplete import DateLineEdit

    field = DateLineEdit()
    QTest.keyClicks(field, "07102026")
    assert field.text() == "07/10/2026"
    assert field.to_pydate() is not None

    field2 = DateLineEdit()
    QTest.keyClicks(field2, "7/1/2026")     # manual style still works
    assert field2.text() == "7/1/2026"
    assert field2.to_pydate() is not None
