"""The HHA note card beside the Time Slot Availability table: shows
Contacts.[HHA] so schedule edits can reference its constraints."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _widget(hha):
    import gui.member_tabs as mt
    w = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)
    w._member = {"hha": hha}
    return w


def test_card_shows_hha_text(qapp):
    from PyQt6.QtWidgets import QLabel
    card = _widget("Mornings only; ride booked for 08:00")._make_hha_note_card()
    assert card is not None
    texts = [l.text() for l in card.findChildren(QLabel)]
    assert "HHA Note" in texts
    assert "Mornings only; ride booked for 08:00" in texts


def test_no_card_when_hha_blank(qapp):
    assert _widget("")._make_hha_note_card() is None
    assert _widget("   ")._make_hha_note_card() is None
    assert _widget(None)._make_hha_note_card() is None
