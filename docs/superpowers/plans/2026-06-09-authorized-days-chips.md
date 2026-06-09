# Authorized-Days Weekday Chips Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the text-only authorized-days display with a row of seven weekday chips (authorized = filled accent, rest dimmed), move the Schedule section to the top of the Info tab, and use the chips in both the Info tab and the Authorizations tab.

**Architecture:** A pure `decode_auth_days(str) -> set[int]` helper feeds a reusable presentational `WeekdayChips(QWidget)`. Both live in `gui/member_tabs.py`; chip appearance is themed via object-named QSS in `gui/theme.py`. `_make_info_tab` and `_make_auths_tab` decode the encoded `auth_days` and hand the set to `WeekdayChips`.

**Tech Stack:** Python 3.11, PyQt6, pytest (with an offscreen `qapp` fixture for widget tests). No new dependencies.

---

## File Map

```
gui/member_tabs.py          modify — decode_auth_days; refactor format_auth_days;
                                     WeekdayChips; Info tab (Schedule→top + chips);
                                     Auths tab (chips in Days column)
gui/theme.py                modify — QSS for #day_chip_on / #day_chip_off
tests/test_weekday_chips.py create — decode + format regression + widget tests
```

---

## Task 1: `decode_auth_days` helper + refactor `format_auth_days` (TDD)

**Files:**
- Create: `tests/test_weekday_chips.py`
- Modify: `gui/member_tabs.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_weekday_chips.py` with (the widget tests come in Task 2; start
with just the pure-function tests + the qapp fixture so the file is ready):

```python
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from gui.member_tabs import decode_auth_days, format_auth_days


def test_decode_basic():
    assert decode_auth_days("1,3,5") == {1, 3, 5}


def test_decode_empty():
    assert decode_auth_days("") == set()


def test_decode_tolerates_blank_tokens():
    assert decode_auth_days("2,,7, ") == {2, 7}


def test_decode_ignores_non_numeric():
    assert decode_auth_days("1,x,3") == {1, 3}


def test_format_auth_days_regression():
    assert format_auth_days("1,3,5") == "Mon Wed Fri"


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv\Scripts\pytest tests/test_weekday_chips.py -v`
Expected: FAIL with `ImportError: cannot import name 'decode_auth_days'`.

- [ ] **Step 3: Implement `decode_auth_days` and refactor `format_auth_days`**

In `gui/member_tabs.py`, the current function (lines 57-62) is:

```python
def format_auth_days(auth_days: str) -> str:
    """'1,3,6' -> 'Mon Wed Sat'. Unknown day numbers fall back to their digit."""
    if not auth_days:
        return ""
    days = sorted(int(x) for x in auth_days.split(",") if x.strip())
    return " ".join(WEEKDAY_NAMES.get(d, str(d)) for d in days)
```

Replace it with (add `decode_auth_days` ABOVE it so the refactor can use it):

```python
def decode_auth_days(auth_days: str) -> set[int]:
    """'1,3,5' -> {1, 3, 5}. Blank, whitespace-only, and non-numeric tokens are
    ignored so malformed data never raises."""
    days = set()
    for tok in (auth_days or "").split(","):
        tok = tok.strip()
        if tok.isdigit():
            days.add(int(tok))
    return days


def format_auth_days(auth_days: str) -> str:
    """'1,3,6' -> 'Mon Wed Sat'. Unknown day numbers fall back to their digit."""
    days = sorted(decode_auth_days(auth_days))
    return " ".join(WEEKDAY_NAMES.get(d, str(d)) for d in days)
```

- [ ] **Step 4: Run to verify they pass**

Run: `.venv\Scripts\pytest tests/test_weekday_chips.py -v`
Expected: the 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_weekday_chips.py gui/member_tabs.py
git commit -m "feat: add decode_auth_days helper; format_auth_days reuses it"
```
End the commit message with a blank line then:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Task 2: `WeekdayChips` widget + theme QSS (TDD)

**Files:**
- Modify: `tests/test_weekday_chips.py`, `gui/member_tabs.py`, `gui/theme.py`

- [ ] **Step 1: Write the failing widget tests**

Append to `tests/test_weekday_chips.py`:

```python
def test_weekday_chips_on_off(qapp):
    from gui.member_tabs import WeekdayChips
    w = WeekdayChips({1, 3, 5})
    names = [c.objectName() for c in w._chips]
    assert len(names) == 7
    assert names == [
        "day_chip_on", "day_chip_off", "day_chip_on",
        "day_chip_off", "day_chip_on", "day_chip_off", "day_chip_off",
    ]


def test_weekday_chips_all_off(qapp):
    from gui.member_tabs import WeekdayChips
    w = WeekdayChips(set())
    assert len(w._chips) == 7
    assert all(c.objectName() == "day_chip_off" for c in w._chips)


def test_weekday_chips_full_labels(qapp):
    from gui.member_tabs import WeekdayChips
    w = WeekdayChips({1})
    assert [c.text() for c in w._chips] == [
        "MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN",
    ]


def test_weekday_chips_compact_single_letter(qapp):
    from gui.member_tabs import WeekdayChips
    w = WeekdayChips({1, 2}, compact=True)
    assert [c.text() for c in w._chips] == ["M", "T", "W", "T", "F", "S", "S"]
    assert w._chips[0].objectName() == "day_chip_on"


def test_theme_has_chip_styles():
    from gui.theme import build_qss, DARK, LIGHT
    for tokens in (DARK, LIGHT):
        qss = build_qss(tokens)
        assert "QLabel#day_chip_on" in qss
        assert "QLabel#day_chip_off" in qss
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv\Scripts\pytest tests/test_weekday_chips.py -v`
Expected: the new tests FAIL (`cannot import name 'WeekdayChips'` / chip styles
missing).

- [ ] **Step 3: Implement `WeekdayChips`**

In `gui/member_tabs.py`, add this class AFTER the module-level helper functions
(after `build_change_summary`, which ends around line 89) and BEFORE the
`class MemberTabsWidget`. `QWidget`, `QHBoxLayout`, `QLabel` are already imported
at the top of the file (lines 1-4), and `Qt` at line 5:

```python
class WeekdayChips(QWidget):
    """A row of seven weekday chips, Mon→Sun. Authorized days are filled with the
    accent color (object name 'day_chip_on'); the rest are dimmed
    ('day_chip_off'). `compact=True` uses single-letter labels for table cells.
    Purely presentational — callers decode the encoded auth_days string with
    `decode_auth_days` and pass the resulting set in."""

    def __init__(self, days, compact: bool = False, parent=None):
        super().__init__(parent)
        self._days = set(days)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(3 if compact else 4)
        row.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._chips = []
        for num in range(1, 8):
            name = WEEKDAY_NAMES[num]
            chip = QLabel(name[0] if compact else name.upper())
            chip.setObjectName("day_chip_on" if num in self._days else "day_chip_off")
            chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._chips.append(chip)
            row.addWidget(chip)
        row.addStretch()
```

- [ ] **Step 4: Add the chip QSS**

In `gui/theme.py`, inside the `build_qss(t)` f-string, add these two rules
immediately after the `QLabel#field_label {{ ... }}` block (around line 255,
before `QLabel#label_field`):

```python
QLabel#day_chip_on {{
    background-color: {t['accent']};
    color: #ffffff;
    border: none;
    border-radius: 9px;
    padding: 2px 9px;
    font-size: 10px;
    font-weight: 700;
}}
QLabel#day_chip_off {{
    background-color: transparent;
    color: {t['text3']};
    border: 1px solid {t['border']};
    border-radius: 9px;
    padding: 2px 9px;
    font-size: 10px;
    font-weight: 500;
}}
```

(These are baseline values; the `/impeccable polish` pass in Task 6 refines them.)

- [ ] **Step 5: Run to verify they pass**

Run: `.venv\Scripts\pytest tests/test_weekday_chips.py -v`
Expected: all tests PASS.

- [ ] **Step 6: Verify the module imports**

Run: `.venv\Scripts\python -c "from gui.member_tabs import WeekdayChips, decode_auth_days; print('OK')"`
Expected: `OK`

- [ ] **Step 7: Commit**

```bash
git add tests/test_weekday_chips.py gui/member_tabs.py gui/theme.py
git commit -m "feat: add WeekdayChips widget with themed on/off chip styles"
```
End with a blank line then:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Task 3: Info tab — Schedule to the top, with chips

**Files:**
- Modify: `gui/member_tabs.py`

- [ ] **Step 1: Replace the Active-Auth value build**

In `_make_info_tab`, the current block (lines 336-349) is:

```python
        enroll_start = self._enrollment_start(self._enrollments)
        enroll_lbl = QLineEdit(str(enroll_start) if enroll_start else "—")
        enroll_lbl.setReadOnly(True)
        active_auth = self._active_authorization(self._authorizations)
        if active_auth:
            days_str = format_auth_days(active_auth.get("auth_days", ""))
            plan = active_auth.get("health_plan", "")
            auth_text = (f"{active_auth['effective_start']} – "
                         f"{active_auth['effective_end']}  [{days_str}]"
                         + (f"  ·  {plan}" if plan else ""))
        else:
            auth_text = "None"
        auth_lbl = QLineEdit(auth_text)
        auth_lbl.setReadOnly(True)
```

Replace it with (compute the day set; build a quieter "Auth Period" line):

```python
        enroll_start = self._enrollment_start(self._enrollments)
        enroll_lbl = QLineEdit(str(enroll_start) if enroll_start else "—")
        enroll_lbl.setReadOnly(True)
        active_auth = self._active_authorization(self._authorizations)
        if active_auth:
            active_days = decode_auth_days(active_auth.get("auth_days", ""))
            plan = active_auth.get("health_plan", "")
            period_text = (f"{active_auth['effective_start']} – "
                           f"{active_auth['effective_end']}"
                           + (f"  ·  {plan}" if plan else ""))
        else:
            active_days = set()
            period_text = "None"
        auth_period_lbl = QLineEdit(period_text)
        auth_period_lbl.setReadOnly(True)
```

- [ ] **Step 2: Remove the Schedule section from the bottom**

Delete this block (currently lines 414-417):

```python
        section("Schedule")
        cell(0, "Enrollment Start", enroll_lbl)
        cell(1, "Active Auth", auth_lbl, wspan=2)
        state["row"] += 1
```

- [ ] **Step 3: Insert the new Schedule section at the top**

Immediately BEFORE the `section("Identity")` line (currently line 376), insert:

```python
        section("Schedule")
        cell(0, "Enrollment Start", enroll_lbl)
        state["row"] += 1
        cell(0, "Authorized Days", WeekdayChips(active_days), wspan=3)
        state["row"] += 1
        cell(0, "Auth Period", auth_period_lbl, wspan=2)
        state["row"] += 1

        section("Identity")
```

(So section order becomes Schedule → Identity → Contact → Medical → Care. The
`cell`/`section` helpers place by the running `state["row"]`, so moving the code
moves the rows.)

- [ ] **Step 4: Verify the module imports + grep**

Run: `.venv\Scripts\python -c "from gui.member_tabs import MemberTabsWidget; print('OK')"`
Expected: `OK`

Grep `gui/member_tabs.py` for `auth_lbl` → no matches (old variable fully gone).
Grep for `Active Auth` → no matches.

- [ ] **Step 5: Run the full suite**

Run: `.venv\Scripts\pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add gui/member_tabs.py
git commit -m "feat: Info tab shows Schedule first with an authorized-days chip track"
```
End with a blank line then:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Task 4: Authorizations tab — chips in the Days column

**Files:**
- Modify: `gui/member_tabs.py`

- [ ] **Step 1: Replace the Days cell with a compact `WeekdayChips`**

In `_make_auths_tab`, the current line (line 776) is:

```python
            table.setItem(r, 3, QTableWidgetItem(a["auth_days"] or ""))
```

Replace it with:

```python
            table.setCellWidget(r, 3, WeekdayChips(
                decode_auth_days(a["auth_days"] or ""), compact=True))
```

(`WeekdayChips` and `decode_auth_days` are module-level in this same file, so no
import is needed. Row height is already 34px at line 768, leaving room for the
chips.)

- [ ] **Step 2: Verify the module imports**

Run: `.venv\Scripts\python -c "from gui.member_tabs import MemberTabsWidget; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Run the full suite**

Run: `.venv\Scripts\pytest -q`
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add gui/member_tabs.py
git commit -m "feat: Authorizations tab Days column uses weekday chips"
```
End with a blank line then:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Task 5: Full suite + exe rebuild + manual smoke test

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

Launch `dist\MemberManager.exe` and open a member:
- The Info tab opens with **Schedule first** (above Identity): Enrollment Start, an
  **Authorized Days** weekday track (authorized days filled in the accent color,
  the rest dimmed), and a quieter **Auth Period** line with the dates · plan.
- The **Authorizations tab** Days column shows compact weekday chips per row
  (no more `1,3,5` text).
- A member with **no active authorization** shows an all-dim track and
  `Auth Period: None`.
- Toggle the theme (light/dark) — chips read correctly in both.

---

## Task 6: `/impeccable polish` pass on the chips

**Files:** likely `gui/theme.py` (and possibly `gui/member_tabs.py` WeekdayChips)

> This is a main-session step run by the controller (not a delegated subagent),
> because it is a design-judgment pass.

- [ ] **Step 1: Run impeccable polish**

Invoke the `impeccable` skill with `polish` targeting the weekday chips: the
`WeekdayChips` widget in `gui/member_tabs.py` and the `#day_chip_on` /
`#day_chip_off` QSS in `gui/theme.py`. Apply its refinements (radius, padding,
weight, spacing, on/off color contrast in both DARK and LIGHT) while keeping the
object-named-QSS structure and the existing theme tokens. Do not change the
widget's public interface (`WeekdayChips(days, compact=False)`) or the object
names the tests assert.

- [ ] **Step 2: Re-run the suite + rebuild**

Run: `.venv\Scripts\pytest -q` → all pass (object-name tests still valid).
Then rebuild the exe (stop instance first, `pyinstaller MemberManager.spec`) and
visually confirm the polished chips in both themes.

- [ ] **Step 3: Commit**

```bash
git add gui/theme.py gui/member_tabs.py
git commit -m "style: polish weekday chips (impeccable pass)"
```
End with a blank line then:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Self-Review Notes

- **Spec coverage:** `decode_auth_days` + `format_auth_days` refactor → Task 1.
  `WeekdayChips` (full + compact, on/off object names) and theme QSS → Task 2.
  Schedule moved to top + Authorized Days chip track + quiet Auth Period + no-auth
  all-dim → Task 3. Authorizations tab Days column chips → Task 4. Suite/exe/manual
  → Task 5. Impeccable polish → Task 6.
- **Type consistency:** `decode_auth_days(str) -> set[int]`;
  `WeekdayChips(days, compact=False, parent=None)` exposing `_chips` and `_days`;
  object names `day_chip_on` / `day_chip_off`; callers pass
  `decode_auth_days(...)` (a set) into `WeekdayChips`. The Info tab uses full
  chips, the Auths tab uses `compact=True`.
- **No placeholders:** every code step shows full code; commands list expected
  output. The baseline QSS numbers in Task 2 are intentionally refined by the
  Task 6 polish pass (not a placeholder — they are valid working values).
