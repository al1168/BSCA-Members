# Member-Profile GUI Tweaks — Design Spec

**Date:** 2026-06-09
**Status:** Approved (pending spec review)

A batch of small, mostly-independent UI changes to the member profile. All live in
`gui/member_tabs.py` except the Notes styling (also `gui/theme.py`).

## Changes

### 1. Info-tab field rearrangement

The Info tab is a `QGridLayout` built with `section(title)` and
`cell(slot, label, widget, wspan=1)` helpers (`slot` 0/1/2 = the three field
columns). Widget attribute names are unchanged, so save/discard/dirty tracking is
unaffected — only cell placement changes.

**Schedule** (unchanged except it loses Enrollment Start):
- Authorized Days (chips, span 3)
- Auth Period (span 2)

**Identity** (gains SSN + Enrollment Start; loses Member ID):
- First Name · Last Name · Chinese Name
- Gender · DOB · **SSN**
- Center ID · **Enrollment Start**

**Medical** (gains Member ID beside Health Plan; loses SSN; Language relabeled):
- Health Plan · **Member ID** · Medicaid
- Medicare · PCP · Hospital
- HHA · **Language Spoken**

`enroll_lbl` (the read-only enrollment-start line) is still built where it is now;
only its `cell(...)` call moves into the Identity section.

### 2. Language label → "Language Spoken"

- The Info cell label changes from `"Language"` to `"Language Spoken"`.
- `FIELD_LABELS["language"]` (used by `build_change_summary` for the audit log)
  changes from `"Language"` to `"Language Spoken"` so edits read
  "Language Spoken: … → …". The stored column/key stays `language`.

### 3. Availability tab → "Time Slot Availability"

In `_build_ui`, the tab text changes from `"Availability"` to
`"Time Slot Availability"`. The add/edit dialog titles and the underlying data are
unchanged.

### 4. Notes band — make it more obvious (impeccable-decided)

The header Notes band (a `"Notes"` `QLabel` + the `_NotesEdit` editor) should read
as a clearly-distinct, slightly-emphasized region. Implementation:

- Give the `"Notes"` label an object name `notes_label` and the `_NotesEdit` an
  object name `notes_edit`, styled by object-named QSS in `gui/theme.py` (both DARK
  and LIGHT) so they theme correctly.
- **Baseline** (working, on-brand starting point): `notes_label` uses the accent
  text token; `notes_edit` gets a thin (1px) subtle border using a theme token.
- An **`/impeccable`** pass (product register, restrained) then decides/refines the
  final treatment within the theme tokens — it may keep both, drop to label-only or
  border-only, or use a faint tinted background. The result stays subtle (no loud
  colors) and uses only existing tokens. The object names above are kept stable.

### 5. Authorizations sort — latest end date on top

`_make_auths_tab` renders rows sorted by **`auth_end` descending** (the most recent
end date first). A pure helper does the ordering:

```python
def sort_auths_latest_first(auths: list[dict]) -> list[dict]:
    """Authorizations ordered by end date, latest first. Missing end dates sort
    last."""
    from datetime import date
    return sorted(auths, key=lambda a: a.get("auth_end") or date.min, reverse=True)
```

`_make_auths_tab` iterates `sort_auths_latest_first(self._authorizations)` instead
of `self._authorizations`. The per-row "Edit" button still attaches to the latest
authorization (matched by id via the existing `latest_authorization`), so display
order does not change which row is editable.

## Testing

- Unit-test `sort_auths_latest_first`: a list with mixed `auth_end` dates (and one
  `None`) returns latest-end first with `None` last; the input list is not mutated.
- Theme test: `build_qss(DARK)` and `build_qss(LIGHT)` each contain
  `QLabel#notes_label` and `#notes_edit` (so the Notes styling exists in both).
- The Info-tab rearrangement, the Language/tab relabels, and the Notes visual are
  verified manually (they need a full member context / visual judgment).
- Then full suite, the `/impeccable` Notes pass, exe rebuild, and a manual check of
  every item.

## Out of scope

- Renaming the recurring-availability data, dialogs, or DB columns (tab label only).
- Reordering or restyling any other tab or section.
- Changing how SSN / Member ID / Language are stored.
