# Unavailable Times Tab — Design Spec

**Date:** 2026-06-09
**Status:** Approved (pending spec review)

## Goal

Add a member tab for recording one-off windows on a specific date when the member
is **busy / unavailable** (e.g. unavailable 9:00 AM–12:00 PM on a given day), with
full add / edit / delete. The tab sits between **Availability** and **Absences**.
It is backed by the existing Access table `OneOffAvailability`.

## Semantics

Each row is a single calendar date plus a start/end time window during which the
member is **NOT available** (the inverse of the recurring Availability tab). The
UI is labeled around "unavailable" even though the storage columns are named
`avail_start` / `avail_end`. This is distinct from **Absences**, which are
full-day (multi-day) leaves; an Unavailable Times row is a partial-day block on
one date.

## Backing table (`OneOffAvailability`, already created in Access)

| Column      | Type        | Use                                            |
|-------------|-------------|------------------------------------------------|
| `ID`        | AutoNumber  | Primary key                                    |
| `Center ID` | Number      | Member id (foreign key by convention)          |
| `date`      | Date/Time   | The specific calendar date                     |
| `avail_start`| Date/Time  | Window start, stored time-only (1899 placeholder) |
| `avail_end` | Date/Time   | Window end, stored time-only (1899 placeholder)|
| `Notes`     | Long Text   | Free-text note                                 |

Column names are used verbatim (bracket-quoted) in SQL: `[ID]`, `[Center ID]`,
`[date]`, `[avail_start]`, `[avail_end]`, `[Notes]`.

## Background (existing patterns this mirrors)

- **UI** (`gui/member_tabs.py`): `_make_avail_tab` builds a `QTableWidget` with a
  per-row **Edit** button plus **+ Add** / **Delete Selected** buttons; `_add_avail`
  / `_edit_avail` / `_delete_avail` open dialogs, write via `db.members`, reload
  via a `get_*` function, call `_refresh_tab(index, ...)`, and log an event with
  `self._log_event(...)`.
- Times are entered as typed `h:mm` + an AM/PM `QComboBox`, validated/converted by
  `db.members.time_12h_to_24h(text, period) -> "HH:mm"`.
- **Writes** live in `db/members.py` (SQL constants + `insert/update/delete_*`,
  using `_connect`, `_hhmm_to_datetime` for time-only DATETIME storage). **Reads**
  for the member detail come from `get_member_context` (a single cached-connection
  fetch returning `member`, `enrollments`, `authorizations`, `availability`,
  `absences`); standalone reloads use functions like `get_authorizations`.
- `monthly_schedule` is an installed **site-packages** package; its `get_*`/mapper
  helpers must NOT be edited. All new code lives in the repo (`db/members.py`,
  `gui/member_tabs.py`).
- Current tab order/indices: Info(0), Enrollments(1), Authorizations(2),
  Availability(3), Absences(4), Events(5). `_refresh_tab` takes a fixed index;
  avail handlers use 3, absence handlers use 4.

## Architecture

### Data layer (`db/members.py`)

- **SQL constants:**
  - `INSERT_ONE_OFF_AVAILABILITY` — `INSERT INTO [OneOffAvailability] ([Center ID],
    [date], [avail_start], [avail_end], [Notes]) VALUES (?, ?, ?, ?, ?)`
  - `UPDATE_ONE_OFF_AVAILABILITY` — `UPDATE [OneOffAvailability] SET [date]=?,
    [avail_start]=?, [avail_end]=?, [Notes]=? WHERE [ID]=?`
  - `DELETE_ONE_OFF_AVAILABILITY` — `DELETE FROM [OneOffAvailability] WHERE [ID]=?`
  - `ONE_OFF_AVAILABILITY_SELECT` — `SELECT [ID],[Center ID],[date],[avail_start],
    [avail_end],[Notes] FROM [OneOffAvailability] WHERE [Center ID]=?`
- **Row mapper** `map_one_off_availability_row(row) -> dict`:
  `{"id": int, "center_id": int, "date": <date>, "avail_start": "HH:mm" | None,
  "avail_end": "HH:mm" | None, "notes": str}`. Reuses the same conventions as
  `map_availability_row` (a date converter for `[date]`, a DATETIME→`HH:mm`
  converter for the times; null-safe). These small converters are defined locally
  in `db/members.py` (no dependency on the site-packages mappers).
- **Write functions** (mirror the Availability ones, with `_connect` +
  commit/rollback/close):
  - `insert_one_off_availability(center_id, on_date, avail_start, avail_end, notes, db_path)`
  - `update_one_off_availability(record_id, on_date, avail_start, avail_end, notes, db_path)`
  - `delete_one_off_availability(record_id, db_path)`
  Times are passed as `"HH:mm"` and stored with `_hhmm_to_datetime`; `on_date` is a
  `date`; `notes` is a string.
- **Reads:**
  - `get_member_context` runs one more query and returns a new key
    `one_off_availability` (list of mapped dicts). Placed alongside the existing
    availability/absences fetches, inside the same try/cached-connection/retry.
  - `get_one_off_availability(center_id, db_path)` — standalone reload over the
    cached read connection, mirroring `get_authorizations` (including the
    stale-connection retry).

### UI (`gui/member_tabs.py`)

- `_load_data` sets `self._one_off = ctx.get("one_off_availability", [])` (default to
  `[]` and also initialize it to `[]` at the top of `_load_data` like the others).
- New `_make_unavailable_tab()` builds the tab (modeled on `_make_avail_tab`):
  - A short caption label: "Times the member is unavailable on a specific date."
  - Columns: **Date · Start · End · Notes · Action**. The Action cell has an
    **Edit** button per row wired to `_edit_unavailable(row_dict)`.
  - **+ Add** → `_add_unavailable`; **Delete Selected** → `_delete_unavailable(table)`.
  - Stores the table as `self._unavail_table`.
- `_add_unavailable()` dialog: `QDateEdit` (calendar popup, default today),
  Start and End time rows (typed `h:mm` + AM/PM combo, default 9:00 AM / 12:00 PM),
  and a multiline Notes field (`QTextEdit` or `QPlainTextEdit`). Validates times via
  `time_12h_to_24h`; on accept, calls `insert_one_off_availability`, reloads via
  `get_one_off_availability`, `_refresh_tab(4, self._make_unavailable_tab())`, and
  logs `self._log_event("AVAIL", f"One-off unavailable added: {d} {ts}–{te}")`.
- `_edit_unavailable(entry)` dialog: same four fields pre-filled from `entry`
  (date, start, end, notes). On accept, `update_one_off_availability`, reload,
  refresh, log `"One-off unavailable edited: …"`.
- `_delete_unavailable(table)`: confirm prompt; look up `entry` by the ID in column
  0 from `self._one_off`; `delete_one_off_availability`, reload, refresh, log
  `"One-off unavailable deleted: …"`.

### Tab placement & index fix

- In `_build_ui`, build `self._tab_unavail = self._make_unavailable_tab()` and
  `addTab` it **after** Availability and **before** Absences, labeled
  **"Unavailable Times"**. New tab order: Info(0), Enrollments(1),
  Authorizations(2), Availability(3), **Unavailable Times(4)**, Absences(5),
  Events(6).
- Update the Absences handlers' `_refresh_tab(4, …)` calls to `_refresh_tab(5, …)`
  (both `_add_absence` and `_delete_absence`). Availability handlers stay at 3. The
  new Unavailable Times handlers use index 4.

## Components / data flow

- Dialog (date + times + notes) → `time_12h_to_24h` → `db.members.insert/update`
  (→ `_hhmm_to_datetime` for storage) → `get_one_off_availability` reload →
  `_refresh_tab` → table re-render. Event audit via `_log_event("AVAIL", …)`.

## Error handling / edge cases

- Invalid typed times → validation warning in the dialog (reuse the Availability
  pattern), no write.
- DB errors → `QMessageBox.critical`, same as the other tabs.
- Empty Notes is allowed (stored as empty string / NULL-safe).
- A member with no one-off rows → empty table with the caption.

## Testing

- Unit test `map_one_off_availability_row`: a fake row (id, center id, a date, two
  1899-placeholder datetimes, a notes string) maps to the expected dict with times
  as `"HH:mm"` and the date preserved; null times map to `None`.
- Unit test the time/date conversion path used for storage (`_hhmm_to_datetime`
  already covered; assert the mapper's round-trip shape).
- DB CRUD (insert → read → update → delete) follows the existing integration-test
  pattern in `tests/` (these exercise a real Access file via the ODBC driver; add
  the one-off case there if that harness is present, otherwise rely on the mapper
  unit tests + manual verification).
- Full suite, exe rebuild, and a manual check: add a one-off unavailable window
  (date + 9:00 AM–12:00 PM + a note), confirm it appears in the tab and persists;
  edit it; delete it; confirm Absences and Events tabs still work (index bump
  correct) and the Events log shows the one-off entries.

## Out of scope

- Whether the `monthly_schedule` generator consumes `OneOffAvailability` rows
  (external package; not part of this CRUD feature).
- Any new Events event-type/badge (reuse `AVAIL`).
- Recurring or multi-date one-off entries (each row is a single date).
