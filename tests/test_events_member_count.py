import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_global_events_shows_member_counts(qapp):
    from PyQt6.QtWidgets import QLabel
    from gui.events_view import EventsTableWidget
    w = EventsTableWidget("", center_id=None, member_count=247, active_count=231)
    lbl = w.findChild(QLabel, "events_member_counts")
    assert lbl is not None
    assert "247 members" in lbl.text()
    assert "231 active" in lbl.text()


def test_global_events_without_counts_has_no_subtitle(qapp):
    from PyQt6.QtWidgets import QLabel
    from gui.events_view import EventsTableWidget
    w = EventsTableWidget("", center_id=None)      # no counts passed
    assert w.findChild(QLabel, "events_member_counts") is None


def test_member_events_tab_has_no_counts(qapp):
    from PyQt6.QtWidgets import QLabel
    from gui.events_view import EventsTableWidget
    # Per-member Events tab: no header, and counts must not render.
    w = EventsTableWidget("", center_id=5, show_header=False,
                          member_count=10, active_count=9)
    assert w.findChild(QLabel, "events_member_counts") is None
