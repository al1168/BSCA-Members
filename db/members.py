"""Read/write helpers for the BSCA Access database.

Read connections reuse bsca-core's build_connection_string.
Write operations open their own connection with autocommit=False
so multiple INSERTs can be wrapped in a single transaction.
"""
import os
from datetime import date, datetime

from monthly_schedule.db import (
    build_connection_string,
    map_member_row,
    map_enrollment_row,
    map_authorization_row,
    map_availability_row,
    map_absence_row,
)

# Selectable health plans. "Aetna" (== AE) and "Anthem" (== BCBS) are dropped as
# duplicates; their colors remain in PLAN_COLORS so any not-yet-migrated rows
# still render a badge.
HEALTH_PLANS = ("AE", "BCBS", "ES", "HC", "HF", "HOF", "VCM")

LEAVE_TYPES = (
    "Vacation", "Medical", "Hospitalization",
    "Family Emergency", "Holiday", "Other",
)

ALL_MEMBERS_QUERY = (
    "SELECT [Center ID], [Last Name], [First Name], [Health Plan] "
    "FROM [Contacts] ORDER BY [Last Name], [First Name]"
)

INSERT_CONTACT = (
    "INSERT INTO [Contacts] ([Center ID], [Last Name], [First Name], "
    "[Health Plan], [Address], [Long Lat], [Member ID], [Home Tell], [Cell], "
    "[DOB], [Gender]) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)


def format_phone(value) -> str:
    """Render a US phone as (xxx)-xxx-xxxx when it has exactly 10 digits;
    otherwise return the input unchanged (trimmed). Idempotent; never raises."""
    s = "" if value is None else str(value).strip()
    digits = "".join(ch for ch in s if ch.isdigit())
    if len(digits) == 10:
        return f"({digits[:3]})-{digits[3:6]}-{digits[6:]}"
    return s


def format_date_only(value) -> str:
    """Drop a trailing clock time so a date stored as a datetime
    ('2000-03-15 00:00:00') shows as just the date ('2000-03-15'). Leaves plain
    date strings untouched; never raises."""
    s = "" if value is None else str(value).strip()
    head, sep, tail = s.partition(" ")
    if sep and ":" in tail:        # the part after the space is a clock time
        return head
    return s

SET_LONG_LAT = "UPDATE [Contacts] SET [Long Lat]=? WHERE [Center ID]=?"

UPDATE_CONTACT = (
    "UPDATE [Contacts] SET "
    "[Last Name]=?, [First Name]=?, [Chinese Name]=?, [Gender]=?, [DOB]=?, "
    "[Member ID]=?, [Health Plan]=?, [Medicaid]=?, [Medicare]=?, [SSN]=?, "
    "[Language]=?, [Case Manager]=?, [Home Tell]=?, [Cell]=?, [Address]=?, "
    "[Emergency]=?, [PCP]=?, [Hospital]=?, [HHA]=?, [Admission Date]=?, [Notes]=? "
    "WHERE [Center ID]=?"
)

INSERT_ENROLLMENT = (
    "INSERT INTO [Enrollment] ([Center ID], [start_date], [end_date]) "
    "VALUES (?, ?, ?)"
)

DELETE_ENROLLMENT = "DELETE FROM [Enrollment] WHERE [ID]=?"
UPDATE_ENROLLMENT_END = "UPDATE [Enrollment] SET [end_date]=? WHERE [ID]=?"

INSERT_AUTHORIZATION = (
    "INSERT INTO [Authorization] ([Center ID], [auth_start], [auth_end], "
    "[effective_start], [effective_end], [auth_days], [Health Plan], [created_at], "
    "[Member ID]) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
)

DELETE_AUTHORIZATION = "DELETE FROM [Authorization] WHERE [ID]=?"

UPDATE_AUTHORIZATION = (
    "UPDATE [Authorization] SET [auth_start]=?, [auth_end]=?, "
    "[auth_days]=?, [Health Plan]=?, [Member ID]=? WHERE [ID]=?"
)

AUTHORIZATION_SELECT = (
    "SELECT [ID],[Center ID],[auth_start],[auth_end],"
    "[effective_start],[effective_end],[auth_days],[Health Plan],[created_at],"
    "[Member ID] "
    "FROM [Authorization] WHERE [Center ID]=?"
)

INSERT_AVAILABILITY = (
    "INSERT INTO [Availability] ([Center ID], [effective_start_date], "
    "[effective_end_date], [Day Of Week], [avail_start], [avail_end]) "
    "VALUES (?, ?, ?, ?, ?, ?)"
)

DELETE_AVAILABILITY = "DELETE FROM [Availability] WHERE [ID]=?"

UPDATE_AVAILABILITY = (
    "UPDATE [Availability] SET [avail_start]=?, [avail_end]=?, "
    "[effective_start_date]=?, [effective_end_date]=? WHERE [ID]=?"
)

INSERT_ABSENCE = (
    "INSERT INTO [Absences] ([Center ID], [Leave Type], [Start_Date], [End_Date]) "
    "VALUES (?, ?, ?, ?)"
)

DELETE_ABSENCE = "DELETE FROM [Absences] WHERE [ID]=?"

INSERT_ONE_OFF_AVAILABILITY = (
    "INSERT INTO [OneOffAvailability] ([Center ID], [date], "
    "[avail_start], [avail_end], [Notes]) VALUES (?, ?, ?, ?, ?)"
)

UPDATE_ONE_OFF_AVAILABILITY = (
    "UPDATE [OneOffAvailability] SET [date]=?, [avail_start]=?, "
    "[avail_end]=?, [Notes]=? WHERE [ID]=?"
)

DELETE_ONE_OFF_AVAILABILITY = "DELETE FROM [OneOffAvailability] WHERE [ID]=?"

ONE_OFF_AVAILABILITY_SELECT = (
    "SELECT [ID],[Center ID],[date],[avail_start],[avail_end],[Notes] "
    "FROM [OneOffAvailability] WHERE [Center ID]=?"
)

INSERT_EMERGENCY_CONTACT = (
    "INSERT INTO [EmergencyContact] ([Center ID], [Full Name], "
    "[Phone Number], [Relationship]) VALUES (?, ?, ?, ?)"
)

UPDATE_EMERGENCY_CONTACT = (
    "UPDATE [EmergencyContact] SET [Full Name]=?, [Phone Number]=?, "
    "[Relationship]=? WHERE [ID]=?"
)

DELETE_EMERGENCY_CONTACT = "DELETE FROM [EmergencyContact] WHERE [ID]=?"

EMERGENCY_CONTACT_SELECT = (
    "SELECT [ID],[Center ID],[Full Name],[Phone Number],[Relationship] "
    "FROM [EmergencyContact] WHERE [Center ID]=?"
)


def encode_auth_days(days: set[int]) -> str:
    """Convert {1, 3, 5} → '1,3,5'. Empty set → ''."""
    return ",".join(str(d) for d in sorted(days))


def decode_auth_days(value: str) -> set[int]:
    """Convert '1,3,5' → {1, 3, 5}. Empty string → set()."""
    if not value:
        return set()
    return {int(x) for x in value.split(",") if x.strip()}


def _hhmm_to_datetime(hhmm: str) -> datetime:
    """'08:30' → datetime(1899, 12, 30, 8, 30) for Access DATETIME storage."""
    h, m = map(int, hhmm.split(":"))
    return datetime(1899, 12, 30, h, m)


def _access_date(value):
    """Access Date/Time -> datetime.date (a date passes through; None -> None)."""
    if value is None:
        return None
    return value.date() if isinstance(value, datetime) else value


def _access_hhmm(value):
    """Access time-only DATETIME -> 'HH:mm' (None -> None)."""
    if value is None:
        return None
    return value.strftime("%H:%M") if hasattr(value, "strftime") else value


def map_one_off_availability_row(row) -> dict:
    """Map a OneOffAvailability row: [date] -> date; [avail_start]/[avail_end]
    are time-only DATETIMEs -> 'HH:mm'; [Notes] -> str."""
    return {
        "id": int(row[0]),
        "center_id": int(row[1]),
        "date": _access_date(row[2]),
        "avail_start": _access_hhmm(row[3]),
        "avail_end": _access_hhmm(row[4]),
        "notes": row[5] or "",
    }


def map_emergency_contact_row(row) -> dict:
    """Map an EmergencyContact row. Null text fields become ''."""
    return {
        "id": int(row[0]),
        "center_id": int(row[1]),
        "full_name": row[2] or "",
        "phone": row[3] or "",
        "relationship": row[4] or "",
    }


def time_12h_to_24h(text: str, period: str) -> str:
    """Convert a typed 12-hour time + AM/PM to 24-hour 'HH:mm'.

    '8:00','AM'  -> '08:00'
    '12:00','AM' -> '00:00'
    '12:00','PM' -> '12:00'
    '4:30','PM'  -> '16:30'

    Raises ValueError if the text is not 'h:mm', hour not in 1..12,
    minute not in 0..59, or period not 'AM'/'PM' (case-insensitive).
    """
    parts = text.strip().split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid time: {text!r}")
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError:
        raise ValueError(f"Invalid time: {text!r}")
    if not (1 <= hour <= 12) or not (0 <= minute <= 59):
        raise ValueError(f"Time out of range: {text!r}")
    p = period.strip().upper()
    if p not in ("AM", "PM"):
        raise ValueError(f"Invalid period: {period!r}")
    h24 = hour % 12 if p == "AM" else (hour % 12) + 12
    return f"{h24:02d}:{minute:02d}"


def _connect(db_path: str):
    """Open a fresh transactional connection (autocommit=False).

    Used for writes and bulk/exists reads — never during member browsing.
    Opening one invalidates the cached read connection (see _read_connection)
    so the next read reflects any committed change: the ACE engine does not
    propagate one connection's commits to another connection's read cache.
    """
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found: {db_path}")
    _drop_read_connection(db_path)
    import pyodbc
    try:
        return pyodbc.connect(build_connection_string(db_path), autocommit=False)
    except pyodbc.Error as exc:
        raise RuntimeError(f"Could not open Access database: {exc}") from exc


# ── Per-click connection caches ──────────────────────────────────────────
# Opening a fresh connection on every member click is the dominant latency:
# ~135 ms for pyodbc and ~115 ms for DAO OpenDatabase, while the queries
# themselves take only a few ms. The GUI is single-threaded and clicks are
# serialized, so we cache one read connection and one DAO database handle per
# db_path and reuse them. Writes still use _connect() (short-lived,
# autocommit=False) so they remain transactional and visible to the cached
# autocommit read connection.
_read_conn_cache: dict = {}
_dao_db_cache: dict = {}


def _read_connection(db_path: str):
    """Return a cached autocommit read connection for db_path, opening if needed.

    The connection is reused while the database file is unchanged (fast member
    browsing) and transparently reopened when the file's mtime changes — e.g.
    after an edit committed by another connection or by Microsoft Access. The
    ACE engine doesn't show an open connection another connection's commits, so
    keying the cache on mtime keeps reads live without reconnecting every click.
    """
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found: {db_path}")
    mtime = os.stat(db_path).st_mtime_ns
    cached = _read_conn_cache.get(db_path)
    if cached is not None:
        conn, cached_mtime = cached
        if cached_mtime == mtime:
            return conn
        try:                       # file changed -> drop the stale connection
            conn.close()
        except Exception:
            pass
    import pyodbc
    try:
        conn = pyodbc.connect(build_connection_string(db_path), autocommit=True)
    except pyodbc.Error as exc:
        raise RuntimeError(f"Could not open Access database: {exc}") from exc
    _read_conn_cache[db_path] = (conn, mtime)
    return conn


def _drop_read_connection(db_path: str) -> None:
    cached = _read_conn_cache.pop(db_path, None)
    if cached is not None:
        try:
            cached[0].close()
        except Exception:
            pass


def _dao_database(db_path: str):
    """Return a cached shared/read-only DAO Database handle, opening if needed."""
    cached = _dao_db_cache.get(db_path)
    if cached is not None:
        return cached[1]
    import win32com.client
    engine = win32com.client.Dispatch("DAO.DBEngine.120")
    # OpenDatabase(Name, Options=False -> shared, ReadOnly=True): a shared
    # read-only handle won't block pyodbc writes to the same file.
    db = engine.OpenDatabase(db_path, False, True)
    _dao_db_cache[db_path] = (engine, db)
    return db


def _drop_dao_database(db_path: str) -> None:
    cached = _dao_db_cache.pop(db_path, None)
    if cached is not None:
        try:
            cached[1].Close()
        except Exception:
            pass


def close_connections() -> None:
    """Close all cached read/DAO handles (call when the DB path changes)."""
    for path in list(_read_conn_cache):
        _drop_read_connection(path)
    for path in list(_dao_db_cache):
        _drop_dao_database(path)


def get_all_members(db_path: str) -> list[dict]:
    """Return all members as dicts with center_id, last_name, first_name, health_plan."""
    conn = _connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(ALL_MEMBERS_QUERY)
        return [
            {
                "center_id": int(row[0]),
                "last_name": row[1] or "",
                "first_name": row[2] or "",
                "health_plan": row[3] or "",
            }
            for row in cursor.fetchall()
            if row[0] is not None  # skip Contacts rows with NULL Center ID
        ]
    finally:
        conn.close()


def get_member_photo(center_id: int, db_path: str) -> bytes | None:
    """Return raw JPEG bytes from the Access Attachment field, or None.

    Access Attachment fields are not readable via pyodbc; this function
    uses DAO (win32com) instead. Failures are silently swallowed because
    the photo is non-critical — the UI falls back to a placeholder.
    """
    if not os.path.exists(db_path):
        return None
    for attempt in (1, 2):
        try:
            db = _dao_database(db_path)
            rs = db.OpenRecordset(
                f"SELECT * FROM [Contacts] WHERE [Center ID]={center_id}"
            )
            if rs.EOF:
                rs.Close()
                return None
            photo_field = rs.Fields("Photo")
            attach_rs = photo_field.Value
            if attach_rs.EOF:
                attach_rs.Close()
                rs.Close()
                return None
            raw = attach_rs.Fields("FileData").Value
            if raw is None:
                attach_rs.Close()
                rs.Close()
                return None
            data = bytes(raw)
            # Access stores attachment metadata before the actual file data.
            # The JPEG data starts at the first FF D8 FF marker.
            jpeg_start = data.find(b'\xff\xd8\xff')
            if jpeg_start >= 0:
                data = data[jpeg_start:]
            attach_rs.Close()
            rs.Close()
            return data
        except Exception:
            # The cached DAO handle may be stale; drop it and retry once.
            _drop_dao_database(db_path)
            if attempt == 2:
                return None


def set_member_photo(center_id: int, image_path: str, db_path: str) -> None:
    """Store image_path (a JPEG file) in the member's Contacts.Photo attachment,
    replacing any existing attachment. Uses a fresh writable DAO handle."""
    import win32com.client
    engine = win32com.client.Dispatch("DAO.DBEngine.120")
    db = engine.OpenDatabase(db_path, False, False)  # shared, read-write
    try:
        rs = db.OpenRecordset(
            f"SELECT * FROM [Contacts] WHERE [Center ID]={int(center_id)}"
        )
        if rs.EOF:
            rs.Close()
            raise ValueError(f"No contact with Center ID {center_id}")
        rs.Edit()
        child = rs.Fields("Photo").Value          # attachment child recordset
        while not child.EOF:                      # clear existing attachment(s)
            child.Delete()
            child.MoveNext()
        child.AddNew()
        child.Fields("FileData").LoadFromFile(image_path)
        child.Update()
        rs.Update()
        rs.Close()
    finally:
        db.Close()
    # Drop the cached read-only handle so the next get_member_photo reads fresh.
    _drop_dao_database(db_path)


def set_auth_document(auth_id: int, file_path: str, db_path: str) -> None:
    """Store file_path in the authorization's [Document] attachment, replacing any
    existing one. Uses a fresh writable DAO handle (the cached one is read-only).
    The file is stored as-is (PDFs/images preserved byte-for-byte)."""
    import win32com.client
    engine = win32com.client.Dispatch("DAO.DBEngine.120")
    db = engine.OpenDatabase(db_path, False, False)  # shared, read-write
    try:
        rs = db.OpenRecordset(
            f"SELECT * FROM [Authorization] WHERE [ID]={int(auth_id)}"
        )
        if rs.EOF:
            rs.Close()
            raise ValueError(f"No authorization with ID {auth_id}")
        rs.Edit()
        child = rs.Fields("Document").Value       # attachment child recordset
        while not child.EOF:                      # clear existing attachment(s)
            child.Delete()
            child.MoveNext()
        child.AddNew()
        child.Fields("FileData").LoadFromFile(file_path)
        child.Update()
        rs.Update()
        rs.Close()
    finally:
        db.Close()
    _drop_dao_database(db_path)


def save_auth_document(auth_id: int, dest_dir: str, db_path: str) -> str | None:
    """Write the authorization's attached document into dest_dir (using its original
    file name) and return the written path, or None if there is no document. Uses
    the cached read DAO handle (like get_member_photo)."""
    if not os.path.exists(db_path):
        return None
    for attempt in (1, 2):
        try:
            db = _dao_database(db_path)
            rs = db.OpenRecordset(
                f"SELECT * FROM [Authorization] WHERE [ID]={int(auth_id)}"
            )
            if rs.EOF:
                rs.Close()
                return None
            child = rs.Fields("Document").Value
            if child.EOF:
                child.Close()
                rs.Close()
                return None
            dest = os.path.join(dest_dir, str(child.Fields("FileName").Value))
            child.Fields("FileData").SaveToFile(dest)
            child.Close()
            rs.Close()
            return dest
        except Exception:
            _drop_dao_database(db_path)
            if attempt == 2:
                return None


def get_auth_ids_with_documents(center_id: int, db_path: str) -> set[int]:
    """Authorization ids (for a member) that have a [Document] attachment. Cached
    read DAO handle. Returns an empty set on any error (e.g. the [Document] column
    not yet added in Access), so the UI still renders."""
    if not os.path.exists(db_path):
        return set()
    for attempt in (1, 2):
        try:
            db = _dao_database(db_path)
            rs = db.OpenRecordset(
                f"SELECT * FROM [Authorization] WHERE [Center ID]={int(center_id)}"
            )
            ids: set[int] = set()
            while not rs.EOF:
                child = rs.Fields("Document").Value
                if not child.EOF:
                    ids.add(int(rs.Fields("ID").Value))
                child.Close()
                rs.MoveNext()
            rs.Close()
            return ids
        except Exception:
            _drop_dao_database(db_path)
            if attempt == 2:
                return set()


def get_member_context(center_id: int, db_path: str, _retry: bool = True) -> dict:
    """Fetch member + all 4 supporting tables over a cached connection.

    Returns dict with keys: member, enrollments, authorizations,
    availability, absences.  The read connection is cached per db_path
    (see _read_connection), so the ~135 ms pyodbc connect cost is paid
    once instead of on every member click.
    """
    import pyodbc
    conn = _read_connection(db_path)
    try:
        c = conn.cursor()

        c.execute(
            "SELECT [Center ID],[Last Name],[First Name],[Chinese Name],[DOB],"
            "[Health Plan],[Member ID],[Medicaid],[Medicare],[SSN],[Language],"
            "[Case Manager],[Home Tell],[Cell],[Address],[Emergency],[PCP],"
            "[Hospital],[HHA],[Notes],[Gender],[Admission Date] "
            "FROM [Contacts] WHERE [Center ID]=?",
            center_id,
        )
        row = c.fetchone()
        if row:
            member = {
                "center_id":      int(row[0]) if row[0] is not None else center_id,
                "last_name":      row[1]  or "",
                "first_name":     row[2]  or "",
                "chinese_name":   row[3]  or "",
                "dob":            str(row[4]) if row[4] else "",
                "health_plan":    row[5]  or "",
                "member_id":      row[6]  or "",
                "medicaid":       row[7]  or "",
                "medicare":       row[8]  or "",
                "ssn":            row[9]  or "",
                "language":       row[10] or "",
                "case_manager":   row[11] or "",
                "home_tell":      row[12] or "",
                "cell":           row[13] or "",
                "address":        row[14] or "",
                "emergency":      row[15] or "",
                "pcp":            row[16] or "",
                "hospital":       row[17] or "",
                "hha":            row[18] or "",
                "notes":          row[19] or "",
                "gender":         row[20] or "",
                "admission_date": str(row[21]) if row[21] else "",
            }
        else:
            member = {}

        c.execute(
            "SELECT [ID],[Center ID],[start_date],[end_date] "
            "FROM [Enrollment] WHERE [Center ID]=?",
            center_id,
        )
        enrollments = [map_enrollment_row(r) for r in c.fetchall()]

        c.execute(AUTHORIZATION_SELECT, center_id)
        authorizations = [_map_auth_row(r) for r in c.fetchall()]

        c.execute(
            "SELECT [ID],[Center ID],[effective_start_date],"
            "[effective_end_date],[Day Of Week],[avail_start],[avail_end] "
            "FROM [Availability] WHERE [Center ID]=?",
            center_id,
        )
        availability = [map_availability_row(r) for r in c.fetchall()]

        c.execute(
            "SELECT [ID],[Center ID],[Leave Type],[Start_Date],[End_Date] "
            "FROM [Absences] WHERE [Center ID]=?",
            center_id,
        )
        absences = [map_absence_row(r) for r in c.fetchall()]

        c.execute(ONE_OFF_AVAILABILITY_SELECT, center_id)
        one_off_availability = [
            map_one_off_availability_row(r) for r in c.fetchall()
        ]

        c.execute(EMERGENCY_CONTACT_SELECT, center_id)
        emergency_contacts = [
            map_emergency_contact_row(r) for r in c.fetchall()
        ]

        return {
            "member": member,
            "enrollments": enrollments,
            "authorizations": authorizations,
            "availability": availability,
            "absences": absences,
            "one_off_availability": one_off_availability,
            "emergency_contacts": emergency_contacts,
        }
    except pyodbc.Error:
        # Cached connection may be stale (file moved, lock dropped); reopen once.
        _drop_read_connection(db_path)
        if _retry:
            return get_member_context(center_id, db_path, _retry=False)
        raise


def _map_auth_row(row) -> dict:
    """bsca-core maps 7 columns by index; add the local [Health Plan] (row[7])
    and [created_at] (row[8], a datetime or None for legacy rows)."""
    d = map_authorization_row(row)
    d["health_plan"] = row[7] or ""
    d["created_at"] = row[8]
    d["member_id"] = row[9]
    return d


def get_authorizations(center_id: int, db_path: str, _retry: bool = True) -> list[dict]:
    """Authorizations for a member, including health_plan (cached read connection).

    Replaces monthly_schedule.db.get_authorizations whose query has no
    [Health Plan] column. Mirrors get_member_context's stale-connection retry.
    """
    import pyodbc
    conn = _read_connection(db_path)
    try:
        c = conn.cursor()
        c.execute(AUTHORIZATION_SELECT, center_id)
        return [_map_auth_row(r) for r in c.fetchall()]
    except pyodbc.Error:
        _drop_read_connection(db_path)
        if _retry:
            return get_authorizations(center_id, db_path, _retry=False)
        raise


def get_one_off_availability(center_id: int, db_path: str,
                             _retry: bool = True) -> list[dict]:
    """One-off unavailable windows for a member (cached read connection).
    Mirrors get_member_context's stale-connection retry."""
    import pyodbc
    conn = _read_connection(db_path)
    try:
        c = conn.cursor()
        c.execute(ONE_OFF_AVAILABILITY_SELECT, center_id)
        return [map_one_off_availability_row(r) for r in c.fetchall()]
    except pyodbc.Error:
        _drop_read_connection(db_path)
        if _retry:
            return get_one_off_availability(center_id, db_path, _retry=False)
        raise


def get_emergency_contacts(center_id: int, db_path: str,
                           _retry: bool = True) -> list[dict]:
    """Emergency contacts for a member (cached read connection). Mirrors
    get_member_context's stale-connection retry."""
    import pyodbc
    conn = _read_connection(db_path)
    try:
        c = conn.cursor()
        c.execute(EMERGENCY_CONTACT_SELECT, center_id)
        return [map_emergency_contact_row(r) for r in c.fetchall()]
    except pyodbc.Error:
        _drop_read_connection(db_path)
        if _retry:
            return get_emergency_contacts(center_id, db_path, _retry=False)
        raise


def latest_authorization(authorizations: list[dict]) -> dict | None:
    """The latest authorization by (auth_start, id).

    Returns None if the list is empty or no row has an auth_start.
    """
    candidates = [a for a in authorizations if a.get("auth_start")]
    if not candidates:
        return None
    return max(candidates, key=lambda a: (a["auth_start"], a["id"]))


def current_authorization(authorizations: list[dict], today=None) -> dict | None:
    """The authorization in effect today: effective_start <= today <=
    effective_end, preferring the latest start. None if none is in effect (e.g.
    every auth is expired or upcoming). This is what the header / Info tab show,
    so a future ("upcoming") auth never displaces the active one."""
    from datetime import date
    if today is None:
        today = date.today()
    candidates = [
        a for a in authorizations
        if a.get("effective_start") and a.get("effective_end")
        and a["effective_start"] <= today <= a["effective_end"]
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda a: a["effective_start"])


def sync_health_plan_from_current_auth(center_id: int, db_path: str) -> str | None:
    """Set Contacts.[Health Plan] to the current (in-effect-today) auth's plan.

    Returns the plan written, or None when nothing changed. Never blanks an
    existing plan: if no auth is currently in effect, or its plan is empty,
    Contacts is left untouched (so an upcoming auth doesn't change it).
    """
    current = current_authorization(get_authorizations(center_id, db_path))
    if not current:
        return None
    plan = (current.get("health_plan") or "").strip()
    if not plan:
        return None
    conn = _connect(db_path)
    try:
        conn.cursor().execute(
            "UPDATE [Contacts] SET [Health Plan]=? WHERE [Center ID]=?",
            (plan, center_id),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return plan


def sync_member_id_from_current_auth(center_id: int, db_path: str) -> str | None:
    """Set Contacts.[Member ID] to the current (in-effect-today) auth's Member ID.

    Mirrors sync_health_plan_from_current_auth: returns the value written, or
    None when nothing changed. Never blanks an existing Member ID.
    """
    current = current_authorization(get_authorizations(center_id, db_path))
    if not current:
        return None
    member_id = (current.get("member_id") or "").strip()
    if not member_id:
        return None
    conn = _connect(db_path)
    try:
        conn.cursor().execute(
            "UPDATE [Contacts] SET [Member ID]=? WHERE [Center ID]=?",
            (member_id, center_id),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return member_id


def center_id_exists(center_id: int, db_path: str) -> bool:
    conn = _connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM [Contacts] WHERE [Center ID]=?", center_id)
        return cursor.fetchone()[0] > 0
    finally:
        conn.close()


def next_center_id(all_ids, terminated_ids, start: int = 10000) -> int:
    """Suggest the next Center ID for a new member.

    Counts up from the highest *active* (non-terminated) member whose ID is a
    5-digit number (10000–99999). Member IDs follow that 5-digit scheme; the data
    also holds a separate 7-digit numbering and a few outliers, which are ignored
    when choosing the base. Never reuses an ID already taken by any member —
    active or terminated, of any length — and never returns one ending in 4 (…4
    jumps to …5). Pure, so it is unit-testable.

    Falls back to the highest 5-digit ID overall when every 5-digit member is
    terminated, and to ``start`` when there are no 5-digit members at all.
    """
    all_ids = set(all_ids)
    five_digit = {i for i in all_ids if 10000 <= i <= 99999}
    active = five_digit - set(terminated_ids)
    if active:
        candidate = max(active) + 1
    elif five_digit:
        candidate = max(five_digit) + 1
    else:
        candidate = start
    while candidate in all_ids or candidate % 10 == 4:
        candidate += 1
    return candidate


def suggest_next_center_id(db_path: str) -> int:
    """The next Center ID for a new member, computed from the live database.

    Thin DB wrapper over next_center_id (see there for the rules)."""
    all_ids = {m["center_id"] for m in get_all_members(db_path)}
    terminated = get_terminated_center_ids(db_path)
    return next_center_id(all_ids, terminated)


def insert_member(
    center_id: int,
    last_name: str,
    first_name: str,
    health_plan: str,
    address: str,
    enrollment_start: date,
    enrollment_end: date | None,
    authorization: dict | None,
    availability_rows: list[dict],
    long_lat: str = "",
    member_id: str = "",
    home_tell: str = "",
    cell: str = "",
    dob: date | None = None,
    gender: str = "",
    db_path: str = "",
) -> None:
    """Insert a new member and all related records in one transaction."""
    conn = _connect(db_path)
    try:
        c = conn.cursor()
        c.execute(INSERT_CONTACT,
                  (center_id, last_name, first_name, health_plan, address,
                   long_lat, member_id, home_tell, cell, dob, gender))
        c.execute(INSERT_ENROLLMENT, (center_id, enrollment_start, enrollment_end))
        if authorization:
            # The wizard's auth step has no plan field — the member's selected
            # plan is the authorization's plan. Fall back to it so a new member's
            # authorization is never created without a health plan.
            auth_plan = (authorization.get("health_plan") or "").strip() or health_plan
            c.execute(
                INSERT_AUTHORIZATION,
                (
                    center_id,
                    authorization["auth_start"],
                    authorization["auth_end"],
                    authorization.get("effective_start"),
                    authorization.get("effective_end"),
                    encode_auth_days(authorization["auth_days"]),
                    auth_plan,
                    datetime.now(),
                    member_id,   # seed the auth's Member ID from the member's
                ),
            )
        for row in availability_rows:
            c.execute(
                INSERT_AVAILABILITY,
                (
                    center_id,
                    row["effective_start_date"],
                    row.get("effective_end_date"),
                    row["day_of_week"],
                    _hhmm_to_datetime(row["avail_start"]),
                    _hhmm_to_datetime(row["avail_end"]),
                ),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def set_member_long_lat(center_id: int, long_lat: str, db_path: str) -> None:
    """Persist 'lng,lat' to a member's [Long Lat] (only when a place was picked)."""
    conn = _connect(db_path)
    try:
        conn.cursor().execute(SET_LONG_LAT, (long_lat, center_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def update_contact(
    center_id: int,
    last_name: str,
    first_name: str,
    chinese_name: str,
    gender: str,
    dob: str,
    member_id: str,
    health_plan: str,
    medicaid: str,
    medicare: str,
    ssn: str,
    language: str,
    case_manager: str,
    home_tell: str,
    cell: str,
    address: str,
    emergency: str,
    pcp: str,
    hospital: str,
    hha: str,
    admission_date: str,
    notes: str,
    db_path: str,
) -> None:
    conn = _connect(db_path)
    try:
        conn.cursor().execute(
            UPDATE_CONTACT,
            (
                last_name, first_name, chinese_name, gender, dob,
                member_id, health_plan, medicaid, medicare, ssn,
                language, case_manager, home_tell, cell, address,
                emergency, pcp, hospital, hha, admission_date, notes,
                center_id,
            ),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def insert_enrollment(center_id: int, start: date, end: date | None, db_path: str) -> None:
    conn = _connect(db_path)
    try:
        conn.cursor().execute(INSERT_ENROLLMENT, (center_id, start, end))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_enrollment(record_id: int, db_path: str) -> None:
    conn = _connect(db_path)
    try:
        conn.cursor().execute(DELETE_ENROLLMENT, (record_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def is_terminated(enrollments: list[dict]) -> bool:
    """True when the member's latest enrollment (by start date) has an end date.
    No enrollments -> False; a latest ongoing enrollment -> False."""
    if not enrollments:
        return False
    latest = max(enrollments, key=lambda e: e.get("start_date") or date.min)
    return latest.get("end_date") is not None


def enrollment_active(enrollment: dict, today) -> bool:
    """True when an enrollment is currently in effect: no end date, or an end
    date strictly after today (an enrollment ending today reads as ended)."""
    end = enrollment.get("end_date")
    if end is None:
        return True
    if isinstance(end, datetime):
        end = end.date()
    return end > today


def has_active_enrollment(enrollments: list[dict], today) -> bool:
    """Whether any enrollment is currently in effect."""
    return any(enrollment_active(e, today) for e in enrollments)


def sort_enrollments_active_first(enrollments: list[dict], today) -> list[dict]:
    """Active (in-effect) enrollments first, then ended ones; within each group
    by start date, most recent first. Returns a new list (input not mutated)."""
    def key(e):
        start = e.get("start_date") or date.min
        if isinstance(start, datetime):
            start = start.date()
        return (enrollment_active(e, today), start)
    return sorted(enrollments, key=key, reverse=True)


def terminated_ids_from_rows(rows) -> set[int]:
    """Group raw (center_id, start_date, end_date) rows by member and return the
    set of terminated center ids. Pure (no DB) so it is unit-testable."""
    from collections import defaultdict
    by_member: dict[int, list[dict]] = defaultdict(list)
    for cid, start, end in rows:
        if cid is None:
            continue
        by_member[int(cid)].append(
            {"start_date": _access_date(start), "end_date": _access_date(end)}
        )
    return {cid for cid, enrs in by_member.items() if is_terminated(enrs)}


def get_terminated_center_ids(db_path: str) -> set[int]:
    """Center ids of terminated members, from all Enrollment rows in one query
    (mirrors get_all_members' connection handling)."""
    conn = _connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT [Center ID], [start_date], [end_date] FROM [Enrollment]"
        )
        return terminated_ids_from_rows(cur.fetchall())
    finally:
        conn.close()


def terminate_enrollment(record_id: int, db_path: str) -> None:
    """Set an enrollment's end date to today (used by the Terminate button)."""
    conn = _connect(db_path)
    try:
        conn.cursor().execute(UPDATE_ENROLLMENT_END, (date.today(), record_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def insert_authorization(
    center_id: int,
    auth_start: date,
    auth_end: date,
    auth_days: set[int],
    effective_start: date | None,
    effective_end: date | None,
    health_plan: str,
    db_path: str,
    member_id: str = "",
) -> None:
    conn = _connect(db_path)
    try:
        conn.cursor().execute(
            INSERT_AUTHORIZATION,
            (center_id, auth_start, auth_end, effective_start, effective_end,
             encode_auth_days(auth_days), health_plan, datetime.now(), member_id),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def update_authorization(
    record_id: int,
    auth_start: date,
    auth_end: date,
    auth_days: set[int],
    health_plan: str,
    db_path: str,
    member_id: str = "",
) -> None:
    """Update an existing authorization's dates, days, plan, and member id."""
    conn = _connect(db_path)
    try:
        conn.cursor().execute(
            UPDATE_AUTHORIZATION,
            (auth_start, auth_end, encode_auth_days(auth_days), health_plan,
             member_id, record_id),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_authorization(record_id: int, db_path: str) -> None:
    conn = _connect(db_path)
    try:
        conn.cursor().execute(DELETE_AUTHORIZATION, (record_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def insert_availability(
    center_id: int,
    day_of_week: int,
    avail_start: str,
    avail_end: str,
    effective_start: date,
    effective_end: date | None,
    db_path: str,
) -> None:
    conn = _connect(db_path)
    try:
        conn.cursor().execute(
            INSERT_AVAILABILITY,
            (center_id, effective_start, effective_end, day_of_week,
             _hhmm_to_datetime(avail_start), _hhmm_to_datetime(avail_end)),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def update_availability(record_id: int, avail_start: str, avail_end: str,
                        effective_start: date, effective_end: date | None,
                        db_path: str) -> None:
    """Update an availability row's start/end times (24-hour 'HH:mm') and its
    effective window. `effective_end` may be None for an open-ended window."""
    conn = _connect(db_path)
    try:
        conn.cursor().execute(
            UPDATE_AVAILABILITY,
            (_hhmm_to_datetime(avail_start), _hhmm_to_datetime(avail_end),
             effective_start, effective_end, record_id),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_availability(record_id: int, db_path: str) -> None:
    conn = _connect(db_path)
    try:
        conn.cursor().execute(DELETE_AVAILABILITY, (record_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def insert_one_off_availability(
    center_id: int,
    on_date: date,
    avail_start: str,
    avail_end: str,
    notes: str,
    db_path: str,
) -> None:
    conn = _connect(db_path)
    try:
        conn.cursor().execute(
            INSERT_ONE_OFF_AVAILABILITY,
            (center_id, on_date, _hhmm_to_datetime(avail_start),
             _hhmm_to_datetime(avail_end), notes),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def update_one_off_availability(
    record_id: int,
    on_date: date,
    avail_start: str,
    avail_end: str,
    notes: str,
    db_path: str,
) -> None:
    conn = _connect(db_path)
    try:
        conn.cursor().execute(
            UPDATE_ONE_OFF_AVAILABILITY,
            (on_date, _hhmm_to_datetime(avail_start),
             _hhmm_to_datetime(avail_end), notes, record_id),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_one_off_availability(record_id: int, db_path: str) -> None:
    conn = _connect(db_path)
    try:
        conn.cursor().execute(DELETE_ONE_OFF_AVAILABILITY, (record_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def insert_emergency_contact(center_id: int, full_name: str, phone: str,
                             relationship: str, db_path: str) -> None:
    conn = _connect(db_path)
    try:
        conn.cursor().execute(
            INSERT_EMERGENCY_CONTACT,
            (center_id, full_name, phone, relationship),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def update_emergency_contact(record_id: int, full_name: str, phone: str,
                             relationship: str, db_path: str) -> None:
    conn = _connect(db_path)
    try:
        conn.cursor().execute(
            UPDATE_EMERGENCY_CONTACT,
            (full_name, phone, relationship, record_id),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_emergency_contact(record_id: int, db_path: str) -> None:
    conn = _connect(db_path)
    try:
        conn.cursor().execute(DELETE_EMERGENCY_CONTACT, (record_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def insert_absence(
    center_id: int,
    leave_type: str,
    start: date,
    end: date,
    db_path: str,
) -> None:
    conn = _connect(db_path)
    try:
        conn.cursor().execute(INSERT_ABSENCE, (center_id, leave_type, start, end))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_absence(record_id: int, db_path: str) -> None:
    conn = _connect(db_path)
    try:
        conn.cursor().execute(DELETE_ABSENCE, (record_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
