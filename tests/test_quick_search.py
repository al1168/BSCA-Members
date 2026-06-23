import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import Qt


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


MEMBERS = [
    {"last_name": "Smith", "first_name": "Ann", "center_id": 1, "health_plan": "AE"},
    {"last_name": "Jones", "first_name": "Bob", "center_id": 2, "health_plan": "HOF"},
    {"last_name": "Smithson", "first_name": "Cara", "center_id": 3, "health_plan": ""},
]


def _cids(dlg):
    return [dlg._list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(dlg._list.count())]


def _dialog(qapp):
    from gui.main_window import matches_search
    from gui.quick_search import QuickSearchDialog
    return QuickSearchDialog(MEMBERS, matches_search)


def test_empty_query_shows_all(qapp):
    dlg = _dialog(qapp)
    assert set(_cids(dlg)) == {1, 2, 3}
    assert dlg._list.currentRow() == 0      # first hit pre-selected for Enter


def test_substring_search(qapp):
    dlg = _dialog(qapp)
    dlg._search.setText("smith")            # Smith + Smithson
    assert set(_cids(dlg)) == {1, 3}


def test_comma_triggered_last_name_rule_preserved(qapp):
    dlg = _dialog(qapp)
    dlg._search.setText("Smith, A")         # exact last name 'Smith', first 'A…'
    assert _cids(dlg) == [1]                 # Smithson excluded (exact last name)


def test_enter_chooses_highlighted_member(qapp):
    dlg = _dialog(qapp)
    dlg._search.setText("Jones")
    dlg._choose_current()
    assert dlg.chosen_center_id == 2


def test_arrow_navigation_moves_selection(qapp):
    dlg = _dialog(qapp)                      # 3 results, row 0 selected
    dlg._move(1)
    assert dlg._list.currentRow() == 1
    dlg._move(-1)
    assert dlg._list.currentRow() == 0
    dlg._move(-1)                            # clamps at top
    assert dlg._list.currentRow() == 0
