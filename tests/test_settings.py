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


def test_google_api_key_default_present(tmp_path):
    from settings import DEFAULT_SETTINGS
    path = tmp_path / "settings.json"
    result = load_settings(str(path))
    assert "google_api_key" in DEFAULT_SETTINGS
    assert result["google_api_key"] == ""


def test_settings_dialog_returns_google_api_key(qtbot):
    from gui.settings_dialog import SettingsDialog
    dlg = SettingsDialog({"db_path": "", "events_db_path": "", "theme": "dark",
                          "google_api_key": "KEY123"})
    qtbot.addWidget(dlg)
    assert dlg.result_settings()["google_api_key"] == "KEY123"


def _dialog(qtbot, key):
    from gui.settings_dialog import SettingsDialog
    dlg = SettingsDialog({"db_path": "", "events_db_path": "", "theme": "dark",
                          "google_api_key": key})
    qtbot.addWidget(dlg)
    return dlg


def test_api_key_masked_and_locked_when_present(qtbot):
    from PyQt6.QtWidgets import QLineEdit
    dlg = _dialog(qtbot, "KEY123")
    assert dlg._api_key.echoMode() == QLineEdit.EchoMode.Password  # blocked off
    assert dlg._api_key.isReadOnly() is True
    assert dlg._api_edit_btn.text() == "Edit"


def test_api_key_editable_when_empty(qtbot):
    from PyQt6.QtWidgets import QLineEdit
    dlg = _dialog(qtbot, "")
    # No key yet: open ready to type, in the clear.
    assert dlg._api_key.isReadOnly() is False
    assert dlg._api_key.echoMode() == QLineEdit.EchoMode.Normal
    assert dlg._api_edit_btn.text() == "Hide"


def test_edit_button_toggles_reveal_and_lock(qtbot):
    from PyQt6.QtWidgets import QLineEdit
    dlg = _dialog(qtbot, "KEY123")

    dlg._api_edit_btn.click()                       # Edit -> reveal + unlock
    assert dlg._api_key.isReadOnly() is False
    assert dlg._api_key.echoMode() == QLineEdit.EchoMode.Normal
    assert dlg._api_edit_btn.text() == "Hide"

    dlg._api_edit_btn.click()                       # Hide -> re-mask + lock
    assert dlg._api_key.isReadOnly() is True
    assert dlg._api_key.echoMode() == QLineEdit.EchoMode.Password
    assert dlg._api_edit_btn.text() == "Edit"


def test_result_settings_returns_key_while_masked(qtbot):
    # Masking is display-only; the field still holds (and saves) the real key.
    dlg = _dialog(qtbot, "KEY123")
    assert dlg.result_settings()["google_api_key"] == "KEY123"


# ── Alt ID password: session-only, never persisted ─────────────────────────
def _dialog_pw(qtbot, password):
    from gui.settings_dialog import SettingsDialog
    dlg = SettingsDialog({"db_path": "", "events_db_path": "", "theme": "dark",
                          "google_api_key": ""}, alt_id_password=password)
    qtbot.addWidget(dlg)
    return dlg


def test_alt_password_masked_and_locked_when_present(qtbot):
    from PyQt6.QtWidgets import QLineEdit
    dlg = _dialog_pw(qtbot, "hunter2")
    assert dlg._altpw.echoMode() == QLineEdit.EchoMode.Password
    assert dlg._altpw.isReadOnly() is True
    assert dlg._altpw_edit_btn.text() == "Edit"


def test_alt_password_editable_when_empty(qtbot):
    from PyQt6.QtWidgets import QLineEdit
    dlg = _dialog_pw(qtbot, "")
    assert dlg._altpw.isReadOnly() is False
    assert dlg._altpw.echoMode() == QLineEdit.EchoMode.Normal


def test_alt_password_never_in_result_settings(qtbot):
    dlg = _dialog_pw(qtbot, "hunter2")
    assert "alt_id_password" not in dlg.result_settings()


def test_alt_password_returned_verbatim(qtbot):
    # No strip: the password must match the encryptor tool byte-for-byte.
    dlg = _dialog_pw(qtbot, " spaced pw ")
    assert dlg.result_alt_id_password() == " spaced pw "
