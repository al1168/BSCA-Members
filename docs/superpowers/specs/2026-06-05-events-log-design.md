# Working Events Log — Design Spec

**Date:** 2026-06-05
**Status:** Approved (pending spec review)

## Goal

Make the Events log actually record member-data changes — additions, edits, and
deletions — and show them per-member (the Info-area "Events" tab) and globally
(the "All Events" view). Add a way to return from All Events to the member you
were viewing.

## Background (current state)

- `db/events.py` is a working SQLite layer: `open_db`, `init_db`, `insert_event`,
  `query_events(center_id, filter_text)`, `purge_old_events` (30-day TTL). It is
  unit-tested.
- `gui/events_view.py` has `EventsTableWidget` (per-member when `center_id` set,
  global when `None`) and `GlobalEventsWidget`.
- Mutations in `gui/member_tabs.py` and the wizard already call `insert_event`
  for most **adds/edits**, but **every call is guarded by `if self._events_path`**.
- **Root cause it "doesn't work":** `events_db_path` is empty in settings, so all
  writes are skipped and the tables are blank.
- **Gaps:** deletions (enrollment, authorization, availability, absence) are not
  logged; the per-member Events tab does not refresh after a change; clicking
  All Events replaces the member profile with no way back.

## Decisions (from brainstorming)

- **Storage stays manual:** keep `events_db_path` configured in Settings (gives
  control over where the SQLite file lives). When unset, show a clear prompt
  instead of a blank table. **No auto-default.**
- **Retention stays 30 days** (existing `purge_old_events`).
- **Comprehensive recording:** member edits log every changed field; deletions
  are recorded for all four entity types.
- **No user/identity attribution** (shared single-login tool) — out of scope.

## Architecture

- A single `MemberTabsWidget._log_event(event_type, description)` helper opens the
  events DB (when a path is set), inserts the row, closes, and refreshes the
  member's Events tab. All member-tab mutations route through it, replacing the
  repeated inline `open_db`/`insert_event`/`close` blocks (DRY).
- `EventsTableWidget` shows an empty-state message when no events path is set.
- `MainWindow` remembers the last-viewed member's `center_id`; the global
  All Events view gets a "← Back" control that restores that member's profile.

## Tech Stack

Python 3.11, PyQt6, SQLite (`db/events.py`), pytest. No new dependencies.

---

## Part 1 — Empty state when no events path

`gui/events_view.py` `EventsTableWidget._load`: when `self._events_path` is
falsy, instead of returning silently, render a single, full-width informational
row (or a label) reading:

> "No events log configured. Set an Events log path in Settings to start recording changes."

When a path is set, behavior is unchanged (load + purge + populate). The search
box may be hidden or disabled in the empty state (implementer's choice; keep it
simple — a message row in the otherwise-empty table is enough).

## Part 2 — `_log_event` helper + live refresh

Add to `MemberTabsWidget`:

```python
def _log_event(self, event_type: str, description: str) -> None:
    """Record an event for this member (if an events log is configured) and
    refresh the member's Events tab."""
    if self._events_path:
        from db.events import open_db, insert_event
        m = self._member
        conn = open_db(self._events_path)
        try:
            insert_event(
                conn, event_type, self._center_id,
                f"{m.get('last_name', '')}, {m.get('first_name', '')}",
                description,
            )
        finally:
            conn.close()
    if hasattr(self, "_tab_events"):
        self._tab_events.refresh()
```

Replace the existing inline `open_db`/`insert_event`/`close` blocks in
`_save_info`, `_add_enrollment`, `_terminate_enrollment`, `_after_auth_change`,
`_add_avail`, `_edit_avail`, and `_add_absence` with single `self._log_event(...)`
calls (same event type + description text as today, except member-edit detail in
Part 3). This also makes the Events tab refresh after each of those actions.

(`self._tab_events` is the `EventsTableWidget` created in `_build_ui`; calling its
existing `refresh()` reloads the table.)

## Part 3 — Member edit logs every changed field

In `_save_info`, the event description currently uses `"; ".join(summary[:5])`.
Drop the cap so all changed fields are recorded:

```python
self._log_event("EDIT", "; ".join(summary))
```

`summary` is the existing `build_change_summary(old, fields)` output
(`Label: old → new` lines), so each entry is human-readable.

## Part 4 — Record deletions

Each delete handler currently removes the row without logging. After a
successful delete (inside the existing `try`, before/after the tab refresh), add
a `self._log_event(...)` describing the removed row. Build the description from
the row data already available in the handler (the selected table row / the
in-memory list entry).

- `_delete_enrollment(table)` → reuse `ENROLL`:
  `"Enrollment deleted: <start> – <end or 'ongoing'>"`.
- `_delete_auth(table)` → reuse `AUTH`:
  `"Authorization deleted: <auth_start> – <auth_end> [<days>] · <plan>"`
  (use `format_auth_days` for the days, `health_plan` for the plan, from the
  matching entry in `self._authorizations`).
- `_delete_avail(table)` → reuse `AVAIL`:
  `"Availability deleted: <Day> <avail_start>–<avail_end>"` (Day via
  `WEEKDAY_NAMES`).
- `_delete_absence(table)` → reuse `ABS`:
  `"Absence deleted: <leave_type> <start> – <end>"`.

Each handler looks up the deleted row's fields (by the `ID` in column 0) from the
corresponding `self._<entities>` list before deleting, so the description has the
real values. No new event types are introduced; the badge stays the entity type
and the description says "deleted".

## Part 5 — Return from All Events

`gui/main_window.py`:

- Track the last-viewed member: in `_show_member`, set
  `self._last_center_id = center_id`. Initialise `self._last_center_id = None`
  in `__init__`.
- `_show_global_events` passes a back callback to the global view:
  `GlobalEventsWidget(events_path, on_back=self._back_from_events)`.
- New `_back_from_events(self)`:
  - If `self._last_center_id` is set and still exists, call
    `self._show_member(self._last_center_id)`.
  - Else clear the detail panel back to the placeholder
    (`self._detail_stack.setCurrentIndex(0)` after removing the events widget,
    mirroring `_set_detail`'s teardown).

`gui/events_view.py`:

- `GlobalEventsWidget.__init__(self, events_path, on_back=None, parent=None)`.
  When `on_back` is provided, add a small header row above the table with a
  **"← Back"** `QPushButton` wired to `on_back` (left-aligned), so the global
  view has an obvious exit. The per-member `EventsTableWidget` (embedded as a
  tab) is unaffected.

## Testing

### Unit tests (`tests/test_db_events.py`, existing file)
- A "deleted" description round-trips: `insert_event(conn, "AUTH", cid, name,
  "Authorization deleted: 2025-01-01 – 2025-12-31 [Mon Wed Fri] · HF")` then
  `query_events(conn, center_id=cid)` returns it with that description and type.
- `query_events` global vs per-member still filters by `center_id` (existing
  coverage; add an assertion if missing).

### Manual verification
With an events log path set in Settings:
- Edit several member fields → Save → the member **Events** tab immediately shows
  one `EDIT` row listing every changed field (`old → new`); it also appears in
  **All Events**.
- Add and then delete an enrollment, authorization, availability row, and
  absence → each add **and** each delete shows as a row (correct badge +
  description) in both views.
- With **no** events path set: both views show the "Set an Events log path in
  Settings" message; saving still works.
- Open a member, click **All Events**, click **← Back** → returns to that
  member's profile. Click All Events with no member open, click ← Back → returns
  to the empty placeholder.

## Out of scope

- Auto-defaulting / relocating the events DB (stays manual, local SQLite).
- Changing the 30-day retention.
- User/identity attribution; CSV export; editing or deleting individual events.
