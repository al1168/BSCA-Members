# Info Tab Layout Font Sizes — Design

**Date:** 2026-09-01
**Branch:** `feature/layout-font-sizes`
**Status:** Approved

## Goal

Extend the customizable Info tab (2026-09-01 spec) with font-size control:
a per-field **value text size** chosen from preset steps, and one **global
label size** for all field labels on the tab.

## Background (current state)

- Field schema (`gui/info_layout.py`): `size` ∈ `SIZES = ("normal",
  "large")`; the renderer sets an `fsize` dynamic property that theme QSS
  matches (`QLineEdit#info_field[fsize="large"] { font-size: 16px; }`, plus
  a generic fallback selector). Default value text is 13px.
- Field labels are `QLabel#field_label`, fixed 11px in the theme; the
  layout has no say over them.
- The editor's properties panel exposes size as a "Large text" checkbox;
  the preview approximates value size (15 vs 12px) via inline styles.

## Decisions made

- **Value size — preset steps, per field:** `SIZES` becomes
  `("small", "normal", "large", "xlarge")` → 11 / 13 / 16 / 20px
  ("normal" stays the un-ruled default). Chosen per field in a "Text size"
  dropdown replacing the "Large text" checkbox.
- **Label size — one global setting:** a top-level layout key
  `label_size` ∈ `LABEL_SIZES = ("small", "normal", "large")` →
  9 / 11 / 13px ("normal" is today's 11px look). One dropdown in the
  editor, applied to every field label. No per-field label sizing.
- **No version bump / migration:** old layouts remain valid — `normal`
  and `large` are still members of `SIZES`, and `normalize()` fills in
  `label_size: "normal"` when the key is absent (clamping unknown values).

## Design

### 1. Model (`gui/info_layout.py`)

- `SIZES = ("small", "normal", "large", "xlarge")`;
  new `LABEL_SIZES = ("small", "normal", "large")`.
- `default_layout()` gains `"label_size": "normal"` at the top level.
- `normalize()` clamps `label_size` to `LABEL_SIZES` (default "normal")
  and keeps clamping field `size` against the widened `SIZES`; the
  normalized dict always carries the key.

### 2. Theme (`gui/theme.py`)

- Value rules join the existing `fsize` pair, in both the
  `#info_field`-qualified and generic blocks:
  `[fsize="small"] { font-size: 11px; }`,
  `[fsize="xlarge"] { font-size: 20px; }`
  (no rule for "normal" — the base 13px applies).
- Label rules after the base `QLabel#field_label` rule:
  `QLabel#field_label[lsize="small"] { font-size: 9px; }`,
  `QLabel#field_label[lsize="large"] { font-size: 13px; }`
  (no rule for "normal" — base 11px applies).
- Pixel sizes are theme-independent (same numbers in dark and light);
  the rules exist once in `build_qss`, not per token dict.

### 3. Renderer (`gui/member_tabs.py`)

- In `_make_info_tab`'s placement loop, each field label gets
  `lab.setProperty("lsize", layout_cfg.get("label_size", "normal"))`
  before being added to the grid. `apply_field_style` is unchanged —
  it already forwards `size` into the `fsize` property, and the new
  values flow through.

### 4. Editor (`gui/info_layout_editor.py`)

- **Per-field:** the "Large text" checkbox becomes a "Text size"
  dropdown over `SIZES` (displayed as Small / Normal / Large / X-Large),
  wired to `_set_prop("size", …)`.
- **Global:** an always-visible "Label size (all fields)" dropdown over
  `LABEL_SIZES` at the top of the right panel (above the per-selection
  properties, surviving `_rebuild_props`), writing
  `self._layout["label_size"]` and re-rendering the preview.
- **Preview fidelity:** preview cells switch from plain text to rich
  text — the label line wrapped in a `font-size` span using the global
  label size's pixel value, the value line using the field's value-size
  pixel value. Bold/dim/highlight styling stays on the cell stylesheet.
  A small `PIXELS_FOR_SIZE` / `PIXELS_FOR_LABEL_SIZE` mapping lives in
  the editor module (presentation detail, not model data).

### 5. Persistence / compatibility

Save path unchanged (`_apply_layout` → settings JSON). A layout saved
before this feature loads with `label_size: "normal"` and its existing
`size` values untouched. A layout saved after this feature, opened by an
older build, is also safe: old `normalize()` clamps `xlarge`/`small` back
to "normal" and ignores the unknown `label_size` key.

## Testing (TDD, existing patterns)

- **Model:** widened `SIZES` accepted and clamped; `label_size`
  defaulted, clamped, round-tripped; old two-value layouts normalize
  unchanged.
- **Theme:** the four new rules present in both themes' QSS; rendered
  check that an `fsize="xlarge"` `#info_field` line edit reports 20px and
  a `lsize="large"` field label reports 13px.
- **Renderer:** labels carry the `lsize` property from the layout;
  a field with `size: "small"` gets `fsize="small"`.
- **Editor:** the Text size dropdown sets `size` on the selected field;
  the global dropdown sets `label_size` and survives selection changes;
  preview cell rich text contains the expected pixel sizes.

## Out of scope

- Per-field label sizes (global only, by decision).
- Free numeric point sizes.
- Section-header or Schedule-card font sizing.
- Fonts/typography beyond size (family, italics, etc.).
