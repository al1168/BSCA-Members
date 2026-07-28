import json
from datetime import date

from bookmarks import (
    NOTE_MAX_LEN, load_bookmarks, save_bookmarks,
    find_bookmark, upsert_bookmark, remove_bookmark,
)

TODAY = date(2026, 7, 21)


def _bm(cid, name="test, yesy", note="call family"):
    return upsert_bookmark([], cid, name, note, TODAY)[0]


# ── upsert_bookmark ────────────────────────────────────────────────────────
def test_upsert_adds_newest_first():
    marks = upsert_bookmark([_bm(1)], 2, "lee, david", "pickup", TODAY)
    assert [b["center_id"] for b in marks] == [2, 1]


def test_upsert_replaces_existing_without_duplicating():
    marks = upsert_bookmark([_bm(1, note="old"), _bm(2)], 1, "test, yesy",
                            "new note", TODAY)
    assert [b["center_id"] for b in marks] == [1, 2]
    assert marks[0]["note"] == "new note"


def test_upsert_caps_and_strips_note():
    marks = upsert_bookmark([], 1, "n", "  " + "x" * 500 + "  ", TODAY)
    assert marks[0]["note"] == "x" * NOTE_MAX_LEN


def test_upsert_allows_empty_note():
    marks = upsert_bookmark([], 1, "n", "", TODAY)
    assert marks[0]["note"] == ""


def test_upsert_stamps_iso_date():
    assert _bm(1)["date"] == "2026-07-21"


# ── remove / find ──────────────────────────────────────────────────────────
def test_remove_bookmark():
    marks = remove_bookmark([_bm(1), _bm(2)], 1)
    assert [b["center_id"] for b in marks] == [2]


def test_remove_missing_is_noop():
    marks = [_bm(1)]
    assert remove_bookmark(marks, 99) == marks


def test_find_bookmark():
    marks = [_bm(1), _bm(2)]
    assert find_bookmark(marks, 2)["center_id"] == 2
    assert find_bookmark(marks, 3) is None


# ── load / save ────────────────────────────────────────────────────────────
def test_load_missing_file_is_empty(tmp_path):
    assert load_bookmarks(str(tmp_path / "nope.json")) == []


def test_load_corrupt_file_is_empty(tmp_path):
    p = tmp_path / "bookmarks.json"
    p.write_text("{not json", encoding="utf-8")
    assert load_bookmarks(str(p)) == []


def test_load_skips_malformed_entries(tmp_path):
    p = tmp_path / "bookmarks.json"
    p.write_text(json.dumps([{"center_id": 1, "name": "a"}, "junk", {}]),
                 encoding="utf-8")
    assert load_bookmarks(str(p)) == [{"center_id": 1, "name": "a"}]


def test_save_load_roundtrip(tmp_path):
    p = str(tmp_path / "sub" / "bookmarks.json")   # dir created on save
    marks = upsert_bookmark([], 25375, "test, yesy", "auth renewal", TODAY)
    save_bookmarks(marks, p)
    assert load_bookmarks(p) == marks


# ── panel date formatting ──────────────────────────────────────────────────
def test_format_bookmark_date():
    from gui.bookmarks_panel import format_bookmark_date
    assert format_bookmark_date("2026-07-05") == "Jul 5, 2026"
    assert format_bookmark_date("") == ""
    assert format_bookmark_date("whenever") == "whenever"
