# Explicit-Entry New Authorizations — Design

**Date:** 2026-09-01
**Branch:** `feature/explicit-auth-entry`
**Status:** Approved

## Goal

Creating an authorization must be a deliberate act: no auto-filled dates, no
silently defaulted dropdowns, and every field completed before it saves.
Today Auth Start/End pre-fill (today / today + 1 year) and Health Plan
defaults to the first plan in the list, so a distracted click can create a
plausible-looking but wrong authorization.

## Background (current state)

Authorizations are created in two places:

- **Auths tab dialog** — `MemberTabsWidget._open_auth_dialog`
  (`gui/member_tabs.py`, ~line 2977). New auths pre-fill Auth Start = today,
  Auth End = today + 1 year; Health Plan combo silently selects the first
  plan; Plan Type has a deliberate blank first entry (kept so legacy rows
  predating the column stay editable); Member ID pre-fills from the member;
  Auth Number is optional. Validation on OK: both dates valid + at least one
  day.
- **New-member wizard** — `StepAuths` (`gui/wizard/step_auths.py`). Same
  date pre-fill. The step is optional; it counts as skipped when no day
  checkbox is checked (`is_skipped()`), which silently discards any dates or
  auth number the user did type. Fields: dates, days, Plan Type, Auth
  Number (no Health Plan or Member ID field in the wizard step).

`DateLineEdit` (`gui/address_autocomplete.py`) already supports an empty
value, `flag_validity(required=True)`, and the red error outline — no widget
changes are needed.

## Decisions made

- **Scope:** both creation paths (dialog and wizard).
- **Required set (new auths):** everything explicit — empty dates that must
  be filled, Health Plan and Plan Type chosen from a blank initial entry,
  Member ID non-empty (pre-fill from the member is kept — it is the
  member's real insurance ID), Auth Number non-empty, at least one day.
- **Edit mode is exempt:** editing an existing authorization keeps today's
  behavior (values pre-filled from the auth; validation = valid dates +
  ≥ 1 day), so legacy rows with blank Plan Type / Auth Number stay editable
  without forcing values onto them.
- **Validation style:** the existing validate-on-OK pattern — red outlines
  via `set_widget_error` plus one warning box listing what is missing. No
  live-disabled OK button.

## Design

### 1. Auths tab dialog (`_open_auth_dialog`)

Creating (no `existing`):

- `auth_start` / `auth_end` start empty (placeholder "MM/DD/YYYY" remains).
- `plan_combo` gains a blank first item and starts on it; items follow as
  today.
- `plan_type_combo` keeps its existing blank first item and starts on it.
- Member ID pre-fills from the member as today; Auth Number starts empty.

`on_accept`, when creating, requires all of: both dates valid
(`flag_validity(required=True)`), ≥ 1 day checked, Health Plan non-blank,
Plan Type non-blank, Member ID non-empty, Auth Number non-empty. Failing
widgets outline red (`set_widget_error` for the combos/line edits), and one
`QMessageBox.warning` lists the missing fields by name. Editing keeps
today's checks (dates + days) unchanged.

The blank Health Plan item exists only while creating; when editing, the
combo is built exactly as today (no blank entry, current value selected).

### 2. Wizard auth step (`StepAuths`)

- Dates start empty (drop the `set_pydate(today / today+1yr)` calls).
- **Skip rule changes:** `is_skipped()` becomes "nothing entered at all" —
  no day checked AND both dates empty AND Auth Number empty AND Plan Type
  blank. Typing anything engages the step.
- `validate()`, when not skipped, requires: both dates valid, ≥ 1 day,
  Plan Type non-blank, Auth Number non-empty — each failure outlined red
  (day-check failures are reported via the wizard's existing message
  pattern for `validate()` returning False).
- Transport Auth Number stays optional (its panel is unchanged); it still
  only produces a transport auth when a care auth exists.
- The step's warning label gains one sentence: an authorization that has
  been started must be completed (or fully cleared) before continuing.
- `collect()` is unchanged in shape; with the stricter `validate()` it can
  no longer emit a half-filled authorization.

### 3. Error handling

No new failure modes: all enforcement happens before the DB insert, using
widgets and helpers that already exist. The overlap-confirmation flow
(`_confirm_overlap`) is untouched.

## Testing (TDD, existing Qt offscreen patterns)

- **Dialog, create mode:** opens with empty dates, blank Health Plan and
  Plan Type selections; OK is rejected (dialog stays open, warning issued)
  while any required field is missing — exercised per-field; accepts once
  all fields are filled and returns the complete dict.
- **Dialog, edit mode:** a legacy auth with blank Plan Type and Auth Number
  opens pre-filled and saves untouched (no new requirements applied).
- **Wizard:** `is_skipped()` true only when nothing is entered (day, date,
  auth number, or plan type each individually engage it); `validate()`
  flags each missing required field; a fully-empty step still validates and
  collects `authorization: None`.

## Out of scope

- Transport authorization fields (stay optional).
- Any change to editing existing authorizations.
- DB-level constraints (enforcement is UI-only, matching the app's pattern).
- Requiring Health Plan / Member ID in the wizard step (those fields do not
  exist there; the wizard takes them from the member record).
