# Expired-Authorization Warning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show an `⚠ Authorization Expired` warning on a member's profile when they have authorization(s) but none is currently valid, and remove the Availability warning entirely.

**Architecture:** Extract the warning decision into a pure module-level function `auth_warning(authorizations, today)` in `gui/member_tabs.py` (unit-testable without Qt). `MemberTabsWidget._build_ui` calls it for the header badge and the Auths tab label; the availability-warning branch and the `_missing()` method are removed.

**Tech Stack:** Python 3.11, PyQt6, pytest. No new dependencies.

---

## File Map

```
gui/member_tabs.py          modify — add auth_warning(); rewire _build_ui; remove _missing()
tests/test_auth_warning.py  create — pure-function unit tests
```

---

## Task 1: `auth_warning` pure function (TDD)

**Files:**
- Create: `tests/test_auth_warning.py`
- Modify: `gui/member_tabs.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_auth_warning.py`:

```python
from datetime import date

from gui.member_tabs import auth_warning

TODAY = date(2026, 6, 5)


def test_no_authorizations_is_missing():
    assert auth_warning([], TODAY) == "Missing: Authorizations"


def test_single_expired_auth():
    auths = [{"auth_end": date(2026, 6, 4)}]
    assert auth_warning(auths, TODAY) == "Authorization Expired"


def test_auth_ending_today_is_valid():
    auths = [{"auth_end": date(2026, 6, 5)}]
    assert auth_warning(auths, TODAY) is None


def test_auth_ending_tomorrow_is_valid():
    auths = [{"auth_end": date(2026, 6, 6)}]
    assert auth_warning(auths, TODAY) is None


def test_mix_expired_and_valid_is_none():
    auths = [{"auth_end": date(2025, 1, 1)}, {"auth_end": date(2026, 12, 31)}]
    assert auth_warning(auths, TODAY) is None


def test_null_end_date_is_not_expired():
    auths = [{"auth_end": None}]
    assert auth_warning(auths, TODAY) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\pytest tests/test_auth_warning.py -v`
Expected: FAIL with `ImportError` / `cannot import name 'auth_warning'`.

- [ ] **Step 3: Implement the function**

In `gui/member_tabs.py`, add this module-level function immediately after
`format_auth_days` (which ends at line 62, before `def _normalize_value`):

```python
def auth_warning(authorizations: list, today) -> str | None:
    """Warning label for a member's authorization state, or None.

    - "Missing: Authorizations" when there are no authorizations.
    - "Authorization Expired" when there are authorizations but none is
      currently valid (the latest end date is before today).
    - None when a currently-valid authorization exists.

    An end date equal to today is still valid; null end dates are open-ended
    and never count as expired.
    """
    if not authorizations:
        return "Missing: Authorizations"
    ends = [a["auth_end"] for a in authorizations if a.get("auth_end")]
    if ends and max(ends) < today:
        return "Authorization Expired"
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\pytest tests/test_auth_warning.py -v`
Expected: all 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_auth_warning.py gui/member_tabs.py
git commit -m "feat: add auth_warning helper for expired/missing authorizations"
```
End the commit message with a blank line then:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Task 2: Wire the warning into the profile UI

**Files:**
- Modify: `gui/member_tabs.py`

- [ ] **Step 1: Replace the badge computation in `_build_ui`**

The current header-badge block is:

```python
        top_row.addWidget(name_label)
        top_row.addStretch()
        missing = self._missing()
        if missing:
            badge = QLabel("⚠ Missing: " + ", ".join(missing))
            badge.setObjectName("warning_badge")
            badge.setMaximumHeight(26)
            top_row.addWidget(badge, alignment=Qt.AlignmentFlag.AlignVCenter)
        right.addLayout(top_row)
```

Replace it with (compute the warning once; the badge text is `"⚠ " + warn`):

```python
        top_row.addWidget(name_label)
        top_row.addStretch()
        from datetime import date
        warn = auth_warning(self._authorizations, date.today())
        if warn:
            badge = QLabel("⚠ " + warn)
            badge.setObjectName("warning_badge")
            badge.setMaximumHeight(26)
            top_row.addWidget(badge, alignment=Qt.AlignmentFlag.AlignVCenter)
        right.addLayout(top_row)
```

- [ ] **Step 2: Update the tab labels**

The current tab-add block is:

```python
        self._tabs.addTab(self._tab_info, "Info")
        self._tabs.addTab(self._tab_enrollments, "Enrollments")
        self._tabs.addTab(self._tab_auths,
            "Auths ⚠" if "Authorizations" in missing else "Authorizations")
        self._tabs.addTab(self._tab_avail,
            "Availability ⚠" if "Availability" in missing else "Availability")
        self._tabs.addTab(self._tab_absences, "Absences")
```

Replace it with (Auths marked when `warn` is set; Availability never marked):

```python
        self._tabs.addTab(self._tab_info, "Info")
        self._tabs.addTab(self._tab_enrollments, "Enrollments")
        self._tabs.addTab(self._tab_auths,
            "Auths ⚠" if warn else "Authorizations")
        self._tabs.addTab(self._tab_avail, "Availability")
        self._tabs.addTab(self._tab_absences, "Absences")
```

- [ ] **Step 3: Remove the now-unused `_missing()` method**

Delete the whole method (currently lines 203-209):

```python
    def _missing(self) -> list[str]:
        missing = []
        if not self._authorizations:
            missing.append("Authorizations")
        if not self._availability:
            missing.append("Availability")
        return missing
```

(Confirm with a grep that `_missing` has no other callers before deleting — it
should appear only at its definition and the `_build_ui` call you just removed.)

- [ ] **Step 4: Verify the module imports and grep for stragglers**

Run: `.venv\Scripts\python -c "from gui.member_tabs import MemberTabsWidget, auth_warning; print('OK')"`
Expected: `OK`

Grep `gui/member_tabs.py` for `_missing` → no matches. Grep for
`Availability ⚠` → no matches.

- [ ] **Step 5: Run the full suite**

Run: `.venv\Scripts\pytest -q`
Expected: all pass (prior 92 + the 6 new auth_warning tests).

- [ ] **Step 6: Commit**

```bash
git add gui/member_tabs.py
git commit -m "feat: show 'Authorization Expired' badge; drop availability warning"
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

Stop any running instance (it locks the output file), then build:

```
powershell -Command "try { Stop-Process -Name MemberManager -Force -ErrorAction Stop } catch {}"
.venv\Scripts\pyinstaller MemberManager.spec
```

Expected: `Build complete! The results are available in: ...\dist`

- [ ] **Step 3: Manual smoke test**

Launch `dist\MemberManager.exe`:
- A member whose latest authorization ended before today shows the header badge
  `⚠ Authorization Expired` and the tab `Auths ⚠`.
- A member with a currently-valid authorization shows **no** badge and the tab
  `Authorizations`.
- A member with no authorizations shows `⚠ Missing: Authorizations` and `Auths ⚠`
  (unchanged behavior).
- **No** member shows any availability warning: the badge never mentions
  Availability, and the tab is always `Availability` (never `Availability ⚠`),
  even for a member with no availability rows.

---

## Self-Review Notes

- **Spec coverage:** `auth_warning` three-state logic → Task 1. Badge + Auths tab
  wiring and availability-warning removal → Task 2. `_missing()` removed → Task 2
  Step 3. Boundary (`auth_end == today` valid) and null-end handling → Task 1
  tests `test_auth_ending_today_is_valid` and `test_null_end_date_is_not_expired`.
  Suite/exe/manual → Task 3.
- **Type consistency:** `auth_warning(authorizations, today) -> str | None`; called
  as `auth_warning(self._authorizations, date.today())`; badge text `"⚠ " + warn`;
  Auths tab `"Auths ⚠" if warn else "Authorizations"`. `self._authorizations` is
  the existing list of auth dicts (each with a `auth_end` `date`).
- **No placeholders:** every step shows full code and exact commands with expected
  output.
