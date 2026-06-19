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
