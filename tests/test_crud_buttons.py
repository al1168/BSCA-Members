import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_style_crud_buttons_disables_delete_until_selection(qapp):
    from PyQt6.QtWidgets import QTableWidget, QPushButton, QAbstractItemView
    import gui.member_tabs as mt
    table = QTableWidget(2, 2)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    add = QPushButton("+ Add")
    dele = QPushButton("Delete Selected")
    mt.MemberTabsWidget._style_crud_buttons(table, add, dele)

    assert add.objectName() == "btn_row_add"        # green add
    assert dele.objectName() == "btn_row_delete"    # red delete
    assert dele.isEnabled() is False                # nothing selected -> disabled
    assert add.isEnabled() is True                  # add never needs a selection

    table.selectRow(0)
    assert dele.isEnabled() is True                 # a row selected -> enabled
    table.clearSelection()
    assert dele.isEnabled() is False                # selection cleared -> disabled


def test_theme_has_row_button_styles(qapp):
    from gui.theme import build_qss, DARK, LIGHT
    for t in (build_qss(DARK), build_qss(LIGHT)):
        assert "btn_row_add" in t
        assert "btn_row_delete" in t
