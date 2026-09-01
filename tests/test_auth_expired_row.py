import os
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


# ── is_auth_expired (mirrors auth_warning's rule) ──────────────────────────
def test_expired_when_end_before_today(qapp):
    from gui.member_tabs import is_auth_expired
    assert is_auth_expired({"auth_end": date(2000, 1, 1)}, date(2026, 6, 17)) is True


def test_today_is_still_in_effect(qapp):
    from gui.member_tabs import is_auth_expired
    assert is_auth_expired({"auth_end": date(2026, 6, 17)}, date(2026, 6, 17)) is False


def test_future_end_not_expired(qapp):
    from gui.member_tabs import is_auth_expired
    assert is_auth_expired({"auth_end": date(2999, 1, 1)}, date(2026, 6, 17)) is False


def test_no_end_date_never_expired(qapp):
    from gui.member_tabs import is_auth_expired
    assert is_auth_expired({"auth_end": None}, date(2026, 6, 17)) is False
    assert is_auth_expired({}, date(2026, 6, 17)) is False


# ── theme exposes the status chips ─────────────────────────────────────────
def test_theme_has_status_chips(qapp):
    from gui.theme import build_qss, DARK, LIGHT
    for t in (build_qss(DARK), build_qss(LIGHT)):
        assert "expired_chip" in t
        assert "active_chip" in t
        assert "upcoming_chip" in t


def test_overlapping_auths_show_conflict_tooltip(qapp, monkeypatch):
    import db.members as dbm
    monkeypatch.setattr(dbm, "get_auth_ids_with_documents", lambda cid, path: set())
    import gui.member_tabs as mt

    def a(i, s, e):
        return {"id": i, "auth_start": s, "auth_end": e,
                "effective_start": s, "effective_end": e,
                "auth_days": "12", "health_plan": "HF",
                "created_at": None, "member_id": ""}

    w = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)
    w._transport_auths = []
    w._authorizations = [
        a(1, date(2026, 1, 1), date(2026, 6, 30)),
        a(2, date(2026, 6, 1), date(2026, 12, 31)),   # overlaps 1
        a(3, date(2027, 1, 1), date(2027, 6, 30)),     # clear
    ]
    w._center_id = 1
    w._db_path = "x"
    tab = w._make_auths_tab()
    t = w._auth_table

    def end_tooltip(auth_id):
        for r in range(t.rowCount()):
            if t.item(r, 0).text() == str(auth_id):
                return t.item(r, 2).toolTip()
        return None

    assert "Overlaps" in end_tooltip(1)
    assert "Overlaps" in end_tooltip(2)
    assert end_tooltip(3) == ""


# ── the table dims expired rows and tags them ──────────────────────────────
def _build_tab(monkeypatch):
    import db.members as dbm
    monkeypatch.setattr(dbm, "get_auth_ids_with_documents", lambda cid, path: set())
    import gui.member_tabs as mt
    w = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)
    w._transport_auths = []
    w._authorizations = [
        {"id": 1, "auth_start": date(2025, 1, 1), "auth_end": date(2999, 12, 31),
         "auth_days": "12345", "health_plan": "HOF", "created_at": None},
        {"id": 2, "auth_start": date(2000, 1, 1), "auth_end": date(2000, 12, 31),
         "auth_days": "135", "health_plan": "Anthem", "created_at": None},
    ]
    w._center_id = 12345
    w._db_path = "unused"
    tab = w._make_auths_tab()      # keep a reference so the table isn't GC'd
    return mt, w._auth_table, tab


def _row_for_id(table, auth_id):
    for r in range(table.rowCount()):
        if table.item(r, 0).text() == str(auth_id):
            return r
    raise AssertionError(f"row for id {auth_id} not found")


def test_expired_row_text_is_grayed(qapp, monkeypatch):
    from PyQt6.QtGui import QColor
    mt, table, _tab = _build_tab(monkeypatch)
    expired = _row_for_id(table, 2)
    current = _row_for_id(table, 1)
    assert table.item(expired, 2).foreground().color() == QColor(mt.EXPIRED_FG)
    assert table.item(current, 2).foreground().color() != QColor(mt.EXPIRED_FG)


def _col(table, label):
    for c in range(table.columnCount()):
        it = table.horizontalHeaderItem(c)
        if it is not None and it.text() == label:
            return c
    raise AssertionError(f"no column titled {label!r}")


def _status_chip_name(table, row):
    from PyQt6.QtWidgets import QLabel
    cell = table.cellWidget(row, _col(table, "Status"))
    if cell is None:
        return None
    for lbl in cell.findChildren(QLabel):
        if lbl.objectName() in ("expired_chip", "active_chip"):
            return lbl.objectName()
    return None


def test_expired_row_has_expired_chip(qapp, monkeypatch):
    mt, table, _tab = _build_tab(monkeypatch)
    assert _status_chip_name(table, _row_for_id(table, 2)) == "expired_chip"


def test_current_row_has_active_chip(qapp, monkeypatch):
    mt, table, _tab = _build_tab(monkeypatch)
    assert _status_chip_name(table, _row_for_id(table, 1)) == "active_chip"


def test_auth_number_column_shows_value(qapp, monkeypatch):
    import db.members as dbm
    monkeypatch.setattr(dbm, "get_auth_ids_with_documents", lambda cid, path: set())
    import gui.member_tabs as mt
    w = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)
    w._transport_auths = []
    w._authorizations = [
        {"id": 5, "auth_start": date(2026, 1, 1), "auth_end": date(2026, 12, 31),
         "auth_days": "12", "health_plan": "HF", "created_at": None,
         "member_id": "M1", "auth_number": "AUTH-123"},
    ]
    w._center_id = 1
    w._db_path = "x"
    tab = w._make_auths_tab()           # keep ref so the table isn't GC'd
    t = w._auth_table
    assert t.item(0, _col(t, "Auth Number")).text() == "AUTH-123"
