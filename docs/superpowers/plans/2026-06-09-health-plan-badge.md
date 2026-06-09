# Health Plan Badge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show the member's health plan as an accent pill badge in the profile header, beside the name, on every tab.

**Architecture:** A new object-named QSS rule `QLabel#plan_badge` in `gui/theme.py` (themed for DARK and LIGHT via the accent tokens), plus a conditional badge `QLabel` added to the header top row in `gui/member_tabs.py._build_ui`. Display-only; the value comes from `self._member["health_plan"]`. Purely additive — the Medical field and the Auth Period `· HF` suffix are untouched.

**Tech Stack:** Python 3.11, PyQt6, pytest. No new dependencies.

---

## File Map

```
gui/theme.py                  modify — QSS rule for #plan_badge (DARK + LIGHT)
gui/member_tabs.py            modify — conditional plan badge in _build_ui header
tests/test_health_plan_badge.py create — theme QSS presence test
```

---

## Task 1: `plan_badge` theme style (TDD)

**Files:**
- Create: `tests/test_health_plan_badge.py`
- Modify: `gui/theme.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_health_plan_badge.py`:

```python
def test_theme_has_plan_badge_style():
    from gui.theme import build_qss, DARK, LIGHT
    for tokens in (DARK, LIGHT):
        qss = build_qss(tokens)
        assert "QLabel#plan_badge" in qss
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\pytest tests/test_health_plan_badge.py -v`
Expected: FAIL (`assert "QLabel#plan_badge" in qss`).

- [ ] **Step 3: Add the QSS rule**

In `gui/theme.py`, inside the `build_qss(t)` f-string, immediately AFTER the
`QLabel#warning_badge {{ ... }}` block (around line 261-269), add:

```python
QLabel#plan_badge {{
    background-color: {t['accent_bg']};
    color: {t['accent_text']};
    border: 1px solid {t['accent']};
    border-radius: 10px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 700;
}}
```

(Read the file first to confirm the `warning_badge` block location and keep the
doubled braces `{{ }}` valid in the f-string.)

- [ ] **Step 4: Run to verify it passes**

Run: `.venv\Scripts\pytest tests/test_health_plan_badge.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add gui/theme.py tests/test_health_plan_badge.py
git commit -m "feat: add plan_badge theme style for the health plan pill"
```
End the commit message with a blank line then:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Task 2: Health plan badge in the header

**Files:**
- Modify: `gui/member_tabs.py`

- [ ] **Step 1: Add the conditional badge to the header top row**

In `_build_ui`, the current block is:

```python
        top_row.addWidget(name_label)
        top_row.addStretch()
        from datetime import date
        warn = auth_warning(self._authorizations, date.today())
```

Replace it with (insert the plan badge between the name and the stretch):

```python
        top_row.addWidget(name_label)
        plan = self._member.get("health_plan", "")
        if plan:
            plan_badge = QLabel(plan)
            plan_badge.setObjectName("plan_badge")
            plan_badge.setToolTip("Health Plan")
            plan_badge.setMaximumHeight(26)
            top_row.addWidget(plan_badge, alignment=Qt.AlignmentFlag.AlignVCenter)
        top_row.addStretch()
        from datetime import date
        warn = auth_warning(self._authorizations, date.today())
```

(`QLabel` and `Qt` are already imported at the top of the file. The warning-badge
block after the stretch is unchanged.)

- [ ] **Step 2: Verify the module imports**

Run: `.venv\Scripts\python -c "from gui.member_tabs import MemberTabsWidget; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Run the full suite**

Run: `.venv\Scripts\pytest -q`
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add gui/member_tabs.py
git commit -m "feat: show health plan as an accent badge beside the member name"
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

Stop any running instance, then build:

```
powershell -Command "try { Stop-Process -Name MemberManager -Force -ErrorAction Stop } catch {}"
.venv\Scripts\pyinstaller MemberManager.spec
```

Expected: `Build complete! ... dist`

- [ ] **Step 3: Manual smoke test**

Launch `dist\MemberManager.exe`:
- Open a member with a health plan (e.g. `HF`) → an accent pill badge shows beside
  the name/ID in the header; it stays visible when switching tabs; hovering shows
  the "Health Plan" tooltip.
- Open a member with no health plan → no badge (header shows just name/ID).
- Confirm the Medical-section Health Plan field and the Auth Period `· HF` line are
  unchanged.
- Toggle light/dark theme — the badge reads correctly in both.

---

## Self-Review Notes

- **Spec coverage:** `plan_badge` QSS in DARK + LIGHT → Task 1. Conditional badge
  beside the name in the header → Task 2. Additive (Medical field + Auth Period
  suffix untouched) — no task changes them. Suite/exe/manual → Task 3.
- **Type consistency:** object name `plan_badge` (matches the QSS selector and the
  test); badge text from `self._member.get("health_plan", "")`; tooltip "Health
  Plan"; inserted before `top_row.addStretch()` so the warning badge stays right.
- **No placeholders:** every step has full code and exact commands/expected output.
  The header conditional is verified manually (constructing the widget needs a full
  member context); the QSS is unit-tested.
