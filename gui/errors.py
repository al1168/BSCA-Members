"""User-facing database error dialogs.

Staff are non-technical: raw pyodbc/ODBC text ("HY000 …The database has been
placed in a state…") isn't actionable. friendly_db_message maps the failures
staff actually hit (file locked by a colleague, file missing/moved) to plain
language, and show_db_error is the one dialog every handler should call — it
also records the full technical detail to the daily debug log so problems in
the field stay diagnosable.
"""
from PyQt6.QtWidgets import QMessageBox

import crash_log

_LOCK_MARKERS = (
    "has been placed in a state",      # ACE: opened exclusively elsewhere
    "could not lock file",
    "is exclusively locked",
    "could not use",                   # "could not use '<file>'; file already in use"
    "file already in use",
)

# Access 42S02: the table simply isn't there. In the field that means the
# database predates a feature's Setup step, not a broken query.
_MISSING_TABLE_MARKERS = (
    "cannot find the input table",
)

_MISSING_MARKERS = (
    "database not found",              # our own FileNotFoundError text
    "could not find file",
    "is not a valid path",
    "path is not valid",
)


def friendly_db_message(exc: BaseException) -> str:
    """A plain-language message for a database error, with the technical detail
    kept to a trailing line."""
    raw = str(exc)
    lowered = raw.lower()
    if isinstance(exc, FileNotFoundError) or any(m in lowered for m in _MISSING_MARKERS):
        return (
            "The database file can't be found.\n\n"
            "It may have been moved or renamed, or the network drive may be "
            "disconnected. Check the path in ⚙ Settings.\n\n"
            f"Details: {raw}"
        )
    if any(m in lowered for m in _MISSING_TABLE_MARKERS):
        return (
            "This database hasn't been set up for the company calendar yet.\n\n"
            "Run BSCA Setup on this database, then try again.\n\n"
            f"Details: {raw}"
        )
    if any(m in lowered for m in _LOCK_MARKERS):
        return (
            "The database is locked by another program.\n\n"
            "Someone may have it open exclusively (for example in Microsoft "
            "Access). Ask them to close it, then try again.\n\n"
            f"Details: {raw}"
        )
    return (
        "Something went wrong talking to the database.\n\n"
        "The change may not have been saved. Try again; if it keeps "
        "happening, note what you were doing and contact support.\n\n"
        f"Details: {raw}"
    )


def show_db_error(parent, exc: BaseException, title: str = "Database Error") -> None:
    """Show a friendly error dialog for `exc` and log the full detail."""
    crash_log.log_warning(f"{title}: {exc!r}")
    QMessageBox.critical(parent, title, friendly_db_message(exc))
