import json
from settings import load_settings, save_settings, DEFAULT_SETTINGS


def test_defaults_returned_when_file_missing(tmp_path):
    path = tmp_path / "settings.json"
    result = load_settings(str(path))
    assert result["db_path"] == ""
    assert result["theme"] == "dark"
    assert result["events_db_path"] == ""


def test_save_and_reload(tmp_path):
    path = tmp_path / "settings.json"
    data = {"db_path": "C:/data/test.accdb", "theme": "light", "events_db_path": ""}
    save_settings(data, str(path))
    result = load_settings(str(path))
    assert result["db_path"] == "C:/data/test.accdb"
    assert result["theme"] == "light"


def test_missing_keys_filled_with_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"theme": "light"}))
    result = load_settings(str(path))
    assert result["db_path"] == DEFAULT_SETTINGS["db_path"]
    assert result["theme"] == "light"
