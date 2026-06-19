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


def test_strip_marks_authorized_days_with_a_check(qapp):
    from PyQt6.QtWidgets import QLabel
    import gui.member_tabs as mt
    w = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)
    w._availability = []
    w._authorizations = [
        {"effective_start": date(2026, 1, 1), "effective_end": date(2026, 12, 31),
         "auth_days": "1,3"},   # Mon + Wed authorized, in effect today
    ]
    strip = w._make_current_schedule_strip(TODAY)
    checks = [l for l in strip.findChildren(QLabel)
              if l.objectName() == "avail_day_check"]
    assert len(checks) == 2     # exactly Mon and Wed get the green check
