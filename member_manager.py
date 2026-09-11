import sys
import os
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtGui import QIcon
from gui.main_window import MainWindow
from gui.theme import apply_theme
from settings import load_settings, save_settings
import crash_log


def _resource_path(name: str) -> str:
    """Path to a bundled resource, working both in dev and when frozen by
    PyInstaller (which extracts datas to sys._MEIPASS)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def _app_data_dir() -> str:
    """A writable, persistent per-user directory for app data.

    When frozen by PyInstaller, ``__file__`` points at a temp extraction
    directory that is deleted on exit, so data must live somewhere stable —
    %APPDATA%\\BSCA-Members. In dev we keep files in the repo.
    """
    if getattr(sys, "frozen", False):
        base = os.path.join(
            os.environ.get("APPDATA") or os.path.dirname(sys.executable),
            "BSCA-Members",
        )
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(base, exist_ok=True)
    return base


def _settings_path() -> str:
    return os.path.join(_app_data_dir(), "bsca_members_settings.json")


def default_events_db_path() -> str:
    """The event log lives in %APPDATA%\\BSCA-Members (next to settings) so it
    isn't accidentally deleted alongside the member database or from a shared
    folder."""
    return os.path.join(_app_data_dir(), "events.db")


def ensure_events_path(settings: dict) -> bool:
    """Default the events log into %APPDATA% when it isn't configured. Returns
    True when the settings dict was changed (so the caller can persist it)."""
    if not settings.get("events_db_path"):
        settings["events_db_path"] = default_events_db_path()
        return True
    return False


SETTINGS_PATH = _settings_path()


def run(app) -> int:
    """Build the main window and run the event loop; rebuild the window when
    it asks to be reopened (a text-size change) and exit otherwise.

    Settings are re-read on every pass so the rebuilt window and the freshly
    applied theme see the size the user just saved. The session-only alt-id
    password is carried in memory (it is never on disk) and handed to the
    new window before the member is reopened. ensure_events_path is re-run
    each pass but only writes on the first (the path is non-empty
    afterwards)."""
    reopen_id = None
    reopen_password = ""
    while True:
        settings = load_settings(SETTINGS_PATH)
        if ensure_events_path(settings):
            save_settings(settings, SETTINGS_PATH)   # persist the appdata default
        apply_theme(app, settings.get("theme", "dark"),
                    settings.get("text_size", "normal"))
        window = MainWindow(settings, SETTINGS_PATH)
        window.set_alt_id_password(reopen_password)
        window.show()
        if reopen_id is not None:
            window.jump_to_member(reopen_id)
        code = app.exec()
        requested = window.reopen_requested
        reopen_id = window.reopen_member_id if requested else None
        reopen_password = window.reopen_alt_id_password if requested else ""
        # Drop the closed window now: otherwise it stays alive through the
        # next pass, apply_theme re-polishes two full widget trees and two
        # member profiles sit in memory at once.
        window = None
        if not requested:
            return code


def main():
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(_resource_path("bowery-emblem.ico")))
    crash_log.install()
    sys.exit(run(app))


if __name__ == "__main__":
    main()
