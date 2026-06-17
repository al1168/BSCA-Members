import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_make_plan_badge_builds_the_pill(qapp):
    from gui.member_tabs import make_plan_badge
    b = make_plan_badge("HOF")
    assert b is not None
    assert b.objectName() == "plan_badge"      # picks up the colored-pill QSS
    assert b.property("plan") == "HOF"          # drives the per-plan color rule
    assert b.text() == "HOF"


def test_make_plan_badge_is_none_when_no_plan(qapp):
    from gui.member_tabs import make_plan_badge
    assert make_plan_badge("") is None
    assert make_plan_badge(None) is None
