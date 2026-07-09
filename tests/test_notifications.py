"""Auth-expiry notifications: bucket classification and the popup panel."""
import os
from datetime import date, datetime

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from db.members import classify_auth_notifications
from gui.notifications import format_notification_line

TODAY = date(2026, 7, 9)


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def classify(rows, active, **kw):
    return classify_auth_notifications(rows, set(active), TODAY, **kw)


def test_expiring_within_35_days_inclusive():
    rows = [(1, date(2026, 8, 13))]           # exactly 35 days out
    out = classify(rows, [1])
    assert out["expiring"] == [(1, date(2026, 8, 13), 35)]
    assert out["expired"] == []


def test_beyond_window_not_listed():
    out = classify([(1, date(2026, 8, 14))], [1])   # 36 days out
    assert out["expiring"] == [] and out["expired"] == []


def test_today_counts_as_expiring_not_expired():
    out = classify([(1, TODAY)], [1])
    assert out["expiring"] == [(1, TODAY, 0)]
    assert out["expired"] == []


def test_expired_yesterday():
    out = classify([(1, date(2026, 7, 8))], [1])
    assert out["expired"] == [(1, date(2026, 7, 8), 1)]


def test_terminated_members_excluded():
    rows = [(1, date(2026, 7, 1)), (2, date(2026, 7, 1))]
    out = classify(rows, [1])                 # 2 is not active
    assert [cid for cid, *_ in out["expired"]] == [1]


def test_members_with_no_dated_auths_skipped():
    # No rows at all for member 1; member 2 has only an open-ended auth.
    out = classify([(2, None)], [1, 2])
    assert out["expiring"] == [] and out["expired"] == []


def test_latest_auth_wins_so_new_auth_resolves():
    rows = [(1, date(2026, 6, 1))]            # expired…
    assert classify(rows, [1])["expired"]
    rows.append((1, date(2027, 6, 1)))        # …until a new auth is added
    out = classify(rows, [1])
    assert out["expired"] == [] and out["expiring"] == []


def test_sorting_soonest_and_most_recent_first():
    rows = [
        (1, date(2026, 7, 20)),               # in 11 days
        (2, date(2026, 7, 12)),               # in 3 days
        (3, date(2026, 6, 20)),               # 19 days ago
        (4, date(2026, 7, 5)),                # 4 days ago
    ]
    out = classify(rows, [1, 2, 3, 4])
    assert [cid for cid, *_ in out["expiring"]] == [2, 1]
    assert [cid for cid, *_ in out["expired"]] == [4, 3]


def test_datetime_values_normalized():
    out = classify([(1, datetime(2026, 7, 8, 0, 0))], [1])
    assert out["expired"] == [(1, date(2026, 7, 8), 1)]


def test_notification_line_phrasing():
    assert format_notification_line(date(2026, 7, 12), 3, False) == \
        "Expires Jul 12 · in 3 days"
    assert format_notification_line(date(2026, 7, 9), 0, False) == \
        "Expires Jul 9 · today"
    assert format_notification_line(date(2026, 7, 10), 1, False) == \
        "Expires Jul 10 · in 1 day"
    assert format_notification_line(date(2026, 6, 27), 12, True) == \
        "Expired Jun 27 · 12 days ago"


def test_panel_tabs_and_rows(qapp):
    from gui.notifications import NotificationsPanel, _NotifRow
    expiring = [(101, date(2026, 7, 12), 3)]
    expired = [(202, date(2026, 6, 27), 12), (303, date(2026, 6, 1), 38)]
    names = {101: "Chan, Mei K", 202: "Alden, Alden", 303: "Chan, De G"}
    panel = NotificationsPanel(expiring, expired, names, today=TODAY)

    assert "1" in panel._btn_expiring.text()
    assert "2" in panel._btn_expired.text()
    # Opens on Expiring (it has items) with one row.
    rows = panel._scroll.widget().findChildren(_NotifRow)
    assert len(rows) == 1

    chosen = []
    panel.member_chosen.connect(chosen.append)
    panel._show_tab("expired")
    rows = panel._scroll.widget().findChildren(_NotifRow)
    assert len(rows) == 2
    rows[0].clicked.emit(rows[0]._center_id)
    panel._choose(202)
    assert 202 in chosen


def test_panel_empty_state(qapp):
    from gui.notifications import NotificationsPanel, _NotifRow
    panel = NotificationsPanel([], [], {}, today=TODAY)
    assert panel._scroll.widget().findChildren(_NotifRow) == []
