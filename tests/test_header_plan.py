import os
from datetime import date, timedelta

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

TODAY = date.today()


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _auth(id, plan, start, end):
    return {"id": id, "health_plan": plan,
            "effective_start": start, "effective_end": end}


def _widget(member_plan, authorizations):
    import gui.member_tabs as mt
    w = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)
    w._member = {"health_plan": member_plan}
    w._authorizations = authorizations
    return w


def test_no_pill_when_only_auth_is_upcoming(qapp):
    """A stale/defaulted Contacts plan (e.g. AE) must not show while the
    member's real auth hasn't started yet."""
    upcoming = _auth(1, "HF", TODAY + timedelta(days=10),
                     TODAY + timedelta(days=375))
    assert _widget("AE", [upcoming])._header_plan() == ""


def test_no_pill_without_any_authorization(qapp):
    assert _widget("AE", [])._header_plan() == ""


def test_active_auth_plan_wins_over_contacts(qapp):
    active = _auth(1, "HF", TODAY - timedelta(days=30),
                   TODAY + timedelta(days=335))
    assert _widget("AE", [active])._header_plan() == "HF"


def test_active_auth_with_blank_plan_falls_back_to_contacts(qapp):
    active = _auth(1, "", TODAY - timedelta(days=30),
                   TODAY + timedelta(days=335))
    assert _widget("HF", [active])._header_plan() == "HF"


def test_expired_auth_shows_no_pill(qapp):
    expired = _auth(1, "HF", TODAY - timedelta(days=400),
                    TODAY - timedelta(days=35))
    assert _widget("HF", [expired])._header_plan() == ""
