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


def test_weekday_chips_on_off(qapp):
    from gui.member_tabs import WeekdayChips
    w = WeekdayChips({1, 3, 5})
    names = [c.objectName() for c in w._chips]
    assert len(names) == 7
    assert names == [
        "day_chip_on", "day_chip_off", "day_chip_on",
        "day_chip_off", "day_chip_on", "day_chip_off", "day_chip_off",
    ]


def test_weekday_chips_all_off(qapp):
    from gui.member_tabs import WeekdayChips
    w = WeekdayChips(set())
    assert len(w._chips) == 7
    assert all(c.objectName() == "day_chip_off" for c in w._chips)


def test_weekday_chips_full_labels(qapp):
    from gui.member_tabs import WeekdayChips
    w = WeekdayChips({1})
    assert [c.text() for c in w._chips] == [
        "MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN",
    ]


def test_weekday_chips_compact_single_letter(qapp):
    from gui.member_tabs import WeekdayChips
    w = WeekdayChips({1, 2}, compact=True)
    assert [c.text() for c in w._chips] == ["M", "T", "W", "T", "F", "S", "S"]
    assert w._chips[0].objectName() == "day_chip_on"


def test_theme_has_chip_styles():
    from gui.theme import build_qss, DARK, LIGHT
    for tokens in (DARK, LIGHT):
        qss = build_qss(tokens)
        assert "QLabel#day_chip_on" in qss
        assert "QLabel#day_chip_off" in qss
