# Explicit-Entry New Authorizations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Creating an authorization requires explicit entry of every field — no auto-filled dates, no silently defaulted dropdowns — in both the Auths tab dialog and the new-member wizard; editing existing auths is unchanged.

**Architecture:** A pure module-level helper `missing_new_auth_fields` in `gui/member_tabs.py` computes which required fields a new authorization is missing (headless-testable). `_open_auth_dialog` uses it in create mode and gains empty date/blank combo defaults; `StepAuths` in the wizard gets empty dates, an all-empty `is_skipped()` rule, and a stricter `validate()`. All widgets and validation plumbing (`DateLineEdit`, `set_widget_error`, the `QComboBox[error="true"]` QSS rule) already exist.

**Tech Stack:** Python 3.11, PyQt6, pytest with offscreen Qt (`QT_QPA_PLATFORM=offscreen`).

**Spec:** `docs/superpowers/specs/2026-09-01-explicit-auth-entry-design.md`

**Working notes for the implementer:**
- Run tests from the repo root: `python -m pytest <file> -v`.
- Qt test files start with `import os` / `os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")` before any PyQt import, plus the module-scoped `qapp` fixture (see `tests/test_plan_type.py`).
- Key existing code: `_open_auth_dialog` in `gui/member_tabs.py` (~line 2977, search for `def _open_auth_dialog`), `StepAuths` in `gui/wizard/step_auths.py`, `DateLineEdit`/`set_widget_error` in `gui/address_autocomplete.py`. Line numbers may drift — anchor on the code.
- `set_widget_error(widget, on)` sets the widget's `error` dynamic property to a Python bool — assert with `.property("error") is True`.
- Every commit message ends with:
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`

---

### Task 1: Pure validation helper `missing_new_auth_fields`

**Files:**
- Modify: `gui/member_tabs.py` (module level, near `build_change_summary`)
- Test: `tests/test_explicit_auth_entry.py` (new)

- [ ] **Step 1: Write the failing tests** — create `tests/test_explicit_auth_entry.py`:

```python
# tests/test_explicit_auth_entry.py
"""Explicit-entry new authorizations: no auto-filled dates, all fields
required when creating (dialog + wizard); editing is exempt."""
import os
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


# ── pure helper: which required fields is a new auth missing ───────────────

def test_missing_fields_all_empty_lists_everything():
    from gui.member_tabs import missing_new_auth_fields
    missing = missing_new_auth_fields(
        start_valid=False, end_valid=False, has_day=False,
        health_plan="", plan_type="", member_id="", auth_number="")
    assert missing == ["Auth Start", "Auth End", "Days", "Health Plan",
                       "Plan Type", "Member ID", "Auth Number"]


def test_missing_fields_complete_returns_empty():
    from gui.member_tabs import missing_new_auth_fields
    assert missing_new_auth_fields(
        start_valid=True, end_valid=True, has_day=True,
        health_plan="HF", plan_type="MAP", member_id="M1",
        auth_number="A1") == []


def test_missing_fields_whitespace_counts_as_missing():
    from gui.member_tabs import missing_new_auth_fields
    missing = missing_new_auth_fields(
        start_valid=True, end_valid=True, has_day=True,
        health_plan="HF", plan_type="MAP", member_id="   ",
        auth_number=" ")
    assert missing == ["Member ID", "Auth Number"]
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_explicit_auth_entry.py -v`
Expected: 3 FAIL with `ImportError: cannot import name 'missing_new_auth_fields'`

- [ ] **Step 3: Implement** — in `gui/member_tabs.py`, at module level directly after the `build_change_summary` function, add:

```python
def missing_new_auth_fields(*, start_valid: bool, end_valid: bool,
                            has_day: bool, health_plan: str, plan_type: str,
                            member_id: str, auth_number: str) -> list[str]:
    """Labels of the required fields still missing when creating a NEW
    authorization (creation requires every field; editing is exempt —
    see _open_auth_dialog). Order matches the dialog's rows."""
    missing = []
    if not start_valid:
        missing.append("Auth Start")
    if not end_valid:
        missing.append("Auth End")
    if not has_day:
        missing.append("Days")
    if not health_plan.strip():
        missing.append("Health Plan")
    if not plan_type.strip():
        missing.append("Plan Type")
    if not member_id.strip():
        missing.append("Member ID")
    if not auth_number.strip():
        missing.append("Auth Number")
    return missing
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_explicit_auth_entry.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add gui/member_tabs.py tests/test_explicit_auth_entry.py
git commit -m "feat: pure required-field check for new authorizations"
```

---

### Task 2: Auths tab dialog — empty defaults + full validation in create mode

**Files:**
- Modify: `gui/member_tabs.py` — `_open_auth_dialog`
- Test: `tests/test_explicit_auth_entry.py` (append)

- [ ] **Step 1: Append the test harness and failing tests** to `tests/test_explicit_auth_entry.py`:

```python
# ── Add Authorization dialog (create mode) ─────────────────────────────────

def _run_auth_dialog(monkeypatch, existing=None, fill=None,
                     member=None):
    """Open _open_auth_dialog with widget spies and a fake exec() that
    optionally fills the widgets, then clicks OK (emits accepted, which runs
    on_accept). Returns (result, cap, warnings).

    cap: dates (DateLineEdit, creation order start/end), combos (creation
    order: health plan, plan type), edits (all QLineEdits incl. dates —
    filter by placeholder), checks (7 day QCheckBoxes), boxes (button box).
    """
    from PyQt6.QtWidgets import (
        QDialog, QComboBox, QLineEdit, QCheckBox, QWidget,
        QDialogButtonBox, QMessageBox,
    )
    import gui.member_tabs as mt
    from gui.address_autocomplete import DateLineEdit

    cap = {"dates": [], "combos": [], "edits": [], "checks": [], "boxes": []}

    def spy(cls, bucket):
        orig = cls.__init__

        def spied(self, *a, **k):
            orig(self, *a, **k)
            cap[bucket].append(self)
        monkeypatch.setattr(cls, "__init__", spied)

    spy(DateLineEdit, "dates")
    spy(QComboBox, "combos")
    spy(QLineEdit, "edits")
    spy(QCheckBox, "checks")
    spy(QDialogButtonBox, "boxes")

    warnings = []
    monkeypatch.setattr(
        QMessageBox, "warning",
        staticmethod(lambda *a, **k: warnings.append(a)))

    def fake_exec(self):
        if fill is not None:
            fill(cap)
        cap["boxes"][-1].accepted.emit()          # runs on_accept
        return int(self.result()) == int(QDialog.DialogCode.Accepted)
    monkeypatch.setattr(QDialog, "exec", fake_exec)

    w = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)
    QWidget.__init__(w)          # C++ base only; QDialog(self) needs it
    w._member = member or {"member_id": "MBR-1"}
    result = w._open_auth_dialog(existing=existing)
    return result, cap, warnings


def _edit_by_placeholder(cap, prefix):
    return [e for e in cap["edits"]
            if e.placeholderText().startswith(prefix)][0]


def test_new_dialog_starts_empty_and_blank(qapp, monkeypatch):
    from db.members import HEALTH_PLANS
    seen = {}

    def inspect(cap):
        start, end = cap["dates"][:2]
        plan, ptype = cap["combos"][:2]
        seen["start"] = start.text()
        seen["end"] = end.text()
        seen["plan_items"] = [plan.itemText(i) for i in range(plan.count())]
        seen["plan_current"] = plan.currentText()
        seen["ptype_current"] = ptype.currentText()
        seen["member_id"] = _edit_by_placeholder(
            cap, "Health plan member").text()
        seen["auth_number"] = _edit_by_placeholder(
            cap, "Authorization number").text()

    result, _cap, _warn = _run_auth_dialog(monkeypatch, fill=inspect)
    assert result is None                      # nothing filled -> rejected
    assert seen["start"] == "" and seen["end"] == ""
    assert seen["plan_items"] == [""] + list(HEALTH_PLANS)
    assert seen["plan_current"] == ""
    assert seen["ptype_current"] == ""
    assert seen["member_id"] == "MBR-1"        # pre-fill kept
    assert seen["auth_number"] == ""


def test_new_dialog_rejects_and_lists_all_missing(qapp, monkeypatch):
    result, cap, warnings = _run_auth_dialog(monkeypatch,
                                             member={"member_id": ""})
    assert result is None
    assert len(warnings) == 1
    text = warnings[0][2]                      # (parent, title, text)
    for name in ("Auth Start", "Auth End", "Days", "Health Plan",
                 "Plan Type", "Member ID", "Auth Number"):
        assert name in text
    # The combos and line edits got the red error outline.
    plan, ptype = cap["combos"][:2]
    assert plan.property("error") is True
    assert ptype.property("error") is True
    assert _edit_by_placeholder(cap, "Authorization number") \
        .property("error") is True


def _fill_everything(cap):
    start, end = cap["dates"][:2]
    start.setText("01/01/2026")
    end.setText("12/31/2026")
    cap["checks"][0].setChecked(True)          # Mon
    plan, ptype = cap["combos"][:2]
    plan.setCurrentText("HF")
    ptype.setCurrentText("MAP")
    _edit_by_placeholder(cap, "Authorization number").setText("A-123")


def test_new_dialog_accepts_when_complete(qapp, monkeypatch):
    result, _cap, warnings = _run_auth_dialog(monkeypatch,
                                              fill=_fill_everything)
    assert warnings == []
    assert result == {
        "auth_start": date(2026, 1, 1),
        "auth_end": date(2026, 12, 31),
        "days": {1},
        "health_plan": "HF",
        "plan_type": "MAP",
        "member_id": "MBR-1",
        "auth_number": "A-123",
    }


def test_edit_mode_exempt_from_new_requirements(qapp, monkeypatch):
    """A legacy auth with blank plan type / auth number / member id still
    saves untouched — edit keeps today's dates+days validation only."""
    from db.members import HEALTH_PLANS
    existing = {"id": 9, "auth_start": date(2026, 1, 1),
                "auth_end": date(2026, 12, 31), "auth_days": "12",
                "health_plan": "HF", "member_id": "", "auth_number": "",
                "plan_type": ""}
    seen = {}

    def inspect(cap):
        plan = cap["combos"][0]
        seen["plan_items"] = [plan.itemText(i) for i in range(plan.count())]

    result, _cap, warnings = _run_auth_dialog(
        monkeypatch, existing=existing, fill=inspect)
    assert warnings == []
    # Edit mode: no blank entry injected into the Health Plan combo.
    assert seen["plan_items"] == list(HEALTH_PLANS)
    assert result is not None
    assert result["plan_type"] == ""
    assert result["auth_number"] == ""
    assert result["member_id"] == ""


def test_new_dialog_error_outline_clears_on_edit(qapp, monkeypatch):
    """After a failed OK, typing/choosing clears a field's red outline."""
    fixed = {}

    def fail_then_fix(cap):
        cap["boxes"][-1].accepted.emit()       # first OK: everything missing
        plan, ptype = cap["combos"][:2]
        num = _edit_by_placeholder(cap, "Authorization number")
        assert plan.property("error") is True
        plan.setCurrentText("HF")
        ptype.setCurrentText("MAP")
        num.setText("A-1")
        fixed["plan"] = plan.property("error")
        fixed["ptype"] = ptype.property("error")
        fixed["num"] = num.property("error")

    _result, _cap, _warn = _run_auth_dialog(monkeypatch, fill=fail_then_fix)
    assert fixed["plan"] is False
    assert fixed["ptype"] is False
    assert fixed["num"] is False
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_explicit_auth_entry.py -v`
Expected: the 5 new tests FAIL (dates pre-filled with today, no blank plan item, dialog accepts while empty); the 3 Task 1 tests pass.

- [ ] **Step 3: Implement** in `gui/member_tabs.py`, `_open_auth_dialog`:

3a. Replace the date-defaults block

```python
        from datetime import date as _date
        auth_start = DateLineEdit()
        auth_end = DateLineEdit()
        if existing:
            auth_start.set_pydate(existing["auth_start"])
            auth_end.set_pydate(existing["auth_end"])
        else:
            today = _date.today()
            auth_start.set_pydate(today)
            auth_end.set_pydate(today.replace(year=today.year + 1))
```

with:

```python
        # Creating: dates start empty and must be typed — a new authorization
        # is an explicit act, nothing is pre-dated.
        auth_start = DateLineEdit()
        auth_end = DateLineEdit()
        if existing:
            auth_start.set_pydate(existing["auth_start"])
            auth_end.set_pydate(existing["auth_end"])
```

(The `from datetime import date as _date` import becomes unused — delete it.)

3b. Replace the `plan_combo` block

```python
        plan_combo = QComboBox()
        plan_combo.addItems(HEALTH_PLANS)
        if existing:
            idx = plan_combo.findText(existing.get("health_plan", ""))
            if idx >= 0:
                plan_combo.setCurrentIndex(idx)
```

with:

```python
        plan_combo = QComboBox()
        if existing:
            plan_combo.addItems(HEALTH_PLANS)
            idx = plan_combo.findText(existing.get("health_plan", ""))
            if idx >= 0:
                plan_combo.setCurrentIndex(idx)
        else:
            # Creating: start on a blank entry so the plan is a choice, not
            # whatever happened to be first in the list.
            plan_combo.addItems(("",) + HEALTH_PLANS)
```

(`plan_type_combo` already has a blank first entry and starts on it for new auths — unchanged.)

3c. Directly after the `auth_number_edit` construction, add the create-mode error-clear wiring:

```python
        if not existing:
            # A failed OK outlines missing fields red; editing one clears it.
            for combo in (plan_combo, plan_type_combo):
                combo.currentIndexChanged.connect(
                    lambda _i, c=combo: set_widget_error(c, False))
            for edit in (member_id_edit, auth_number_edit):
                edit.textEdited.connect(
                    lambda _t, e=edit: set_widget_error(e, False))
```

3d. Replace `on_accept`:

```python
        def on_accept():
            ok = auth_start.flag_validity(required=True)
            ok = auth_end.flag_validity(required=True) and ok
            if existing:
                # Editing keeps the original rules (dates + days) so legacy
                # rows with blank plan type / auth number stay editable.
                if not ok:
                    QMessageBox.warning(dlg, "Validation",
                        "Enter valid Auth Start and Auth End dates "
                        "(MM/DD/YYYY).")
                    return
                if not any(cb.isChecked() for cb in day_checks.values()):
                    QMessageBox.warning(dlg, "Validation",
                                        "Select at least one day.")
                    return
                dlg.accept()
                return
            missing = missing_new_auth_fields(
                start_valid=auth_start.is_valid(required=True),
                end_valid=auth_end.is_valid(required=True),
                has_day=any(cb.isChecked() for cb in day_checks.values()),
                health_plan=plan_combo.currentText(),
                plan_type=plan_type_combo.currentText(),
                member_id=member_id_edit.text(),
                auth_number=auth_number_edit.text(),
            )
            set_widget_error(plan_combo, "Health Plan" in missing)
            set_widget_error(plan_type_combo, "Plan Type" in missing)
            set_widget_error(member_id_edit, "Member ID" in missing)
            set_widget_error(auth_number_edit, "Auth Number" in missing)
            if missing:
                QMessageBox.warning(
                    dlg, "Validation",
                    "All fields are required for a new authorization. "
                    "Missing:\n  •  " + "\n  •  ".join(missing))
                return
            dlg.accept()
        btns.accepted.connect(on_accept)
```

Note: the two `flag_validity(required=True)` calls at the top paint the
date outlines for both modes; the `is_valid(required=True)` calls inside
`missing_new_auth_fields(...)` re-read the same state without repainting.

- [ ] **Step 4: Run to verify pass, then the full suite**

Run: `python -m pytest tests/test_explicit_auth_entry.py -v`
Expected: 8 passed
Run: `python -m pytest tests/test_plan_type.py tests/test_transport_auth.py tests/test_authorized_weekdays.py -q`
Expected: all pass (these exercise neighboring auth code; `test_auth_dialog_has_plan_type_combo` uses edit mode and must be unaffected)

- [ ] **Step 5: Commit**

```bash
git add gui/member_tabs.py tests/test_explicit_auth_entry.py
git commit -m "feat: new-auth dialog starts empty and requires every field"
```

---

### Task 3: Wizard auth step — empty dates, all-empty skip rule, strict validate

**Files:**
- Modify: `gui/wizard/step_auths.py`
- Test: `tests/test_explicit_auth_entry.py` (append)

- [ ] **Step 1: Append the failing tests** to `tests/test_explicit_auth_entry.py`:

```python
# ── wizard auth step ───────────────────────────────────────────────────────

def _step(qapp):
    from gui.wizard.step_auths import StepAuths
    return StepAuths()


def test_wizard_dates_start_empty(qapp):
    s = _step(qapp)
    assert s.auth_start.text() == ""
    assert s.auth_end.text() == ""


def test_wizard_skipped_only_when_nothing_entered(qapp):
    s = _step(qapp)
    assert s.is_skipped() is True
    # Each kind of entry individually engages the step.
    s.auth_start.setText("01/01/2026")
    assert s.is_skipped() is False
    s.auth_start.setText("")
    s.auth_number.setText("A-1")
    assert s.is_skipped() is False
    s.auth_number.setText("")
    s.plan_type.setCurrentText("MAP")
    assert s.is_skipped() is False
    s.plan_type.setCurrentText("")
    s._day_checks[3].setChecked(True)
    assert s.is_skipped() is False


def test_wizard_empty_step_validates_and_collects_none(qapp):
    s = _step(qapp)
    assert s.validate() is True
    assert s.collect()["authorization"] is None


def test_wizard_engaged_step_requires_everything(qapp):
    s = _step(qapp)
    s._day_checks[1].setChecked(True)          # engaged, rest missing
    assert s.validate() is False
    assert s.auth_start.property("error") is True
    assert s.auth_end.property("error") is True
    assert s.plan_type.property("error") is True
    assert s.auth_number.property("error") is True


def test_wizard_engaged_without_days_fails(qapp):
    s = _step(qapp)
    s.auth_start.setText("01/01/2026")
    s.auth_end.setText("12/31/2026")
    s.plan_type.setCurrentText("MLTC")
    s.auth_number.setText("A-9")
    assert s.is_skipped() is False
    assert s.validate() is False               # no day checked


def test_wizard_complete_step_validates_and_collects(qapp):
    s = _step(qapp)
    s.auth_start.setText("01/01/2026")
    s.auth_end.setText("12/31/2026")
    s._day_checks[1].setChecked(True)
    s._day_checks[3].setChecked(True)
    s.plan_type.setCurrentText("MAP")
    s.auth_number.setText("A-9")
    assert s.validate() is True
    auth = s.collect()["authorization"]
    assert auth == {
        "auth_start": date(2026, 1, 1),
        "auth_end": date(2026, 12, 31),
        "auth_days": {1, 3},
        "auth_number": "A-9",
        "plan_type": "MAP",
    }


def test_wizard_error_outline_clears_on_edit(qapp):
    s = _step(qapp)
    s._day_checks[1].setChecked(True)
    s.validate()                               # paints everything red
    s.auth_number.setText("")                  # setText doesn't clear...
    assert s.auth_number.property("error") is True
    from PyQt6.QtTest import QTest
    QTest.keyClicks(s.auth_number, "A")        # ...but typing does
    assert s.auth_number.property("error") is False
    s.plan_type.setCurrentText("MAP")
    assert s.plan_type.property("error") is False
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_explicit_auth_entry.py -v`
Expected: the 7 new wizard tests FAIL (dates pre-filled, `is_skipped` ignores dates/number/plan-type, `validate` passes with missing fields); the 8 earlier tests pass.

- [ ] **Step 3: Implement** in `gui/wizard/step_auths.py`:

3a. In `_build`, replace

```python
        today = date.today()
        self.auth_start = DateLineEdit()
        self.auth_start.set_pydate(today)
        self.auth_end = DateLineEdit()
        self.auth_end.set_pydate(today.replace(year=today.year + 1))
```

with:

```python
        # Dates start empty: an authorization here is an explicit act (the
        # whole step can still be skipped by leaving everything blank).
        self.auth_start = DateLineEdit()
        self.auth_end = DateLineEdit()
```

3b. Replace the warning label's text (top of `_build`) with:

```python
        warning = QLabel(
            "⚠  This step is optional. You can skip it and add authorizations "
            "and availability later, but the member won't appear on schedules "
            "until this information is filled in. If you start an "
            "authorization, every field of it is required before continuing."
        )
```

3c. Replace the `self.plan_type` and `self.auth_number` construction with
(the only changes: the comment, the placeholder losing "(optional)", and the
error-clear connections):

```python
        # Plan type (MAP/MLTC). The blank first entry is the untouched state
        # that keeps the whole step skippable; once the step is engaged,
        # validate() requires a real choice.
        from db.members import PLAN_TYPES
        self.plan_type = QComboBox()
        self.plan_type.addItems(PLAN_TYPES)
        self.plan_type.currentIndexChanged.connect(
            lambda _i: set_widget_error(self.plan_type, False))
        auth_layout.addRow("Plan Type:", self.plan_type)

        self.auth_number = QLineEdit()
        self.auth_number.setPlaceholderText("Authorization number")
        self.auth_number.textEdited.connect(
            lambda _t: set_widget_error(self.auth_number, False))
        auth_layout.addRow("Auth #:", self.auth_number)
```

3d. Replace `is_skipped`:

```python
    def is_skipped(self) -> bool:
        """The step counts as skipped only when nothing at all was entered —
        typing a date or number without checking days no longer silently
        discards the entry."""
        return (not any(cb.isChecked() for cb in self._day_checks.values())
                and not self.auth_start.text().strip()
                and not self.auth_end.text().strip()
                and not self.auth_number.text().strip()
                and not self.plan_type.currentText())
```

3e. Replace `validate`:

```python
    def validate(self) -> bool:
        """When the step is engaged, every authorization field is required:
        both dates, at least one day, a plan type, and an auth number. Added
        availability times must always be valid. Flags the bad fields red."""
        ok = True
        if not self.is_skipped():
            ok = self.auth_start.flag_validity(required=True) and ok
            ok = self.auth_end.flag_validity(required=True) and ok
            ok = any(cb.isChecked()
                     for cb in self._day_checks.values()) and ok
            plan_ok = bool(self.plan_type.currentText())
            set_widget_error(self.plan_type, not plan_ok)
            ok = plan_ok and ok
            num_ok = bool(self.auth_number.text().strip())
            set_widget_error(self.auth_number, not num_ok)
            ok = num_ok and ok
        for r in self._avail_rows:
            for field in (r["t_start"], r["t_end"]):
                valid = field.is_valid()
                set_widget_error(field, not valid)
                ok = ok and valid
        return ok
```

3f. `collect()` gates the auth on `is_skipped()` already — unchanged. The
`today = date.today()` deletion in 3a may leave the `date` import used only
by `collect()`/`_add_avail_row` — it is still used there; keep the import.

- [ ] **Step 4: Run to verify pass, then neighbors + full suite**

Run: `python -m pytest tests/test_explicit_auth_entry.py -v`
Expected: 15 passed
Run: `python -m pytest tests/test_plan_type.py tests/test_default_availability.py -q`
Expected: all pass (`test_default_availability` builds an untouched StepAuths — still skipped; the two wizard plan-type tests check a day and call `collect()`, which is unchanged)
Run: `python -m pytest -q`
Expected: full suite passes (667 = 652 + 15)

- [ ] **Step 5: Commit**

```bash
git add gui/wizard/step_auths.py tests/test_explicit_auth_entry.py
git commit -m "feat: wizard auth step — empty dates, started-must-finish validation"
```

---

### Task 4: Full verification

- [ ] **Step 1:** `python -m pytest -q` → all pass (expect 667).
- [ ] **Step 2:** Manual smoke test in the app: Auths tab → Add Authorization opens fully blank (except Member ID); OK lists every missing field and outlines them red; filling everything saves; Edit on an old auth with blank Plan Type/Auth Number still saves untouched. Wizard: leaving the auth panel untouched skips it; typing only a date then Next flags the rest instead of silently dropping it.
- [ ] **Step 3:** Use the superpowers:finishing-a-development-branch skill.

---

## Self-Review (done at plan time)

- **Spec coverage:** empty dates + blank combos + required set (Task 2), edit exemption (Task 2 `on_accept` split + `test_edit_mode_exempt...`), wizard empty dates / skip rule / strict validate / warning text (Task 3), error-clear affordances both places, transport panel untouched, overlap flow untouched.
- **Placeholder scan:** none.
- **Type consistency:** `missing_new_auth_fields` keyword names match both call sites; `set_widget_error(widget, bool)` matches `gui/address_autocomplete.py:64`; dialog result-dict keys unchanged from today's contract.
