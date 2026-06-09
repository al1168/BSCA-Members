# Enrollment End Default + Per-Insurer Pill Colors — Design Spec

**Date:** 2026-06-09
**Status:** Approved (pending spec review)

Two small, independent UI changes requested together.

---

## Part A — Remove the default enrollment end date

### Goal
The "Enrollment End (optional)" date field should read **"Ongoing (leave blank)"**
by default instead of showing a stray date (`1/1/2001`). Leaving it blank still
means ongoing enrollment (stored as `NULL`).

### Background
Two places build this field the same way and have the same bug:

- Wizard: `gui/wizard/step_enrollment.py` lines 18-21 —
  `self.end_date = QDateEdit(); setCalendarPopup(True);
  setSpecialValueText("Ongoing (leave blank)"); setDate(QDate(2000, 1, 1))`.
- Enrollments tab add dialog: `gui/member_tabs.py` `_add_enrollment` lines 728-731 —
  `end = QDateEdit(); setCalendarPopup(True); setSpecialValueText("Ongoing");
  setDate(QDate(2000, 1, 1))`.

`QDateEdit.setSpecialValueText` only displays when the value equals the widget's
**minimum** date. Neither call sets the minimum, so the sentinel date shows as a
normal date instead of the special text. (`collect()` in both already maps the
`QDate(2000, 1, 1)` sentinel to `None`, so storage is already correct.)

### Change
In both places, set the minimum to the sentinel before setting the value:

```python
end.setMinimumDate(QDate(2000, 1, 1))
end.setSpecialValueText("Ongoing (leave blank)")   # wizard; tab uses "Ongoing"
end.setDate(QDate(2000, 1, 1))
```

(Keep each call site's existing special-value text. Order: minimum → special text →
date.) With the value at the minimum, the field renders the special text. No change
to the `collect()` sentinel→`None` logic.

### Edge cases
- Default (untouched) → displays the special text → `collect()` returns `None`.
- A real chosen end date → displays/stored normally.
- Minimum date is 2000-01-01, so no real enrollment end could predate it (these are
  current adult-day-care enrollments) — acceptable floor.

---

## Part B — Per-insurer colored health-plan pills

### Goal
The header health-plan badge is color-coded per insurer so plans are
distinguishable at a glance, using brand-approximate colors.

### Background
`gui/theme.py` `build_qss(t)` defines `QLabel#plan_badge` (a single accent pill,
added earlier). The header (`gui/member_tabs.py` `_build_ui`) creates the badge with
object name `plan_badge` when `self._member["health_plan"]` is non-empty. Plan values
come from `HEALTH_PLANS` in `db/members.py`:
`("AE", "Aetna", "Anthem", "BCBS", "ES", "HC", "HF", "HOF", "VCM")`. The app
re-applies the whole stylesheet on theme toggle (`apply_theme`), so QSS attribute
selectors restyle live.

### Architecture
- Add a module-level map in `gui/theme.py`:

```python
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

- In `build_qss(t)`, generate one rule per plan and include them in the returned QSS
  (e.g. build a `plan_rules` string and interpolate it). Each rule is a solid pill
  with near-white text and a matching border (so its box size equals the base
  `plan_badge`, which has a 1px border):

```css
QLabel#plan_badge[plan="<code>"] {
    background-color: <hex>;
    color: #f4f6fd;
    border: 1px solid <hex>;
}
```

  Codes contain no spaces, so `[plan="Aetna"]` selectors are valid. The base
  `QLabel#plan_badge` (accent) remains as the fallback for blank/unknown plans.

- In `_build_ui`, set the dynamic property on the badge:

```python
plan_badge.setObjectName("plan_badge")
plan_badge.setProperty("plan", plan)
plan_badge.setToolTip("Health Plan")
```

  (The property is set once at construction; the global `apply_theme` re-polish on
  theme switch keeps it correct — no manual unpolish/polish needed.)

### Edge cases
- A plan not in `PLAN_COLORS` (or blank) → falls back to the base accent
  `plan_badge` style (still a visible pill).
- Theme toggle → `apply_theme` re-applies the stylesheet, so per-plan colors persist
  in both light and dark (the colors are solid and theme-independent by design).

---

## Testing

- **Part A:** `from gui.wizard.step_enrollment import StepEnrollment` — under an
  offscreen `QApplication`, `StepEnrollment().collect()["enrollment_end"]` is `None`
  by default (the field's special-value sentinel). (Reuse the offscreen `qapp`
  pattern; no DB.)
- **Part B:**
  - `PLAN_COLORS` contains every code in `HEALTH_PLANS` (import both; assert the set
    of `HEALTH_PLANS` is a subset of `PLAN_COLORS` keys).
  - `build_qss(DARK)` and `build_qss(LIGHT)` each contain a `[plan="<code>"]` rule
    for every `HEALTH_PLANS` code.
- Full suite, exe rebuild, and a manual check: the wizard's End field shows
  "Ongoing (leave blank)" by default and the enrollment saves as ongoing; the header
  pill is the brand color for several different plans; a blank-plan member shows no
  badge; colors hold across a light/dark toggle.

## Out of scope
- Coloring plan text anywhere else (the sidebar `· HC` text stays plain).
- Making the badge interactive.
- Changing how health plan or enrollment end are stored.
