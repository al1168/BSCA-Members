"""Crash logging: write unhandled-exception reports to a daily debug file.

On an unhandled Python exception, install() writes a timestamped report to
%APPDATA%/BSCA-Members/logs/debug_<date>.txt (appending), shows an error
dialog with the path, and exits. Pure helpers are unit-tested; the Qt dialog
is verified manually.
"""
import os
import sys
import platform
import traceback
from datetime import datetime


def app_base_dir() -> str:
    """Writable base dir: %APPDATA%/BSCA-Members when frozen, else the repo dir.

    Mirrors member_manager._settings_path so logs sit beside settings.
    """
    if getattr(sys, "frozen", False):
        return os.path.join(
            os.environ.get("APPDATA") or os.path.dirname(sys.executable),
            "BSCA-Members",
        )
    return os.path.dirname(os.path.abspath(__file__))


def log_dir() -> str:
    """Return (creating if needed) the logs directory."""
    d = os.path.join(app_base_dir(), "logs")
    os.makedirs(d, exist_ok=True)
    return d


def format_report(exc_type, exc_value, exc_tb, *, now: datetime) -> str:
    """Build the crash report text for one exception."""
    bar = "=" * 60
    header = f"{bar}\nCRASH {now:%Y-%m-%d %H:%M:%S}\n{bar}\n"
    env = (
        f"Frozen: {bool(getattr(sys, 'frozen', False))}\n"
        f"Platform: {platform.platform()}\n"
        f"Python: {platform.python_version()}\n\n"
    )
    tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    return header + env + tb_text + "\n"


def write_crash_report(directory: str, text: str, *, now: datetime) -> str:
    """Append the report text to debug_<date>.txt in `directory`; return the path."""
    path = os.path.join(directory, f"debug_{now:%Y-%m-%d}.txt")
    with open(path, "a", encoding="utf-8") as f:
        f.write(text)
    return path


def install(parent=None) -> None:
    """Route unhandled exceptions to a crash log + dialog, then exit."""
    def handler(exc_type, exc_value, exc_tb):
        now = datetime.now()
        text = format_report(exc_type, exc_value, exc_tb, now=now)
        try:
            path = write_crash_report(log_dir(), text, now=now)
        except Exception:
            path = "(could not write log)"
        try:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(
                parent, "Unexpected Error",
                "The application encountered an error and must close.\n\n"
                f"Details saved to:\n{path}",
            )
        except Exception:
            pass
        sys.exit(1)

    sys.excepthook = handler
