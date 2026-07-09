"""The running build's version string.

deploy/deploy.ps1 writes _build_info.py (gitignored) just before PyInstaller
runs, so packaged builds report the date+commit they were built from; running
from source without it reports "dev". Shown in the window title so anyone can
tell at a glance which build a given office PC is running.
"""


def app_version() -> str:
    try:
        from _build_info import APP_VERSION
        return APP_VERSION
    except ImportError:
        return "dev"
