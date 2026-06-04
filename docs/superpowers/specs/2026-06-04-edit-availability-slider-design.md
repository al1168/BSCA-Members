# Edit Availability — Range Slider + Manual Entry — Design Spec

**Date:** 2026-06-04
**Status:** Approved (pending spec review)

## Goal

Let a user edit an existing availability row's **time window** (Start/End) via an
"Edit" button that opens a modal dialog containing a two-handle **range slider**
paired with **manual time fields**, kept in two-way sync. Dragging snaps to
15-minute steps; typing accepts any minute within the bounds.

## Scope

- Edits **Start and End times only**. Day and Effective From are not editable
  here (delete + re-add to change those).
- Bounds: **8:00 AM – 4:00 PM** for both the slider and manual entry.
- Drag snaps to 15 minutes; manual entry accepts any minute in range.
- Minimum window: **15 minutes** (End ≥ Start + 15).
- The **Add Availability** dialog is unchanged (out of scope).

## Architecture

- A new self-contained widget, `TimeRangeEditor` (in a new module
  `gui/time_range_editor.py`), owns the custom range slider plus two manual
  time fields and keeps them in sync. It exposes the chosen window as
  `"HH:mm"` strings.
- Pure value/range logic (minutes ↔ `"HH:mm"`, snapping, clamping, min-window)
  lives as **module-level pure functions** in that file, unit-tested without Qt.
- The Availability tab in `gui/member_tabs.py` becomes a bespoke `QTableWidget`
  (like the Authorizations tab) with a per-row **Edit** button that opens a
  modal dialog hosting a `TimeRangeEditor`.
- A new `update_availability(...)` + `UPDATE_AVAILABILITY` in `db/members.py`
  persists the change, mirroring `insert_availability` (which stores times as
  Access DATETIME via `_hhmm_to_datetime`).

## Tech Stack

Python 3.11, PyQt6, pyodbc (Access), pytest. **No new dependencies** (the range
slider is hand-built).

---

## Constants & domain

- Bounds in minutes since midnight: `MIN_MINUTES = 480` (08:00),
  `MAX_MINUTES = 960` (16:00).
- `SNAP_MINUTES = 15` (drag granularity).
- `MIN_WINDOW = 15` (minimum End − Start).
- Stored/returned time strings are 24-hour `"HH:mm"` (e.g. `"08:00"`, `"16:00"`),
  consistent with `insert_availability` / `get_availability`.

## Pure helpers (in `gui/time_range_editor.py`, module level — unit tested)

```python
def hhmm_to_minutes(hhmm: str) -> int:
    """'08:00' -> 480, '16:00' -> 960. Raises ValueError on malformed input."""

def minutes_to_hhmm(m: int) -> str:
    """480 -> '08:00' (24-hour, zero-padded)."""

def clamp_minutes(m: int) -> int:
    """Clamp to [MIN_MINUTES, MAX_MINUTES]."""

def snap_minutes(m: int) -> int:
    """Round to the nearest SNAP_MINUTES, then clamp to bounds."""
```

Behavior notes:
- `clamp_minutes` and `snap_minutes` both keep results within [480, 960].
- Manual entry uses `clamp_minutes` (no snap); drag uses `snap_minutes`.
- The 12-hour text ↔ 24-hour conversion reuses the existing
  `db.members.time_12h_to_24h` (typed `h:mm` + AM/PM → `"HH:mm"`), then
  `hhmm_to_minutes`.

## `TimeRangeEditor` widget

A `QWidget` composed of:
1. A **live readout** `QLabel`: `"{start} – {end}  ·  {duration}"`, e.g.
   `"8:00 AM – 4:00 PM  ·  8h 0m"`, updated on every change.
2. A **`RangeSlider`** (nested custom `QWidget`, see below).
3. Two manual rows: **Start** and **End**, each a `QLineEdit` (`h:mm`,
   placeholder) + an AM/PM `QComboBox` — the same pattern as Add Availability.

State: `self._start_min`, `self._end_min` (ints, minutes). Public API:
- `set_window(start_hhmm: str, end_hhmm: str)` — seed from a row.
- `start_hhmm() -> str`, `end_hhmm() -> str` — current values for saving.

**Two-way sync rules**
- **Slider moves a handle** → value already snapped+clamped by the slider →
  update `_start_min`/`_end_min` → refresh the two text fields and the readout.
- **A text field commits** (`editingFinished`):
  - Parse via `time_12h_to_24h(text, period)` → `"HH:mm"` → `hhmm_to_minutes` →
    `clamp_minutes` (no snap).
  - Enforce ordering/min-window: if editing Start, `start = min(start, end - MIN_WINDOW)`;
    if editing End, `end = max(end, start + MIN_WINDOW)`; keep both within bounds.
  - On success: update state, slider handles, the other field if it shifted, and
    the readout.
  - On parse failure (or empty): show a brief inline warning (reuse the
    "Enter times as h:mm…" message style) and **revert the field to the last
    valid value**, so the slider and fields never disagree.

## `RangeSlider` (custom `QWidget`, in the same module)

Single horizontal track representing 8:00 AM–4:00 PM with two draggable handles.

- Internal model: `start_min`, `end_min` ints in [480, 960].
- Signals: `windowChanged(start_min: int, end_min: int)` emitted on drag.
- **Painting** (`paintEvent`): muted rounded track; accent-filled band between
  the handles; two circular handles (white fill, accent border); hour tick
  labels (`8a 9a 10a 11a 12p 1p 2p 3p 4p`) under the track.
- **Mapping:** `x(minutes) = track_left + (minutes - 480)/480 * track_width`;
  inverse maps a mouse x back to minutes.
- **Interaction** (`mousePressEvent`/`mouseMoveEvent`): grab the nearer handle;
  while dragging, convert x → minutes → `snap_minutes`; clamp so the dragged
  handle can't cross the other (respecting `MIN_WINDOW`); emit `windowChanged`.
- **Keyboard (nice-to-have):** Left/Right move the focused handle by
  `SNAP_MINUTES`. Optional; not required for acceptance.
- `set_window(start_min, end_min)` to seed/sync from typed values (accepts any
  minute, not just snapped, so a typed 8:07 renders off-tick).

Layout: `setMinimumHeight(~64)`, expanding width. Styling via inline palette
colors consistent with the dark theme (accent `#5b7cf4`, track `#2a2e3a`).

## Availability tab changes (`gui/member_tabs.py`)

Replace `_make_avail_tab()` (currently uses the shared `_make_table_tab`) with a
bespoke `QTableWidget`:

- Columns: `["ID", "Day", "Start", "End", "Effective From", "Action"]`.
- Header resize modes like the Auths tab (ResizeToContents for most; a stretch
  column; Action sized to the Edit button).
- Each row: populate ID/Day/Start/End/Effective From; add an **Edit**
  `QPushButton` (objectName `btn_edit`, reusing the existing accent style) wired
  to `self._edit_avail(a)` via a default-arg lambda (`avail=a`).
- Keep the **+ Add** and **Delete Selected** buttons (wired to the existing
  `_add_avail` / `_delete_avail`).

New `_edit_avail(self, avail: dict)`:
1. Build a modal `QDialog` titled `f"Edit Availability — {day_name}"`.
2. Add a read-only Day label, a `TimeRangeEditor` seeded via
   `set_window(avail["avail_start"], avail["avail_end"])`, and Save/Cancel
   (`QDialogButtonBox`).
3. On Save: read `start_hhmm()`/`end_hhmm()`, call
   `update_availability(avail["id"], start, end, self._db_path)`, reload via
   `monthly_schedule.db.get_availability`, `self._refresh_tab(3, self._make_avail_tab())`,
   and log an `AVAIL` event:
   `f"Availability edited: {day_name} {start}–{end}"` (guarded by
   `self._events_path`). Errors via `QMessageBox.critical`.

## Data layer (`db/members.py`)

```python
UPDATE_AVAILABILITY = (
    "UPDATE [Availability] SET [avail_start]=?, [avail_end]=? WHERE [ID]=?"
)

def update_availability(record_id: int, avail_start: str, avail_end: str,
                        db_path: str) -> None:
    """Update an availability row's start/end times (HH:mm 24-hour)."""
    # _connect → execute(UPDATE_AVAILABILITY,
    #     (_hhmm_to_datetime(avail_start), _hhmm_to_datetime(avail_end), record_id))
    # commit / except rollback+raise / finally close  (same pattern as the other writers)
```

## Testing

### Unit tests (`tests/test_time_range_editor.py`, new)
- `hhmm_to_minutes` / `minutes_to_hhmm` round-trip (`"08:00"`↔480, `"16:00"`↔960,
  `"08:07"`↔487); malformed input raises `ValueError`.
- `clamp_minutes`: below 480 → 480; above 960 → 960; in-range unchanged.
- `snap_minutes`: 487 → 480, 488 → 495, 953 → 960 (and clamped to bounds).

### Unit test (`tests/test_db_members.py`)
- `UPDATE_AVAILABILITY` targets `[avail_start]`, `[avail_end]`, `WHERE [ID]=?`.

### Integration test (`tests/test_db_members_integration.py`)
- Insert an availability row, `update_availability` to a new window, read back
  via `get_availability` and assert `avail_start`/`avail_end` changed; delete in
  a `finally` to clean up.

### Manual verification
- Drag snaps to 15-min; typing `8:07 AM` places the start handle off-tick;
  typing a time outside 8–4 reverts with a warning; End can't go below
  Start + 15 min; Save persists and the table row updates; an AVAIL event is
  logged.

## Out of scope

- Changing Day / Effective From in the editor.
- Unifying the **Add Availability** dialog to use `TimeRangeEditor` (possible
  follow-up for consistency).
- Editing other tabs' rows.
