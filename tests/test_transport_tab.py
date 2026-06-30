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
    """Column index whose header text == label (robust to the optional
    Document column shifting positions)."""
    for c in range(table.columnCount()):
        item = table.horizontalHeaderItem(c)
        if item is not None and item.text() == label:
            return c
    raise AssertionError(f"no column titled {label!r}")


def _t(i, s, e, num, plan="HF"):
    """A transport-auth dict shaped like a mapped row."""
    return {"id": i, "auth_start": s, "auth_end": e,
            "effective_start": s, "effective_end": e,
            "auth_days": "12", "health_plan": plan,
            "created_at": None, "member_id": "", "auth_number": num}


def _build(monkeypatch, has_doc=True, edges=None, auths=None, transports=None):
    import db.members as dbm
    monkeypatch.setattr(dbm, "get_transport_ids_with_documents",
                        lambda cid, path: set())
    monkeypatch.setattr(dbm, "get_auth_edges", lambda path: edges or [])
    monkeypatch.setattr(dbm, "transport_has_document_column",
                        lambda path: has_doc)
    import gui.member_tabs as mt
    # The tab imports these names from db.members at call time; patch there too.
    monkeypatch.setattr(mt, "get_transport_ids_with_documents",
                        lambda cid, path: set(), raising=False)
    monkeypatch.setattr(mt, "get_auth_edges", lambda path: edges or [],
                        raising=False)
    monkeypatch.setattr(mt, "transport_has_document_column",
                        lambda path: has_doc, raising=False)

    w = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)
    w._authorizations = auths if auths is not None else []
    w._transport_auths = transports if transports is not None else []
    w._center_id = 1
    w._db_path = "x"
    tab = w._make_transport_tab()      # keep ref so the table isn't GC'd
    return mt, w._transport_table, tab


def _row_for_id(table, rid):
    col = _col(table, "ID")
    for r in range(table.rowCount()):
        if table.item(r, col).text() == str(rid):
            return r
    raise AssertionError(f"row for id {rid} not found")


def test_auth_number_column_shows_value(qapp, monkeypatch):
    mt, table, _tab = _build(
        monkeypatch,
        transports=[_t(5, date(2026, 1, 1), date(2026, 12, 31), "T-123")],
    )
    r = _row_for_id(table, 5)
    assert table.item(r, _col(table, "Auth Number")).text() == "T-123"


def test_linked_auth_shows_care_auth_number(qapp, monkeypatch):
    care = {"id": 99, "auth_start": date(2026, 1, 1), "auth_end": date(2026, 12, 31),
            "auth_days": "12", "health_plan": "HF", "created_at": None,
            "member_id": "", "auth_number": "CARE-1"}
    mt, table, _tab = _build(
        monkeypatch,
        auths=[care],
        transports=[_t(5, date(2026, 1, 1), date(2026, 12, 31), "T-123")],
        edges=[{"id": 1, "authorization_id": 99,
                "transport_authorization_id": 5}],
    )
    r = _row_for_id(table, 5)
    assert table.item(r, _col(table, "Linked Auth")).text() == "CARE-1"


def test_unlinked_transport_has_blank_linked_cell(qapp, monkeypatch):
    mt, table, _tab = _build(
        monkeypatch,
        transports=[_t(5, date(2026, 1, 1), date(2026, 12, 31), "T-123")],
        edges=[],
    )
    r = _row_for_id(table, 5)
    assert table.item(r, _col(table, "Linked Auth")).text() == ""


def _status_chip_name(mt, table, row):
    from PyQt6.QtWidgets import QLabel
    cell = table.cellWidget(row, _col(table, "Status"))
    if cell is None:
        return None
    for lbl in cell.findChildren(QLabel):
        if lbl.objectName() in ("expired_chip", "active_chip", "upcoming_chip"):
            return lbl.objectName()
    return None


def test_status_chips_active_and_expired(qapp, monkeypatch):
    mt, table, _tab = _build(
        monkeypatch,
        transports=[
            _t(1, date(2025, 1, 1), date(2999, 12, 31), "T-A"),   # active
            _t(2, date(2000, 1, 1), date(2000, 12, 31), "T-B"),   # expired
        ],
    )
    assert _status_chip_name(mt, table, _row_for_id(table, 1)) == "active_chip"
    assert _status_chip_name(mt, table, _row_for_id(table, 2)) == "expired_chip"


def test_expired_row_text_is_grayed(qapp, monkeypatch):
    from PyQt6.QtGui import QColor
    mt, table, _tab = _build(
        monkeypatch,
        transports=[
            _t(1, date(2025, 1, 1), date(2999, 12, 31), "T-A"),
            _t(2, date(2000, 1, 1), date(2000, 12, 31), "T-B"),
        ],
    )
    end = _col(table, "Auth End")
    expired = _row_for_id(table, 2)
    current = _row_for_id(table, 1)
    assert table.item(expired, end).foreground().color() == QColor(mt.EXPIRED_FG)
    assert table.item(current, end).foreground().color() != QColor(mt.EXPIRED_FG)


def test_document_column_present_only_when_probe_true(qapp, monkeypatch):
    _, table_with, _t1 = _build(
        monkeypatch, has_doc=True,
        transports=[_t(5, date(2026, 1, 1), date(2026, 12, 31), "T-1")])
    cols_with = [table_with.horizontalHeaderItem(c).text()
                 for c in range(table_with.columnCount())]
    assert "Document" in cols_with


def test_document_column_absent_when_probe_false(qapp, monkeypatch):
    _, table_without, _t2 = _build(
        monkeypatch, has_doc=False,
        transports=[_t(5, date(2026, 1, 1), date(2026, 12, 31), "T-1")])
    cols_without = [table_without.horizontalHeaderItem(c).text()
                    for c in range(table_without.columnCount())]
    assert "Document" not in cols_without


def test_delete_button_disabled_until_selection(qapp, monkeypatch):
    from PyQt6.QtWidgets import QPushButton
    _, table, tab = _build(
        monkeypatch,
        transports=[_t(5, date(2026, 1, 1), date(2026, 12, 31), "T-1")])
    del_btn = next(b for b in tab.findChildren(QPushButton)
                   if b.objectName() == "btn_row_delete")
    assert del_btn.isEnabled() is False
    table.selectRow(0)
    assert del_btn.isEnabled() is True
