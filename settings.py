import json
import os

DEFAULT_SETTINGS = {
    "db_path": "",
    "theme": "dark",
    "events_db_path": "",
    "google_api_key": "",
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
