import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _m(last, first, cid=10000):
    return {"last_name": last, "first_name": first, "center_id": cid}


# ── no comma: existing substring behavior over last / first / center id ─────
def test_no_comma_substring(qapp):
    from gui.main_window import matches_search
    assert matches_search(_m("Lee", "Bob"), "lee")
    assert matches_search(_m("Lee", "Bob"), "bo")          # first-name substring
    assert matches_search(_m("Lee", "Bob", 12345), "234")  # center id
    assert not matches_search(_m("Lee", "Bob"), "xyz")


def test_empty_or_blank_query_matches_all(qapp):
    from gui.main_window import matches_search
    assert matches_search(_m("Lee", "Bob"), "")
    assert matches_search(_m("Anything", "Person"), "   ")


# ── comma: exact last name ─────────────────────────────────────────────────
def test_comma_exact_last_name(qapp):
    from gui.main_window import matches_search
    assert matches_search(_m("Lee", "Bob"), "Lee,")
    assert matches_search(_m("lee", "bob"), "LEE,")          # case-insensitive
    assert not matches_search(_m("Leese", "Bob"), "Lee,")    # exact, not prefix
    assert not matches_search(_m("Wong", "Bob"), "Lee,")


# ── comma + first-name prefix ──────────────────────────────────────────────
def test_comma_last_plus_first_prefix(qapp):
    from gui.main_window import matches_search
    assert matches_search(_m("Lee", "Bob"), "Lee, B")
    assert matches_search(_m("Lee", "Bob"), "Lee, bo")
    assert not matches_search(_m("Lee", "Anna"), "Lee, B")   # first not B*
    assert not matches_search(_m("Wong", "Bob"), "Lee, B")   # wrong last name


# ── spaces around the comma are tolerated ──────────────────────────────────
def test_spaces_around_comma(qapp):
    from gui.main_window import matches_search
    assert matches_search(_m("Lee", "Bob"), "Lee ,")
    assert matches_search(_m("Lee", "Bob"), "Lee,   B")
    assert matches_search(_m("Lee", "Bob"), "  Lee , b ")
    assert not matches_search(_m("Leese", "Bob"), "Lee ,")
