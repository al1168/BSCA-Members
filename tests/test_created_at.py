import os
from datetime import date, datetime

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


# ── format_created_at (display) ────────────────────────────────────────────
def test_format_datetime_shows_date_and_12h_time(qapp):
    from gui.member_tabs import format_created_at
    assert format_created_at(datetime(2026, 6, 17, 14, 30)) == "06/17/2026 2:30 PM"


def test_format_pads_minutes_not_hours(qapp):
    from gui.member_tabs import format_created_at
    assert format_created_at(datetime(2026, 1, 5, 9, 5)) == "01/05/2026 9:05 AM"
    assert format_created_at(datetime(2026, 1, 5, 0, 0)) == "01/05/2026 12:00 AM"


def test_format_plain_date_has_no_time(qapp):
    from gui.member_tabs import format_created_at
    assert format_created_at(date(2026, 6, 17)) == "06/17/2026"


def test_format_blank_for_missing(qapp):
    from gui.member_tabs import format_created_at
    assert format_created_at(None) == ""
    assert format_created_at("") == ""


# ── _map_auth_row carries created_at ───────────────────────────────────────
def test_map_auth_row_includes_created_at_and_member_id():
    from db.members import _map_auth_row
    created = datetime(2026, 6, 17, 14, 30)
    row = (7, 12345, date(2026, 1, 1), date(2026, 6, 30),
           None, None, "12345", "HOF", created, "M-9001", "AUTH-77")
    d = _map_auth_row(row)
    assert d["created_at"] == created
    assert d["health_plan"] == "HOF"
    assert d["member_id"] == "M-9001"
    assert d["auth_number"] == "AUTH-77"


def test_map_auth_row_created_at_and_member_id_may_be_none():
    from db.members import _map_auth_row
    row = (8, 12345, date(2026, 1, 1), date(2026, 6, 30),
           None, None, "135", "Anthem", None, None, None)
    d = _map_auth_row(row)
    assert d["created_at"] is None
    assert d["member_id"] is None
    assert d["auth_number"] is None
