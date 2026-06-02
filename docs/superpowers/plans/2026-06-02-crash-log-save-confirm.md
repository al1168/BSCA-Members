# Crash Logging & Save Confirmation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Write a crash report to `%APPDATA%\BSCA-Members\logs\debug_<date>.txt` (then dialog + exit) on any unhandled exception, and add a Save-confirmation dialog summarizing changes on the Info tab.

**Architecture:** Feature 1 is a self-contained `crash_log.py` with pure functions (`format_report`, `write_crash_report`) plus a thin `install()` that sets `sys.excepthook`; `member_manager.main()` calls it once. Feature 2 adds a module-level `FIELD_LABELS` dict and pure `build_change_summary()` to `gui/member_tabs.py`, and a Save/Cancel `QMessageBox` gate inside `_save_info()`.

**Tech Stack:** Python 3.11, PyQt6, pytest. No new dependencies.

---

## File Map

```
crash_log.py                       create — app_base_dir, log_dir, format_report, write_crash_report, install
member_manager.py                  modify — call crash_log.install() in main()
.gitignore                         modify — add logs/
gui/member_tabs.py                 modify — FIELD_LABELS, build_change_summary, confirm dialog in _save_info
tests/test_crash_log.py            create — unit tests for format_report + write_crash_report
tests/test_member_tabs_summary.py  create — unit tests for build_change_summary
```

---

## Task 1: crash_log.py module

**Files:**
- Create: `crash_log.py`
- Test: `tests/test_crash_log.py`

- [ ] **Step 1: Write the failing unit tests**

Create `tests/test_crash_log.py`:

```python
from datetime import datetime


def _sample_exc():
    """Raise and catch a real exception, returning (exc_type, exc_value, exc_tb)."""
    import sys
    try:
        raise ValueError("boom-message")
    except ValueError:
        return sys.exc_info()


def test_format_report_includes_message_traceback_and_header():
    from crash_log import format_report
    et, ev, tb = _sample_exc()
    now = datetime(2026, 6, 2, 14, 51, 20)
    text = format_report(et, ev, tb, now=now)
    assert "CRASH 2026-06-02 14:51:20" in text
    assert "boom-message" in text
    assert "Traceback (most recent call last)" in text
    assert "ValueError" in text


def test_write_crash_report_uses_dated_filename(tmp_path):
    from crash_log import write_crash_report
    now = datetime(2026, 6, 2, 14, 51, 20)
    path = write_crash_report(str(tmp_path), "hello\n", now=now)
    assert path.endswith("debug_2026-06-02.txt")
    import os
    assert os.path.exists(path)


def test_write_crash_report_appends(tmp_path):
    from crash_log import write_crash_report
    now = datetime(2026, 6, 2, 9, 0, 0)
    write_crash_report(str(tmp_path), "===== CRASH A =====\n", now=now)
    path = write_crash_report(str(tmp_path), "===== CRASH B =====\n", now=now)
    with open(path, encoding="utf-8") as f:
        content = f.read()
    assert "CRASH A" in content
    assert "CRASH B" in content
    assert content.count("CRASH") == 2
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv\Scripts\pytest tests/test_crash_log.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'crash_log'`

- [ ] **Step 3: Create `crash_log.py`**

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv\Scripts\pytest tests/test_crash_log.py -v`
Expected: 3 passed

- [ ] **Step 5: Run the full suite**

Run: `.venv\Scripts\pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add crash_log.py tests/test_crash_log.py
git commit -m "feat: add crash_log module (daily appended debug report)"
```
End the commit message with the trailer:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Task 2: Wire crash_log into the app entry point

**Files:**
- Modify: `member_manager.py`
- Modify: `.gitignore`

- [ ] **Step 1: Install the excepthook in `main()`**

In `member_manager.py`, the current `main()` is:

```python
def main():
    app = QApplication(sys.argv)
    settings = load_settings(SETTINGS_PATH)
    apply_theme(app, settings.get("theme", "dark"))
    window = MainWindow(settings, SETTINGS_PATH)
    window.show()
    sys.exit(app.exec())
```

Replace it with (add the two `crash_log` lines right after the app is created):

```python
def main():
    app = QApplication(sys.argv)
    import crash_log
    crash_log.install()
    settings = load_settings(SETTINGS_PATH)
    apply_theme(app, settings.get("theme", "dark"))
    window = MainWindow(settings, SETTINGS_PATH)
    window.show()
    sys.exit(app.exec())
```

- [ ] **Step 2: Add `logs/` to `.gitignore`**

Append a line to `.gitignore`:

```
logs/
```

- [ ] **Step 3: Verify the entry point imports cleanly**

Run: `.venv\Scripts\python -c "import member_manager, crash_log; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Run the full suite (unaffected)**

Run: `.venv\Scripts\pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add member_manager.py .gitignore
git commit -m "feat: install crash_log excepthook at startup; ignore logs/"
```
End with:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Task 3: build_change_summary + FIELD_LABELS

**Files:**
- Modify: `gui/member_tabs.py`
- Test: `tests/test_member_tabs_summary.py`

- [ ] **Step 1: Write the failing unit tests**

Create `tests/test_member_tabs_summary.py`:

```python
def test_summary_lists_only_changed_fields():
    from gui.member_tabs import build_change_summary
    old = {"first_name": "Mary", "cell": "", "address": "12 Elm St"}
    fields = {"first_name": "Marie", "cell": "", "address": "14 Oak Ave"}
    lines = build_change_summary(old, fields)
    joined = "\n".join(lines)
    assert any(line.startswith("First Name:") for line in lines)
    assert any(line.startswith("Address:") for line in lines)
    assert "Cell" not in joined  # unchanged -> excluded


def test_summary_uses_friendly_labels_and_arrow():
    from gui.member_tabs import build_change_summary
    lines = build_change_summary({"first_name": "Mary"}, {"first_name": "Marie"})
    assert lines == ["First Name: Mary → Marie"]


def test_summary_renders_empty_placeholder():
    from gui.member_tabs import build_change_summary
    # filling a blank field
    lines = build_change_summary({"cell": ""}, {"cell": "917-555-0143"})
    assert lines == ["Cell: (empty) → 917-555-0143"]
    # clearing a populated field
    lines = build_change_summary({"address": "12 Elm St"}, {"address": ""})
    assert lines == ["Address: 12 Elm St → (empty)"]


def test_summary_empty_when_no_changes():
    from gui.member_tabs import build_change_summary
    assert build_change_summary({"first_name": "Mary"}, {"first_name": "Mary"}) == []
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv\Scripts\pytest tests/test_member_tabs_summary.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_change_summary'`

- [ ] **Step 3: Add `FIELD_LABELS` and `build_change_summary` at module level in `gui/member_tabs.py`**

Insert after the imports at the top of the file (before `class MemberTabsWidget`):

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
    """Friendly 'Label: old → new' lines for each field whose value changed.

    Blank values render as '(empty)'. Order follows `fields` iteration order.
    """
    lines = []
    for key, new_val in fields.items():
        old_val = old.get(key) or ""
        if new_val != old_val:
            label = FIELD_LABELS.get(key, key)
            lines.append(f"{label}: {old_val or '(empty)'} → {new_val or '(empty)'}")
    return lines
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv\Scripts\pytest tests/test_member_tabs_summary.py -v`
Expected: 4 passed

- [ ] **Step 5: Run the full suite**

Run: `.venv\Scripts\pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add gui/member_tabs.py tests/test_member_tabs_summary.py
git commit -m "feat: add build_change_summary() + FIELD_LABELS for save confirmation"
```
End with:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Task 4: Save confirmation dialog in _save_info

**Files:**
- Modify: `gui/member_tabs.py`

- [ ] **Step 1: Replace the change-detection block in `_save_info()`**

In `_save_info()`, find this block (it comes right after the `fields = { ... }` dict literal):

```python
        changes = [
            f"{k}: {old.get(k)!r} → {v!r}"
            for k, v in fields.items()
            if v != (old.get(k) or "")
        ]

        if not changes:
            self._dirty = False
            return
```

Replace it with:

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

- [ ] **Step 2: Update the event-log description to reuse `summary`**

Still in `_save_info()`, find the event-log call:

```python
                    insert_event(
                        conn, "EDIT", self._center_id,
                        f"{fields['last_name']}, {fields['first_name']}",
                        "; ".join(changes[:5]),
                    )
```

Replace the last argument so it uses `summary` (the variable `changes` no longer exists):

```python
                    insert_event(
                        conn, "EDIT", self._center_id,
                        f"{fields['last_name']}, {fields['first_name']}",
                        "; ".join(summary[:5]),
                    )
```

- [ ] **Step 3: Verify the import works**

Run: `.venv\Scripts\python -c "from gui.member_tabs import MemberTabsWidget; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Confirm no leftover `changes` reference in `_save_info`**

Grep `gui/member_tabs.py` for `changes` — there should be no remaining reference in `_save_info` (the variable was fully replaced by `summary`).

- [ ] **Step 5: Run the full suite (unaffected)**

Run: `.venv\Scripts\pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add gui/member_tabs.py
git commit -m "feat: confirm changes summary dialog before saving member info"
```
End with:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Task 5: Full suite + exe rebuild + manual smoke test

**Files:** none changed

- [ ] **Step 1: Run the full test suite**

Run: `.venv\Scripts\pytest -q`
Expected: all pass (the prior 63 plus the 7 new unit tests: 3 crash_log + 4 summary).

- [ ] **Step 2: Rebuild the exe**

Stop any running instance (it locks the output file), then build:

```
powershell -Command "try { Stop-Process -Name MemberManager -Force -ErrorAction Stop } catch {}"
.venv\Scripts\pyinstaller MemberManager.spec
```

Expected: `Build complete! The results are available in: ...\dist`

- [ ] **Step 3: Manual smoke test**

Launch `dist\MemberManager.exe`, set the DB path if needed, click a member:
- **Save confirm:** edit a field (e.g. Cell), click **Save Changes** → a "Confirm Changes for <Last, First>?" dialog lists the change(s) as `Label: old → new`. **Cancel** keeps editing (still dirty, nothing saved). **Save** writes and logs the event. Clicking Save with no edits shows no dialog.
- **Crash log (optional):** the crash path is covered by unit tests; to verify end-to-end you can temporarily add `raise RuntimeError("test")` to a slot, trigger it, confirm `debug_<date>.txt` appears under `%APPDATA%\BSCA-Members\logs\` with the traceback and the dialog shows the path, then remove the test raise.

---

## Self-Review Notes

- **Spec coverage:** Feature 1 → Task 1 (module: app_base_dir/log_dir/format_report/write_crash_report/install) + Task 2 (wire into main, .gitignore). Feature 2 → Task 3 (FIELD_LABELS + build_change_summary) + Task 4 (confirm dialog in _save_info, event-log reuse). Testing → Task 1 (3 unit) + Task 3 (4 unit) + Task 5 (full run + manual).
- **Type consistency:** `format_report(exc_type, exc_value, exc_tb, *, now)`, `write_crash_report(directory, text, *, now) -> str`, `install(parent=None)`, `build_change_summary(old, fields) -> list[str]`, `FIELD_LABELS` are referenced consistently across tasks. `summary` replaces `changes` in both the guard and the event log in Task 4.
- **No placeholders:** every code step shows full code; commands list expected output.
- **Note:** `FIELD_LABELS` intentionally omits `health_plan` (read-only on the profile; its value is unchanged in `fields`, so it is filtered out by `build_change_summary` and never summarized).
