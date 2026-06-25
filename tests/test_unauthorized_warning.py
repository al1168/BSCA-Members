import os
from datetime import date, timedelta

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

TODAY = date(2026, 6, 19)
# A current authorization covering Mon/Wed/Fri.
AUTHS = [{"effective_start": date(2026, 1, 1), "effective_end": date(2026, 12, 31),
          "auth_days": "1,3,5"}]


def test_weekdays_in_range():
    from gui.member_tabs import weekdays_in_range
    d = date(2026, 6, 22)
    assert weekdays_in_range(d, d) == {d.isoweekday()}
    expected = {d.isoweekday(), (d + timedelta(days=1)).isoweekday(),
                (d + timedelta(days=2)).isoweekday()}
    assert weekdays_in_range(d, d + timedelta(days=2)) == expected
    assert weekdays_in_range(date(2026, 6, 1), date(2026, 6, 30)) == {1, 2, 3, 4, 5, 6, 7}
    assert weekdays_in_range(d, d - timedelta(days=1)) == set()   # invalid range


def test_needs_warning_for_unauthorized_single_day():
    from gui.member_tabs import needs_unauthorized_warning
    assert needs_unauthorized_warning(AUTHS, {2}, TODAY) is True    # Tue not authorized
    assert needs_unauthorized_warning(AUTHS, {1}, TODAY) is False   # Mon authorized
    assert needs_unauthorized_warning(AUTHS, {6, 7}, TODAY) is True  # weekend, disjoint


def test_no_warning_when_any_day_authorized():
    from gui.member_tabs import needs_unauthorized_warning
    assert needs_unauthorized_warning(AUTHS, {1, 2}, TODAY) is False  # Mon overlaps


def test_warns_when_no_current_authorization():
    from gui.member_tabs import needs_unauthorized_warning
    assert needs_unauthorized_warning([], {1}, TODAY) is True
    assert needs_unauthorized_warning(AUTHS, set(), TODAY) is False   # nothing to check
