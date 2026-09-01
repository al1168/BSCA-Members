# Customizable Info Tab — Design

**Date:** 2026-09-01
**Branch:** `feature/customizable-info-tab`
**Status:** Approved

## Goal

Let the user rearrange the member view's Info tab — which fields appear, where,
under which section headings — and adjust how each field looks (width, emphasis,
highlight color), through a WYSIWYG layout editor dialog. The layout persists
per machine and the tab renders from it.

## Background (current state)

The Info tab is built by `MemberTabs._make_info_tab` (`gui/member_tabs.py`):
a hardcoded `QGridLayout` with five fixed sections (Identity, Contact, Medical,
Care, Emergency), three label+widget column pairs per row, a Schedule card on
top, and the emergency-contacts table at the bottom. Field widgets are
`_ViewEditLineEdit` instances stored as attributes (`_info_first`,
`_info_dob`, …) that the save/discard/dirty machinery reads directly.
Settings live in a per-machine JSON (`settings.load_settings` /
`save_settings`) passed into the GUI as a dict.

## Decisions made

- **Editor style:** separate dialog with a live miniature preview (left) and a
  properties panel (right). Not an in-place edit mode, not a config file.
- **Structure:** custom sections — the user adds, renames, deletes, and
  reorders section headers; fields go in any section in any order. Inside a
  section, fields auto-flow in a fixed 3-column grid (no free row/col
  placement, no adjustable column count).
- **Per-field styling:** column span (1–3), bold toggle, size
  (normal / large), highlight color from a preset palette
  (none / amber / blue / green / red), visible toggle.
- **Special blocks:** the Schedule card and the Emergency contacts block are
  reorderable and hideable as whole blocks; their internals are not
  customizable.
- **Persistence:** per-machine, under an `info_tab_layout` key in the existing
  settings JSON. No DB change; other workstations are unaffected.

## Architecture

Three units:

### 1. Layout model — `gui/info_layout.py` (new, pure Python, no Qt)

- **Field registry:** the canonical ordered list of customizable fields:
  `key → (label, kind)` where kind ∈ {plain, phone, medicaid, medicare, ssn,
  dob, address, readonly}. Single source of truth for both renderer and
  editor. Keys match the member-dict keys already used by `_make_info_tab`
  (`first_name`, `last_name`, `chinese_name`, `gender`, `dob`, `ssn`,
  `center_id`, `enrollment_start`, `language`, `alt_id`, `address`,
  `home_tell`, `cell`, `health_plan`, `member_id`, `medicaid`, `medicare`,
  `hospital`, `pcp`, `hha`, `case_manager`).
- **Layout schema** (`version: 1`), an ordered list of blocks:

  ```json
  {
    "version": 1,
    "blocks": [
      {"type": "schedule", "visible": true},
      {"type": "section", "title": "Identity", "fields": [
        {"key": "first_name", "span": 1, "bold": false,
         "size": "normal", "color": "none", "visible": true},
        ...
      ]},
      {"type": "emergency", "visible": true}
    ]
  }
  ```

- **`default_layout()`** reproduces today's tab exactly (sections, order,
  the existing full-row spans for Address/PCP/HHA).
- **`normalize(layout)`** reconciles a saved layout with the registry:
  unknown field keys dropped; registry fields missing from the layout
  appended to the section holding their default neighbors (fallback: last
  section, creating "Other" if no sections exist); `schedule` and
  `emergency` blocks forced to appear exactly once; invalid
  span/size/color values clamped to defaults. Anything unparseable →
  return `default_layout()`. Never raises.
- JSON round-trip via plain dicts (the settings file is already JSON).

### 2. Rendering — changes to `MemberTabs._make_info_tab`

- All field widgets are constructed exactly as today, same attribute names,
  same validators/formatters — save/discard/dirty tracking, header sync, and
  existing tests are untouched.
- Only the placement code changes: it walks
  `normalize(settings.get("info_tab_layout"))` and emits, per block:
  the Schedule card (kept as `_schedule_card` so
  `_refresh_schedule_card` still works), a section header + field cells in
  layout order, or the emergency box. A widget map `key → widget` connects
  registry keys to the constructed widgets.
- **Hidden fields:** the widget is still created and populated but never
  placed (no parent, `setVisible(False)`), so saving continues to read every
  widget and no data is ever lost by hiding a field.
- **Styling at placement:** span uses the existing `wspan` mechanism;
  bold/large set the widget font (large ≈ +2pt); highlight sets a dynamic
  Qt property (`highlight="amber"`), with per-theme colors added to
  `gui/theme.py` for both light and dark palettes.
- The layout dict lives on the settings dict the window already passes down,
  so a rebuild after saving is: re-create the Info tab widget and swap it
  into the tab bar at the same index.

### 3. Editor dialog — `gui/info_layout_editor.py` (new)

`InfoLayoutEditor(QDialog)`, opened by a new "Customize Layout…" button in
the Info tab's bottom button row (left of Discard/Save). Operates on a deep
copy of the current layout; the caller applies the result only on accept.

- **Left — live preview:** a schematic miniature rendered from the model:
  each field is a compact box showing its label and the current member's
  value as static text, with span/bold/large/color applied, sections with
  their headers, plus the Schedule/Emergency blocks as gray placeholders.
  Rebuilt from the model on every change (cheap at this scale). Clicking a
  box selects that field (outline highlight); clicking a section header or
  special block selects the block.
- **Right — properties panel** for the selection:
  - Field selected: section dropdown (moves it), Move Up / Move Down within
    the section, span (1/2/3), Bold, Large, color swatch row, Visible.
  - Section selected: rename (line edit), Move Up / Move Down among blocks,
    Add Section (inserts after), Delete Section — deleting a non-empty
    section asks to confirm and moves its fields to the previous section
    (or next, if it was first).
  - Schedule/Emergency block selected: Move Up / Move Down, Visible.
- **Buttons:** Reset to Default (loads `default_layout()` into the editor),
  Cancel, Save. Save → `save_settings` with the new layout, then the member
  view rebuilds the Info tab in place.

## Error handling

- Corrupt/hand-edited/stale saved layouts can never crash the tab:
  `normalize()` degrades field-by-field and falls back to the default.
- Fields added to the app in future releases appear automatically on
  upgraded machines (normalize appends them) instead of silently vanishing.
- Any field may be hidden — the tab is a view; the data stays in the DB and
  in the (unplaced) widget.

## Testing (TDD)

- **Model** (headless): default layout matches the registry and today's
  visual order; normalize drops unknown keys, appends missing ones, dedupes
  special blocks, clamps bad values, survives garbage input; JSON
  round-trip; delete-section field migration.
- **Renderer** (Qt, existing test patterns): tab honors a custom layout —
  section order/titles, field order, span, hidden fields absent from the
  grid but still saving correctly, font/highlight properties applied.
- **Editor** (Qt): selecting a field and changing section/span/style updates
  the model; delete-section migrates fields; reset restores default; Save
  persists via settings and the Info tab rebuilds.

## Out of scope

- Shared/networked layouts (per-machine only, by decision).
- Customizing the internals of the Schedule card or Emergency table.
- Free row/column placement or configurable column counts.
- Layouts for other tabs (this establishes the pattern; extending is later
  work).
