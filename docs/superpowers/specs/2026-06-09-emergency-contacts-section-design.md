# Emergency Contacts Section — Design Spec

**Date:** 2026-06-09
**Status:** Approved (pending spec review)

## Goal

Hold a member's emergency contacts (one-to-many) in an "Emergency" section at the
bottom of the Info tab, with add / edit / delete, backed by the new Access table
`EmergencyContact`. Remove the old single free-text Emergency field from the form.

## Backing table (`EmergencyContact`, already created in Access)

| Column         | Type        |
|----------------|-------------|
| `ID`           | AutoNumber  |
| `Center ID`    | Number      |
| `Full Name`    | Short Text  |
| `Phone Number` | Short Text  |
| `Relationship` | Short Text  |

Plain columns (no attachment), so writes use standard pyodbc.

## Background (existing patterns)

- One-to-many data (Authorizations, Availability, Absences, OneOffAvailability)
  follows: SQL constants + `insert/update/delete_*` in `db/members.py`; a row
  mapper; a key in `get_member_context`; a standalone `get_*` reload; a UI table
  with Add / Edit / Delete. The most recent example is **OneOffAvailability**
  (`map_one_off_availability_row`, `get_one_off_availability`,
  `insert/update/delete_one_off_availability`, `_make_unavailable_tab`).
- The Info tab (`_make_info_tab`) is a `QGridLayout` with `section(title)` and
  `cell(slot, label, widget, wspan=1)` helpers; sections currently are Schedule,
  Identity, Contact, Medical, Care. `grid.addWidget(widget, row, 0, 1, 6)` spans a
  full-width widget across the six grid columns (as `section()` does for headers).
- The single Emergency field: `self._info_emergency = field("emergency")` is shown
  via `cell(2, "Emergency", self._info_emergency)` in the Contact section, and is
  part of `collect()` / `_save_info` / `_discard_info` (the Contacts `[Emergency]`
  column).
- Integration tests use a real Access file; `tests/conftest.py` already creates the
  `OneOffAvailability` table in it (because `get_member_context` queries it) and
  drops it at session end.

## Architecture

### 1. Data layer (`db/members.py`)

- **SQL constants:**
  - `INSERT_EMERGENCY_CONTACT` — `INSERT INTO [EmergencyContact] ([Center ID],
    [Full Name], [Phone Number], [Relationship]) VALUES (?, ?, ?, ?)`
  - `UPDATE_EMERGENCY_CONTACT` — `UPDATE [EmergencyContact] SET [Full Name]=?,
    [Phone Number]=?, [Relationship]=? WHERE [ID]=?`
  - `DELETE_EMERGENCY_CONTACT` — `DELETE FROM [EmergencyContact] WHERE [ID]=?`
  - `EMERGENCY_CONTACT_SELECT` — `SELECT [ID],[Center ID],[Full Name],
    [Phone Number],[Relationship] FROM [EmergencyContact] WHERE [Center ID]=?`
- **Mapper** `map_emergency_contact_row(row) -> dict`:
  `{"id": int, "center_id": int, "full_name": str, "phone": str,
  "relationship": str}` (null text → "").
- **Write functions** (standard `_connect` + commit/rollback/close, mirror the
  absence functions):
  - `insert_emergency_contact(center_id, full_name, phone, relationship, db_path)`
  - `update_emergency_contact(record_id, full_name, phone, relationship, db_path)`
  - `delete_emergency_contact(record_id, db_path)`
- **Reads:**
  - `get_member_context` runs `EMERGENCY_CONTACT_SELECT` and returns a new
    `emergency_contacts` key (list of mapped dicts), inside the same cached-read try.
  - `get_emergency_contacts(center_id, db_path)` — standalone reload mirroring
    `get_one_off_availability` (cached read connection + stale-retry).

### 2. UI — Emergency section in the Info tab (`gui/member_tabs.py`)

- `_load_data` sets `self._emergency_contacts = ctx.get("emergency_contacts", [])`
  (init to `[]` with the other lists).
- In `_make_info_tab`, after the **Care** section (the last one), add:
  - `section("Emergency")`
  - A full-width container `self._emergency_box` (a `QWidget` with a `QVBoxLayout`,
    no margins) added via `grid.addWidget(self._emergency_box, state["row"], 0, 1, 6)`
    then `state["row"] += 1`. Populate it with `self._fill_emergency_box()`.
- `_fill_emergency_box()`: clears the box's layout and rebuilds it:
  - A `QTableWidget` with columns **Full Name · Phone · Relationship · Action**;
    each row's Action cell is an **Edit** button (`btn_edit` object name) wired to
    `self._edit_emergency(entry)`. Built from `self._emergency_contacts`. Row height
    34 (room for the button), like the other CRUD tables.
  - A button row: **+ Add** → `self._add_emergency`; **Delete Selected** →
    `self._delete_emergency(table)`.
  - Stores the table as `self._emergency_table`.
- Remove the old field: delete the `cell(2, "Emergency", self._info_emergency)` line
  from the Contact section. **Keep** `self._info_emergency` constructed and in
  `collect`/`_save_info`/`_discard_info` (unplaced widget) so its current value
  round-trips to the DB unchanged — no data loss, no save-signature change.

### 3. CRUD handlers (`gui/member_tabs.py`)

- `_open_emergency_dialog(existing=None)`: a `QDialog`/`QFormLayout` with three
  `QLineEdit`s — **Full Name** (required), **Phone Number**, **Relationship**
  (free text). On OK, requires a non-empty Full Name (else a validation warning);
  returns `{full_name, phone, relationship}` or `None`.
- `_add_emergency()`: dialog → `insert_emergency_contact(...)` → reload via
  `get_emergency_contacts` → `self._fill_emergency_box()` → `self._log_event("EDIT",
  f"Emergency contact added: {full_name}")`.
- `_edit_emergency(entry)`: dialog prefilled → `update_emergency_contact(entry["id"],
  ...)` → reload → refill → log "Emergency contact edited: …".
- `_delete_emergency(table)`: confirm; look up `entry` by the ID in column-0 data
  from `self._emergency_contacts`; `delete_emergency_contact` → reload → refill →
  log "Emergency contact deleted: …". (The contact's ID is stored on the row, e.g.
  via `Qt.ItemDataRole.UserRole` on the Full Name cell, since the table has no
  visible ID column.)

These commit immediately, independent of the Info tab's Save/Discard (consistent
with the other one-to-many editors).

## Error handling / edge cases

- No contacts → empty table under the Emergency header (with the Add button).
- Empty Full Name in the dialog → validation warning, no write.
- DB errors → `QMessageBox.critical`, like the other editors.
- Phone / Relationship may be blank (stored as empty/NULL-safe).

## Testing

- Unit-test `map_emergency_contact_row`: a fake row maps to the expected dict;
  null text fields map to `""`.
- Update `tests/conftest.py` to also create the `EmergencyContact` table in the
  integration DB (same create-if-missing / drop-at-session-end pattern as
  `OneOffAvailability`), so the integration tests that call `get_member_context`
  keep passing.
- The embedded section, dialog, and CRUD are verified manually (need a full member
  context / real DB writes).
- Then full suite, exe rebuild, and a manual check: the Emergency section lists
  contacts; Add/Edit/Delete work and persist after reopening the member; the old
  single Emergency field is gone from the Contact section; the Events log shows the
  "Emergency contact …" entries.

## Out of scope

- Migrating the old single Emergency text into the new table.
- A "primary contact" flag or contact ordering.
- Changing the Contacts `[Emergency]` column (it stays; just unshown).
