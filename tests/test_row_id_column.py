import os
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _col(table, label):
    for c in range(table.columnCount()):
        it = table.horizontalHeaderItem(c)
        if it is not None and it.text() == label:
            return c
    raise AssertionError(f"no column titled {label!r}")


# ── settings plumbing ──────────────────────────────────────────────────────

def test_show_row_ids_defaults_off(tmp_path):
    from settings import load_settings, DEFAULT_SETTINGS
    assert DEFAULT_SETTINGS["show_row_ids"] is False
    result = load_settings(str(tmp_path / "settings.json"))
    assert result["show_row_ids"] is False


def test_settings_dialog_roundtrips_show_row_ids(qapp):
    from gui.settings_dialog import SettingsDialog
    base = {"db_path": "", "events_db_path": "", "theme": "dark",
            "google_api_key": ""}
    off = SettingsDialog({**base, "show_row_ids": False})
    assert off._show_row_ids.isChecked() is False
    assert off.result_settings()["show_row_ids"] is False

    on = SettingsDialog({**base, "show_row_ids": True})
    assert on._show_row_ids.isChecked() is True
    assert on.result_settings()["show_row_ids"] is True


# ── the hide helper on a bare table ────────────────────────────────────────

def _table_with_id():
    from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem
    columns = ["ID", "Auth Start", "Status"]
    table = QTableWidget(1, len(columns))
    table.setHorizontalHeaderLabels(columns)
    table.setItem(0, 0, QTableWidgetItem("442"))
    return table


def test_apply_id_column_hides_when_off(qapp):
    import gui.member_tabs as mt
    w = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)
    w._show_row_ids = False
    table = _table_with_id()
    w._apply_id_column(table)
    assert table.isColumnHidden(_col(table, "ID")) is True
    # Data is still there — only the view is hidden.
    assert table.item(0, _col(table, "ID")).text() == "442"


def test_apply_id_column_shows_when_on(qapp):
    import gui.member_tabs as mt
    w = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)
    w._show_row_ids = True
    table = _table_with_id()
    w._apply_id_column(table)
    assert table.isColumnHidden(_col(table, "ID")) is False


def test_apply_id_column_ignores_tables_without_id(qapp):
    from PyQt6.QtWidgets import QTableWidget
    import gui.member_tabs as mt
    w = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)
    w._show_row_ids = False
    table = QTableWidget(1, 2)
    table.setHorizontalHeaderLabels(["Full Name", "Phone"])
    w._apply_id_column(table)          # must not raise or hide anything
    assert table.isColumnHidden(0) is False
    assert table.isColumnHidden(1) is False


# ── integration: the Authorizations table ──────────────────────────────────

def _auth(i):
    return {"id": i, "auth_start": date(2026, 1, 1), "auth_end": date(2026, 12, 31),
            "auth_days": "12", "health_plan": "HF", "created_at": None,
            "member_id": "", "auth_number": ""}


def _build_auths_tab(monkeypatch, show_row_ids):
    import db.members as dbm
    monkeypatch.setattr(dbm, "get_auth_ids_with_documents", lambda cid, path: set())
    monkeypatch.setattr(dbm, "get_auth_edges", lambda path: [])
    import gui.member_tabs as mt
    w = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)
    w._authorizations = [_auth(442)]
    w._transport_auths = []
    w._center_id = 1
    w._db_path = "x"
    w._show_row_ids = show_row_ids
    tab = w._make_auths_tab()          # keep ref so the table isn't GC'd
    return w, w._auth_table, tab


def test_auth_table_id_hidden_by_default(qapp, monkeypatch):
    w, table, _tab = _build_auths_tab(monkeypatch, show_row_ids=False)
    idc = _col(table, "ID")
    assert table.isColumnHidden(idc) is True
    assert table.item(0, idc).text() == "442"   # id still populated for lookups


def test_auth_table_id_shown_when_enabled(qapp, monkeypatch):
    w, table, _tab = _build_auths_tab(monkeypatch, show_row_ids=True)
    assert table.isColumnHidden(_col(table, "ID")) is False


def test_set_show_row_ids_toggles_live(qapp, monkeypatch):
    w, table, _tab = _build_auths_tab(monkeypatch, show_row_ids=False)
    idc = _col(table, "ID")
    assert table.isColumnHidden(idc) is True
    w.set_show_row_ids(True)
    assert table.isColumnHidden(idc) is False
    w.set_show_row_ids(False)
    assert table.isColumnHidden(idc) is True
