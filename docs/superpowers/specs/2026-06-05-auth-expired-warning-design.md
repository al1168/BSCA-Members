# Expired-Authorization Warning — Design Spec

**Date:** 2026-06-05
**Status:** Approved (pending spec review)

## Goal

Warn on a member's profile when their authorization has lapsed — they have
authorization records but none is currently valid (the latest end date is before
today). This mirrors the existing "Missing: Authorizations" warning. At the same
time, remove the "Availability" warning entirely.

## Background (current state)

All member warnings live in `gui/member_tabs.py`:

- `MemberTabsWidget._missing()` (lines 203-209) returns a list: `"Authorizations"`
  when `self._authorizations` is empty, `"Availability"` when `self._availability`
  is empty.
- `_build_ui` uses that list in two places:
  - Header badge (a `QLabel` with object name `warning_badge`): shows
    `"⚠ Missing: " + ", ".join(missing)` when the list is non-empty.
  - Tab labels: `"Auths ⚠"` when `"Authorizations" in missing`; `"Availability ⚠"`
    when `"Availability" in missing`.
- There is **no** per-member warning in the sidebar/member-list. Warnings appear
  only on the open profile.
- Each authorization dict has `auth_end` as a Python `date` (the auth dialog sets
  it via `QDateEdit.date().toPyDate()`).

## Decisions (from brainstorming)

- **Expired = no currently-valid authorization.** Warn only when the member has
  authorization(s) and the **latest** `auth_end` is strictly before today. A past
  expired auth is ignored when a newer valid one exists.
- **Boundary:** `auth_end == today` is still **valid** (not expired). Expired means
  `auth_end < today`.
- **Null end dates** count as not-expired (open-ended authorization).
- **Three mutually-exclusive auth states** drive the indicator:
  - No authorizations → `Missing: Authorizations`
  - Has authorizations, latest `auth_end < today` → `Authorization Expired`
  - Has a currently-valid authorization → no warning
- **Availability warning removed entirely** — gone from the header badge and from
  the Availability tab label. Availability data, the Availability tab, and its
  editing are untouched; only the warning indicator is removed.

## Architecture

Extract the decision into a pure, module-level function in `gui/member_tabs.py`
so it is unit-testable without constructing a Qt widget:

```python
def auth_warning(authorizations: list[dict], today: date) -> str | None:
    """Warning label for a member's authorization state, or None.

    - "Missing: Authorizations" when there are no authorizations.
    - "Authorization Expired" when there are authorizations but none is
      currently valid (the latest end date is before today).
    - None when a currently-valid authorization exists.
    """
    if not authorizations:
        return "Missing: Authorizations"
    ends = [a["auth_end"] for a in authorizations if a.get("auth_end")]
    if ends and max(ends) < today:
        return "Authorization Expired"
    return None
```

`MemberTabsWidget._build_ui` changes:

- Compute `warn = auth_warning(self._authorizations, date.today())` once.
- Header badge: when `warn` is not None, set the `warning_badge` label text to
  `"⚠ " + warn` (so `"⚠ Missing: Authorizations"` or `"⚠ Authorization Expired"`).
  When `warn` is None, no badge (as today).
- Auths tab label: `"Auths ⚠"` when `warn` is not None, else `"Authorizations"`.
- Availability tab label: always `"Availability"` (drop the `⚠` branch).

Remove the now-unused `_missing()` method. `date` is imported in
`gui/member_tabs.py` (confirm during implementation; add `from datetime import
date` if absent).

## Components / data flow

- **`auth_warning` (pure function):** input is the member's list of authorization
  dicts plus today's date; output is the badge string or None. No Qt, no DB.
- **`_build_ui` (consumer):** calls `auth_warning`, renders the badge and the
  Auths tab marker. Availability tab marker removed.

## Error handling / edge cases

- Empty `authorizations` → `Missing: Authorizations`.
- All `auth_end` values null → not expired → None.
- `max(ends) == today` → valid → None.
- Mixed expired + valid → `max(ends) >= today` → None.

## Testing

New file `tests/test_auth_warning.py` (pure-function tests, no Qt):

- No authorizations → `"Missing: Authorizations"`.
- Single auth ended yesterday → `"Authorization Expired"`.
- Single auth ending today → `None` (still valid).
- Single auth ending tomorrow → `None`.
- Two auths, one expired and one valid → `None`.
- Auth with `auth_end = None` → `None`.

Plus: full suite, exe rebuild, and a manual check (a member with a lapsed auth
shows `⚠ Authorization Expired` and `Auths ⚠`; no member shows any availability
warning).

## Out of scope

- Sidebar/member-list warning indicators (none exist today; not adding).
- Future-dated (not-yet-started) authorizations as a distinct warning state.
- Changing availability data, the Availability tab, or its editing.
- Any change to how authorizations are stored or queried.
