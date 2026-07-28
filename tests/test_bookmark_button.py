import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _widget(center_id=25375):
    from PyQt6.QtWidgets import QPushButton
    import gui.member_tabs as mt
    w = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)
    w._center_id = center_id
    w._member = {"last_name": "test", "first_name": "yesy"}
    w._btn_bookmark = QPushButton()
    return w


def test_button_reads_unmarked_when_not_bookmarked(qapp, monkeypatch):
    import bookmarks
    monkeypatch.setattr(bookmarks, "load_bookmarks", lambda path=None: [])
    w = _widget()
    w._sync_bookmark_button()
    assert w._btn_bookmark.text() == "🔖 Bookmark"
    assert w._btn_bookmark.property("marked") is False


def test_button_reads_marked_when_bookmarked(qapp, monkeypatch):
    import bookmarks
    saved = bookmarks.upsert_bookmark([], 25375, "test, yesy", "note")
    monkeypatch.setattr(bookmarks, "load_bookmarks", lambda path=None: saved)
    w = _widget()
    w._sync_bookmark_button()
    assert w._btn_bookmark.text() == "🔖 Bookmarked"
    assert w._btn_bookmark.property("marked") is True


def test_display_name_matches_header_format(qapp):
    assert _widget()._display_name() == "test, yesy"


# ── main-window wiring ─────────────────────────────────────────────────────

def _main_window(tmp_path, monkeypatch, saved):
    """A MainWindow (no db) whose bookmark store lives in tmp_path and
    initially holds `saved`."""
    import bookmarks
    store = str(tmp_path / "bookmarks.json")
    monkeypatch.setattr(bookmarks, "bookmarks_path", lambda: store)
    bookmarks.save_bookmarks(saved, store)
    from gui.main_window import MainWindow
    return MainWindow({"db_path": "", "theme": "dark"},
                      str(tmp_path / "settings.json"))


def test_panel_remove_updates_open_profile_button(qapp, tmp_path, monkeypatch):
    """✕ in the bookmarks panel must also flip the open profile's header
    button back to un-bookmarked, not just the toolbar count."""
    import bookmarks
    saved = bookmarks.upsert_bookmark([], 25375, "test, yesy", "note")
    w = _main_window(tmp_path, monkeypatch, saved)
    assert "(1)" in w._btn_bookmarks.text()

    from PyQt6.QtWidgets import QWidget
    profile = QWidget()
    synced = []
    profile._sync_bookmark_button = lambda: synced.append(True)
    w._set_detail(profile)

    w._open_bookmarks()
    w._bookmarks_panel._remove(25375)

    assert synced == [True]                      # profile button refreshed
    assert "(1)" not in w._btn_bookmarks.text()  # toolbar count refreshed
    assert bookmarks.load_bookmarks() == []      # store actually emptied


def test_panel_row_click_opens_member_profile(qapp, tmp_path, monkeypatch):
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    import bookmarks
    saved = bookmarks.upsert_bookmark([], 25375, "test, yesy", "note")
    w = _main_window(tmp_path, monkeypatch, saved)

    opened = []
    w._show_member = lambda cid: opened.append(cid)

    w._open_bookmarks()
    from gui.bookmarks_panel import _BookmarkRow
    row = w._bookmarks_panel.findChild(_BookmarkRow)
    QTest.mouseClick(row, Qt.MouseButton.LeftButton)

    assert opened == [25375]
