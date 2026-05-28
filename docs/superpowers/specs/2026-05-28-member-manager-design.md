# BSCA Member Manager — Design Spec

**Date:** 2026-05-28
**Repo:** BSCA-Members (separate from BSCA schedule generator)
**Shared dependency:** `bsca-core` installed via `pip install -e ../BSCA`
**Stack:** Python 3.11, PyQt6, QSS stylesheets, SQLite (events only)

---

## Overview

A standalone desktop application for non-technical administrative staff to manage member records in the BSCA Access database. Staff can add new members, maintain their information, record authorizations, availability, and absences, and review an audit history of all changes.

The app reads and writes the same `.accdb` database used by the monthly schedule generator. It does not replace the schedule generator — it is a companion tool.

---

## Entry Point

```
member_manager.py   ← python member_manager.py
```

Settings (database path, theme preference) are stored in a local `bsca_members_settings.json` file next to the executable, matching the pattern of the schedule generator.

---

## Main Window Layout

Side-by-side two-panel layout. No modal dialogs for the main editing workflow.

```
┌─────────────────────────────────────────────────────────┐
│  titlebar                                               │
├──────────────┬──────────────────────────────────────────┤
│  Sidebar     │  Detail panel                           │
│  (210px)     │                                         │
│              │  Member header + warning badge          │
│  + Add New   │  ─────────────────────────────          │
│  Member      │  Tabs: Info | Enrollments | Auths |     │
│              │        Availability | Absences | Events  │
│  Search      │                                         │
│  ──────────  │  Tab content (editable form)            │
│  Member list │                                         │
│  (scrollable)│  [Discard]  [Save Changes]              │
│              │                                         │
│  ── ──────── │                                         │
│  All Events  │                                         │
└──────────────┴──────────────────────────────────────────┘
```

### Sidebar

- **+ Add New Member** button at top (opens wizard)
- **Search box** — filters list by name or Center ID, case-insensitive
- **Member list** — each row shows Last, First name + Center ID + Health Plan; clicking selects and loads the detail panel
- **All Events** link pinned to bottom — switches the detail panel to the global events log

### Detail panel — selected member

Six tabs:

| Tab | Content |
|---|---|
| **Info** | First Name, Last Name, Health Plan (dropdown), Center ID (read-only), Address |
| **Enrollments** | Table of enrollment periods; Add / Delete row buttons; date pickers |
| **Authorizations** | Table of auth records; Add / Delete; auth start/end, effective start/end (optional), Mon–Fri checkboxes |
| **Availability** | Table of availability rows; Add / Delete; Day dropdown, start time, end time, effective start/end dates |
| **Absences** | Table of absence records; Add / Delete; Leave Type dropdown, start date, end date |
| **Events** | Read-only audit log for this member only (see Events section) |

**Warning state:** If a member has no authorizations or no availability records, a warning badge appears in the member header and the affected tabs are flagged with ⚠. The badge reads: "Missing: Authorizations, Availability" (or whichever subset applies).

**Unsaved changes:** Navigating away from a tab or selecting a different member when there are unsaved edits prompts a confirmation dialog: "You have unsaved changes. Discard them?"

---

## Add New Member Wizard

Four-step wizard opened as a dialog from the "+ Add New Member" button. Top progress bar with numbered circles and step labels. Back/Next navigation. Cancel at any point discards all entries.

### Step 1 — Contact Info

Required fields: First Name, Last Name, Center ID, Health Plan
Optional fields: Address

- **Center ID**: free text, validated as a positive integer not already in the database. Shows inline error if duplicate or non-integer.
- **Health Plan**: dropdown — AE, Aetna, Anthem, BCBS, ES, HC, HF, HOF, VCM

### Step 2 — Enrollment

- **Enrollment Start**: date picker, defaults to today's date
- **Enrollment End**: date picker, optional — leave blank for ongoing

When the member is saved at Step 4, an enrollment record is automatically created with these dates. Staff do not need to manually add an enrollment row later.

### Step 3 — Authorizations & Availability (skippable)

Warning banner: "This step is optional. You can skip it and add authorizations and availability later, but the member won't appear on schedules until this information is filled in."

Two side-by-side sub-panels:

**Authorization sub-panel**
- Auth Start / Auth End (date pickers, required if not skipping)
- Days Authorized: Mon Tue Wed Thu Fri toggle chips (at least one required if not skipping)
- Effective Start / Effective End: optional overrides (collapsed by default, expandable)

**Availability sub-panel**
- Add rows per day: Day (Mon–Fri dropdown), Start Time, End Time
- "+ Add day" link to add more rows

"Skip for now" button proceeds to Step 4 without saving any auth/availability data.

### Step 4 — Review & Save

Read-only summary of all entered data. "Back" returns to step 3. "Create Member" writes all records to the database in a single transaction:

1. INSERT into CONTACTS
2. INSERT into ENROLLMENT
3. INSERT into AUTHORIZATION (if not skipped)
4. INSERT into AVAILABILITY (if not skipped)
5. Write NEW event to events.db

On success: dialog closes, new member appears selected in the member list. On database error: show error message, stay on Step 4.

---

## Leave Type Dropdown

Used in the Absences tab. Fixed options:

- Vacation
- Medical
- Hospitalization
- Family Emergency
- Holiday
- Other

---

## Events Log

### Storage

Local SQLite database at `events.db` next to the app settings file. Not part of the Access database. Schema:

```sql
CREATE TABLE events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,          -- ISO 8601 timestamp
    event_type  TEXT NOT NULL,          -- NEW | EDIT | AUTH | ABS | AVAIL | ENROLL
    center_id   INTEGER NOT NULL,
    member_name TEXT NOT NULL,          -- "Last, First" snapshot at time of event
    description TEXT NOT NULL           -- human-readable summary of the change
);
```

**TTL:** On every app launch, DELETE all rows where `ts < (today - 30 days)`.

### Event types and when they fire

| Type | Fires when |
|---|---|
| NEW | Member created via wizard |
| EDIT | Info tab saved (only if values changed; records which fields changed and old/new values) |
| AUTH | Authorization row added or deleted |
| AVAIL | Availability row added or deleted |
| ABS | Absence row added or deleted |
| ENROLL | Enrollment row added or deleted |

### Global Events view

Accessed via "All Events" in the sidebar. Replaces the detail panel content with:

- Title: "All Events" + "Auto-deletes after 30 days" label
- Filter/search box (searches member name and description text)
- Chronological list of all events, newest first
- Each row: timestamp (monospace) | colored type badge | description

### Per-member Events tab

Same list, filtered to `center_id = selected member`. Same row format. Read-only.

---

## Theme

Two themes: **Dark** and **Light**. Toggled in a settings dialog accessible from the titlebar.

Both themes use the same OKLCH design token system with a muted indigo accent (`oklch(0.58 0.14 260)` dark / `oklch(0.46 0.15 260)` light). A single QSS stylesheet per theme is loaded at startup and on toggle. Theme preference is persisted in `bsca_members_settings.json`.

---

## Settings Dialog

Accessible from a gear icon in the titlebar. Fields:

- **Database path** — path to the `.accdb` file, with Browse button. Same file used by the schedule generator.
- **Theme** — Dark / Light radio buttons (applies immediately on change)
- **Events database path** — path to `events.db`, with Browse button (default: same directory as settings file)

---

## File Structure

```
BSCA-Members/
├── member_manager.py          ← entry point
├── PRODUCT.md                 ← impeccable context
├── requirements.txt
├── gui/
│   ├── __init__.py
│   ├── main_window.py         ← MainWindow, sidebar, detail panel
│   ├── member_tabs.py         ← all six tab widgets
│   ├── settings_dialog.py     ← settings dialog
│   ├── events_view.py         ← global events log widget
│   ├── theme.py               ← QSS loader, token constants
│   └── wizard/
│       ├── __init__.py
│       ├── wizard.py          ← QWizard subclass, orchestrates steps
│       ├── step_contact.py    ← Step 1
│       ├── step_enrollment.py ← Step 2
│       ├── step_auths.py      ← Step 3
│       └── step_review.py     ← Step 4
└── db/
    ├── __init__.py
    ├── members.py             ← read/write CONTACTS, ENROLLMENT, AUTHORIZATION, AVAILABILITY, ABSENCES
    └── events.py              ← SQLite events.db read/write, TTL purge
```

`monthly_schedule.*` is imported from `bsca-core` (installed package) — not duplicated here.

---

## Error Handling

- **Database unreachable at launch**: show a blocking error dialog with path and a "Open Settings" button. App stays open but disabled until a valid path is configured.
- **Duplicate Center ID**: inline validation on the wizard Center ID field before Next is enabled.
- **Save failure**: show error message in-place (status bar or inline), do not close dialog or clear form.
- **Events write failure**: log to stderr, do not surface to user (non-critical path).
