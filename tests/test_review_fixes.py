"""Tests for the review fixes: friendly error mapping, warn logging,
theme-aware badge/count helpers, and table empty states."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from gui.errors import friendly_db_message
from gui import theme
import crash_log


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_friendly_message_for_locked_db():
    exc = Exception(
        "('HY000', '[HY000] [Microsoft][ODBC Microsoft Access Driver] The "
        "database has been placed in a state by user Admin that prevents it "
        "from being opened or locked. (-1034)')")
    msg = friendly_db_message(exc)
    assert "locked by another program" in msg
    assert "Details:" in msg              # technical detail preserved


def test_friendly_message_for_missing_file():
    msg = friendly_db_message(FileNotFoundError("Database not found: Z:\\x.accdb"))
    assert "can't be found" in msg
    assert "Settings" in msg


def test_friendly_message_generic_keeps_detail():
    msg = friendly_db_message(RuntimeError("weird failure 123"))
    assert "weird failure 123" in msg


def test_log_warning_appends_to_daily_file(tmp_path, monkeypatch):
    monkeypatch.setattr(crash_log, "log_dir", lambda: str(tmp_path))
    crash_log.log_warning("something odd")
    files = os.listdir(tmp_path)
    assert len(files) == 1 and files[0].startswith("debug_")
    text = (tmp_path / files[0]).read_text(encoding="utf-8")
    assert "WARN" in text and "something odd" in text


def test_event_badge_colors_differ_per_theme():
    for name in ("dark", "light"):
        theme._current_name = name
        bg, fg = theme.event_badge_colors("NEW")
        assert bg.startswith("#") and fg.startswith("#")
    assert (theme.EVENT_BADGE_COLORS["dark"]["NEW"]
            != theme.EVENT_BADGE_COLORS["light"]["NEW"])
    theme._current_name = "dark"


def test_format_member_counts_uses_tokens():
    theme._current_name = "dark"
    html = theme.format_member_counts(10, 7)
    assert "10 members" in html and "7 active" in html
    assert theme.DARK["success"] in html


def test_table_empty_state_row(qapp):
    from PyQt6.QtWidgets import QTableWidget
    from PyQt6.QtCore import Qt
    from gui.member_tabs import set_table_empty_state

    table = QTableWidget(0, 4)
    table.setHorizontalHeaderLabels(["ID", "A", "B", "C"])
    set_table_empty_state(table, "No things yet — click + Add.")
    assert table.rowCount() == 1
    item = table.item(0, 0)
    assert item is not None and "No things yet" in item.text()
    assert not item.flags() & Qt.ItemFlag.ItemIsSelectable

    # A table that has data is left alone.
    table2 = QTableWidget(2, 4)
    set_table_empty_state(table2, "nope")
    assert table2.rowCount() == 2


def test_sidebar_zero_result_message(qapp):
    from gui.main_window import MainWindow
    from PyQt6.QtWidgets import QListWidget
    from PyQt6.QtCore import Qt

    w = MainWindow.__new__(MainWindow)          # no DB needed for this path
    w._terminated_ids = set()
    w._member_list = QListWidget()
    w._populate_list([], search_text="zzz")
    assert w._member_list.count() == 1
    item = w._member_list.item(0)
    assert "No members match" in item.text()
    assert not item.flags() & Qt.ItemFlag.ItemIsSelectable
