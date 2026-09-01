import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _m(last, first, cid, alt=None):
    m = {"last_name": last, "first_name": first, "center_id": cid}
    if alt is not None:
        m["alt_id"] = alt
    return m


def _ranked(members, query):
    from gui.main_window import search_rank_key
    return [m["center_id"] for m in
            sorted(members, key=lambda m: search_rank_key(m, query))]


# ── numeric queries: exact id first, then id-prefix numerically, then rest ──
def test_numeric_query_exact_id_first(qapp):
    members = [
        _m("Adams", "Amy", 2500),
        _m("Baker", "Ben", 250),
        _m("Chan", "Cid", 25),
        _m("Diaz", "Dan", 1257),   # "25" mid-string
    ]
    assert _ranked(members, "25") == [25, 250, 2500, 1257]


def test_numeric_query_prefix_matches_sorted_numerically(qapp):
    members = [
        _m("Adams", "Amy", 2531),
        _m("Baker", "Ben", 254),
        _m("Chan", "Cid", 2502),
    ]
    assert _ranked(members, "25") == [254, 2502, 2531]


def test_numeric_query_alt_id_exact_ranks_with_exact(qapp):
    members = [
        _m("Adams", "Amy", 30001),          # no 25 in id at all (name match)
        _m("Baker", "Ben", 40002, alt=25),  # alt id exactly 25
        _m("Chan", "Cid", 2599),            # id prefix
    ]
    assert _ranked(members, "25") == [40002, 2599, 30001]


# ── name queries: name-prefix matches first, alphabetical within tiers ──────
def test_name_query_prefix_before_substring(qapp):
    members = [
        _m("Ohlee", "Zoe", 1),    # "lee" mid-string
        _m("Lee", "Bob", 2),      # last-name prefix
        _m("Klee", "Ann", 3),     # mid-string
        _m("Leeson", "Cal", 4),   # last-name prefix
    ]
    assert _ranked(members, "lee") == [2, 4, 3, 1]


def test_name_query_first_name_prefix_counts(qapp):
    members = [
        _m("Adams", "Bob", 1),     # first-name prefix "bo"
        _m("Osborne", "Al", 2),    # "bo" mid-string in last name
    ]
    assert _ranked(members, "bo") == [1, 2]


def test_name_query_alphabetical_within_tier(qapp):
    members = [
        _m("Lees", "Ann", 9),
        _m("Lee", "Cal", 5),
        _m("Lee", "Bob", 7),
    ]
    assert _ranked(members, "lee") == [7, 5, 9]


# ── comma / DOB / empty queries keep alphabetical order ─────────────────────
def test_comma_query_alphabetical(qapp):
    members = [
        _m("Lee", "Cal", 1),
        _m("Lee", "Bob", 2),
    ]
    assert _ranked(members, "Lee,") == [2, 1]


def test_empty_query_alphabetical(qapp):
    members = [
        _m("Wong", "Ann", 1),
        _m("Adams", "Zoe", 2),
    ]
    assert _ranked(members, "") == [2, 1]


def test_missing_fields_are_safe(qapp):
    from gui.main_window import search_rank_key
    # Must not raise on members with absent/None fields.
    search_rank_key({"center_id": None, "last_name": None, "first_name": None}, "25")
    search_rank_key({}, "lee")


# ── the sidebar filter shows the exact-id member first ──────────────────────
def test_sidebar_filter_ranks_exact_id_first(qapp):
    from gui.main_window import MainWindow
    w = MainWindow.__new__(MainWindow)  # skip __init__; wire just what we need
    from PyQt6.QtWidgets import QListWidget
    w._member_list = QListWidget()
    w._terminated_ids = set()
    w._all_members = [
        {"last_name": "Adams", "first_name": "Amy", "center_id": 2500,
         "health_plan": "P"},
        {"last_name": "Chan", "first_name": "Cid", "center_id": 25,
         "health_plan": "P"},
    ]
    w._filter_members("25")
    from PyQt6.QtCore import Qt
    first = w._member_list.item(0).data(Qt.ItemDataRole.UserRole)
    assert first == 25


# ── quick search (Ctrl+K) ranks the same way ────────────────────────────────
def test_quick_search_ranks_exact_id_first(qapp):
    from gui.quick_search import QuickSearchDialog
    from gui.main_window import matches_search, search_rank_key
    members = [
        {"last_name": "Adams", "first_name": "Amy", "center_id": 2500},
        {"last_name": "Chan", "first_name": "Cid", "center_id": 25},
    ]
    dlg = QuickSearchDialog(members, matches_search, ranker=search_rank_key)
    dlg._search.setText("25")
    from PyQt6.QtCore import Qt
    assert dlg._list.item(0).data(Qt.ItemDataRole.UserRole) == 25
    dlg.close()
