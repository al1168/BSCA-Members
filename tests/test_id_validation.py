import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from db.members import (
    format_ssn, is_valid_ssn,
    format_medicaid, is_valid_medicaid,
    format_medicare, is_valid_medicare,
)


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


# ── SSN: format xxx-xx-xxxx ────────────────────────────────────────────────
def test_format_ssn_from_digits():
    assert format_ssn("123456789") == "123-45-6789"
    assert format_ssn("123-45-6789") == "123-45-6789"   # idempotent
    assert format_ssn("12345") == "12345"               # not 9 digits -> unchanged
    assert format_ssn("") == ""


def test_is_valid_ssn():
    assert is_valid_ssn("") is True                      # optional
    assert is_valid_ssn("123-45-6789") is True
    assert is_valid_ssn("123456789") is False            # must be dashed form
    assert is_valid_ssn("12-345-6789") is False


# ── Medicaid: AAdddddA ─────────────────────────────────────────────────────
def test_format_medicaid_uppercases():
    assert format_medicaid("ab12345c") == "AB12345C"
    assert format_medicaid("") == ""


def test_is_valid_medicaid():
    assert is_valid_medicaid("") is True
    assert is_valid_medicaid("AB12345C") is True
    assert is_valid_medicaid("ab12345c") is True         # case-insensitive
    assert is_valid_medicaid("A12345C") is False         # one letter prefix
    assert is_valid_medicaid("AB1234C") is False         # 4 digits
    assert is_valid_medicaid("AB123456") is False        # ends with a digit


# ── Medicare (MBI) ─────────────────────────────────────────────────────────
def test_is_valid_medicare():
    assert is_valid_medicare("") is True
    assert is_valid_medicare("1EG4TE5MK73") is True      # no dashes
    assert is_valid_medicare("1EG4-TE5-MK73") is True    # dashes optional
    assert is_valid_medicare("1eg4te5mk73") is True      # lowercase ok
    assert is_valid_medicare("0EG4TE5MK73") is False     # must start 1-9
    assert is_valid_medicare("1BG4TE5MK73") is False     # B not allowed in 2nd pos
    assert is_valid_medicare("1EG4TE5MK7") is False      # too short


def test_format_medicare_uppercases():
    assert format_medicare("1eg4-te5-mk73") == "1EG4-TE5-MK73"


# ── live (as-you-type) formatters ──────────────────────────────────────────
def test_format_ssn_live():
    from db.members import format_ssn_live
    assert format_ssn_live("1") == "1"
    assert format_ssn_live("123") == "123"
    assert format_ssn_live("1234") == "123-4"
    assert format_ssn_live("12345") == "123-45"
    assert format_ssn_live("123456") == "123-45-6"
    assert format_ssn_live("123456789") == "123-45-6789"
    assert format_ssn_live("1234567890123") == "123-45-6789"   # capped at 9
    assert format_ssn_live("12ab34") == "123-4"                 # non-digits dropped


def test_format_medicare_live():
    from db.members import format_medicare_live
    assert format_medicare_live("1eg4") == "1EG4"
    assert format_medicare_live("1eg45") == "1EG4-5"            # dash after 4
    assert format_medicare_live("1eg4te5") == "1EG4-TE5"
    assert format_medicare_live("1eg4te5m") == "1EG4-TE5-M"     # dash after 7
    assert format_medicare_live("1eg4te5mk73") == "1EG4-TE5-MK73"
    assert format_medicare_live("1eg4-te5-mk73xx") == "1EG4-TE5-MK73"  # capped at 11


def test_format_medicaid_live():
    from db.members import format_medicaid_live
    assert format_medicaid_live("ab123") == "AB123"
    assert format_medicaid_live("ab12345c") == "AB12345C"
    assert format_medicaid_live("ab-123 45c!") == "AB12345C"    # strips non-alnum
    assert format_medicaid_live("ab12345cZZ") == "AB12345C"     # capped at 8


# ── inline field auto-formats on commit and flags invalid input ────────────
def test_viewedit_formats_and_flags_error(qapp):
    import gui.member_tabs as mt
    f = mt._ViewEditLineEdit("123456789", formatter=format_ssn, validator=is_valid_ssn)
    assert f.text() == "123-45-6789"            # formatted on construction

    f._begin_edit()
    f.setText("12345")                          # invalid (not 9 digits)
    f._finish_edit()
    assert f.property("error") is True

    f._begin_edit()
    f.setText("999999999")                      # valid -> formats, clears error
    f._finish_edit()
    assert f.text() == "999-99-9999"
    assert f.property("error") in (False, None)


def test_viewedit_formats_as_you_type(qapp):
    import gui.member_tabs as mt
    from db.members import format_ssn_live, format_medicare_live
    f = mt._ViewEditLineEdit("", formatter=format_ssn, validator=is_valid_ssn,
                             live_formatter=format_ssn_live)
    f.setReadOnly(False)
    f.setText("1234")
    f._on_edited()                              # simulate a keystroke edit
    assert f.text() == "123-4"

    g = mt._ViewEditLineEdit("", formatter=format_medicare,
                             validator=is_valid_medicare,
                             live_formatter=format_medicare_live)
    g.setReadOnly(False)
    g.setText("1eg45")
    g._on_edited()
    assert g.text() == "1EG4-5"                 # dashed + uppercased live
