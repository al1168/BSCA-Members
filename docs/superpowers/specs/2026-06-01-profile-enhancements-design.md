# Profile Page Enhancements — Design Spec

**Date:** 2026-06-01
**Repo:** BSCA-Members

---

## Overview

Three targeted improvements to the member profile UI:

1. **Photo** — display the member's photo from the Access Attachment field in the member header
2. **Expanded Info tab** — show all meaningful Contacts columns in grouped sections, plus a read-only Schedule Summary pulled from the Authorization and Enrollment tables
3. **Larger wizard** — increase the Add New Member dialog minimum size so all text fits

---

## 1. Photo Display

### Data access

Access's Attachment field type is not readable via pyodbc (it returns `1` — the attachment count). It must be read via **DAO** using `pywin32`:

```python
dao = win32com.client.Dispatch("DAO.DBEngine.120")
db  = dao.OpenDatabase(db_path)
rs  = db.OpenRecordset(f"SELECT * FROM [Contacts] WHERE [Center ID]={center_id}")
photo_field   = rs.Fields("Photo")
attachment_rs = photo_field.Value          # Recordset2
file_data     = attachment_rs.Fields("FileData").Value  # memoryview → bytes
```

File is named `{center_id}.jpeg` and is typically ~230 KB.

### New function: `db/members.py`

```python
def get_member_photo(center_id: int, db_path: str) -> bytes | None:
```

- Opens a DAO connection, reads the first attachment from `[Photo]`
- Returns `bytes` (JPEG) or `None` if no attachment or any error
- Failures are silently swallowed (non-critical path)

`pywin32` added to `requirements.txt`.

### Display

- Shown in the **member header**, left of the name
- `QLabel` with a fixed 80×80 px `QPixmap`, scaled with `Qt.KeepAspectRatioByExpanding`, clipped to a rounded rectangle via `QLabel` stylesheet (`border-radius: 40px`)
- Fallback: gray placeholder icon (drawn with `QPainter` if no photo)
- Photo loaded once when `MemberTabsWidget` is constructed; not reloaded on tab switch

---

## 2. Expanded Info Tab

### Data fetch

`get_member_context()` in `db/members.py` extended to fetch **all** meaningful Contacts columns in the same single pyodbc connection (no extra round-trips). The `SELECT` query replaces the narrow 6-column fetch.

Columns fetched:

| Column | Notes |
|---|---|
| Center ID | read-only identifier |
| Last Name, First Name, Chinese Name | editable |
| Gender, DOB | editable |
| Member ID | editable |
| Health Plan | dropdown (HEALTH_PLANS) |
| Medicaid, Medicare, SSN | editable text |
| Language | editable |
| Case Manager | editable |
| Home Tell, Cell | editable |
| Address | editable |
| Emergency | editable |
| PCP, Hospital, HHA | editable |
| Admission Date | editable |
| Notes | editable, multi-line |

**Skipped** (legacy/internal): SADC, SADC Auth, Auth BGN, Auth EXP, TRANS Auth, SADC_Latest, Long Lat.

The `ctx["member"]` dict returned by `get_member_context()` gains all these keys. Keys missing from the DB row default to `""`.

### Schedule Summary section (read-only)

Derived from `ctx["enrollments"]` and `ctx["authorizations"]` — no new DB queries:

- **Enrollment Start** — earliest `start_date` across all enrollment rows
- **Active Authorization** — the auth row whose `effective_start`–`effective_end` window covers today; shows date range and `auth_days` decoded to day names (Mon Tue …). Shows "None" if no active auth.

### Layout: grouped scrollable form

The Info tab content is wrapped in a `QScrollArea`. Fields are organized into collapsible `QGroupBox` sections:

| Section | Fields |
|---|---|
| **Identity** | First Name, Last Name, Chinese Name, Gender, DOB, Center ID (read-only), Member ID |
| **Contact** | Address, Home Tell, Cell, Emergency |
| **Medical** | Health Plan, Medicaid, Medicare, SSN, PCP, Hospital, HHA, Language |
| **Care** | Case Manager, Admission Date, Notes |
| **Schedule Summary** | Enrollment Start, Active Authorization (both read-only) |

Save Changes / Discard buttons remain at the bottom of the tab (outside the scroll area, always visible).

### `update_contact()` extension

`update_contact()` in `db/members.py` extended to write all editable fields (not just First/Last/Plan/Address). Single `UPDATE [Contacts] SET ...` statement.

### Dirty tracking

`_setup_dirty_tracking()` extended to connect `textChanged` / `currentIndexChanged` signals for all new editable widgets.

---

## 3. Wizard Minimum Size

`gui/wizard/wizard.py` line: `self.setMinimumSize(560, 520)` → `self.setMinimumSize(700, 640)`.

---

## Files Changed

| File | Change |
|---|---|
| `db/members.py` | Add `get_member_photo()`, extend `get_member_context()` SELECT + return dict, extend `update_contact()` |
| `gui/member_tabs.py` | Photo in header, expanded grouped Info tab, extended dirty tracking |
| `gui/wizard/wizard.py` | Minimum size bump |
| `requirements.txt` | Add `pywin32` |
