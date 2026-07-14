import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_schedule_card_shows_days_and_period(qapp):
    from PyQt6.QtWidgets import QLabel
    import gui.member_tabs as mt
    w = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)
    card = w._make_schedule_card({1, 3, 5}, "2026-06-01 – 2027-06-19")
    assert card.objectName() == "schedule_card"
    texts = [l.text() for l in card.findChildren(QLabel)]
    assert any("Authorized Days" in t for t in texts)
    assert any("Auth Period" in t for t in texts)
    assert any("2026-06-01" in t for t in texts)
    assert "SADC" in texts
    assert "1.3.5" in texts                    # day numbers, dotted


def test_schedule_card_sadc_dash_when_no_days(qapp):
    from PyQt6.QtWidgets import QLabel
    import gui.member_tabs as mt
    w = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)
    card = w._make_schedule_card(set(), "None")
    texts = [l.text() for l in card.findChildren(QLabel)]
    assert "—" in texts


def test_theme_has_schedule_card_styles(qapp):
    from gui.theme import build_qss, DARK, LIGHT
    for t in (build_qss(DARK), build_qss(LIGHT)):
        assert "schedule_card" in t
        assert "btn_icon_edit" in t
