import os
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

TODAY = date(2026, 6, 17)


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _av(id, dow, start, end, eff_start, eff_end):
    return {"id": id, "day_of_week": dow, "avail_start": start, "avail_end": end,
            "effective_start_date": eff_start, "effective_end_date": eff_end}


# ── is_avail_expired ───────────────────────────────────────────────────────
def test_expired_when_eff_end_before_today(qapp):
    from gui.member_tabs import is_avail_expired
    assert is_avail_expired(_av(1, 1, "08:00", "16:00",
                                date(2025, 1, 1), date(2025, 12, 31)), TODAY) is True


def test_not_expired_today_future_or_open(qapp):
    from gui.member_tabs import is_avail_expired
    assert is_avail_expired(_av(1, 1, "08:00", "16:00",
                                date(2026, 1, 1), TODAY), TODAY) is False
    assert is_avail_expired(_av(1, 1, "08:00", "16:00",
                                date(2026, 1, 1), date(2027, 1, 1)), TODAY) is False
    assert is_avail_expired(_av(1, 1, "08:00", "16:00",
                                date(2026, 1, 1), None), TODAY) is False


# ── avail_in_effect_on ─────────────────────────────────────────────────────
def test_in_effect_within_or_open_window(qapp):
    from gui.member_tabs import avail_in_effect_on
    assert avail_in_effect_on(_av(1, 1, "08:00", "16:00",
                                  date(2026, 1, 1), None), TODAY) is True
    assert avail_in_effect_on(_av(1, 1, "08:00", "16:00",
                                  date(2026, 1, 1), date(2026, 12, 31)), TODAY) is True


def test_not_in_effect_future_or_expired(qapp):
    from gui.member_tabs import avail_in_effect_on
    assert avail_in_effect_on(_av(1, 1, "08:00", "16:00",
                                  date(2026, 7, 1), None), TODAY) is False   # future
    assert avail_in_effect_on(_av(1, 1, "08:00", "16:00",
                                  date(2025, 1, 1), date(2025, 12, 31)), TODAY) is False


# ── current_schedule ───────────────────────────────────────────────────────
def test_current_schedule_groups_in_effect_by_day(qapp):
    from gui.member_tabs import current_schedule
    avails = [
        _av(1, 1, "08:00", "16:00", date(2026, 1, 1), None),               # Mon active
        _av(2, 1, "09:00", "17:00", date(2025, 1, 1), date(2025, 12, 31)),  # Mon expired
        _av(3, 4, "09:00", "15:00", date(2026, 3, 1), None),               # Thu active
        _av(4, 2, "08:00", "12:00", date(2026, 7, 1), None),               # Tue future
    ]
    sched = current_schedule(avails, TODAY)
    assert sched.get(1) == [("08:00", "16:00")]
    assert sched.get(4) == [("09:00", "15:00")]
    assert 2 not in sched   # Tue's only row is future, not in effect


# ── sort_avail_for_table ───────────────────────────────────────────────────
def test_sort_active_first_then_day_then_eff_start(qapp):
    from gui.member_tabs import sort_avail_for_table
    avails = [
        _av(1, 1, "x", "y", date(2025, 1, 1), date(2025, 6, 1)),   # Mon expired
        _av(2, 4, "x", "y", date(2026, 3, 1), None),               # Thu active
        _av(3, 1, "x", "y", date(2026, 1, 1), None),               # Mon active
        _av(4, 1, "x", "y", date(2024, 1, 1), date(2024, 6, 1)),   # Mon expired (older)
    ]
    out = sort_avail_for_table(avails, TODAY)
    assert [a["id"] for a in out] == [3, 2, 4, 1]
    assert [a["id"] for a in avails] == [1, 2, 3, 4]   # input not mutated


# ── format_avail_window ────────────────────────────────────────────────────
def test_format_window(qapp):
    from gui.member_tabs import format_avail_window
    assert format_avail_window("08:00", "16:00") == "08:00–16:00"
    assert format_avail_window("", "") == "—"


# ── theme exposes the strip day styles ─────────────────────────────────────
def test_theme_has_avail_day_styles(qapp):
    from gui.theme import build_qss, DARK, LIGHT
    for t in (build_qss(DARK), build_qss(LIGHT)):
        assert "avail_day" in t


# ── table hides expired rows (kept in the DB as history) ───────────────────
def test_table_hides_expired_rows_shows_active_as_text(qapp):
    import gui.member_tabs as mt
    w = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)
    w._availability = [
        _av(1, 1, "08:00", "16:00", date(2025, 1, 1), date(2025, 12, 31)),  # expired
        _av(2, 1, "08:00", "16:00", date(2026, 1, 1), None),                # active
    ]
    w._authorizations = []   # strip reads this for the authorized-day check
    w._center_id = 1
    w._db_path = "x"
    tab = w._make_avail_tab()            # keep ref so the table isn't GC'd
    t = w._avail_table

    # Only the active row is shown; the expired (capped) row stays out of view.
    assert t.rowCount() == 1
    assert t.item(0, 0).text() == "2"

    # Active renders as plain centered text (no pill).
    assert t.cellWidget(0, 6) is None
    assert t.item(0, 6).text() == "Active"


# ── Delete enabled only for a selected Upcoming row ────────────────────────
def test_delete_button_only_for_upcoming_rows(qapp):
    from datetime import date, timedelta
    from PyQt6.QtWidgets import QPushButton
    import gui.member_tabs as mt
    today = date.today()
    w = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)
    w._availability = [
        _av(1, 1, "08:00", "16:00", today - timedelta(days=30), None),   # active
        _av(2, 2, "08:00", "16:00", today + timedelta(days=30), None),   # upcoming
    ]
    w._authorizations = []
    w._center_id = 1
    w._db_path = "x"
    tab = w._make_avail_tab()
    t = w._avail_table
    btn_del = next(b for b in tab.findChildren(QPushButton)
                   if b.text() == "Delete Selected")

    assert btn_del.isEnabled() is False              # nothing selected
    by_id = {t.item(r, 0).text(): r for r in range(t.rowCount())}
    t.selectRow(by_id["1"])                          # active row
    assert btn_del.isEnabled() is False
    t.selectRow(by_id["2"])                          # upcoming row
    assert btn_del.isEnabled() is True
