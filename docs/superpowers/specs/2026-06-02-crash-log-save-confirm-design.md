# Crash Logging & Save Confirmation — Design Spec

**Date:** 2026-06-02
**Status:** Approved (pending spec review)

## Goal

Two small, independent reliability/UX features for the BSCA Member Manager:

1. **Crash log** — when the app hits an unhandled Python exception, append a report to `%APPDATA%\BSCA-Members\logs\debug_<YYYY-MM-DD>.txt`, show the user an error dialog with the file path, and exit.
2. **Save confirmation** — when the user clicks "Save Changes" on the Info tab, show a confirmation dialog summarizing the changed fields (friendly label, old → new) and require confirmation before writing.

## Architecture

- **Feature 1** lives in a new self-contained module `crash_log.py` with pure, testable functions (`format_report`, `write_crash_report`) and a thin `install()` that wires `sys.excepthook`. `member_manager.main()` calls `install()` once after the `QApplication` is created.
- **Feature 2** adds a module-level `FIELD_LABELS` dict and a pure `build_change_summary(old, fields)` function to `gui/member_tabs.py` (unit-testable without a display), and inserts a confirmation `QMessageBox` into `MemberTabsWidget._save_info()` before the existing write.

## Tech Stack

Python 3.11, PyQt6, pytest. No new dependencies.

---

## Feature 1 — Crash log

### New module: `crash_log.py` (repo root, next to `member_manager.py`)

```python
import os, sys, platform, traceback
from datetime import datetime
```

**`def app_base_dir() -> str`**
- If `getattr(sys, "frozen", False)`: `os.path.join(os.environ.get("APPDATA") or os.path.dirname(sys.executable), "BSCA-Members")`.
- Else (dev): the repo directory = `os.path.dirname(os.path.abspath(__file__))`.
- (Mirrors `member_manager._settings_path`'s base logic. Minor duplication is acceptable to keep this module self-contained.)

**`def log_dir() -> str`**
- `d = os.path.join(app_base_dir(), "logs")`; `os.makedirs(d, exist_ok=True)`; return `d`.

**`def format_report(exc_type, exc_value, exc_tb, *, now: datetime) -> str`** *(pure)*
- Build a report string:
  - Header line: `"=" * 60` then `f"CRASH {now:%Y-%m-%d %H:%M:%S}"` then `"=" * 60`.
  - Environment lines: `Frozen: <bool>`, `Platform: <platform.platform()>`, `Python: <platform.python_version()>`.
  - A blank line, then the formatted traceback via `"".join(traceback.format_exception(exc_type, exc_value, exc_tb))`.
  - Trailing newline.
- Must include the exception's message (it's part of `format_exception`).

**`def write_crash_report(directory: str, text: str, *, now: datetime) -> str`**
- `path = os.path.join(directory, f"debug_{now:%Y-%m-%d}.txt")`.
- Open in **append** mode (`"a"`, `encoding="utf-8"`), write `text`, return `path`.

**`def install(parent=None) -> None`**
- Define a handler `(exc_type, exc_value, exc_tb)`:
  - `now = datetime.now()`.
  - `text = format_report(exc_type, exc_value, exc_tb, now=now)`.
  - `try: path = write_crash_report(log_dir(), text, now=now)` — guard the write so a logging failure never masks the original crash; on failure set `path = "(could not write log)"`.
  - Show `QMessageBox.critical(parent, "Unexpected Error", f"The application encountered an error and must close.\n\nDetails saved to:\n{path}")` (import `QMessageBox` lazily inside the handler so the module has no hard Qt dependency at import time — keeps it unit-testable).
  - `sys.exit(1)`.
- Assign `sys.excepthook = handler`.

### Wiring in `member_manager.py`

In `main()`, immediately after `app = QApplication(sys.argv)`:

```python
    import crash_log
    crash_log.install()
```

(Placed right after the app is constructed so the dialog can be shown. The handler runs on the main thread; the app uses no worker threads.)

### `.gitignore`

Add `logs/` so dev-run crash files are not committed.

### Notes / limitations

- Covers unhandled **Python** exceptions (the realistic crash mode, e.g. a bad enum or a DAO error escaping a slot). Native crashes (segfaults) are not catchable via `sys.excepthook` — out of scope.
- Append mode means multiple crashes the same day accumulate in one file, each with its own timestamped header separator.

---

## Feature 2 — Save confirmation dialog

### Current behavior (`MemberTabsWidget._save_info`)

`_save_info` builds a `fields` dict, computes `changes = [f"{k}: {old.get(k)!r} → {v!r}" ...]`, returns early if `not changes`, then calls `update_contact(...)` and logs an event. It writes immediately with no confirmation.

### New behavior

Add at module level in `gui/member_tabs.py`:

```python
FIELD_LABELS = {
    "first_name": "First Name", "last_name": "Last Name",
    "chinese_name": "Chinese Name", "gender": "Gender", "dob": "DOB",
    "member_id": "Member ID", "medicaid": "Medicaid", "medicare": "Medicare",
    "ssn": "SSN", "language": "Language", "case_manager": "Case Manager",
    "home_tell": "Home Phone", "cell": "Cell", "address": "Address",
    "emergency": "Emergency", "pcp": "PCP", "hospital": "Hospital",
    "hha": "HHA", "admission_date": "Admission Date", "notes": "Notes",
}


def build_change_summary(old: dict, fields: dict) -> list[str]:
    """Friendly 'Label: old -> new' lines for each field whose value changed.
    Blank values render as '(empty)'. Order follows `fields` insertion order."""
    lines = []
    for key, new_val in fields.items():
        old_val = old.get(key) or ""
        if new_val != old_val:
            label = FIELD_LABELS.get(key, key)
            lines.append(f"{label}: {old_val or '(empty)'} → {new_val or '(empty)'}")
    return lines
```

(Note: `health_plan` is intentionally absent from `FIELD_LABELS` — it is read-only on the profile and never part of the change set, so it is never summarized.)

In `_save_info`, replace the current change-detection + early-return with:

```python
        summary = build_change_summary(old, fields)
        if not summary:
            self._dirty = False
            return

        name = f"{old.get('last_name', '')}, {old.get('first_name', '')}"
        confirm = QMessageBox(self)
        confirm.setWindowTitle("Confirm Changes")
        confirm.setIcon(QMessageBox.Icon.Question)
        confirm.setText(f"Confirm changes for {name}?")
        confirm.setInformativeText("\n".join(summary))
        confirm.setStandardButtons(
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Cancel
        )
        confirm.setDefaultButton(QMessageBox.StandardButton.Save)
        if confirm.exec() != QMessageBox.StandardButton.Save:
            return  # user cancelled — keep edits, stay dirty
```

The existing `update_contact(...)` call and the event log follow unchanged. The event-log description reuses the `summary` list (`"; ".join(summary[:5])`) instead of the old raw `changes` formatting, so the log matches the dialog.

### Scope

Only the Info tab "Save Changes" button. The wizard and the add-row dialogs (enrollment, auth, availability, absence) are unchanged.

---

## Testing

### Feature 1 unit tests (`tests/test_crash_log.py`, new)
- `format_report` with a real raised/caught exception includes: the exception message, the traceback (`Traceback (most recent call last)`), and a header containing `CRASH` and the formatted timestamp.
- `write_crash_report` writes `debug_<date>.txt` in a `tmp_path` dir and **appends** — two calls with the same `now` date produce a file containing both report texts (and two `CRASH` headers).
- The filename uses the date: `write_crash_report` with `now = datetime(2026, 6, 2, ...)` creates `debug_2026-06-02.txt`.

### Feature 2 unit tests (`tests/test_member_tabs_summary.py`, new)
- `build_change_summary` returns only changed fields: given `old={"first_name":"Mary","cell":""}` and `fields={"first_name":"Marie","cell":"","address":"14 Oak"}`, the result lists First Name and Address but not Cell.
- Friendly labels: the line for `first_name` starts with `"First Name:"`.
- Blank handling: an empty old value renders `(empty)` (e.g. `"Cell: (empty) → 917-555-0143"`), and clearing a field renders `→ (empty)`.
- No changes → empty list.

### Manual verification
- **Crash:** temporarily raise inside a slot (or trust the unit tests) — confirm a `debug_<date>.txt` appears under `%APPDATA%\BSCA-Members\logs\`, the dialog shows the path, and the app exits.
- **Save confirm:** edit a member field, click Save Changes → dialog lists the change(s) with old → new; Cancel keeps editing (still dirty); Save writes and logs the event.

## Out of scope

- Native/segfault crash capture (only Python exceptions).
- Save confirmation on the wizard or add-row dialogs.
- Rotating/pruning old daily log files.
