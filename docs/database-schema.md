# Database Schema Reference

Tables, fields, and types the Care Manager app expects. Last updated 2026-08-27.

The app uses two databases:

1. **The BSCA Access database** (`.accdb`, via pyodbc/ACE and DAO for attachments) — all member data. Path is user-configurable in Settings.
2. **A local SQLite events log** — the per-machine change history shown in the Events tab.

Type names below are Access DDL types as used in this repo's test fixtures
(`tests/conftest.py`). In the Access table designer they map as: `LONG` = Number
(Long Integer), `TEXT(255)` = Short Text, `MEMO` = Long Text, `DATETIME` =
Date/Time, `AUTOINCREMENT` = AutoNumber, Attachment = Attachment. Types marked
*(inferred)* are not created by any script in this repo — they are what the
app's reads/writes assume about the pre-existing production tables.

The subset of tables/columns the app **requires** (checked once per database at
startup by `missing_schema()`) is defined in `REQUIRED_SCHEMA` in
[db/members.py](../db/members.py). Everything else degrades gracefully when
absent (e.g. the Transportation Document feature only appears when the column
exists).

---

## Access database

### Contacts — one row per member

The member key is **Center ID** (not the AutoNumber). Rows with a NULL
Center ID are skipped by the app.

| Field | Type | Notes |
|---|---|---|
| Center ID | LONG *(inferred)* | Member key used by every other table. 5-digit scheme (10000–99999) for new members; IDs ending in 4 are skipped when suggesting the next ID. Required at startup. |
| Last Name | TEXT(255) *(inferred)* | Required at startup. |
| First Name | TEXT(255) *(inferred)* | Required at startup. |
| Chinese Name | TEXT(255) *(inferred)* | |
| Gender | TEXT(255) *(inferred)* | |
| DOB | DATETIME *(inferred)* | Stored as a real Date/Time value (integration test asserts this); the app also tolerates ISO or `M/D/YYYY` text in legacy rows. Displayed as MM/DD/YYYY. Required at startup. |
| Member ID | TEXT(255) *(inferred)* | Health-plan member number. Can be auto-synced from the current authorization. |
| Health Plan | TEXT(255) *(inferred)* | One of `AE, BCBS, ES, HC, HF, HOF, VCM` for new rows (legacy values like "Aetna"/"Anthem" still render). Auto-synced from the current authorization. Required at startup. |
| Medicaid | TEXT(255) *(inferred)* | Format `AAdddddA` (2 letters, 5 digits, 1 letter), uppercased. |
| Medicare | TEXT(255) *(inferred)* | MBI format (11 chars, 4-3-4 with optional dashes), uppercased, enforced on edit. Legacy rows hold ids in other formats; an untouched legacy value never blocks saving the record. |
| SSN | TEXT(255) *(inferred)* | Stored formatted `xxx-xx-xxxx`. |
| Language | TEXT(255) *(inferred)* | |
| Case Manager | TEXT(255) *(inferred)* | |
| Home Tell | TEXT(255) *(inferred)* | Phone, stored formatted `(xxx)-xxx-xxxx`. |
| Cell | TEXT(255) *(inferred)* | Phone, same format. |
| Address | TEXT(255) *(inferred)* | |
| Long Lat | TEXT(255) *(inferred)* | `"lng,lat"` string written when an address is picked from autocomplete. |
| Emergency | TEXT(255) *(inferred)* | Legacy free-text emergency info (structured contacts live in EmergencyContact). |
| PCP | TEXT(255) *(inferred)* | Primary care provider. |
| Hospital | TEXT(255) *(inferred)* | |
| HHA | TEXT(255) *(inferred)* | Home health aide info (shown as the HHA note card). |
| Admission Date | DATETIME *(inferred)* | Written as text from the edit form; read for display only. |
| Notes | MEMO *(inferred)* | |
| alt_id | LONG | Optional alternative member id, 0 ≤ value < 2³¹. **Encrypted at rest** with format-preserving encryption (see [db/alt_id_crypto.py](../db/alt_id_crypto.py)); the stored number is the ciphertext. Required at startup. |
| Photo | Attachment | Member photo (JPEG/PNG). Read/written via DAO only — pyodbc cannot access Attachment fields. |

### Enrollment — enrollment periods per member

| Field | Type | Notes |
|---|---|---|
| ID | AUTOINCREMENT PK *(inferred)* | Row key for edits/deletes. |
| Center ID | LONG *(inferred)* | FK → Contacts.[Center ID]. Required at startup. |
| start_date | DATETIME *(inferred)* | Required at startup. |
| end_date | DATETIME, nullable *(inferred)* | NULL = ongoing. A member whose **latest** enrollment has an end date ≤ today is "Terminated". Required at startup. |

### Authorization — care authorizations per member

| Field | Type | Notes |
|---|---|---|
| ID | AUTOINCREMENT PK *(inferred)* | |
| Center ID | LONG *(inferred)* | FK → Contacts.[Center ID]. Required at startup. |
| auth_start | DATETIME *(inferred)* | Required at startup. |
| auth_end | DATETIME *(inferred)* | Drives the expiring/expired notifications (latest auth_end per member; NULL = open-ended, ignored). Required at startup. |
| effective_start | DATETIME, nullable *(inferred)* | Optional override window for "in effect today". Cleared (set NULL) on every auth edit so the window follows the edited dates. |
| effective_end | DATETIME, nullable *(inferred)* | Same. |
| auth_days | TEXT(255) *(inferred)* | Comma-separated weekday numbers, `"1,3,5"` (1=Mon … 7=Sun); empty string = none. Required at startup. |
| Health Plan | TEXT(255) *(inferred)* | Plan this auth was issued under. Required at startup. |
| created_at | DATETIME | Set to now() on insert; NULL on legacy rows. Required at startup. |
| Member ID | TEXT(255) | Plan member number on the auth (seeds/syncs Contacts.[Member ID]). Required at startup. |
| auth_number | TEXT(255) *(inferred)* | Authorization number from the plan. Required at startup. |
| Plan Type | TEXT(255) | `""`, `"MAP"`, `"MLTC"`, or `"N/A"` (blank kept so legacy rows aren't force-migrated). Required at startup. |
| Document | Attachment | Attached authorization document (PDF/image), via DAO. |

### TransportAuthorization — transportation authorizations

Structurally identical to Authorization **minus [Plan Type]**. Kept separate so
transportation never affects the scheduler's eligibility logic. Only
Center ID / auth_start / auth_end are required at startup; the app returns no
transport rows (rather than erroring) if the whole table is missing.

| Field | Type | Notes |
|---|---|---|
| ID | AUTOINCREMENT PK *(inferred)* | |
| Center ID | LONG *(inferred)* | FK → Contacts.[Center ID]. |
| auth_start / auth_end | DATETIME *(inferred)* | Mirror the linked care auth's dates when created from the wizard. |
| effective_start / effective_end | DATETIME, nullable *(inferred)* | Always written NULL; nothing reads them for transport. |
| auth_days | TEXT(255) *(inferred)* | Same `"1,3,5"` encoding. |
| Health Plan | TEXT(255) *(inferred)* | |
| created_at | DATETIME *(inferred)* | |
| Member ID | TEXT(255) *(inferred)* | |
| auth_number | TEXT(255) *(inferred)* | |
| Document | Attachment — **optional** | The Transportation tab's Document feature only appears when this column exists. |

### AuthEdge — care ↔ transport junction

Links a transport auth to its care auth. A transport auth has at most one edge
(edges are cleared and rewritten on relink, and deleted with the transport auth).

| Field | Type | Notes |
|---|---|---|
| ID | AUTOINCREMENT PK *(inferred)* | |
| authorization_id | LONG *(inferred)* | FK → Authorization.ID. Required at startup. |
| transport_authorization_id | LONG *(inferred)* | FK → TransportAuthorization.ID. Required at startup. |

### Availability — recurring weekly availability

| Field | Type | Notes |
|---|---|---|
| ID | AUTOINCREMENT PK *(inferred)* | |
| Center ID | LONG *(inferred)* | FK → Contacts.[Center ID]. Required at startup. |
| effective_start_date | DATETIME *(inferred)* | |
| effective_end_date | DATETIME, nullable *(inferred)* | NULL = open-ended. |
| Day Of Week | LONG *(inferred)* | 1=Mon … 7=Sun. Required at startup. |
| avail_start | DATETIME *(inferred)* | **Time-only** value stored on the Access epoch date 1899-12-30 (e.g. `1899-12-30 08:30`); read back as `"HH:mm"`. Required at startup. |
| avail_end | DATETIME *(inferred)* | Same encoding. Required at startup. New members default to 08:00–16:00 all seven days. |

### Absences — leave records

| Field | Type | Notes |
|---|---|---|
| ID | AUTOINCREMENT PK *(inferred)* | |
| Center ID | LONG *(inferred)* | FK → Contacts.[Center ID]. Required at startup. |
| Leave Type | TEXT(255) *(inferred)* | One of `Vacation, Medical, Hospitalization, Family Emergency, Holiday, Other`. Required at startup. |
| Start_Date | DATETIME *(inferred)* | Note the underscore names (unlike Enrollment's `start_date`). Required at startup. |
| End_Date | DATETIME *(inferred)* | Required at startup. |
| Notes | MEMO | Required at startup. |

### OneOffAvailability — single-day unavailable/changed windows

Created by this app (DDL in [tests/conftest.py](../tests/conftest.py)).

| Field | Type | Notes |
|---|---|---|
| ID | AUTOINCREMENT PK | |
| Center ID | LONG | FK → Contacts.[Center ID]. Required at startup. |
| date | DATETIME | The single day this row applies to. Required at startup. |
| avail_start | DATETIME | Time-only on 1899-12-30, same as Availability. Required at startup. |
| avail_end | DATETIME | Same. Required at startup. |
| Notes | MEMO | |

### EmergencyContact — structured emergency contacts

Created by this app (DDL in [tests/conftest.py](../tests/conftest.py)).

| Field | Type | Notes |
|---|---|---|
| ID | AUTOINCREMENT PK | |
| Center ID | LONG | FK → Contacts.[Center ID]. Required at startup. |
| Full Name | TEXT(255) | Required at startup. |
| Phone Number | TEXT(255) | Stored formatted `(xxx)-xxx-xxxx`. Required at startup. |
| Relationship | TEXT(255) | |

### Holidays — company-wide closed dates

Created by the BSCA Setup chain (`scripts/create_supporting_tables.py`).
Edited here through **🏢 Company Calendar**.

| Field | Type | Notes |
|---|---|---|
| ID | AUTOINCREMENT PK | |
| holiday_name | TEXT(255) | Required at startup. |
| date | DATETIME | Date only. One row per closed date. Required at startup. |

The scheduler generates no times on a holiday (blank day, not an absence).

### OperatingDays — weekly hours, one row per open weekday

Created by the BSCA Setup chain and seeded Monday–Sunday 08:00–16:00 by
`scripts/seed_operating_days.py` when empty. Edited here through
**🏢 Company Calendar**; "Save Hours" rewrites the whole table.

| Field | Type | Notes |
|---|---|---|
| ID | AUTOINCREMENT PK | |
| day_name | TEXT(20) | `Monday` … `Sunday`. Required at startup. |
| Day Of Week | LONG | 1 = Monday … 7 = Sunday (Availability's convention). The scheduler matches on this, not on `day_name`. Required at startup. |
| opening_time | DATETIME | Time-only on 1899-12-30, same as Availability. Required at startup. |
| closing_time | DATETIME | Same; later than `opening_time`. Required at startup. |

A weekday with no row is **closed**. On an open day these times are the
scheduler's day bounds (earliest Time-In / latest Time-Out).

---

## SQLite events log

Local per-machine change history (Events tab). Created automatically by
[db/events.py](../db/events.py); rows older than 30 days are purged.

### events

| Field | Type | Notes |
|---|---|---|
| id | INTEGER PRIMARY KEY AUTOINCREMENT | |
| ts | TEXT NOT NULL | ISO-8601 timestamp, second precision. |
| event_type | TEXT NOT NULL | One of `NEW, EDIT, AUTH, ABS, AVAIL, ENROLL`. |
| center_id | INTEGER NOT NULL | Member the event concerns. |
| member_name | TEXT NOT NULL | "Last, First" snapshot at event time. |
| description | TEXT NOT NULL | Human-readable summary of the change. |

---

## Conventions recap

- **Member key:** `Contacts.[Center ID]` (LONG); every child table carries it.
- **Row key:** every Access child table has an AutoNumber `[ID]` used for update/delete.
- **Dates:** Access Date/Time; displayed/entered as MM/DD/YYYY.
- **Times of day:** stored as time-only DATETIME on 1899-12-30; handled in code as 24-hour `"HH:mm"`, shown as 12-hour.
- **Weekdays:** integers 1=Monday … 7=Sunday; sets encoded as comma-separated text (`"1,3,5"`).
- **Attachments** (Photo, Document): readable only through DAO (`DAO.DBEngine.120`), not pyodbc; the blob has an Access header stripped by its declared length.
- **NULL text** is normalized to `""` when read.
