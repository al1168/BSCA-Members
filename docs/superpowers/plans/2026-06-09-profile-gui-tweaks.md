# Member-Profile GUI Tweaks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rearrange Info-tab fields (SSN→Identity, Member ID→Medical, Enrollment Start→Identity), relabel Language→"Language Spoken" and the Availability tab→"Time Slot Availability", make the Notes band more obvious, and sort the Authorizations table by latest end date first.

**Architecture:** All in `gui/member_tabs.py` (grid cell moves, label text, a pure `sort_auths_latest_first` helper) plus object-named Notes QSS in `gui/theme.py`. An `/impeccable` pass finalizes the Notes look.

**Tech Stack:** Python 3.11, PyQt6, pytest. No new dependencies.

---

## File Map

```
gui/member_tabs.py        modify — auth sort helper + use; Info-tab cell moves;
                                   Language/Availability relabels; Notes object names
gui/theme.py              modify — QSS for #notes_label / #notes_edit
tests/test_auth_sort.py   create — sort_auths_latest_first unit tests
tests/test_terminated.py  (no change)   # example of existing theme-test style
```

---

## Task 1: Authorizations sort — latest end first (TDD)

**Files:**
- Create: `tests/test_auth_sort.py`
- Modify: `gui/member_tabs.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_auth_sort.py`:

```python
from datetime import date

from gui.member_tabs import sort_auths_latest_first


def test_sort_latest_end_first():
    auths = [
        {"id": 1, "auth_end": date(2025, 1, 1)},
        {"id": 2, "auth_end": date(2026, 12, 31)},
        {"id": 3, "auth_end": date(2025, 6, 1)},
    ]
    assert [a["id"] for a in sort_auths_latest_first(auths)] == [2, 3, 1]


def test_sort_none_end_last():
    auths = [{"id": 1, "auth_end": None}, {"id": 2, "auth_end": date(2025, 1, 1)}]
    assert [a["id"] for a in sort_auths_latest_first(auths)] == [2, 1]


def test_sort_does_not_mutate_input():
    auths = [{"id": 1, "auth_end": date(2025, 1, 1)},
             {"id": 2, "auth_end": date(2026, 1, 1)}]
    snapshot = list(auths)
    sort_auths_latest_first(auths)
    assert auths == snapshot
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv\Scripts\pytest tests/test_auth_sort.py -v`
Expected: FAIL (`cannot import name 'sort_auths_latest_first'`).

- [ ] **Step 3: Add the helper**

In `gui/member_tabs.py`, add at module scope among the other module-level helpers
(e.g. after `to_jpeg_bytes`, before `class MemberTabsWidget`):

```python
def sort_auths_latest_first(auths: list[dict]) -> list[dict]:
    """Authorizations ordered by end date, latest first. Missing end dates sort
    last. Returns a new list (does not mutate the input)."""
    from datetime import date
    return sorted(auths, key=lambda a: a.get("auth_end") or date.min, reverse=True)
```

- [ ] **Step 4: Use it in `_make_auths_tab`**

The current loop start (around line 907-909) is:

```python
        latest = latest_authorization(self._authorizations)
        latest_id = latest["id"] if latest else None
        for r, a in enumerate(self._authorizations):
```

Replace the `for` line so it iterates the sorted list (keep the two `latest` lines
as-is — they match by id):

```python
        latest = latest_authorization(self._authorizations)
        latest_id = latest["id"] if latest else None
        for r, a in enumerate(sort_auths_latest_first(self._authorizations)):
```

- [ ] **Step 5: Run tests + verify import**

Run: `.venv\Scripts\pytest tests/test_auth_sort.py -v` → 3 PASS.
Run: `.venv\Scripts\python -c "from gui.member_tabs import MemberTabsWidget, sort_auths_latest_first; print('OK')"` → `OK`.

- [ ] **Step 6: Commit**

```bash
git add gui/member_tabs.py tests/test_auth_sort.py
git commit -m "feat: sort authorizations with the latest end date on top"
```
End the commit message with a blank line then:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Task 2: Info-tab field moves + Language / Availability relabels

**Files:**
- Modify: `gui/member_tabs.py`

- [ ] **Step 1: Drop Enrollment Start from the Schedule section**

The current Schedule block is:

```python
        section("Schedule")
        cell(0, "Enrollment Start", enroll_lbl)
        state["row"] += 1
        cell(0, "Authorized Days", WeekdayChips(active_days), wspan=3)
        state["row"] += 1
        cell(0, "Auth Period", auth_period_lbl, wspan=2)
        state["row"] += 1
```

Replace with (remove the Enrollment Start cell + its `state["row"] += 1`):

```python
        section("Schedule")
        cell(0, "Authorized Days", WeekdayChips(active_days), wspan=3)
        state["row"] += 1
        cell(0, "Auth Period", auth_period_lbl, wspan=2)
        state["row"] += 1
```

- [ ] **Step 2: Identity — add SSN + Enrollment Start, remove Member ID**

The current Identity block is:

```python
        section("Identity")
        cell(0, "First Name", self._info_first)
        cell(1, "Last Name", self._info_last)
        cell(2, "Chinese Name", self._info_chinese)
        state["row"] += 1
        cell(0, "Gender", self._info_gender)
        cell(1, "DOB", self._info_dob)
        cell(2, "Member ID", self._info_member_id)
        state["row"] += 1
        cell(0, "Center ID", self._info_cid)
        state["row"] += 1
```

Replace with:

```python
        section("Identity")
        cell(0, "First Name", self._info_first)
        cell(1, "Last Name", self._info_last)
        cell(2, "Chinese Name", self._info_chinese)
        state["row"] += 1
        cell(0, "Gender", self._info_gender)
        cell(1, "DOB", self._info_dob)
        cell(2, "SSN", self._info_ssn)
        state["row"] += 1
        cell(0, "Center ID", self._info_cid)
        cell(1, "Enrollment Start", enroll_lbl)
        state["row"] += 1
```

- [ ] **Step 3: Medical — add Member ID beside Health Plan, remove SSN, relabel Language**

The current Medical block is:

```python
        section("Medical")
        cell(0, "Health Plan", self._info_plan)
        cell(1, "Medicaid", self._info_medicaid)
        cell(2, "Medicare", self._info_medicare)
        state["row"] += 1
        cell(0, "SSN", self._info_ssn)
        cell(1, "PCP", self._info_pcp)
        cell(2, "Hospital", self._info_hospital)
        state["row"] += 1
        cell(0, "HHA", self._info_hha)
        cell(1, "Language", self._info_language)
        state["row"] += 1
```

Replace with:

```python
        section("Medical")
        cell(0, "Health Plan", self._info_plan)
        cell(1, "Member ID", self._info_member_id)
        cell(2, "Medicaid", self._info_medicaid)
        state["row"] += 1
        cell(0, "Medicare", self._info_medicare)
        cell(1, "PCP", self._info_pcp)
        cell(2, "Hospital", self._info_hospital)
        state["row"] += 1
        cell(0, "HHA", self._info_hha)
        cell(1, "Language Spoken", self._info_language)
        state["row"] += 1
```

- [ ] **Step 4: Update `FIELD_LABELS["language"]`**

In the `FIELD_LABELS` dict (around line 46), change:

```python
    "ssn": "SSN", "language": "Language", "case_manager": "Case Manager",
```
to:
```python
    "ssn": "SSN", "language": "Language Spoken", "case_manager": "Case Manager",
```

- [ ] **Step 5: Rename the Availability tab**

In `_build_ui`, change (around line 413):

```python
        self._tabs.addTab(self._tab_avail, "Availability")
```
to:
```python
        self._tabs.addTab(self._tab_avail, "Time Slot Availability")
```

- [ ] **Step 6: Verify import + run the suite**

Run: `.venv\Scripts\python -c "from gui.member_tabs import MemberTabsWidget; print('OK')"` → `OK`.
Run: `.venv\Scripts\pytest -q` → all pass.

- [ ] **Step 7: Commit**

```bash
git add gui/member_tabs.py
git commit -m "feat: rearrange Info fields; rename Language Spoken + Time Slot Availability"
```
End with a blank line then:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Task 3: Notes band — object names + baseline QSS (TDD theme test)

**Files:**
- Modify: `gui/member_tabs.py`, `gui/theme.py`, `tests/test_auth_sort.py`

- [ ] **Step 1: Write the failing theme test**

Append to `tests/test_auth_sort.py`:

```python
def test_theme_has_notes_styles():
    from gui.theme import build_qss, DARK, LIGHT
    for tokens in (DARK, LIGHT):
        qss = build_qss(tokens)
        assert "notes_label" in qss
        assert "notes_edit" in qss
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv\Scripts\pytest tests/test_auth_sort.py::test_theme_has_notes_styles -v`
Expected: FAIL.

- [ ] **Step 3: Set object names on the Notes widgets**

In `_build_ui`, the current Notes band (around lines 387-391) is:

```python
        notes_lbl = QLabel("Notes")
        notes_lbl.setObjectName("field_label")
        notes_row.addWidget(notes_lbl, alignment=Qt.AlignmentFlag.AlignTop)
        self._info_notes = _NotesEdit()
        self._info_notes.setPlainText(self._member.get("notes", "") or "")
```

Replace with (rename the label's object name; name the editor):

```python
        notes_lbl = QLabel("Notes")
        notes_lbl.setObjectName("notes_label")
        notes_row.addWidget(notes_lbl, alignment=Qt.AlignmentFlag.AlignTop)
        self._info_notes = _NotesEdit()
        self._info_notes.setObjectName("notes_edit")
        self._info_notes.setPlainText(self._member.get("notes", "") or "")
```

- [ ] **Step 4: Add the baseline QSS**

In `gui/theme.py`, inside `build_qss(t)`, immediately AFTER the
`QLabel#field_label {{ ... }}` block, add:

```python
QLabel#notes_label {{
    color: {t['accent_text']};
    font-size: 11px;
    font-weight: 700;
}}
QTextEdit#notes_edit {{
    border: 1px solid {t['accent']};
    border-radius: 6px;
}}
```

(Baseline — Task 4's `/impeccable` pass refines it.)

- [ ] **Step 5: Run the test + verify**

Run: `.venv\Scripts\pytest tests/test_auth_sort.py -v` → all PASS.
Run: `.venv\Scripts\python -c "from gui.theme import build_qss, DARK; build_qss(DARK); from gui.member_tabs import MemberTabsWidget; print('OK')"` → `OK`.

- [ ] **Step 6: Run the full suite**

Run: `.venv\Scripts\pytest -q` → all pass.

- [ ] **Step 7: Commit**

```bash
git add gui/member_tabs.py gui/theme.py tests/test_auth_sort.py
git commit -m "feat: make the Notes band stand out (accent label + bordered editor)"
```
End with a blank line then:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Task 4: `/impeccable` pass on the Notes band

**Files:** likely `gui/theme.py` (and possibly `gui/member_tabs.py`)

> Main-session step run by the controller (design judgment), not a delegated
> subagent.

- [ ] **Step 1: Run impeccable**

Invoke the `impeccable` skill (product register, restrained) targeting the Notes
band: the `#notes_label` / `#notes_edit` QSS in `gui/theme.py` (and the Notes widgets
in `gui/member_tabs.py` if needed). Decide the final treatment — keep the accent
label + border, or switch to a faint tinted background, label-only, or
border-only — using only existing theme tokens, in both DARK and LIGHT. Keep the
object names `notes_label` / `notes_edit` (the test asserts them) and don't change
the Notes save/dirty behavior.

- [ ] **Step 2: Re-run the suite + commit**

Run: `.venv\Scripts\pytest -q` → all pass (object-name test still valid).

```bash
git add gui/theme.py gui/member_tabs.py
git commit -m "style: polish the Notes band (impeccable pass)"
```
End with a blank line then:
`Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`

---

## Task 5: Full suite + exe rebuild + manual smoke test

**Files:** none changed

- [ ] **Step 1: Run the full test suite**

Run: `.venv\Scripts\pytest -q` → all pass.

- [ ] **Step 2: Rebuild the exe**

```
powershell -Command "try { Stop-Process -Name MemberManager -Force -ErrorAction Stop } catch {}"
.venv\Scripts\pyinstaller MemberManager.spec
```
Expected: `Build complete! ... dist`

- [ ] **Step 3: Manual smoke test**

Launch `dist\MemberManager.exe`, open a member, Info tab:
- **Identity** now shows SSN (next to DOB) and Enrollment Start (next to Center ID);
  Member ID is gone from Identity.
- **Medical** shows Member ID beside Health Plan; SSN is gone from Medical; the
  language field reads **"Language Spoken"**.
- Editing SSN / Member ID / Language Spoken still saves; the Events log shows
  "Language Spoken: …" for a language edit.
- The **Time Slot Availability** tab (renamed) still adds/edits/deletes normally.
- The **Notes** band reads as clearly emphasized (the impeccable result), in both
  light and dark.
- The **Authorizations** tab lists rows with the latest end date on top; the Edit
  button is still on the most recent authorization.

---

## Self-Review Notes

- **Spec coverage:** auth sort by `auth_end` desc → Task 1. SSN→Identity,
  Member ID→Medical, Enrollment Start→Identity, Language Spoken label +
  FIELD_LABELS, Time Slot Availability tab → Task 2. Notes object names + baseline
  QSS → Task 3; impeccable finalization → Task 4. Suite/exe/manual → Task 5.
- **Type consistency:** `sort_auths_latest_first(list[dict]) -> list[dict]` keyed on
  `auth_end`; object names `notes_label` / `notes_edit` match the QSS selectors and
  the theme test; widget attribute names (`self._info_ssn`, `_info_member_id`,
  `_info_language`, `enroll_lbl`) are unchanged, so save/collect still work.
- **No placeholders:** every step has full code and exact commands/expected output.
  The baseline Notes QSS is a working value refined by Task 4; the field moves and
  relabels are verified manually.
