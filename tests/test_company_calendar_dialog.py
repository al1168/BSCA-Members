"""Company Calendar dialog: holiday add/delete gating and the weekly
hours editor, with db.company_calendar stubbed."""
import os
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


HOLIDAYS = [
    {"id": 1, "name": "New Year's Day", "date": date(2026, 1, 1)},
    {"id": 2, "name": "Labor Day", "date": date(2026, 9, 7)},
]


def _open_days(*days, opening="08:00", closing="16:00"):
    return {d: {"id": d, "day_name": "", "day_of_week": d,
                "opening_time": opening, "closing_time": closing}
            for d in days}


@pytest.fixture
def stubs(monkeypatch):
    """Stub every db call; record writes."""
    calls = {"insert": [], "delete": [], "save": []}
    state = {"holidays": list(HOLIDAYS),
             "days": _open_days(1, 2, 3, 4, 5, 6, 7)}
    monkeypatch.setattr("db.company_calendar.get_holidays",
                        lambda db: list(state["holidays"]))
    monkeypatch.setattr("db.company_calendar.get_operating_days",
                        lambda db: dict(state["days"]))

    def insert(name, day, db):
        calls["insert"].append((name, day))
        state["holidays"].append(
            {"id": 99, "name": name, "date": day})

    def delete(record_id, db):
        calls["delete"].append(record_id)
        state["holidays"] = [h for h in state["holidays"]
                             if h["id"] != record_id]

    def save(rows, db):
        calls["save"].append(rows)

    monkeypatch.setattr("db.company_calendar.insert_holiday", insert)
    monkeypatch.setattr("db.company_calendar.delete_holiday", delete)
    monkeypatch.setattr("db.company_calendar.save_operating_days", save)
    # Auto-answer every confirmation with "Yes"/the first (accept) button.
    from PyQt6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "warning",
                        lambda *a, **k: QMessageBox.StandardButton.Ok)
    return calls, state


def _dialog():
    from gui.company_calendar import CompanyCalendarDialog
    return CompanyCalendarDialog("fake.accdb")


def test_holidays_listed_sorted_and_add_gated(qapp, stubs):
    dlg = _dialog()
    assert dlg._table.rowCount() == 2
    assert dlg._table.item(0, 0).text() == "New Year's Day"
    assert dlg._table.item(1, 1).text() == "09/07/2026"
    assert not dlg._btn_add.isEnabled()
    dlg._name_edit.setText("Thanksgiving")
    assert not dlg._btn_add.isEnabled()          # no date yet
    dlg._date_edit.setText("11/26/2026")
    assert dlg._btn_add.isEnabled()
    dlg._date_edit.setText("13/40/2026")
    assert not dlg._btn_add.isEnabled()          # invalid date


def test_add_holiday_writes_and_reloads(qapp, stubs):
    calls, _state = stubs
    dlg = _dialog()
    dlg._name_edit.setText("Thanksgiving")
    dlg._date_edit.setText("11/26/2026")
    dlg._btn_add.click()
    assert calls["insert"] == [("Thanksgiving", date(2026, 11, 26))]
    assert dlg._table.rowCount() == 3
    assert dlg._name_edit.text() == ""
    assert dlg._date_edit.text() == ""


def test_delete_holiday_needs_selection_then_deletes(qapp, stubs):
    calls, _state = stubs
    dlg = _dialog()
    assert not dlg._btn_delete.isEnabled()
    dlg._table.selectRow(1)
    assert dlg._btn_delete.isEnabled()
    dlg._btn_delete.click()
    assert calls["delete"] == [2]
    assert dlg._table.rowCount() == 1


def test_hours_loaded_from_table(qapp, stubs):
    _calls, state = stubs
    state["days"] = _open_days(1, 2, 3, 4, 5, opening="09:00", closing="15:30")
    dlg = _dialog()
    check, opening, closing = dlg._day_rows[1]
    assert check.isChecked()
    assert (opening.edit.text(), opening.period.currentText()) == ("9:00", "AM")
    assert (closing.edit.text(), closing.period.currentText()) == ("3:30", "PM")
    sat_check, sat_open, _ = dlg._day_rows[6]
    assert not sat_check.isChecked()
    assert not sat_open.isEnabled()
    assert sat_open.edit.text() == "8:00"        # default shown for a closed day
    assert not dlg._btn_save.isEnabled()         # nothing dirty yet


def test_uncheck_day_and_save_writes_six_rows(qapp, stubs):
    calls, _state = stubs
    dlg = _dialog()
    dlg._day_rows[3][0].setChecked(False)        # close Wednesday
    assert dlg._btn_save.isEnabled()
    dlg._btn_save.click()
    assert len(calls["save"]) == 1
    rows = calls["save"][0]
    assert [r["day_of_week"] for r in rows] == [1, 2, 4, 5, 6, 7]
    assert rows[0] == {"day_of_week": 1, "opening_time": "08:00",
                       "closing_time": "16:00"}
    assert not dlg._btn_save.isEnabled()


def test_invalid_hours_block_save(qapp, stubs):
    calls, _state = stubs
    dlg = _dialog()
    _check, opening, _closing = dlg._day_rows[2]
    opening.edit.setText("5:00")
    opening.period.setCurrentText("PM")          # opens after it closes
    dlg._btn_save.click()
    assert calls["save"] == []


def test_zero_open_days_asks_then_saves(qapp, stubs, monkeypatch):
    calls, _state = stubs
    from PyQt6.QtWidgets import QMessageBox
    asked = []
    monkeypatch.setattr(
        QMessageBox, "question",
        lambda *a, **k: (asked.append(True), QMessageBox.StandardButton.Yes)[1])
    dlg = _dialog()
    for d in range(1, 8):
        dlg._day_rows[d][0].setChecked(False)
    dlg._btn_save.click()
    assert asked == [True]
    assert calls["save"] == [[]]


def test_close_with_dirty_hours_asks_first(qapp, stubs, monkeypatch):
    from PyQt6.QtWidgets import QDialog
    closed = []
    monkeypatch.setattr(QDialog, "reject", lambda self: closed.append(True))
    dlg = _dialog()
    dlg._day_rows[1][0].setChecked(False)
    dlg._confirm_discard = lambda: False          # "Keep Editing"
    dlg.reject()
    assert closed == []                           # stayed open
    dlg._confirm_discard = lambda: True           # "Discard"
    dlg.reject()
    assert closed == [True]


def test_close_when_clean_does_not_ask(qapp, stubs, monkeypatch):
    from PyQt6.QtWidgets import QDialog
    closed = []
    monkeypatch.setattr(QDialog, "reject", lambda self: closed.append(True))
    dlg = _dialog()
    dlg._confirm_discard = lambda: (_ for _ in ()).throw(AssertionError("asked"))
    dlg.reject()
    assert closed == [True]


def test_window_close_asks_once(qapp, stubs):
    """The X button must not prompt twice: a visible QDialog's closeEvent
    goes on to call reject(), which checks the dirty flag again."""
    asked = []
    dlg = _dialog()
    dlg.show()
    dlg._day_rows[1][0].setChecked(False)
    dlg._confirm_discard = lambda: (asked.append(True), True)[1]
    dlg.close()
    assert asked == [True]
    assert not dlg.isVisible()


def test_window_close_can_be_cancelled(qapp, stubs):
    dlg = _dialog()
    dlg.show()
    dlg._day_rows[1][0].setChecked(False)
    dlg._confirm_discard = lambda: False
    dlg.close()
    assert dlg.isVisible()          # stayed open
    assert dlg._dirty
    dlg._confirm_discard = lambda: True
    dlg.close()
    assert not dlg.isVisible()


def test_discard_box_defaults_to_keep_editing(qapp, stubs):
    """Enter must not throw away unsaved hours: Qt defaults to the first
    button added, so "Keep Editing" has to be set as the default."""
    from gui.company_calendar import _build_discard_box
    dlg = _dialog()
    box, discard_btn, keep_btn = _build_discard_box(dlg)
    assert box.defaultButton() is keep_btn
    assert box.defaultButton() is not discard_btn
    assert box.escapeButton() is keep_btn


def test_dialog_opens_at_its_design_width(qapp, stubs):
    """The explanatory labels must wrap: unwrapped, each one forces the whole
    dialog to its single-line width (~1765px) and the window opens off-screen
    wide."""
    dlg = _dialog()
    assert dlg.layout().minimumSize().width() <= 560


def test_group_boxes_are_themed():
    """The dialog is the first QGroupBox in the app; without a rule it draws
    native light chrome over the dark theme."""
    from gui.theme import DARK, LIGHT, build_qss
    for tokens in (DARK, LIGHT):
        qss = build_qss(tokens)
        assert "QGroupBox {" in qss
        assert "QGroupBox::title {" in qss
        assert tokens["border_mid"] in qss.split("QGroupBox {")[1][:200]


# ── main-window wiring ─────────────────────────────────────────────────────

def test_toolbar_button_sits_after_absences(qapp, tmp_path):
    from PyQt6.QtWidgets import QToolBar
    from gui.main_window import MainWindow
    w = MainWindow({"db_path": "", "theme": "dark"},
                   str(tmp_path / "settings.json"))
    toolbar = w.findChild(QToolBar, "main_toolbar")
    names = [toolbar.widgetForAction(a).objectName()
             for a in toolbar.actions()
             if toolbar.widgetForAction(a) is not None]
    i = names.index("btn_absence_report")
    assert names[i + 1] == "btn_company_calendar"


def test_open_company_calendar_without_db_warns(qapp, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox
    from gui.main_window import MainWindow
    warned = []
    monkeypatch.setattr(QMessageBox, "warning",
                        lambda *a, **k: warned.append(a[1]))
    w = MainWindow({"db_path": "", "theme": "dark"},
                   str(tmp_path / "settings.json"))
    w._open_company_calendar()
    assert warned == ["No Database"]


def test_open_company_calendar_execs_dialog(qapp, tmp_path, monkeypatch, stubs):
    from gui.main_window import MainWindow
    import gui.company_calendar as cc
    import db.members as members
    monkeypatch.setattr(members, "get_all_members", lambda db: [])
    monkeypatch.setattr(members, "get_terminated_center_ids", lambda db: set())
    monkeypatch.setattr(members, "missing_schema", lambda db: [])
    execd = []
    monkeypatch.setattr(cc.CompanyCalendarDialog, "exec",
                        lambda self: execd.append(self._db_path) or 0)
    w = MainWindow({"db_path": "fake.accdb", "theme": "dark"},
                   str(tmp_path / "settings.json"))
    w._open_company_calendar()
    assert execd == ["fake.accdb"]
