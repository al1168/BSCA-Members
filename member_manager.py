import sys
import os
from PyQt6.QtWidgets import QApplication, QMessageBox, QDateTimeEdit, QAbstractSpinBox
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QObject, QEvent
from gui.main_window import MainWindow
from gui.theme import apply_theme
from settings import load_settings, save_settings
import crash_log


class _NoStepButtonsFilter(QObject):
    """App-wide fix: force every date/time edit (QDateEdit/QTimeEdit) to show no
    up/down step buttons, so a stray click on a field edge can't increment the
    value. The calendar popup and typing still work. Installed on the
    application, so it covers every dialog, current and future."""

    _NONE = QAbstractSpinBox.ButtonSymbols.NoButtons

    def eventFilter(self, obj, event):
        t = event.type()
        if (t == QEvent.Type.Polish or t == QEvent.Type.Show) \
                and isinstance(obj, QDateTimeEdit) \
                and obj.buttonSymbols() != self._NONE:
            obj.setButtonSymbols(self._NONE)
        return False


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


def main():
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(_resource_path("bowery-emblem.ico")))
    # Disable up/down steppers on every date/time edit (prevents click-to-increment).
    app._no_step_filter = _NoStepButtonsFilter(app)
    app.installEventFilter(app._no_step_filter)
    crash_log.install()
    settings = load_settings(SETTINGS_PATH)
    if ensure_events_path(settings):
        save_settings(settings, SETTINGS_PATH)   # persist the appdata default
    apply_theme(app, settings.get("theme", "dark"))
    window = MainWindow(settings, SETTINGS_PATH)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
