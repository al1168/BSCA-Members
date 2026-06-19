import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_set_dirty_toggles_action_buttons(qapp):
    from PyQt6.QtWidgets import QPushButton
    import gui.member_tabs as mt
    w = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)
    w._btn_save = QPushButton()
    w._btn_discard = QPushButton()

    w._set_dirty(False)
    assert w._dirty is False
    assert not w._btn_save.isEnabled()
    assert not w._btn_discard.isEnabled()

    w._set_dirty(True)
    assert w._dirty is True
    assert w._btn_save.isEnabled()
    assert w._btn_discard.isEnabled()


def test_theme_has_discard_button_style(qapp):
    from gui.theme import build_qss, DARK, LIGHT
    for t in (build_qss(DARK), build_qss(LIGHT)):
        assert "btn_discard" in t


def test_theme_styles_calendar_popup(qapp):
    # The QDateEdit calendar popup needs its own rule so the year editor isn't
    # clipped by the global input padding.
    from gui.theme import build_qss, DARK, LIGHT
    for t in (build_qss(DARK), build_qss(LIGHT)):
        assert "QCalendarWidget QSpinBox" in t


def test_dateedit_step_buttons_collapsed(qapp):
    # Styling a QDateEdit makes Qt render spin up/down buttons whose hit area
    # increments the highlighted section on click. The theme must collapse them
    # to zero width so a click can't increment the date.
    from PyQt6.QtWidgets import QDateEdit, QStyle, QStyleOptionSpinBox
    from gui.theme import apply_theme
    apply_theme(qapp, "light")
    de = QDateEdit()
    de.setCalendarPopup(True)
    de.resize(160, 32)
    de.show()              # polish so the stylesheet applies to subcontrol rects
    qapp.processEvents()
    opt = QStyleOptionSpinBox()
    opt.initFrom(de)
    opt.buttonSymbols = de.buttonSymbols()
    up = de.style().subControlRect(
        QStyle.ComplexControl.CC_SpinBox, opt, QStyle.SubControl.SC_SpinBoxUp, de)
    assert up.width() == 0
