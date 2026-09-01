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


# ── alt id: substring match, same semantics as center id ───────────────────
def test_alt_id_substring(qapp):
    from gui.main_window import matches_search
    m = {**_m("Lee", "Bob", 10000), "alt_id": 555123}
    assert matches_search(m, "555123")                     # full alt id
    assert matches_search(m, "5551")                       # substring
    assert not matches_search(m, "9999")


def test_alt_id_none_or_missing_is_safe(qapp):
    from gui.main_window import matches_search
    assert not matches_search({**_m("Lee", "Bob"), "alt_id": None}, "555")
    assert not matches_search(_m("Lee", "Bob"), "555")     # key absent
    assert matches_search({**_m("Lee", "Bob"), "alt_id": None}, "")  # empty q


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


# ── slash: date-of-birth search ────────────────────────────────────────────
def _md(dob):
    from datetime import date
    return {"last_name": "Smith", "first_name": "Ann", "center_id": 1, "dob": dob}


def test_dob_search_full_and_unpadded(qapp):
    from datetime import date
    from gui.main_window import matches_search
    m = _md(date(2000, 1, 5))
    assert matches_search(m, "01/05/2000")
    assert matches_search(m, "1/5/2000")        # leading zeros optional
    assert not matches_search(m, "2/5/2000")    # wrong month


def test_dob_search_prefix(qapp):
    from datetime import date
    from gui.main_window import matches_search
    m = _md(date(2000, 1, 5))
    assert matches_search(m, "1/5")             # Jan 5, any year
    assert matches_search(m, "01/")             # month 01
    assert matches_search(m, "1/5/20")          # partial year prefix
    assert not matches_search(m, "1/6")         # wrong day


def test_dob_search_edge_cases(qapp):
    from datetime import date
    from gui.main_window import matches_search
    assert not matches_search(_md(None), "1/5/2000")     # member has no DOB
    assert not matches_search(_md(date(2000, 1, 5)), "/")  # slash only, no digits


# ── session decryption key: the corpus is searched by decrypted alt id ──────
def test_decrypt_corpus_alt_ids(qapp):
    from gui.main_window import decrypt_corpus_alt_ids, matches_search
    from db.alt_id_crypto import derive_key, encrypt_alt_id
    key = derive_key("test-pass")
    members = [
        {**_m("Lee", "Bob", 1), "alt_id": encrypt_alt_id(key, 4321)},
        {**_m("Wong", "Ann", 2), "alt_id": None},
    ]
    decrypt_corpus_alt_ids(members, key)
    assert members[0]["alt_id"] == 4321
    assert members[1]["alt_id"] is None
    assert matches_search(members[0], "4321")


def test_decrypt_corpus_noop_without_key(qapp):
    from gui.main_window import decrypt_corpus_alt_ids
    members = [{**_m("Lee", "Bob", 1), "alt_id": 555}]
    decrypt_corpus_alt_ids(members, None)
    assert members[0]["alt_id"] == 555
