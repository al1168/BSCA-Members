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


# ── the table dims expired rows and tags them ──────────────────────────────
def _build_tab(monkeypatch):
    import db.members as dbm
    monkeypatch.setattr(dbm, "get_auth_ids_with_documents", lambda cid, path: set())
    import gui.member_tabs as mt
    w = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)
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


def _status_chip_name(table, row):
    from PyQt6.QtWidgets import QLabel
    cell = table.cellWidget(row, 7)        # the dedicated Status column
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
