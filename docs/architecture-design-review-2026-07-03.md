# BSCA Member Manager — Architecture & Design Review

*July 3, 2026. Method: full read of the data layer and main window, structural analysis of
`gui/member_tabs.py`, QSS/theme audit, test-suite run, and a live GUI walkthrough against a
copy of the test database (18 screenshots of every tab, the wizard, settings, quick search,
and both themes).*

---

## Executive summary

The app is in better shape than most internal tools: the domain rules are pure functions with
docstrings that explain *why*, there are ~90 focused test files, destructive actions confirm
first, dirty-state tracking guards navigation everywhere, and the address autocomplete does its
network I/O asynchronously. The product principles in PRODUCT.md are visibly enforced in code.

The two structural debts that will hurt the most as the app grows:

1. **`gui/member_tabs.py` is a 3,815-line god module** — one widget class (~3,120 lines, ~90
   methods) owns all eight tabs, every add/edit/delete dialog, photo handling, printing, event
   logging, and cross-tab navigation. The same CRUD pattern is hand-copied seven times.
2. **`db/members.py` mixes four layers** — SQL + connection caching, row mapping, domain rules,
   and *UI text formatting* all live in the "db" module, so the GUI imports its phone/SSN/date
   formatters from the database layer.

Neither is a rewrite; both are mechanical extractions that the existing test suite already
covers well.

Top recommendations, ranked by value-for-effort:

| # | Change | Effort |
|---|--------|--------|
| 1 | Delete or fix the stale `main.py` entry point (it crashes on launch) | trivial |
| 2 | Fix the "No database configured" placeholder shown when a DB *is* loaded | trivial |
| 3 | Add empty-state text to every table and to zero-result search | small |
| 4 | Collapse the ~25 copies of connect/commit/rollback into one context manager | small |
| 5 | Extract formatters + domain rules out of `db/members.py` | small |
| 6 | Split `member_tabs.py` into per-tab modules with a shared CRUD-tab base | medium |
| 7 | Tame the Enrollments "Terminate" button (full-width alarm red today) | trivial |
| 8 | Centralize user-facing error messages (raw pyodbc errors reach staff today) | small |
| 9 | Add a startup schema check for optional tables/columns | small |
| 10 | Route all colors through theme tokens (39 hard-coded hex values bypass them) | medium |

---

## What's working well (keep doing this)

- **Pure logic, unit-tested.** `next_center_id` (db/members.py:1083), `is_terminated`,
  `current_authorization`, `auth_status`, `current_schedule`, `merge_default_availability` are
  side-effect-free and covered by fast tests. This is the right shape.
- **Docstrings explain intent**, not mechanics — e.g. the mtime-keyed read-connection cache
  (db/members.py:480–507) documents the ACE-engine visibility quirk it works around.
- **Forgiving workflows** per PRODUCT.md: incomplete members are allowed and surfaced as header
  warning chips ("Authorization Expired", "Missing: Emergency Contact"); the wizard's optional
  step 3 explains the consequence of skipping ("won't appear on schedules until…").
- **Non-destructive defaults**: delete confirmations, unsaved-changes guard on member switch
  (gui/main_window.py:289), change-summary confirmation before saving Info edits
  (gui/member_tabs.py:1630–1646) — which doubles as a great audit-log entry.
- **Async where it matters**: Google Places autocomplete uses `QNetworkAccessManager`
  (gui/address_autocomplete.py:244) — no UI freezes on network; photo load is deferred.
- **Crash logging** (crash_log.py) writes a daily report and tells the user where it is.
- **Theme tokens** (gui/theme.py DARK/LIGHT dicts) are a real design system in miniature, with
  per-plan badge colors matched to the staff's physical color legend and auto-picked text color.

---

## Architecture

### A1. `gui/member_tabs.py` is a god module (3,815 lines) — split it

`MemberTabsWidget` (line 694 to EOF) owns: data loading, header (photo/badges/notes/warnings),
all 8 tabs, ~10 modal dialogs, printing, event logging, dirty tracking, and cross-tab
navigation. The same quintet — `_make_X_tab` / `_open_X_dialog` / `_add_X` / `_edit_X` /
`_delete_X` — is hand-copied for enrollments (1841), authorizations (2002), transportation
(2443), availability (3012), scheduled changes (3302), one-off availability (3546), absences
(3728), plus emergency contacts (1359). The Authorizations and Transportation sections
(~430 lines each) are near-identical clones differing mainly in table name and the link column.
There are ~28 copies of `except Exception as exc: QMessageBox.critical(...)`.

Consequences today: any change to the shared pattern (e.g. the row-ID debug column,
`_apply_id_column` line 1721) must be threaded through every tab by hand; review diffs are
noisy; the file is slow to navigate even for its author.

**Suggested decomposition** (mechanical, no behavior change):

```
gui/
  member_tabs.py          -> thin container: header + QTabWidget + tab wiring   (~400)
  tabs/
    base_crud_tab.py      -> table + Add/Delete bar + confirm + refresh hook    (~150)
    info_tab.py           -> fields, sections, emergency box, save/discard      (~700)
    enrollments_tab.py                                                          (~150)
    auth_tab.py           -> shared by Authorizations AND Transportation        (~450)
    availability_tab.py   -> incl. scheduled changes + current-schedule strip   (~600)
    one_off_tab.py                                                              (~150)
    absences_tab.py                                                             (~100)
  widgets/
    fields.py             -> _ViewEditLineEdit, _NotesEdit, _PhotoLabel         (~300)
    chips.py              -> WeekdayChips, make_plan_badge, pill helpers        (~120)
domain/
  auth_rules.py           -> lines 106–465 of today's file (already pure)       (~360)
```

A small `MemberSession` object (center_id, db_path, events_path, api_key, show_row_ids, plus a
`log_event()` method and a `data_changed` signal) passed to each tab removes the 5-parameter
constructor threading that today goes `MainWindow → MemberTabsWidget → every dialog`
(gui/main_window.py:349–359).

The existing tests are already written against small units (weekday chips, pill columns, auth
status, dirty buttons…), so this refactor is largely `git mv` + import fixes — do it one tab at
a time, running the suite between moves.

### A2. `db/members.py` mixes four layers (1,715 lines) — extract two of them

Current contents:

| Concern | Where | Belongs in |
|---|---|---|
| SQL constants, connection & DAO caches | :30–547 | `db/` (stay) |
| Row mappers | :398–419, 858–866 | `db/` (stay) |
| **UI formatters/validators** — `format_phone_live`, `format_ssn_live`, `format_time_live`, `parse_mdy`, `time_12h_to_24h`… | :42–232, 422–447 | `ui/formats.py` or `core/formats.py` |
| **Domain rules** — `next_center_id`, `is_terminated`, `current_authorization`, `enrollment_active`, `merge_default_availability`… | :175–193, 989–1116, 1295–1342 | `domain/` |

Today the wizard and the tabs import their keystroke formatters *from the database module*
(gui/wizard/step_contact.py:9, gui/member_tabs.py:8–15). That coupling means you can't touch
the data layer without recompiling your mental model of the UI, and vice versa. The functions
are already pure — this is a file move plus imports.

### A3. ~25 identical connect/commit/rollback blocks — one context manager

Every write function repeats the same 10-line template (`insert_enrollment` :1271 through
`delete_absence` :1706 — enrollments, auths ×3, transport ×4, availability ×3, one-off ×3,
emergency ×3, absences ×2, contact ×2, sync ×2…). Replace with:

```python
@contextmanager
def write_conn(db_path: str):
    conn = _connect(db_path)
    try:
        yield conn.cursor()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def delete_absence(record_id: int, db_path: str) -> None:
    with write_conn(db_path) as c:
        c.execute(DELETE_ABSENCE, (record_id,))
```

Saves ~250 lines and guarantees no future write op forgets the rollback.

### A4. Two entry points; `main.py` is broken

`main.py` calls `MainWindow()` with no arguments; the constructor requires
`(settings, settings_path)` (gui/main_window.py:116), so `python main.py` raises `TypeError`
immediately. `member_manager.py` is the real entry point (and what `CareManager.spec` builds).
Delete `main.py`, or make it a one-line shim calling `member_manager.main()` — a stale
launcher is a trap for the next contributor.

### A5. Sibling-repo coupling to `bsca-core` is unpinned

- `monthly_schedule.db` provides `build_connection_string` + 5 row mappers (db/members.py:11–18).
- Installed via `pip install -e "C:\Users\luald\OneDrive\Desktop\BSCA"` (requirements.txt comment).
- `tests/conftest.py:9–14` hard-codes `..\..\BSCA\scripts\test_dbs\populate_real_members.accdb`.

Risks: the two apps share a live schema contract with no version pin — a mapper change in
bsca-core silently changes what this app reads; nobody else can run the integration tests
without recreating your exact desktop layout. Suggestions: pin bsca-core (versioned wheel or
git tag), and read the test-DB location from an env var (`BSCA_TEST_DB`) with the current path
as fallback.

### A6. Schema assumptions are enforced inconsistently — add a startup check

The code tolerates a missing `TransportAuthorization` table (returns `[]`,
db/members.py:888–908) but *not* missing `OneOffAvailability` / `EmergencyContact` tables or
the newer `Authorization` columns — `get_member_context` queries them unconditionally
(:831–839), so against an older DB the member fails to load entirely with a raw ODBC error.
This is not hypothetical: the sibling repo's test fixture lacks four tables and three columns
that this app requires (tests/conftest.py exists precisely to patch them in), and my demo run
hit exactly this crash until I applied the same DDL.

Recommendation: on connect (or in Settings when picking a DB), run one schema probe and show a
single friendly dialog listing anything missing — ideally with a "create them now" button
reusing the DDL that already exists in tests/conftest.py. Per-feature silent degradation
(transport's approach) hides real setup problems; per-feature hard crash (one-off's approach)
blocks the whole member.

### A7. The audit log is per-machine, but the principle is "audit everything"

Events go to SQLite in `%APPDATA%\BSCA-Members` on *each staff PC*
(member_manager.py:default_events_db_path). With 1–3 concurrent users on a shared Access DB,
staff A never sees staff B's changes in "All Events", and a re-imaged PC silently loses its
history (30-day TTL notwithstanding). Options, in increasing effort:

1. Document the limitation in-app ("events recorded on this computer only") — one label.
2. Point `events_db_path` at the shared folder. SQLite over SMB is workable at this write rate
   if you keep the default rollback journal (avoid WAL on network shares).
3. Store events in a table inside the Access DB itself — same engine, same sharing semantics,
   one backup artifact.

Option 3 is the most coherent with the product goal; the `EventsTableWidget` already takes a
data source behind two functions (`open_db`/`query_events`), so the swap is contained.

### A8. Concurrency: last-write-wins with no detection

`update_contact` rewrites all 21 columns from the form snapshot (db/members.py:1226). If two
staff edit the same member simultaneously, the second save silently reverts the first one's
fields. At this team size a full locking scheme is overkill, but a cheap guard is worth it:
re-read the row inside the save and warn if any field changed since `_load_data` (the
`build_change_summary` machinery in member_tabs.py:221 already computes diffs — reuse it).

Related: the read-connection cache is keyed on file mtime (db/members.py:491). On SMB shares,
mtime propagation can lag seconds; a colleague's committed change may not be visible until the
next write locally drops the cache. Acceptable, but worth a comment and a manual "Refresh"
affordance in the UI (there is none today — F5 does nothing).

### A9. Everything runs on the UI thread

All pyodbc/DAO work is synchronous. With the DB on a network share, each save/load stalls the
event loop for its round-trip time; the photo/document DAO calls (get_member_photo,
db/members.py:571) are the heaviest. The connection cache already hides the worst cost for
browsing. If jank appears in production, move photo/document I/O to `QThreadPool` first; don't
pre-emptively thread the CRUD paths — the modal-dialog UX makes their latency visible but safe.

### A10. Smaller architectural notes

- **DAO SQL uses f-string interpolation** (db/members.py:584, 624, 654, 684, 715). The values
  are `int()`-coerced so injection is not reachable, but it contradicts the parameterized style
  used everywhere else; DAO supports parameters via QueryDefs if you ever pass strings.
- **`_after_auth_change`** (member_tabs.py:2236) performs 5 sequential connections (two
  read-modify-write syncs + a reload). Correct but chatty; a single `sync_contact_from_current_auth`
  doing one read + one write would halve the flashes on slow shares.
- **`main_window._show_member`** rebuilds the whole `MemberTabsWidget` per click, and
  `_populate_list` rebuilds all `QListWidgetItem`s per keystroke of the filter. Fine at 455
  members; just be aware these are the first places to optimize if the roster grows 10×.
- **Deferred imports** (`from db.members import …` inside methods) are used inconsistently —
  sometimes for startup speed, sometimes seemingly out of habit (e.g. `from datetime import
  date as _date` inside `_open_auth_dialog`, member_tabs.py:2279 — it's already imported at
  module level). Pick a policy: top-level imports except where a measured startup win exists.

---

## Code quality

### Q1. Error messages leak raw ODBC text to non-technical staff

Nearly every handler does `QMessageBox.critical(self, "…", str(exc))` (~28 sites in
member_tabs.py alone). A locked Access file — the most likely failure with 1–3 concurrent
users — surfaces as `('HY000', '[Microsoft][ODBC Microsoft Access Driver] The database has
been placed in a state…')`. Add one helper, e.g. `show_db_error(parent, exc)`, that maps the
common cases (file locked → "Someone else has the database open exclusively — try again in a
moment"; file missing → "The database file wasn't found — check Settings"; else generic +
"details were logged") and use it everywhere. This also creates the single choke point for
logging errors to the crash log, which currently only sees *unhandled* exceptions.

### Q2. Silent exception swallowing hides real failures

Justified for the photo (member_tabs.py:843 — placeholder fallback is documented). Less so:

- gui/main_window.py:257–259 — `get_terminated_center_ids` failure → all members silently
  render as active; staff can't tell the marks are missing.
- gui/main_window.py:369 — same, on refresh.
- gui/wizard/wizard.py:39 — `suggest_next_center_id` failure → the wizard's Center ID is just
  blank with no explanation.

Minimum fix: log these to the crash-log file (a `crash_log.log_warning()` helper) so field
issues are diagnosable; ideally show a soft inline notice.

### Q3. Duplication beyond the CRUD quintet

- The sidebar member-count HTML is duplicated with identical hard-coded colors in
  gui/main_window.py:272–274 and gui/events_view.py:51–55.
- `decode_auth_days` exists twice: db/members.py:371 and member_tabs.py:133 (plus a
  `decode_auth_days_static` wrapper at member_tabs.py:911).
- Day-checkbox rows are built by hand in at least three dialogs (auth :2293, transport :2630,
  wizard step_auths) — `WeekdayChips` exists but isn't reused for input.

### Q4. Parameter-list APIs are fragile

`update_contact` takes 22 positional-capable parameters (db/members.py:1226); `insert_member`
takes 17 (:1119). One transposition compiles fine and corrupts data. Accept a dict or a
`dataclass` (`ContactFields`) and keyword-only args (`*,`) at minimum.

### Q5. Miscellaneous

- gui/main_window.py:31 — docstring contains leftover working notes: *"('1/1/20' matches
  2001-? no — matches 2000s)"*.
- gui/main_window.py:100–104 — member names are interpolated into rich-text HTML unescaped; a
  name containing `&` or `<` breaks the terminated-row rendering. Use `html.escape()`.
- db/events.py:66–74 — the tuple-row fallback branch is dead code (`open_db` always sets
  `row_factory`); delete it or drop the row_factory.
- Info tab shows DOB / Admission Date as raw ISO (`2000-03-15`) while every editor uses
  MM/DD/YYYY — `get_member_context` stringifies dates (db/members.py:784, 801) instead of
  returning dates and letting the UI format. Pick MM/DD/YYYY everywhere for this audience.

---

## Design & UX (from the live walkthrough)

Screenshots referenced below were captured against a demo copy of the test DB
(dark + light themes, all tabs, wizard, quick search, settings).

### D1. Wrong empty-state message on launch — **trivial, do first**

With a database configured and 455 members loaded, the detail pane still reads **"No database
configured. Open ⚙ Settings to set the database path."** The placeholder text is set once at
build time (gui/main_window.py:197) and only updated when the DB path is *missing*
(:248–251). For staff, this reads as "the app is broken." When members are loaded it should
say something like *"Select a member from the list, or press Ctrl+K to search."*

### D2. No empty states anywhere else, either

Transportation, Availability Override, Absences, member Events, and All Events all render a
bare header row above a black void when empty. Zero-result sidebar searches show an empty
list with no message. For a non-technical audience every empty table should say what it is
and what to do: *"No transportation authorizations yet — click + Add."*, *"No events recorded
in the last 30 days."*, *"No members match 'mar'."* This is a small generic addition to
`_make_table_tab` (member_tabs.py:1751) + one label in the sidebar filter path.

### D3. The Terminate button is the loudest thing in the app

On the Enrollments tab, the active row's Status cell is a **full-width, solid-red "Terminate"
button** — visually an alarm banner, stretching the entire remaining table width. PRODUCT.md
asks for "calm, professional"; this is neither, and it puts a destructive action under the
largest click target on screen. Make it a compact outline/danger button sized to its text,
right-aligned in the cell; keep the confirmation dialog.

### D4. The window must be 1800px wide because the Auths table dictates it

`_apply_default_geometry` (gui/main_window.py:127) opens at 1800×920 explicitly so the
10-column Authorizations table fits — and even then a horizontal scrollbar appears. The table
drives the window instead of the reverse. Ideas: move `Created` behind the debug/row-ID
toggle (it's an audit field); merge `Status` into the Auth End cell (colored date/pill);
`Member ID` is duplicated on the Info tab and rarely differs per row. Three fewer columns
puts the tab comfortably inside ~1400px, which matters on the office's smaller/laptop screens.

### D5. Live theme switching leaves stale chrome

Switching dark↔light at runtime left the toolbar with the previous theme's background in my
run (screenshots 19/20) even though `QToolBar#main_toolbar` is themed in QSS
(gui/theme.py:312). Qt caches some native-styled chrome; after `apply_theme`, force a
repolish of the toolbar (and any widget using property-based selectors) the same way
`_update_db_indicator` already does for its label, or simply recommend a restart in the
Settings dialog. Worth a quick manual verification in the packaged app.

### D6. 39 hard-coded hex colors bypass the token system

`grep '#[0-9a-f]{6}'` outside theme.py: events_view.py (8 — the event-type badge palette is
dark-theme-only and will render illegible chips in light mode), wizard (7), member_tabs (6),
time_range_editor (5), profile_print (4), main_window (3), address_autocomplete (3),
step_contact (2), step_auths (1). Move these into the DARK/LIGHT token dicts (or a
`badge_colors(theme)` helper) so light mode stays coherent — the theme system is good;
these are leaks around it.

### D7. Wizard combo boxes are indistinguishable from text fields

In step 1, **Gender** and **Health Plan** render as blank boxes identical to the line edits,
with no visible dropdown arrow (dark theme). Non-technical users will try to type into them.
Check the QSS `QComboBox::drop-down` / `::down-arrow` rules under dark mode; an explicit
arrow glyph and a slightly different background would restore the affordance.

### D8. Mixed editing affordances on the Info tab

Filled fields render as plain text (edit via hover-pencil / double-click); empty fields render
as input boxes. The one-at-a-time inline edit with explicit Save/Discard is a good, safe
pattern — but its discoverability relies on hover. Consider a persistent, subtle pencil on
all editable fields (not just hover/empty) or a one-line hint under the header
("Double-click any field to edit").

### D9. Small polish items

- **Settings dialog**: the API key is masked with an Edit/Hide toggle — good — but the key is
  stored in plain JSON in `%APPDATA%` (settings.py). Fine for an office tool; consider at
  least noting it, or use Windows DPAPI (`win32crypt.CryptProtectData` — pywin32 is already a
  dependency) if the key ever gains billing scope.
- **Quick search (Ctrl+K)** is excellent and staff-friendly; the footer hint line is a nice
  touch. Consider also opening it from an empty-state click.
- **Header warning chips** ("Authorization Expired", "Missing: Emergency Contact") are the
  best UX in the app — they make incompleteness visible without blocking. Consider making
  them clickable (jump to the relevant tab), which the cross-tab navigation plumbing
  (member_tabs.py:2877–2941) already supports.
- **Sidebar counts** use a 10px font (gui/main_window.py:185) — small for the 40–60+ age
  bracket typical of admin staff; 12px minimum.
- **Date formats** vary between ISO in tables (2026-06-02) and MM/DD/YYYY in editors — see Q5;
  standardize on MM/DD/YYYY for display.

---

## Tests & tooling

- **Suite**: ~90 files, **418 tests, all passing in ~26s** (run during this review). The unit
  layer (pure functions, widget behavior via pytest-qt) is fast and well-targeted. Integration tests hit a real Access DB and self-skip when it's
  absent — good — but its location is a hard-coded sibling path (see A5).
- **Gaps worth filling**: an end-to-end wizard save (create → verify rows in all four
  tables); a locked-database error path (open the file exclusively in the test, assert the
  friendly message once Q1 is done); light-theme snapshot of the event badges (D6).
- **No CI config** is present. Even a minimal GitHub Actions/pre-commit running the
  non-integration tests on push would protect the refactors proposed above.
- **Packaging**: CareManager.spec is sound (icon bundled, QtNetwork hidden-import handled).
  Note `upx=True` occasionally triggers antivirus false-positives on Windows; if staff PCs
  ever quarantine the exe, disable UPX first.

---

## Suggested sequencing

1. **Day 1 fixes**: delete/fix `main.py` (A4); placeholder text (D1); Terminate button
   styling (D3); escape delegate HTML (Q5); docstring cleanup.
2. **Quick wins week**: empty states (D2); `write_conn` context manager (A3); central
   `show_db_error` (Q1) + stop swallowing the terminated-ids failure (Q2); sidebar font size.
3. **Extraction**: formatters/domain out of db/members.py (A2), then member_tabs split (A1),
   one tab at a time with the suite green between steps.
4. **Product decisions** (need your call, not just code): shared vs per-machine event log
   (A7); schema-check-on-connect UX (A6); column diet for the Auths table (D4).
