# Authorized-Days Weekday Chips — Design Spec

**Date:** 2026-06-09
**Status:** Approved (pending spec review)

## Goal

Make a member's authorized days of the week visually obvious instead of buried in
read-only text. Replace the text-only day displays with a row of seven weekday
chips where authorized days are filled with the accent color and the rest are
dimmed, so the on/off pattern reads at a glance. Move the Schedule section to the
top of the Info tab, and use the chips in both the Info tab and the
Authorizations tab.

## Background (current state)

In `gui/member_tabs.py`:

- **Info tab** (`_make_info_tab`, lines 294-417): a dense sectioned `QGridLayout`
  in section order Identity → Contact → Medical → Care → **Schedule** (last).
  The Schedule section (lines 414-417) has two cells: `Enrollment Start` and
  `Active Auth`. The Active Auth value is a read-only `QLineEdit` whose text is
  built at lines 339-349 as
  `"{effective_start} – {effective_end}  [{days_str}]  ·  {plan}"`, where
  `days_str = format_auth_days(active_auth["auth_days"])` → `"Mon Wed Fri"`.
- **Authorizations tab** (`_make_auths_tab`, around line 776): column 3 ("Days")
  is set via `table.setItem(r, 3, QTableWidgetItem(a["auth_days"] or ""))` — it
  shows the **raw encoded string** `"1,3,5"`, not even the friendly form.
- `format_auth_days(auth_days: str)` (lines 57-62) parses `"1,3,5"` →
  `"Mon Wed Sat"`. `WEEKDAY_NAMES` (lines 52-54) maps `1→"Mon" … 7→"Sun"`.
- `_active_authorization(...)` returns the active auth dict with keys
  `effective_start`, `effective_end`, `auth_days` (encoded string), `health_plan`.
- The app themes via object-named QSS in `gui/theme.py` (`build_qss(t)` for both
  `DARK` and `LIGHT` token dicts); existing examples include `warning_badge`,
  `section_header`, `field_label`.

The Add/Edit authorization dialog already uses Mon–Sun checkboxes (a visual
selector) and is **out of scope**.

## Decisions (from brainstorming)

- **Treatment:** "Full weekday track" — all seven days always shown; authorized =
  filled accent pill, unauthorized = dimmed outline.
- **Placement:** the Schedule section moves to the **top** of the Info tab (before
  Identity).
- **Chip scope:** both the Info tab Schedule and the Authorizations tab day column.
- **Keep** the auth dates and plan, but as a quieter secondary line; the chips are
  the prominent element.
- **Design language (impeccable, product register, restrained):** one accent color
  from the existing theme tokens (`accent`/`accent_bg`) for "on"; existing dim
  neutral tokens (`text3`/`border`) for "off". No new palette. Rounded pill chips,
  hierarchy through fill + weight.
- **Polish:** after the chips are implemented and rendering, run an
  `/impeccable polish` pass over the chip widget + its QSS to refine spacing,
  radius, weight, and color before finishing.

## Architecture

### 1. `decode_auth_days(auth_days: str) -> set[int]`  (pure, module-level)

New helper in `gui/member_tabs.py`. Parses the encoded string into a set of day
numbers: `"1,3,5" → {1, 3, 5}`, `"" → set()`. Ignores blank/garbage tokens (same
tolerant parse as `format_auth_days`). `format_auth_days` is refactored to use it
(DRY): `days = sorted(decode_auth_days(auth_days))`.

### 2. `WeekdayChips(QWidget)`  (reusable component)

New widget in `gui/member_tabs.py`.

- **Constructor:** `WeekdayChips(days: set[int], compact: bool = False, parent=None)`.
- Builds a single horizontal row of seven `QLabel` chips, one per day 1→7 in
  Mon→Sun order. Each chip's object name is `day_chip_on` when its day number is in
  `days`, else `day_chip_off`. Full mode label = the 3-letter name from
  `WEEKDAY_NAMES` uppercased (`"MON"`); compact mode label = the first letter
  (`"M"`, `"T"`, …) for tight table cells.
- Chips are center-aligned, fixed-height, with small horizontal spacing; the row
  has zero contents margins so it drops cleanly into a grid cell or a table cell.
- Exposes the input so it's testable: store `self._days = set(days)`.
- No business logic, no DB — purely presentational. Callers decode the encoded
  string via `decode_auth_days` and pass the set in.

### 3. Theme QSS (`gui/theme.py`)

Add rules inside `build_qss(t)` (so both DARK and LIGHT get them from their token
dicts):

- `QLabel#day_chip_on` — background `{t['accent']}`, color `#ffffff`, `border:none`,
  `border-radius: 9px`, bold, small font, padding `2px 8px`.
- `QLabel#day_chip_off` — background transparent, color `{t['text3']}`,
  `border: 1px solid {t['border']}`, same radius/padding/font, normal weight.

(Exact numeric values are refined during the `/impeccable polish` step; the tokens
and structure above are the baseline.)

### 4. Info tab (`_make_info_tab`)

- Move the `section("Schedule")` block (and its cells) so it is added **first**,
  before `section("Identity")`. Identity/Contact/Medical/Care keep their relative
  order after it.
- Replace the single `Active Auth` cell with:
  - `Enrollment Start: <date>` (unchanged).
  - `Authorized Days:` → a full-mode `WeekdayChips` built from
    `decode_auth_days(active_auth["auth_days"])`, spanning the widget columns.
  - `Auth Period:` → a quiet read-only line/label showing
    `"{effective_start} – {effective_end}"` plus `"  ·  {plan}"` when a plan exists.
- **No active authorization:** `WeekdayChips(set())` (all chips dimmed) and
  `Auth Period: None`.

### 5. Authorizations tab (`_make_auths_tab`)

- Column 3 ("Days"): replace `table.setItem(r, 3, QTableWidgetItem(a["auth_days"]))`
  with `table.setCellWidget(r, 3, WeekdayChips(decode_auth_days(a["auth_days"]),
  compact=True))`. Row height is already 34px (line 768), enough for compact chips.

## Components / data flow

- `decode_auth_days` (string → set) feeds `WeekdayChips` (set → 7 styled labels).
- `_make_info_tab` and `_make_auths_tab` are the only consumers; they decode the
  encoded `auth_days` and hand the set to `WeekdayChips`.
- Theme tokens drive the on/off appearance via QSS object names — no inline color.

## Error handling / edge cases

- Empty or missing `auth_days` → `decode_auth_days` returns `set()` → all chips off.
- Garbage tokens (non-integers, stray commas) are skipped, mirroring
  `format_auth_days`'s tolerant parse.
- No active auth on the Info tab → all-dim track + `Auth Period: None`.

## Testing

New unit tests:

- `decode_auth_days`: `"1,3,5" → {1,3,5}`; `"" → set()`; `"2,,7, " → {2,7}`
  (whitespace/empty tolerated); a non-numeric token is ignored.
- `format_auth_days` still returns `"Mon Wed Fri"` for `"1,3,5"` after the refactor
  (regression guard).
- `WeekdayChips` (offscreen Qt, like the existing `EventsTableWidget` test): build
  `WeekdayChips({1,3,5})`, assert it has 7 chip `QLabel`s, and that the Mon/Wed/Fri
  chips carry object name `day_chip_on` while the other four carry `day_chip_off`;
  build `WeekdayChips(set())` and assert all seven are `day_chip_off`.

Then: full suite, exe rebuild, `/impeccable polish` pass on the chip widget + QSS,
and a manual check (Info tab opens with Schedule on top and a lit weekday track;
Authorizations tab rows show compact chips; a no-auth member shows an all-dim
track in both light and dark themes).

## Out of scope

- The Add/Edit authorization dialog (already checkbox-based) and the wizard.
- Changing how `auth_days` is stored or queried.
- Any change to the warning badge / tab markers (separate, already shipped).
