import os
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _abs(id, lt, s, e):
    return {"id": id, "center_id": 1, "leave_type": lt,
            "start_date": s, "end_date": e}


def _widget_with_absences(absences):
    import gui.member_tabs as mt
    w = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)
    w._absences = absences
    return w


def test_absences_tab_has_action_column_with_edit_buttons(qapp):
    from PyQt6.QtWidgets import QPushButton
    w = _widget_with_absences([
        _abs(1, "Vacation", date(2026, 7, 1), date(2026, 7, 3)),
        _abs(2, "Medical", date(2026, 7, 10), date(2026, 7, 10)),
    ])
    tab = w._make_absences_tab()
    table = w._abs_table
    headers = [table.horizontalHeaderItem(c).text()
               for c in range(table.columnCount())]
    assert headers == ["ID", "Leave Type", "Start", "End", "Action"]
    for r in range(2):
        btn = table.cellWidget(r, 4)
        assert isinstance(btn, QPushButton) and btn.text() == "Edit"


def test_edit_button_passes_its_absence_entry(qapp):
    entries = [
        _abs(1, "Vacation", date(2026, 7, 1), date(2026, 7, 3)),
        _abs(2, "Medical", date(2026, 7, 10), date(2026, 7, 10)),
    ]
    w = _widget_with_absences(entries)
    tab = w._make_absences_tab()          # keep the table's parent alive
    seen = []
    w._edit_absence = lambda entry: seen.append(entry)
    w._abs_table.cellWidget(1, 4).click()
    assert seen == [entries[1]]
