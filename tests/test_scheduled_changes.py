import os
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

TODAY = date(2026, 6, 19)


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _av(id, dow, start, end, eff_start, eff_end):
    return {"id": id, "day_of_week": dow, "avail_start": start, "avail_end": end,
            "effective_start_date": eff_start, "effective_end_date": eff_end}


# ── avail_status: expired / upcoming / active ──────────────────────────────
def test_avail_status():
    from gui.member_tabs import avail_status
    assert avail_status(_av(1, 3, "08:00", "16:00",
                            date(2025, 1, 1), date(2025, 12, 31)), TODAY) == "expired"
    assert avail_status(_av(2, 3, "10:00", "15:00",
                            date(2026, 7, 1), None), TODAY) == "upcoming"
    assert avail_status(_av(3, 3, "08:00", "16:00",
                            date(2026, 1, 1), None), TODAY) == "active"


# ── current_schedule: latest-effective wins per weekday ────────────────────
def test_current_schedule_latest_effective_wins():
    from gui.member_tabs import current_schedule
    avails = [
        _av(1, 3, "08:00", "16:00", date(2026, 1, 1), None),   # old Wed, ongoing
        _av(2, 3, "10:00", "15:00", date(2026, 6, 1), None),   # newer Wed, ongoing
    ]
    # both in effect today -> the later effective_start wins, one window only
    assert current_schedule(avails, TODAY).get(3) == [("10:00", "15:00")]


# ── pending_changes: future-effective rows, soonest first ──────────────────
def test_pending_changes_lists_future_rows():
    from gui.member_tabs import pending_changes
    avails = [
        _av(1, 3, "08:00", "16:00", date(2026, 1, 1), None),    # current
        _av(2, 3, "10:00", "15:00", date(2026, 7, 1), None),    # future
        _av(3, 5, "09:00", "12:00", date(2026, 9, 1), None),    # future, later
    ]
    out = pending_changes(avails, TODAY)
    assert [a["id"] for a in out] == [2, 3]


# ── cap-on-add: which row gets its end date capped ─────────────────────────
def test_avail_to_cap_picks_in_effect_predecessor():
    from gui.member_tabs import avail_to_cap
    avails = [
        _av(1, 3, "08:00", "16:00", date(2026, 1, 1), None),    # ongoing Wed
        _av(9, 5, "09:00", "12:00", date(2026, 1, 1), None),    # other weekday
    ]
    pred = avail_to_cap(avails, 3, date(2026, 7, 1))
    assert pred["id"] == 1
    # nothing to cap when the predecessor already ends before the change
    avails2 = [_av(1, 3, "08:00", "16:00", date(2026, 1, 1), date(2026, 5, 1))]
    assert avail_to_cap(avails2, 3, date(2026, 7, 1)) is None


# ── restore-on-delete: re-extend the capped predecessor ────────────────────
def test_avail_to_restore_finds_capped_predecessor():
    from gui.member_tabs import avail_to_restore
    avails = [
        _av(1, 3, "08:00", "16:00", date(2026, 1, 1), date(2026, 6, 30)),  # capped to 6/30
        _av(2, 3, "10:00", "15:00", date(2026, 7, 1), None),               # the change
    ]
    pred = avail_to_restore(avails, 3, date(2026, 7, 1))
    assert pred["id"] == 1
    assert avail_to_restore(avails, 5, date(2026, 7, 1)) is None


# ── the availability table flags a future row as Upcoming ──────────────────
def test_avail_tab_marks_future_row_upcoming(qapp):
    from PyQt6.QtWidgets import QLabel
    import gui.member_tabs as mt
    w = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)
    # Dates relative to the real today (the tab derives status from date.today()),
    # so this doesn't turn stale as the calendar advances.
    from datetime import timedelta
    today = date.today()
    w._availability = [
        _av(1, 3, "08:00", "16:00", today - timedelta(days=180), None),   # current
        _av(2, 3, "10:00", "15:00", today + timedelta(days=30), None),    # upcoming
    ]
    w._authorizations = []
    w._center_id = 1
    w._db_path = "x"
    tab = w._make_avail_tab()            # keep ref so the table isn't GC'd
    t = w._avail_table
    chips, texts = set(), set()
    for r in range(t.rowCount()):
        cell = t.cellWidget(r, 6)
        if cell is None:                 # Active renders as plain text, no pill
            texts.add(t.item(r, 6).text())
            continue
        for lbl in cell.findChildren(QLabel):
            if lbl.objectName():
                chips.add(lbl.objectName())
    assert "upcoming_chip" in chips      # the future change reads as Upcoming
    assert "Active" in texts             # the current window reads as Active


def test_avail_tab_uses_scheduled_changes_as_add(qapp):
    from PyQt6.QtWidgets import QPushButton
    import gui.member_tabs as mt
    w = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)
    w._availability = []
    w._authorizations = []
    w._center_id = 1
    w._db_path = "x"
    tab = w._make_avail_tab()
    buttons = tab.findChildren(QPushButton)
    assert not any(b.text() == "+ Add" for b in buttons)   # raw Add is hidden
    sched = [b for b in buttons if "Scheduled Changes" in b.text()]
    assert sched, "expected a Scheduled Changes button"
    assert sched[0].objectName() == "btn_row_add"          # styled as the add action
