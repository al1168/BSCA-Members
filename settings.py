import json
import os

DEFAULT_SETTINGS = {
    "db_path": "",
    "theme": "dark",
    "events_db_path": "",
    "google_api_key": "",
    # Debug: show the internal row "ID" column in the member tables. Off by
    # default so day-to-day users don't see database ids like 442.
    "show_row_ids": False,
    # App-wide text size: "normal" (13px base) | "large" (25px) | "xlarge" (30px).
    "text_size": "normal",
}


def load_settings(path: str) -> dict:
    if not os.path.exists(path):
        return dict(DEFAULT_SETTINGS)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {**DEFAULT_SETTINGS, **data}


def save_settings(data: dict, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
