# Enrollment End Default + Per-Insurer Pill Colors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** (A) Make the optional Enrollment End field show "Ongoing (leave blank)" by default instead of a stray date, in both the wizard and the Enrollments-tab add dialog. (B) Color-code the header health-plan pill per insurer.

**Architecture:** (A) Set the `QDateEdit` minimum to the sentinel so `setSpecialValueText` renders. (B) A `PLAN_COLORS` map in `gui/theme.py` drives per-plan `QLabel#plan_badge[plan="<code>"]` QSS rules generated in `build_qss`; the header sets a `plan` dynamic property on the badge.

**Tech Stack:** Python 3.11, PyQt6, pytest (offscreen `qapp`). No new dependencies.

---

## File Map

```
gui/wizard/step_enrollment.py     modify — set minimum date (Part A)
gui/member_tabs.py                modify — set minimum date in _add_enrollment (A);
                                           set plan property on badge (B)
gui/theme.py                      modify — PLAN_COLORS + per-plan QSS rules (B)
tests/test_step_enrollment.py     create — wizard end-date default test (A)
tests/test_health_plan_badge.py   modify — per-plan color tests (B)
```

---

## Task 1: Part A — Enrollment End default = "Ongoing"

**Files:**
- Create: `tests/test_step_enrollment.py`
- Modify: `gui/wizard/step_enrollment.py`, `gui/member_tabs.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_step_enrollment.py`:

```python
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QDate


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_end_date_minimum_is_sentinel(qapp):
    from gui.wizard.step_enrollment import StepEnrollment
    w = StepEnrollment()
    assert w.end_date.minimumDate() == QDate(2000, 1, 1)
    assert w.end_date.specialValueText() == "Ongoing (leave blank)"


def test_collect_end_none_by_default(qapp):
    from gui.wizard.step_enrollment import StepEnrollment
    w = StepEnrollment()
    assert w.collect()["enrollment_end"] is None
```

- [ ] **Step 2: Run to verify the first test fails**

Run: `.venv\Scripts\pytest tests/test_step_enrollment.py -v`
Expected: `test_end_date_minimum_is_sentinel` FAILS (minimumDate is Qt's default
`1752-09-14`, not the sentinel). `test_collect_end_none_by_default` may already pass.

- [ ] **Step 3: Fix the wizard field**

In `gui/wizard/step_enrollment.py`, the current block (lines 18-21):

```python
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setSpecialValueText("Ongoing (leave blank)")
        self.end_date.setDate(QDate(2000, 1, 1))
```

Replace with (add the `setMinimumDate` line first):

```python
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setMinimumDate(QDate(2000, 1, 1))
        self.end_date.setSpecialValueText("Ongoing (leave blank)")
        self.end_date.setDate(QDate(2000, 1, 1))
```

- [ ] **Step 4: Fix the Enrollments-tab add dialog**

In `gui/member_tabs.py` `_add_enrollment`, the current block (lines 728-731):

```python
        end = QDateEdit()
        end.setCalendarPopup(True)
        end.setSpecialValueText("Ongoing")
        end.setDate(QDate(2000, 1, 1))
```

Replace with:

```python
        end = QDateEdit()
        end.setCalendarPopup(True)
        end.setMinimumDate(QDate(2000, 1, 1))
        end.setSpecialValueText("Ongoing")
        end.setDate(QDate(2000, 1, 1))
```

(The `collect()` / sentinel→`None` logic in both places is unchanged.)

- [ ] **Step 5: Run the test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_step_enrollment.py -v`
Expected: both PASS.

- [ ] **Step 6: Verify member_tabs imports**

Run: `.venv\Scripts\python -c "from gui.member_tabs import MemberTabsWidget; print('OK')"`
Expected: `OK`

- [ ] **Step 7: Commit**

```bash
git add gui/wizard/step_enrollment.py gui/member_tabs.py tests/test_step_enrollment.py
git commit -m "fix: enrollment end date defaults to 'Ongoing' instead of a stray date"
```
End the commit message with a blank line then:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Task 2: Part B — Per-insurer pill colors

**Files:**
- Modify: `gui/theme.py`, `gui/member_tabs.py`, `tests/test_health_plan_badge.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_health_plan_badge.py`:

```python
def test_plan_colors_cover_all_health_plans():
    from gui.theme import PLAN_COLORS
    from db.members import HEALTH_PLANS
    assert set(HEALTH_PLANS) <= set(PLAN_COLORS)


def test_theme_has_per_plan_rules():
    from gui.theme import build_qss, DARK, LIGHT
    from db.members import HEALTH_PLANS
    for tokens in (DARK, LIGHT):
        qss = build_qss(tokens)
        for code in HEALTH_PLANS:
            assert f'[plan="{code}"]' in qss
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv\Scripts\pytest tests/test_health_plan_badge.py -v`
Expected: the two new tests FAIL (`cannot import name 'PLAN_COLORS'`).

- [ ] **Step 3: Add the `PLAN_COLORS` map**

In `gui/theme.py`, add a module-level constant after the `LIGHT = {...}` dict
(before `def build_qss`):

```python
# Brand-approximate pill colors, one per health plan (see HEALTH_PLANS).
# Solid background with near-white text; theme-independent by design.
PLAN_COLORS = {
    "Aetna": "#7d3f98",
    "Anthem": "#1a9dd9",
    "BCBS": "#0033a0",
    "HF": "#e07b1a",
    "VCM": "#5c9e31",
    "AE": "#2bb3a3",
    "ES": "#c0392b",
    "HC": "#b8860b",
    "HOF": "#c0507e",
}
```

- [ ] **Step 4: Generate per-plan rules in `build_qss`**

In `gui/theme.py`, change `build_qss` to build the rules string before the return.
The function currently is:

```python
def build_qss(t: dict) -> str:
    return f"""
QMainWindow, QDialog, QWidget {{
```

Replace those two lines with:

```python
def build_qss(t: dict) -> str:
    plan_rules = "\n".join(
        f'QLabel#plan_badge[plan="{code}"] {{ background-color: {color}; '
        f'color: #f4f6fd; border: 1px solid {color}; }}'
        for code, color in PLAN_COLORS.items()
    )
    return f"""
QMainWindow, QDialog, QWidget {{
```

Then, inside the returned f-string, immediately after the `QLabel#plan_badge {{ ... }}`
block (which ends with its `}}` around line 296, before `QLabel#wizard_warning`),
add a line that interpolates the generated rules:

```python
}}
{plan_rules}
QLabel#wizard_warning {{
```

(The `{{ }}` inside the `plan_rules` f-string produce literal braces; `{code}` and
`{color}` interpolate. The base `QLabel#plan_badge` rule stays as the fallback for
blank/unknown plans.)

- [ ] **Step 5: Set the `plan` property on the header badge**

In `gui/member_tabs.py` `_build_ui`, the current badge block is:

```python
        if plan:
            plan_badge = QLabel(plan)
            plan_badge.setObjectName("plan_badge")
            plan_badge.setToolTip("Health Plan")
            plan_badge.setMaximumHeight(26)
            top_row.addWidget(plan_badge, alignment=Qt.AlignmentFlag.AlignVCenter)
```

Add the `setProperty` line right after `setObjectName`:

```python
        if plan:
            plan_badge = QLabel(plan)
            plan_badge.setObjectName("plan_badge")
            plan_badge.setProperty("plan", plan)
            plan_badge.setToolTip("Health Plan")
            plan_badge.setMaximumHeight(26)
            top_row.addWidget(plan_badge, alignment=Qt.AlignmentFlag.AlignVCenter)
```

- [ ] **Step 6: Run the tests + verify imports**

Run: `.venv\Scripts\pytest tests/test_health_plan_badge.py -v`
Expected: all PASS (including the two new ones).

Run: `.venv\Scripts\python -c "from gui.theme import build_qss, DARK, PLAN_COLORS; build_qss(DARK); from gui.member_tabs import MemberTabsWidget; print('OK')"`
Expected: `OK` (confirms the f-string renders without a brace error).

- [ ] **Step 7: Run the full suite**

Run: `.venv\Scripts\pytest -q`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add gui/theme.py gui/member_tabs.py tests/test_health_plan_badge.py
git commit -m "feat: color-code the health plan pill per insurer"
```
End with a blank line then:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Task 3: Full suite + exe rebuild + manual smoke test

**Files:** none changed

- [ ] **Step 1: Run the full test suite**

Run: `.venv\Scripts\pytest -q`
Expected: all pass.

- [ ] **Step 2: Rebuild the exe**

```
powershell -Command "try { Stop-Process -Name MemberManager -Force -ErrorAction Stop } catch {}"
.venv\Scripts\pyinstaller MemberManager.spec
```
Expected: `Build complete! ... dist`

- [ ] **Step 3: Manual smoke test**

Launch `dist\MemberManager.exe`:
- **Add New Member → Enrollment:** the End field shows **"Ongoing (leave blank)"**
  by default (no `1/1/2001`); leaving it blank creates an ongoing enrollment.
  Same in a member's **Enrollments → + Add** dialog ("Ongoing").
- **Header pill:** open members on different plans (e.g. Aetna, HF, BCBS) → each
  shows its brand color; a blank-plan member shows no pill; an unknown plan shows the
  default accent pill.
- Toggle light/dark theme — the pill colors hold.

---

## Self-Review Notes

- **Spec coverage:** Part A wizard + tab `setMinimumDate` and the "Ongoing" display →
  Task 1 (with a wizard test). Part B `PLAN_COLORS`, per-plan `build_qss` rules, and
  the header `plan` property → Task 2 (with coverage + selector tests).
  Suite/exe/manual → Task 3.
- **Type consistency:** `PLAN_COLORS: dict[str, str]` keyed by the `HEALTH_PLANS`
  codes; selector form `QLabel#plan_badge[plan="<code>"]` matches the
  `setProperty("plan", plan)` value; near-white text `#f4f6fd`. Sentinel date
  `QDate(2000, 1, 1)` is used for minimum, special-value, and the collect() check in
  both enrollment dialogs.
- **No placeholders:** every step has full code and exact commands/expected output.
  The display fix is anchored by the `minimumDate` assertion (fails pre-fix); the
  enrollment-tab dialog and the rendered pill colors are verified manually.
