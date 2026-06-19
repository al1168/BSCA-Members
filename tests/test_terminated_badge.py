import os
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _bare_widget():
    from PyQt6.QtWidgets import QWidget, QHBoxLayout
    import gui.member_tabs as mt
    w = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)
    container = QWidget()
    w._header_top_row = QHBoxLayout(container)
    w._header_plan_badge = None
    w._term_badge = None
    return w, container


def test_reenrolling_removes_terminated_badge(qapp):
    from PyQt6.QtWidgets import QLabel
    w, _c = _bare_widget()
    # terminated: latest enrollment has an end date -> badge present
    w._term_badge = QLabel("⊘ Terminated")
    w._header_top_row.addWidget(w._term_badge)
    w._enrollments = [{"start_date": date(2020, 1, 1), "end_date": date(2021, 1, 1)}]
    w._refresh_terminated_badge()
    assert w._term_badge is not None    # still terminated

    # re-enroll with an open-ended enrollment (latest start) -> not terminated
    w._enrollments.append({"start_date": date(2026, 1, 1), "end_date": None})
    w._refresh_terminated_badge()
    assert w._term_badge is None        # terminated badge removed


def test_terminating_adds_badge(qapp):
    w, _c = _bare_widget()
    w._enrollments = [{"start_date": date(2026, 1, 1), "end_date": date(2026, 6, 1)}]
    w._refresh_terminated_badge()
    assert w._term_badge is not None
