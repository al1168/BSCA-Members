"""Member bookmarks: a small per-user list saved as JSON.

The file lives beside settings/logs — %APPDATA%\\BSCA-Members when frozen,
the repo dir in dev (see crash_log.app_base_dir) — so bookmarks survive app
updates and never travel with the shared member database. Each bookmark is
{"center_id", "name", "note", "date"}; notes are capped at NOTE_MAX_LEN
characters so the list always renders compactly.
"""
import json
import os
from datetime import date

from crash_log import app_base_dir

# Keeps every note short enough to show in full in the bookmarks list.
NOTE_MAX_LEN = 120


def bookmarks_path() -> str:
    return os.path.join(app_base_dir(), "bookmarks.json")


def load_bookmarks(path: str | None = None) -> list[dict]:
    """The saved bookmarks, newest first. A missing or unreadable file is an
    empty list — bookmarks are a convenience, never worth an error dialog."""
    path = path or bookmarks_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    return [
        b for b in data
        if isinstance(b, dict) and b.get("center_id") is not None
    ]


def save_bookmarks(bookmarks: list[dict], path: str | None = None) -> None:
    path = path or bookmarks_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(bookmarks, f, indent=2)


def find_bookmark(bookmarks: list[dict], center_id) -> dict | None:
    return next((b for b in bookmarks if b.get("center_id") == center_id), None)


def upsert_bookmark(bookmarks: list[dict], center_id, name: str, note: str,
                    on_date: date | None = None) -> list[dict]:
    """A new list with `center_id` bookmarked (moved to the front). Re-saving
    an existing bookmark replaces its note and stamps a fresh date."""
    entry = {
        "center_id": center_id,
        "name": name,
        "note": (note or "").strip()[:NOTE_MAX_LEN],
        "date": (on_date or date.today()).isoformat(),
    }
    return [entry] + [b for b in bookmarks if b.get("center_id") != center_id]


def remove_bookmark(bookmarks: list[dict], center_id) -> list[dict]:
    return [b for b in bookmarks if b.get("center_id") != center_id]
