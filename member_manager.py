import sys
import os
from PyQt6.QtWidgets import QApplication, QMessageBox
from gui.main_window import MainWindow
from gui.theme import apply_theme
from settings import load_settings


def _settings_path() -> str:
    """Return a writable, persistent path for the settings file.

    When frozen by PyInstaller, ``__file__`` points at a temp extraction
    directory that is deleted on exit, so settings must live somewhere
    stable — %APPDATA%\\BSCA-Members. In dev we keep the file in the repo.
    """
    if getattr(sys, "frozen", False):
        base = os.path.join(
            os.environ.get("APPDATA") or os.path.dirname(sys.executable),
            "BSCA-Members",
        )
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "bsca_members_settings.json")


SETTINGS_PATH = _settings_path()


def main():
    app = QApplication(sys.argv)
    import crash_log
    crash_log.install()
    settings = load_settings(SETTINGS_PATH)
    apply_theme(app, settings.get("theme", "dark"))
    window = MainWindow(settings, SETTINGS_PATH)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
