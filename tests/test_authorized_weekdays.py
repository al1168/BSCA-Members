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


def test_authorized_weekdays_uses_current_auth():
    from gui.member_tabs import authorized_weekdays
    auths = [
        {"effective_start": date(2026, 1, 1), "effective_end": date(2026, 12, 31),
         "auth_days": "1,3,5"},                                   # current -> Mon/Wed/Fri
        {"effective_start": date(2027, 1, 1), "effective_end": date(2027, 12, 31),
         "auth_days": "1,2,3,4,5"},                               # upcoming, ignored
    ]
    assert authorized_weekdays(auths, TODAY) == {1, 3, 5}


def test_authorized_weekdays_empty_when_no_current_auth():
    from gui.member_tabs import authorized_weekdays
    auths = [
        {"effective_start": date(2027, 1, 1), "effective_end": date(2027, 12, 31),
         "auth_days": "1,2,3,4,5"},                               # upcoming only
    ]
    assert authorized_weekdays(auths, TODAY) == set()
    assert authorized_weekdays([], TODAY) == set()


def test_strip_tints_authorized_days_light_green(qapp):
    from PyQt6.QtWidgets import QWidget, QLabel
    import gui.member_tabs as mt
    w = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)
    w._availability = []
    w._authorizations = [
        {"effective_start": date(2026, 1, 1), "effective_end": date(2026, 12, 31),
         "auth_days": "1,3"},   # Mon + Wed authorized, in effect today
    ]
    strip = w._make_current_schedule_strip(TODAY)
    cells = [c for c in strip.findChildren(QWidget)
             if c.objectName() in ("avail_day", "avail_day_empty")]
    authorized = [c for c in cells if c.property("authorized")]
    assert len(authorized) == 2     # exactly Mon and Wed tinted green
    # the old green checkmark is gone
    assert not [l for l in strip.findChildren(QLabel)
                if l.objectName() == "avail_day_check"]


# ── the table rows carry the same authorized-day tint as the strip ─────────
# _make_avail_tab() reads date.today() itself, so these build their windows
# around the real today rather than the fixed TODAY above.
def _avail_row(id, dow, eff_start, eff_end=None):
    return {"id": id, "day_of_week": dow, "avail_start": "08:00",
            "avail_end": "16:00", "effective_start_date": eff_start,
            "effective_end_date": eff_end}


def _avail_tab_with(authorizations, availability):
    from datetime import date
    import gui.member_tabs as mt
    w = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)
    w._availability = availability
    w._authorizations = authorizations
    w._center_id = 1
    w._db_path = "x"
    tab = w._make_avail_tab()        # keep the ref so the table isn't GC'd
    return w, tab, w._avail_table


def _row_by_id(table, id):
    return {table.item(r, 0).text(): r for r in range(table.rowCount())}[str(id)]


def _is_tinted(table, r):
    """A tinted row has a non-default background on every column up to (not
    including) the trailing gray spacer."""
    spacer = table.columnCount() - 1
    return all(table.item(r, c) is not None
               and table.item(r, c).background().style() != 0
               for c in range(spacer))


def test_table_tints_authorized_day_rows(qapp):
    from datetime import date, timedelta
    today = date.today()
    # Authorize the weekday today falls on, but not the next day's weekday.
    yes, no = today.isoweekday(), (today + timedelta(days=1)).isoweekday()
    _, _, t = _avail_tab_with(
        [{"effective_start": today - timedelta(days=30),
          "effective_end": today + timedelta(days=30),
          "auth_days": str(yes)}],
        [_avail_row(1, yes, today - timedelta(days=30)),
         _avail_row(2, no, today - timedelta(days=30))],
    )
    assert _is_tinted(t, _row_by_id(t, 1)) is True     # authorized -> green band
    assert _is_tinted(t, _row_by_id(t, 2)) is False    # unauthorized -> plain

    # The band reaches the widget columns: Status/Action hold cell widgets, so
    # they only tint if a backing item was created under them.
    r = _row_by_id(t, 1)
    assert t.item(r, 7) is not None
    assert t.item(r, 1).toolTip() == "Authorized day"

    # Selecting a tinted row still works (the backing items are NoItemFlags).
    t.selectRow(r)
    assert [ix.row() for ix in t.selectionModel().selectedRows()] == [r]


def test_edit_button_is_not_clipped_in_its_cell(qapp):
    """The Edit button is centered in its cell rather than filling it (so the
    authorized-day tint shows around it). The view sizes a cell widget to the
    item's content rect, which the QSS item padding shrinks well below the row
    height — so the button must still get its full natural height there, or it
    renders squeezed with a cut-off border."""
    from datetime import date, timedelta
    from PyQt6.QtWidgets import QPushButton
    today = date.today()
    _, tab, t = _avail_tab_with(
        [], [_avail_row(i, i, today - timedelta(days=30)) for i in range(1, 8)])
    tab.resize(1000, 520)
    tab.show()
    qapp.processEvents()
    try:
        for r in range(t.rowCount()):
            cell = t.cellWidget(r, 7)
            btn = cell.findChild(QPushButton)
            assert btn is not None
            # Not squeezed below what it needs to draw its border and text.
            assert btn.height() >= btn.minimumSizeHint().height()
            # And still wholly inside the cell, so nothing is cut off.
            assert btn.y() >= 0
            assert btn.y() + btn.height() <= cell.height()
    finally:
        tab.hide()


def test_pill_cell_wrapper_is_transparent(qapp):
    """The wrapper must not paint over the row background, or it punches a hole
    through the authorized-day tint around every pill and button."""
    from datetime import date, timedelta
    from gui.theme import build_qss, DARK, LIGHT
    today = date.today()
    _, _, t = _avail_tab_with(
        [], [_avail_row(1, 1, today - timedelta(days=30))])
    assert t.cellWidget(0, 7).objectName() == "pill_cell"
    for qss in (build_qss(DARK), build_qss(LIGHT)):
        assert "QWidget#pill_cell" in qss


def test_table_tints_upcoming_rows_by_todays_auth(qapp):
    """An Upcoming availability row is judged against the auth in effect today,
    so the table and the Current Schedule strip never disagree."""
    from datetime import date, timedelta
    today = date.today()
    yes = today.isoweekday()
    _, _, t = _avail_tab_with(
        [{"effective_start": today - timedelta(days=30),
          "effective_end": today + timedelta(days=30),
          "auth_days": str(yes)}],
        [_avail_row(1, yes, today + timedelta(days=30))],   # upcoming
    )
    assert t.cellWidget(0, 6) is not None      # it really is the Upcoming row
    assert _is_tinted(t, 0) is True


def test_table_untinted_when_no_current_auth(qapp):
    from datetime import date, timedelta
    today = date.today()
    _, _, t = _avail_tab_with(
        [], [_avail_row(1, today.isoweekday(), today - timedelta(days=30))])
    assert _is_tinted(t, 0) is False
