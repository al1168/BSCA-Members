"""Sidebar search: Enter opens the highlighted (or first) result; arrow keys
move the highlight without opening members along the way."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


MEMBERS = [
    {"center_id": 12345, "last_name": "Chan", "first_name": "Mei",
     "health_plan": "HF", "dob": None},
    {"center_id": 20001, "last_name": "Lu", "first_name": "Wei",
     "health_plan": "AE", "dob": None},
    {"center_id": 20002, "last_name": "Wong", "first_name": "Ka",
     "health_plan": "AE", "dob": None},
]


# The handlers are unit-tested by direct call: MainWindow.__new__ skips the
# QObject init (no database), which also means Qt signal connections to its
# bound methods never fire. The one-line signal wiring in _build_ui is
# covered by the scripted GUI walkthrough instead.
def make_window(qapp):
    from gui.main_window import MainWindow
    from PyQt6.QtWidgets import QListWidget, QLineEdit
    w = MainWindow.__new__(MainWindow)      # skip DB-touching __init__
    w._terminated_ids = set()
    w._all_members = list(MEMBERS)
    w._member_list = QListWidget()
    w._search = QLineEdit()
    w.opened = []
    w._jump_to_member = w.opened.append     # record instead of loading the DB
    w._populate_list(w._all_members)
    return w


def test_enter_opens_first_result_without_arrowing(qapp):
    w = make_window(qapp)
    w._filter_members("12345")              # filters to one member
    w._open_from_search()                   # Enter
    assert w.opened == [12345]


def test_arrows_move_highlight_then_enter_opens_it(qapp):
    from PyQt6.QtCore import Qt
    w = make_window(qapp)
    opened_during_arrows = []
    w._member_list.currentRowChanged.connect(
        lambda _r: opened_during_arrows.append(_r))
    w._move_search_selection(1)             # -> row 0
    w._move_search_selection(1)             # -> row 1
    assert opened_during_arrows == []       # nothing loaded while browsing
    w._open_from_search()                   # Enter
    assert w.opened == [
        w._member_list.item(1).data(Qt.ItemDataRole.UserRole)]


def test_up_arrow_clamps_at_top(qapp):
    w = make_window(qapp)
    w._move_search_selection(1)
    w._move_search_selection(-1)
    w._move_search_selection(-1)
    assert w._member_list.currentRow() == 0


def test_enter_on_zero_results_does_nothing(qapp):
    w = make_window(qapp)
    w._filter_members("zzz-no-match")       # placeholder row only
    w._open_from_search()
    assert w.opened == []
