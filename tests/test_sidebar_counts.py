import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_sidebar_member_counts_text(qapp):
    from PyQt6.QtWidgets import QLabel
    import gui.main_window as mw
    w = mw.MainWindow.__new__(mw.MainWindow)      # bypass __init__ (no DB/UI)
    w._member_counts = QLabel()
    w._all_members = [{"center_id": 1}, {"center_id": 2}, {"center_id": 3}]
    w._terminated_ids = {2}                         # one terminated -> 2 active
    w._update_member_counts()
    txt = w._member_counts.text()
    assert "3 members" in txt
    assert "2 active" in txt


def test_sidebar_member_counts_all_active(qapp):
    from PyQt6.QtWidgets import QLabel
    import gui.main_window as mw
    w = mw.MainWindow.__new__(mw.MainWindow)
    w._member_counts = QLabel()
    w._all_members = [{"center_id": 10}, {"center_id": 11}]
    w._terminated_ids = set()
    w._update_member_counts()
    assert "2 members" in w._member_counts.text()
    assert "2 active" in w._member_counts.text()
