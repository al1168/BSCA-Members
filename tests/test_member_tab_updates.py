import os
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


# ── Info-tab schedule card refresh (auth day changes reflect immediately) ───

def _active_auth(days):
    # An authorization in effect today (wide effective window).
    return {"id": 1, "effective_start": date(2000, 1, 1),
            "effective_end": date(2100, 1, 1), "auth_days": days,
            "health_plan": "HF"}


def _widget_with_schedule_card(auths):
    from PyQt6.QtWidgets import QWidget, QVBoxLayout
    import gui.member_tabs as mt
    w = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)
    w._authorizations = auths
    container = QWidget()
    cvbox = QVBoxLayout(container)
    card = w._build_schedule_card()
    cvbox.addWidget(card)
    w._schedule_card = card
    w._info_content_layout = cvbox
    return w, container


def _chip_days(card):
    from gui.member_tabs import WeekdayChips
    return card.findChildren(WeekdayChips)[0]._days


def test_build_schedule_card_reflects_active_auth(qapp):
    w, _c = _widget_with_schedule_card([_active_auth("1,3,5")])
    assert _chip_days(w._schedule_card) == {1, 3, 5}


def test_refresh_schedule_card_picks_up_new_auth(qapp):
    # Starts with no auth (empty chips), then an auth is "added" and refreshed.
    w, _c = _widget_with_schedule_card([])
    assert _chip_days(w._schedule_card) == set()
    old = w._schedule_card
    w._authorizations = [_active_auth("2,4")]
    w._refresh_schedule_card()
    assert w._schedule_card is not old          # rebuilt in place
    assert _chip_days(w._schedule_card) == {2, 4}


def test_refresh_schedule_card_noop_before_info_built(qapp):
    import gui.member_tabs as mt
    w = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)
    w._authorizations = []
    w._refresh_schedule_card()                  # must not raise (no _schedule_card)


# ── Tab-switch unsaved-changes guard ────────────────────────────────────────

# Note: the guard is driven directly via _on_tab_changed(index) rather than the
# currentChanged signal, because PyQt won't invoke a signal-connected bound
# method on a __new__-built widget (its C++ base is uninitialized). The signal
# wiring itself is a single connect() line in _build_ui.
def _widget_with_tabs():
    from PyQt6.QtWidgets import QTabWidget, QWidget
    import gui.member_tabs as mt
    w = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)
    tabs = QTabWidget()
    tabs.addTab(QWidget(), "Info")
    tabs.addTab(QWidget(), "Other")
    w._tabs = tabs
    w._info_tab_index = 0
    w._prev_tab_index = 0
    w._dirty = False
    w._discarded = False

    def _discard():
        w._discarded = True
        w._dirty = False
    w._discard_info = _discard
    return w, tabs


def _simulate_switch_to(w, tabs, index):
    """Move to `index` as a click would, then run the guard for that change."""
    tabs.setCurrentIndex(index)
    w._on_tab_changed(index)


def test_clean_tab_switch_is_not_guarded(qapp):
    w, tabs = _widget_with_tabs()
    w._dirty = False
    _simulate_switch_to(w, tabs, 1)
    assert tabs.currentIndex() == 1
    assert w._prev_tab_index == 1


def test_dirty_switch_cancel_snaps_back(qapp, monkeypatch):
    import gui.member_tabs as mt
    w, tabs = _widget_with_tabs()
    w._dirty = True
    monkeypatch.setattr(mt.QMessageBox, "question",
                        lambda *a, **k: mt.QMessageBox.StandardButton.Cancel)
    _simulate_switch_to(w, tabs, 1)
    assert tabs.currentIndex() == 0             # snapped back to Info
    assert w._discarded is False
    assert w._dirty is True
    assert w._prev_tab_index == 0


def test_dirty_switch_discard_proceeds(qapp, monkeypatch):
    import gui.member_tabs as mt
    w, tabs = _widget_with_tabs()
    w._dirty = True
    monkeypatch.setattr(mt.QMessageBox, "question",
                        lambda *a, **k: mt.QMessageBox.StandardButton.Discard)
    _simulate_switch_to(w, tabs, 1)
    assert tabs.currentIndex() == 1             # allowed through
    assert w._discarded is True
    assert w._dirty is False
    assert w._prev_tab_index == 1
