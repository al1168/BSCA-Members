# App-wide Text Size Mode — Design

**Date:** 2026-09-11
**Branch:** `feature/text-size-mode`
**Status:** Approved

## Goal

Let staff make every piece of on-screen text much larger — large enough to
read at a glance from across a desk — with one setting that applies to the
whole program. Two new steps: **Large** (base text 25px) and **Extra Large**
(base text 30px), alongside today's **Normal** (13px). The Info tab layout
editor also gains matching 25px / 30px per-field choices so individual
fields can be pushed larger still.

## Background (current state)

- Every on-screen font size is a literal pixel value. `gui/theme.py`'s
  `build_qss(t)` holds 48 `font-size: Npx` rules (base 13px; buttons, tabs
  and tables 12px; labels, hints and badges 9–11px). About 45 more inline
  `setStyleSheet("... font-size:Npx")` calls live in the widget files, plus
  two point-size `QFont` constructions (events-log timestamps at 10pt,
  time-slider hour ticks at 7pt).
- Dimensions that hold text are also literal: sidebar `setFixedWidth(220)`,
  table `setDefaultSectionSize` of 34/36/40/`ROW_H`, header row bounds
  `_MIN_H`/`_MAX_H` (36/150), badge and toolbar `setMaximumHeight(26)`,
  edit/delete buttons `setFixedWidth(26|28)`, wizard step dots (28) and
  labels (84), note boxes (60/64), Company Calendar hour/date edits
  (64/110), bookmarks/notifications panels (380/360 wide, 260/220 scroll),
  and about 21 `setColumnWidth` calls.
- Theme is the only app-wide look setting: chosen in `SettingsDialog`,
  stored in the settings JSON, applied at startup in
  `member_manager.main()` and live from `MainWindow._open_settings` via
  `theme.apply_theme(app, name)`, which re-polishes all widgets.
- The Info tab layout (`gui/info_layout.py`) sizes values per field via
  `SIZES = ("small", "normal", "large", "xlarge")` → 11/13/16/20px and
  labels globally via `LABEL_SIZES = ("small", "normal", "large")` →
  9/11/13px; the theme QSS matches `fsize`/`lsize` properties. The editor
  (`gui/info_layout_editor.py`) mirrors those pixels in `VALUE_PX` /
  `LABEL_PX` for its preview.
- Printed reports (`profile_print.py`, meal sheet, absence and birthday
  reports) use their own point-size scale so they fit one page.

## Decisions made

- **Three steps, fixed base sizes:** Normal 13px / Large 25px / Extra Large
  30px. Scale factor = base ÷ 13 (≈ 1.923 and ≈ 2.308). No slider, no free
  numeric input.
- **Approach: scale factor in the theme.** Text and the dimensions that
  hold text scale; icons, photos, spacing, paddings and radii do not. (Qt's
  whole-UI `QT_SCALE_FACTOR` was rejected: at 2.3x the list + detail layout
  becomes unusably cramped. Replacing pixel sizes with the application font
  was rejected as a rewrite that loses the tuned hierarchy.)
- **Placement:** Settings dialog only, a "Text size:" row under Theme.
  Persisted like every other setting. No toolbar toggle or shortcut.
- **Screen only.** Printouts keep their compact scale.
- **Info tab per-field sizes scale with the mode.** Per-field pixels are
  defined at Normal scale and multiply with the app factor, so a Normal
  field is never smaller than the buttons around it.
- **Editor gains bigger steps:** values +25px, +30px; labels +20px, +25px,
  +30px (so the label ladder has no gap between 13 and 25).
- **Applying a change rebuilds the main window** (row heights and panel
  widths are fixed at construction). Theme-only changes stay live as today.

## Design

### 1. Setting and scale model

- `settings.py`: `DEFAULT_SETTINGS["text_size"] = "normal"`. Values:
  `"normal" | "large" | "xlarge"`. Older settings files load as Normal.
- `gui/theme.py`:
  - `TEXT_SIZES = {"normal": 13, "large": 25, "xlarge": 30}` and
    `BASE_PX = 13`.
  - `text_scale_for(name) -> float` = `TEXT_SIZES[name] / BASE_PX`
    (unknown names → 1.0).
  - Module state `_current_scale` next to `_current_name`;
    `current_text_scale() -> float`.
  - `px(n: int | float) -> int` = `int(n * current_text_scale() + 0.5)`
    (nearest whole pixel). This is the single helper widget code uses for
    both inline font sizes and text-holding dimensions.
  - `apply_theme(app, theme_name, text_size=None)`: when `text_size` is
    given it becomes the active size; when omitted the current size is kept
    (so a theme-only change never resets the scale). Then
    `app.setStyleSheet(build_qss(tokens, scale))` and re-polish as today.
  - `px` and `build_qss` share one private rounding helper
    (`_scaled(n, scale)`) so QSS and inline sizes cannot drift apart.
  - Tests: an autouse fixture in `tests/conftest.py` pins the scale to
    Normal before and after every test.

### 2. Theme stylesheet

- `build_qss(t: dict, scale: float = 1.0) -> str`. A local `p(n)` closure
  (`int(n * scale + 0.5)`) replaces every literal font-size pixel:
  `font-size: {p(13)}px;` etc., across all 48 rules — including the Info
  tab `fsize` / `lsize` rules and the new ones from §4.
- Not scaled: padding, margin, border widths, border-radius, the
  combo-box drop-down/arrow widths, spin-box `min-width: 72px`, scrollbar
  width and handle `min-height`. They hold no text.
- Pixel values remain theme-independent: identical numbers in dark and
  light; `build_qss(t)` with the default scale is byte-identical to today's
  output, so existing tests keep passing.

### 3. Widget code

All through `theme.px(...)`, evaluated at construction time (the window is
rebuilt on change, see §5):

- **Inline font sizes (45):** `f"font-size:{px(11)}px"` in
  `address_autocomplete`, `bookmarks_panel`, `confirm_changes`,
  `events_view`, `expiring_report`, `info_layout_editor`, `main_window`,
  `member_tabs`, `notifications`, `time_range_editor`, and the four wizard
  step files plus `wizard.py`. Rich-text `<span style='font-size:..'>`
  values in `member_tabs` and the editor preview likewise.
- **Point-size fonts:** `QFont("Cascadia Mono, Consolas", px(10))` in
  `events_view`; `QFont("Segoe UI", px(7))` in `time_range_editor` (scaling
  a point size by the same factor is the intended behaviour).
- **Text-holding dimensions:** sidebar `setFixedWidth(px(220))`; every
  `setDefaultSectionSize(px(...))` and `setColumnWidth(..., px(...))`
  (including the computed ones — the constant terms and floors scale, the
  measured `widest`/`edit_w` terms already reflect the larger font); header
  `_MIN_H`/`_MAX_H` applied as `px(...)`; `make_plan_badge(max_height=26)`
  and the toolbar/badge `setMaximumHeight(26)` calls; edit/delete
  `setFixedWidth(26|28)`; wizard dots `setFixedSize(px(28), px(28))`, step
  labels `setFixedWidth(px(84))`, connector `setFixedWidth(px(64))`; note
  editors `setFixedHeight(px(60|64))`; Company Calendar `setFixedWidth(px(64|110))`;
  `step_auths` `setFixedWidth(px(64))`; bookmarks/notifications panel widths
  and scroll heights; `card.setMaximumWidth(px(400))`; the print dialog's
  `combo.setMaximumWidth(px(240))`; `time_range_editor.setMinimumHeight(px(60))`.
  `address_autocomplete`'s `sizeHint`-based minimum is already font-driven
  and needs no change.
- **Not scaled:** `PHOTO_SIZE`, the 12px colour swatch, the 18px icon,
  1px rules, `confirm_changes`' 70 %-of-screen cap, connector line heights.
- **Startup geometry:** `desired = QSize(px(1800), px(920))`;
  `choose_startup_geometry` already falls back to maximized when that does
  not fit the work area.
- **Time slider ticks:** `_TRACK_Y`/`_TRACK_H` unchanged; only the label
  font scales (labels are drawn, not laid out, so no clipping risk).

### 4. Info layout model, theme rules and editor

- `gui/info_layout.py`:
  `SIZES = ("small", "normal", "large", "xlarge", "xxlarge", "xxxlarge")`;
  `LABEL_SIZES = ("small", "normal", "large", "xlarge", "xxlarge", "xxxlarge")`.
  `normalize()` logic unchanged — it clamps against the widened tuples.
- `gui/theme.py` (inside `build_qss`, both the `#info_field`-qualified and
  generic blocks): `[fsize="xxlarge"] { font-size: {p(25)}px; }`,
  `[fsize="xxxlarge"] { font-size: {p(30)}px; }`; labels:
  `QLabel#field_label[lsize="xlarge"] { font-size: {p(20)}px; }`,
  `[lsize="xxlarge"] … {p(25)}px`, `[lsize="xxxlarge"] … {p(30)}px`.
- `gui/info_layout_editor.py`: `VALUE_PX` gains `xxlarge: 25, xxxlarge: 30`;
  `LABEL_PX` gains `xlarge: 20, xxlarge: 25, xxxlarge: 30`; display names
  `xlarge: "X-Large"`, `xxlarge: "2X-Large"`, `xxxlarge: "3X-Large"` for
  both dropdowns. The preview spans emit `px(VALUE_PX[...])` /
  `px(LABEL_PX[...])` so the preview matches the live tab in every mode.
  The existing "editor maps track the QSS" test keeps comparing at scale 1.
- **Compatibility:** an older layout loads unchanged. A layout saved with a
  new size and opened by an older build clamps it to "normal" for display
  (and, as today, permanently if that old build re-saves the layout).

### 5. Settings dialog and applying a change

- `SettingsDialog`: a "Text size:" row under Theme with three
  `QRadioButton`s — Normal / Large / Extra Large — in a `QButtonGroup`,
  pre-checked from `settings["text_size"]`; `result_settings()` includes
  `"text_size"`.
- `MainWindow._open_settings`, after `dlg.exec()` returns accepted:
  1. `new = result["text_size"]`, `old = self._settings.get("text_size", "normal")`.
  2. If `new != old` and `not self._ok_to_leave_current()` (the existing
     unsaved-edits prompt), set `result["text_size"] = old` — the text
     size reverts; every other setting still applies and saves.
  3. Update and save settings as today; apply theme live as today.
  4. If the text size did change: set `self.reopen_requested = True`,
     record `self.reopen_member_id` (the member widget currently on
     screen, or `None` when the All Events view is showing or the
     database path changed in the same dialog), record
     `self.reopen_alt_id_password` (the session-only password, which is
     never on disk and must be carried in memory), and `self.close()`.
- `member_manager.main()` becomes a loop:

  ```python
  reopen_id = None
  while True:
      settings = load_settings(SETTINGS_PATH)
      apply_theme(app, settings.get("theme", "dark"),
                  settings.get("text_size", "normal"))
      window = MainWindow(settings, SETTINGS_PATH)
      window.show()
      if reopen_id is not None:
          window.jump_to_member(reopen_id)   # public wrapper over _jump_to_member
      app.exec()
      if not window.reopen_requested:
          break
      reopen_id = window.reopen_member_id
  sys.exit(0)
  ```

  `app.quit()` semantics are unchanged: closing the last window ends
  `exec()`; the loop only continues when the window asked to be reopened.
  `ensure_events_path` runs once before the loop, as today.
- Theme-only changes do not rebuild — `apply_theme` + the existing refresh
  path stay live.

### 6. Testing (TDD, existing patterns)

- **Theme:** `build_qss(DARK)` output unchanged at default scale;
  `build_qss(DARK, text_scale_for("large"))` contains `font-size: 25px`
  for the base rule and `font-size: 23px` for a 12px rule;
  `text_scale_for("xlarge") * 13 == 30`; `px()` rounding cases (9→17/21,
  10→19/23, 12→23/28, 20→38/46). Rendered: a plain `QLabel` under the
  xlarge stylesheet reports `pixelSize() == 30`; an `fsize="xxxlarge"`
  `#info_field` reports 30 at Normal scale and 69 at Extra Large.
- **Settings:** default `text_size == "normal"`; `load_settings` on a file
  lacking the key returns Normal; `SettingsDialog.result_settings()`
  round-trips each of the three radios.
- **Info layout:** `xxlarge`/`xxxlarge` accepted for `size`;
  `xlarge`/`xxlarge`/`xxxlarge` accepted for `label_size`; unknown values
  still clamp; the editor dropdowns list the new names and write the keys;
  `VALUE_PX`/`LABEL_PX` match the QSS rules.
- **Main window (fakes, no relaunch):** changing text size with no dirty
  editor sets `reopen_requested` and `reopen_member_id`; cancelling the
  discard prompt with a dirty editor leaves `text_size` unchanged in the
  saved settings while another changed setting (e.g. `show_row_ids`) is
  saved; changing only the theme does not set `reopen_requested`.
- **Widgets:** sidebar width equals `px(220)` under a patched scale;
  a member table's default section size equals `px(34)`.
- **Entry point:** `member_manager.main` loop tested with a stub
  `MainWindow` and stub `app.exec` — reopens once when requested, passes
  the member id through, exits when not requested.

## Out of scope

- Printed reports and the Diagnose tool.
- A toolbar toggle or keyboard shortcut for stepping the size.
- Free numeric sizes, font family, weight or letter-spacing changes.
- Per-field label sizes in the Info tab (the label size stays global).
- Live (no-rebuild) application of a text-size change.
