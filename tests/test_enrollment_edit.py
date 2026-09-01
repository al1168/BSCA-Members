import os
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _enr(id, s, e):
    return {"id": id, "center_id": 1, "start_date": s, "end_date": e}


def _widget_with_enrollments(enrollments):
    import gui.member_tabs as mt
    w = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)
    w._enrollments = enrollments
    return w


def _buttons_in_action_cell(table, row):
    from PyQt6.QtWidgets import QPushButton
    wrap = table.cellWidget(row, 4)
    assert wrap is not None
    return {b.text(): b for b in wrap.findChildren(QPushButton)}


def test_enrollments_tab_has_status_and_action_columns(qapp):
    w = _widget_with_enrollments([_enr(1, date(2026, 1, 1), None)])
    tab = w._make_enrollments_tab()       # keep the table's parent alive
    table = w._enroll_table
    headers = [table.horizontalHeaderItem(c).text()
               for c in range(table.columnCount())]
    assert headers == ["ID", "Start Date", "End Date", "Status", "Action"]


def test_active_row_status_text_and_buttons(qapp):
    w = _widget_with_enrollments([_enr(1, date(2026, 1, 1), None)])
    tab = w._make_enrollments_tab()
    assert w._enroll_table.item(0, 3).text() == "Active"
    btns = _buttons_in_action_cell(w._enroll_table, 0)
    assert "Edit" in btns
    assert "Terminate…" in btns


def test_ended_row_status_text_and_edit_only(qapp):
    w = _widget_with_enrollments([_enr(1, date(2020, 1, 1), date(2020, 6, 1))])
    tab = w._make_enrollments_tab()
    assert w._enroll_table.item(0, 3).text() == "Ended"
    btns = _buttons_in_action_cell(w._enroll_table, 0)
    assert "Edit" in btns
    assert "Terminate…" not in btns


def test_edit_button_passes_its_enrollment_entry(qapp):
    entries = [
        _enr(1, date(2026, 1, 1), None),                  # active -> row 0
        _enr(2, date(2020, 1, 1), date(2020, 6, 1)),      # ended  -> row 1
    ]
    w = _widget_with_enrollments(entries)
    tab = w._make_enrollments_tab()
    seen = []
    w._edit_enrollment = lambda entry: seen.append(entry)
    _buttons_in_action_cell(w._enroll_table, 1)["Edit"].click()
    assert seen == [entries[1]]
