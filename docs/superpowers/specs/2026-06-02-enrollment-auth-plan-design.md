# Enrollment Termination, Read-Only Plan & Plan-Per-Authorization — Design Spec

**Date:** 2026-06-02
**Status:** Approved (pending spec review)

## Goal

Four related changes to the BSCA Member Manager member profile:

1. **Terminate enrollment** — a red "Terminate" button in a new Status column on the Enrollments tab that sets the enrollment's end date to today.
2. **Read-only health plan** — the Health Plan field on the Info tab becomes read-only; it is now driven by authorizations, not edited directly.
3. **Plan-per-authorization + auto-sync** — each authorization carries its own Health Plan. The member's health plan is the plan of their *latest* authorization, auto-synced into `Contacts.[Health Plan]` on every auth change.
4. **Edit the latest authorization** — an Edit button on the latest authorization row to fix mistakes, reusing the Add dialog.

## Architecture decisions

- **A1 — Bespoke tables for Enrollments and Authorizations.** Both tabs stop using the shared `_make_table_tab` helper and build their own `QTableWidget` so per-row action buttons (`Terminate`, `Edit`) can be placed via `setCellWidget`. The shared helper and the other three tabs (Availability, Absences, and the unchanged columns) remain untouched — no regression risk.
- **B1 — Health-plan sync lives in the DB layer.** A single function `sync_health_plan_from_latest_auth(center_id, db_path)` encodes the "latest auth wins" rule and writes `Contacts.[Health Plan]`. The GUI calls it after add/edit/delete auth. The business rule is in one testable place, not spread across UI code.

## Tech stack

Python 3.11, PyQt6, pyodbc (Access reads/writes), pytest. No new dependencies.

---

## Feature 1 — Terminate enrollment

### UI (Enrollments tab)

The Enrollments tab is rebuilt as a bespoke `QTableWidget` with columns:

```
ID · Start Date · End Date · Status
```

**Status cell logic** (per row):

- A row is **active** when `end_date is None` **or** `end_date > today` (strictly after today).
  → render a red **Terminate** button (`objectName="btn_terminate"`, styled via theme).
- Otherwise (`end_date <= today`, i.e. ended today or earlier)
  → render a plain **"Ended"** label.

Using *strictly after today* means a just-terminated row (end = today) immediately shows "Ended" rather than lingering as active until tomorrow.

The existing **+ Add** and **Delete Selected** buttons remain below the table.

### Behavior

On **Terminate** click:

1. Confirmation dialog (`QMessageBox.question`):
   > "Terminate this enrollment? The end date will be set to today (`YYYY-MM-DD`). This can't be undone."
   Yes / No.
2. On Yes: call `terminate_enrollment(record_id, db_path)`.
3. Refresh the Enrollments tab.
4. Log an `ENROLL` event: `"Enrollment terminated: end set to YYYY-MM-DD"` (only when `events_path` is set, matching existing pattern).

### DB layer (`db/members.py`)

```python
UPDATE_ENROLLMENT_END = "UPDATE [Enrollment] SET [end_date]=? WHERE [ID]=?"

def terminate_enrollment(record_id: int, db_path: str) -> None:
    """Set an enrollment's end date to today."""
    # _connect (autocommit=False) → execute UPDATE_ENROLLMENT_END with (date.today(), record_id) → commit
    # rollback + raise on error; close in finally (matches existing write helpers)
```

---

## Feature 2 — Health Plan read-only on the profile

### UI (Info tab, Medical group)

- Replace the editable Health Plan `QComboBox` (`self._info_plan`) with a **read-only `QLineEdit`** showing the current `Contacts.[Health Plan]` value (dashed read-only style, like Center ID). Stored as `self._info_plan` still (a read-only line edit) so other code paths referencing it stay valid, OR renamed `self._info_plan_display` with call sites updated — implementer's choice, but it must not be editable and must not be wired into dirty tracking.
- Remove Health Plan from `_setup_dirty_tracking` (no `currentIndexChanged` connection).
- Remove the plan reset from `_discard_info`.

### Save path

- `_save_info` no longer reads a user-chosen plan. It passes the **existing** `self._member["health_plan"]` unchanged to `update_contact`, so the `UPDATE_CONTACT` statement and `update_contact` signature are unchanged (the column is still written, with the same value).
- Health Plan is therefore never part of the profile "changes" diff.

---

## Feature 3 — Health Plan per authorization + auto-sync

### DB precondition

The `[Authorization]` table has a `[Health Plan]` text column (added by the user out-of-band). All reads/writes below assume it exists; if it is missing, auth reads/writes will raise (surfaced via the existing `QMessageBox.critical` error handling).

### DB layer (`db/members.py`)

**Insert** — extend the statement and function:

```python
INSERT_AUTHORIZATION = (
    "INSERT INTO [Authorization] ([Center ID], [auth_start], [auth_end], "
    "[effective_start], [effective_end], [auth_days], [Health Plan]) "
    "VALUES (?, ?, ?, ?, ?, ?, ?)"
)

def insert_authorization(center_id, auth_start, auth_end, auth_days,
                         effective_start, effective_end, health_plan, db_path):
    # bind encode_auth_days(auth_days) and health_plan
```

**Read** — auth dicts must carry `health_plan`. bsca-core's `map_authorization_row` only maps 7 columns, so the local layer owns auth reads:

```python
AUTH_COLUMNS = ("[ID],[Center ID],[auth_start],[auth_end],"
                "[effective_start],[effective_end],[auth_days],[Health Plan]")

def _map_auth_row(row) -> dict:
    d = map_authorization_row(row)        # maps row[0..6]
    d["health_plan"] = row[7] or ""       # add the new column
    return d

def get_authorizations(center_id: int, db_path: str) -> list[dict]:
    """Local replacement that includes Health Plan (cached read connection)."""
    # SELECT AUTH_COLUMNS FROM [Authorization] WHERE [Center ID]=? → [_map_auth_row(r) for r in ...]
```

- `get_member_context()` uses the same `AUTH_COLUMNS` select and `_map_auth_row`, so the `member` view and the tab refresh both get `health_plan`.
- `gui/member_tabs.py` switches its auth-refresh imports from `monthly_schedule.db.get_authorizations` to `db.members.get_authorizations`.

**Latest-auth helper** (pure, unit-tested):

```python
def latest_authorization(authorizations: list[dict]) -> dict | None:
    """Latest by (auth_start, id). None if list empty or no auth_start present."""
    candidates = [a for a in authorizations if a.get("auth_start")]
    if not candidates:
        return None
    return max(candidates, key=lambda a: (a["auth_start"], a["id"]))
```

**Sync function (B1):**

```python
def sync_health_plan_from_latest_auth(center_id: int, db_path: str) -> str | None:
    """Set Contacts.[Health Plan] to the latest auth's plan. Returns the plan
    written, or None if nothing was changed.

    - Reads all authorizations, picks latest_authorization().
    - If there is a latest auth AND its health_plan is non-empty,
      UPDATE [Contacts] SET [Health Plan]=? WHERE [Center ID]=?.
    - If there are no auths, or the latest plan is blank, leave Contacts
      unchanged (never blank an existing plan).
    """
```

### UI (Authorizations tab)

Rebuilt as a bespoke `QTableWidget` with columns:

```
ID · Auth Start · Auth End · Days (1=Mon…5=Fri) · Health Plan · Action
```

- The **latest** auth row (per `latest_authorization`) shows an **Edit** button in the Action column (see Feature 4). Other rows leave Action empty.
- **+ Add** and **Delete Selected** remain below.

### Add Authorization dialog

The dialog builder is refactored into one reusable function supporting **add** and **edit** modes (see Feature 4). It gains a required **Health Plan** `QComboBox` populated from `HEALTH_PLANS`.

- Validation on OK: at least one day selected **and** a plan selected (the combo has no blank entry, so any selection is valid; the day check is the existing rule).

On successful **Add**:

1. `insert_authorization(..., health_plan=..., ...)`.
2. `sync_health_plan_from_latest_auth(center_id, db_path)`.
3. Update `self._member["health_plan"]` and the read-only profile field to the synced value.
4. Refresh the Authorizations tab.
5. Log `AUTH` event including the plan.

On **Delete** (existing flow) — also call `sync_health_plan_from_latest_auth` afterward, then update the in-memory plan + profile field, since removing the latest auth changes the derived plan.

### Schedule Summary

The "Active Auth" line on the Info tab appends the plan, e.g.:

```
2026-01-01 – 2026-12-31  [Mon Wed Fri]  ·  Aetna
```

---

## Feature 4 — Edit the latest authorization

### UI

- Only the **latest** authorization row (per `latest_authorization`) renders an **Edit** button in the Action column.
- Clicking Edit opens the shared authorization dialog in **edit mode**, pre-filled with that row's Auth Start, Auth End, Days, and Health Plan. All fields editable; same validation as Add.

### Behavior

On successful save:

1. `update_authorization(record_id, auth_start, auth_end, auth_days, health_plan, db_path)`.
2. `sync_health_plan_from_latest_auth(center_id, db_path)` (the edit may change the latest plan or which row is latest).
3. Update `self._member["health_plan"]` + read-only profile field.
4. Refresh the Authorizations tab.
5. Log `AUTH` event: `"Auth edited: <start> – <end> · <days> · <plan>"`.

**Effective dates** (`effective_start`/`effective_end`) are preserved/untouched (the Add flow leaves them NULL and the mapper falls back to auth_start/end), so editing does not disturb them.

### DB layer

```python
UPDATE_AUTHORIZATION = (
    "UPDATE [Authorization] SET [auth_start]=?, [auth_end]=?, "
    "[auth_days]=?, [Health Plan]=? WHERE [ID]=?"
)

def update_authorization(record_id, auth_start, auth_end, auth_days,
                         health_plan, db_path):
    # bind (auth_start, auth_end, encode_auth_days(auth_days), health_plan, record_id)
    # _connect → execute → commit; rollback + raise on error; close in finally
```

---

## Testing

Unit tests (`tests/test_db_members.py`):
- `UPDATE_ENROLLMENT_END` targets `[end_date]` and `WHERE [ID]=?`.
- `INSERT_AUTHORIZATION` includes `[Health Plan]` and has 7 placeholders.
- `UPDATE_AUTHORIZATION` targets `[auth_start],[auth_end],[auth_days],[Health Plan]` and `WHERE [ID]=?`.
- `latest_authorization()` picks by (auth_start, id); returns None on empty.

Integration tests (`tests/test_db_members_integration.py`, against the real test DB):
- `terminate_enrollment` sets the end date to today for a known enrollment (insert → terminate → read back → restore/cleanup).
- `insert_authorization` persists a Health Plan; `get_authorizations` returns it in `health_plan`.
- `update_authorization` round-trips a changed plan/date.
- `sync_health_plan_from_latest_auth` writes the latest auth's plan into `Contacts.[Health Plan]`; leaves it unchanged when there are no auths or the latest plan is blank.

All tests restore any rows they mutate (the integration DB is a shared fixture).

## Out of scope

- Editing non-latest authorizations (delete + re-add as today).
- Bulk re-sync of all members' plans; sync is per-member on auth change only.
- Auto-creating the `[Authorization].[Health Plan]` column (precondition).
- Live sidebar refresh on plan change; the sidebar reflects the new plan on next load.
