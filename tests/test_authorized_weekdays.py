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
