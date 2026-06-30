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


def _auth(i, num):
    return {"id": i, "auth_start": date(2026, 1, 1), "auth_end": date(2026, 12, 31),
            "auth_days": "12", "health_plan": "HF", "created_at": None,
            "member_id": "", "auth_number": num}


def _build(monkeypatch, auths, transports, edges):
    import db.members as dbm
    monkeypatch.setattr(dbm, "get_auth_ids_with_documents",
                        lambda cid, path: set())
    monkeypatch.setattr(dbm, "get_auth_edges", lambda path: edges)
    import gui.member_tabs as mt
    w = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)
    w._authorizations = auths
    w._transport_auths = transports
    w._center_id = 1
    w._db_path = "x"
    tab = w._make_auths_tab()      # keep ref so the table isn't GC'd
    return mt, w._auth_table, tab


def _row_for_id(table, rid):
    c = _col(table, "ID")
    for r in range(table.rowCount()):
        if table.item(r, c).text() == str(rid):
            return r
    raise AssertionError(f"row {rid} not found")


def test_transport_column_view_button_when_linked(qapp, monkeypatch):
    from PyQt6.QtWidgets import QPushButton
    mt, table, _tab = _build(
        monkeypatch,
        auths=[_auth(1, "C-1")],
        transports=[_auth(7, "T-7"), _auth(8, "T-8")],
        edges=[{"id": 1, "authorization_id": 1, "transport_authorization_id": 7},
               {"id": 2, "authorization_id": 1, "transport_authorization_id": 8}],
    )
    r = _row_for_id(table, 1)
    cell = table.cellWidget(r, _col(table, "Transport"))
    assert isinstance(cell, QPushButton)
    assert "2" in cell.text()          # "View (2)"


def test_transport_column_dash_when_none(qapp, monkeypatch):
    mt, table, _tab = _build(
        monkeypatch, auths=[_auth(1, "C-1")], transports=[], edges=[])
    r = _row_for_id(table, 1)
    assert table.cellWidget(r, _col(table, "Transport")) is None
    assert table.item(r, _col(table, "Transport")).text() == "—"


def test_select_row_by_id_selects_match(qapp):
    from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem
    import gui.member_tabs as mt
    w = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)
    table = QTableWidget(3, 1)
    for i, rid in enumerate([10, 20, 30]):
        table.setItem(i, 0, QTableWidgetItem(str(rid)))
    w._select_row_by_id(table, 20)
    assert table.currentRow() == 1
