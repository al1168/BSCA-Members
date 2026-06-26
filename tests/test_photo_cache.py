import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_member_photo_fetched_once_and_cached(qapp, monkeypatch):
    """The photo is loaded just after the member opens (off the click's critical
    path) and cached per center_id, so revisiting a member doesn't re-read/decode
    it (the slow part of opening a member)."""
    import gui.member_tabs as mt
    import db.members as dbm

    mt._PHOTO_CACHE.clear()
    fetches = []
    monkeypatch.setattr(dbm, "get_member_photo",
                        lambda cid, db: fetches.append(cid) or None)

    def make(cid):
        w = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)
        w._center_id = cid
        w._db_path = "dummy.accdb"
        w._make_photo_label()
        return w

    w1 = make(42)
    assert fetches == []          # not fetched during the click (deferred)
    w1._load_photo_async()        # the deferred load fires -> fetch + cache
    assert fetches == [42]

    make(42)                      # revisit -> cache hit, no schedule/fetch
    assert fetches == [42]

    make(99)._load_photo_async()  # different member -> one more fetch
    assert fetches == [42, 99]
