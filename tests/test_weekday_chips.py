import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from gui.member_tabs import decode_auth_days, format_auth_days


def test_decode_basic():
    assert decode_auth_days("1,3,5") == {1, 3, 5}


def test_decode_empty():
    assert decode_auth_days("") == set()


def test_decode_tolerates_blank_tokens():
    assert decode_auth_days("2,,7, ") == {2, 7}


def test_decode_ignores_non_numeric():
    assert decode_auth_days("1,x,3") == {1, 3}


def test_format_auth_days_regression():
    assert format_auth_days("1,3,5") == "Mon Wed Fri"


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app
