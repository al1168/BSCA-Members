"""Read/write helpers for the BSCA Access database.

Read connections reuse bsca-core's build_connection_string.
Write operations open their own connection with autocommit=False
so multiple INSERTs can be wrapped in a single transaction.
"""
import os
import re
from contextlib import contextmanager
from datetime import date, datetime

from monthly_schedule.db import (
    build_connection_string,
    map_member_row,
    map_enrollment_row,
    map_authorization_row,
    map_availability_row,
)

# Selectable health plans. "Aetna" (== AE) and "Anthem" (== BCBS) are dropped as
# duplicates; their colors remain in PLAN_COLORS so any not-yet-migrated rows
# still render a badge.
HEALTH_PLANS = ("AE", "BCBS", "ES", "HC", "HF", "HOF", "VCM")

# Authorization [Plan Type] values. The leading blank keeps legacy rows (which
# predate the column) editable without silently forcing a value on them.
PLAN_TYPES = ("", "MAP", "MLTC")

LEAVE_TYPES = (
    "Vacation", "Medical", "Hospitalization",
    "Family Emergency", "Holiday", "Other",
)

ALL_MEMBERS_QUERY = (
    "SELECT [Center ID], [Last Name], [First Name], [Health Plan], [DOB], "
    "[alt_id] FROM [Contacts] ORDER BY [Last Name], [First Name]"
)

HEALTH_PLANS_CONTACTS_QUERY = (
    "SELECT DISTINCT [Health Plan] FROM [Contacts]"
)
HEALTH_PLANS_AUTHS_QUERY = (
    "SELECT DISTINCT [Health Plan] FROM [Authorization]"
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


def format_phone_live(text) -> str:
    """Phone formatted as you type: 2125 -> '(212)-5', building toward
    (xxx)-xxx-xxxx. Digits only, capped at 10."""
    d = "".join(ch for ch in (text or "") if ch.isdigit())[:10]
    if not d:
        return ""
    if len(d) <= 3:
        return f"({d}"
    if len(d) <= 6:
        return f"({d[:3]})-{d[3:]}"
    return f"({d[:3]})-{d[3:6]}-{d[6:]}"


# ── SSN / Medicaid / Medicare validation (optional fields: empty == valid) ──
_SSN_RE = re.compile(r"^\d{3}-\d{2}-\d{4}$")
_MEDICAID_RE = re.compile(r"^[A-Za-z]{2}\d{5}[A-Za-z]$")
# Medicare Beneficiary Identifier (MBI), dashes optional. Anchored full-field
# version of the standard MBI character pattern.
_MEDICARE_RE = re.compile(
    r"^[1-9]"
    r"[AC-HJKMNP-RT-Yac-hjkmnp-rt-y]"
    r"[AC-HJKMNP-RT-Yac-hjkmnp-rt-y0-9]"
    r"[0-9]-?"
    r"[AC-HJKMNP-RT-Yac-hjkmnp-rt-y]"
    r"[AC-HJKMNP-RT-Yac-hjkmnp-rt-y0-9]"
    r"[0-9]-?"
    r"[AC-HJKMNP-RT-Yac-hjkmnp-rt-y]{2}\d{2}$"
)


def format_ssn(value) -> str:
    """Render an SSN as xxx-xx-xxxx when it has exactly 9 digits; otherwise the
    trimmed input. Idempotent; never raises."""
    s = "" if value is None else str(value).strip()
    digits = "".join(ch for ch in s if ch.isdigit())
    if len(digits) == 9:
        return f"{digits[:3]}-{digits[3:5]}-{digits[5:]}"
    return s


def is_valid_ssn(value) -> bool:
    s = "" if value is None else str(value).strip()
    return s == "" or bool(_SSN_RE.match(s))


def is_valid_alt_id(value) -> bool:
    """Optional alternative member id: empty, or an integer that fits an
    Access Long (digits only, <= 2147483647)."""
    s = "" if value is None else str(value).strip()
    return s == "" or (s.isdigit() and int(s) <= 2_147_483_647)


def format_medicaid(value) -> str:
    """Medicaid ids are AAdddddA — normalize letters to uppercase."""
    s = "" if value is None else str(value).strip()
    return s.upper()


def is_valid_medicaid(value) -> bool:
    s = "" if value is None else str(value).strip()
    return s == "" or bool(_MEDICAID_RE.match(s))


def format_medicare(value) -> str:
    """Normalize a Medicare (MBI) id to uppercase."""
    s = "" if value is None else str(value).strip()
    return s.upper()


def is_valid_medicare(value) -> bool:
    s = "" if value is None else str(value).strip()
    return s == "" or bool(_MEDICARE_RE.match(s))


# ── Live (as-you-type) formatters: format the partial value on each keystroke ──
def format_ssn_live(text) -> str:
    """Digits only, dashed as you type: 1234 -> '123-4', etc. (xxx-xx-xxxx)."""
    d = "".join(ch for ch in (text or "") if ch.isdigit())[:9]
    if len(d) <= 3:
        return d
    if len(d) <= 5:
        return f"{d[:3]}-{d[3:]}"
    return f"{d[:3]}-{d[3:5]}-{d[5:]}"


def format_medicare_live(text) -> str:
    """Alphanumerics, uppercased and dashed as you type in 4-3-4 groups:
    12345 -> '1234-5' (xxxx-xxx-xxxx)."""
    c = "".join(ch for ch in (text or "") if ch.isalnum()).upper()[:11]
    out = c[:4]
    if len(c) > 4:
        out += "-" + c[4:7]
    if len(c) > 7:
        out += "-" + c[7:11]
    return out


def format_medicaid_live(text) -> str:
    """Alphanumerics, uppercased (AAdddddA, 8 chars, no separators)."""
    return "".join(ch for ch in (text or "") if ch.isalnum()).upper()[:8]


def format_mdy_live(text) -> str:
    """A date slashed as you type when entering bare digits: '0710' -> '07/10',
    '07102026' -> '07/10/2026' (MMDDYYYY, capped at 8 digits). Hand-typed
    shorthand like '7/1/2026' (slashes off the auto positions) is returned
    unchanged so both entry styles work."""
    t = text or ""
    if any(i not in (2, 5) for i, ch in enumerate(t) if ch == "/"):
        return t
    d = "".join(ch for ch in t if ch.isdigit())[:8]
    if len(d) <= 2:
        return d
    if len(d) <= 4:
        return f"{d[:2]}/{d[2:]}"
    return f"{d[:2]}/{d[2:4]}/{d[4:]}"


def format_time_live(text) -> str:
    """A 12-hour time as you type, digits only: '815' -> '8:15',
    '1230' -> '12:30'. The colon appears once there are 3+ digits (before the
    last two); 1-2 digits stay bare so the hour can still grow (e.g. '1' -> '12')."""
    d = "".join(ch for ch in (text or "") if ch.isdigit())[:4]
    if len(d) <= 2:
        return d
    return f"{d[:-2]}:{d[-2:]}"


def normalize_time_12h(text) -> str | None:
    """Coerce a typed/partial 12-hour time to canonical 'H:MM' (hour 1-12,
    minute 00-59), padding an hour-only entry with ':00'. Returns None when the
    digits can't form a valid 12-hour time (so callers can flag an error)."""
    d = "".join(ch for ch in (text or "") if ch.isdigit())
    if not d:
        return None
    if len(d) <= 2:
        hh, mm = int(d), 0
    elif len(d) == 3:
        hh, mm = int(d[0]), int(d[1:])
    else:
        hh, mm = int(d[:2]), int(d[2:4])
    if not (1 <= hh <= 12 and 0 <= mm <= 59):
        return None
    return f"{hh}:{mm:02d}"


def merge_default_availability(added_rows, effective_start,
                              start="08:00", end="16:00"):
    """Give a new member a default availability of `start`–`end` on every weekday
    (Mon–Sun). Any rows the user added substitute their weekday's default (so a
    user-added Monday window replaces only Monday). Returns a list of availability
    row dicts ordered Mon→Sun, added rows first within a day."""
    added_days = {r["day_of_week"] for r in added_rows}
    rows = list(added_rows)
    for day in range(1, 8):
        if day not in added_days:
            rows.append({
                "day_of_week": day,
                "avail_start": start,
                "avail_end": end,
                "effective_start_date": effective_start,
                "effective_end_date": None,
            })
    rows.sort(key=lambda r: r["day_of_week"])
    return rows


# Free-text date entry (MM/DD/YYYY) for the date fields.
_MDY_RE = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")


def parse_mdy(text):
    """Parse 'M/D/YYYY' (1-2 digit month/day, 4-digit year) to a date, or None
    if it isn't a real calendar date in that form."""
    text = (text or "").strip()
    if not _MDY_RE.match(text):
        return None
    try:
        return datetime.strptime(text, "%m/%d/%Y").date()
    except ValueError:
        return None


def format_mdy(value) -> str:
    """Auto-format a typed date: 8 bare digits (MMDDYYYY) -> MM/DD/YYYY.
    Anything already containing '/' (or not 8 digits) is returned trimmed."""
    s = "" if value is None else str(value).strip()
    if "/" in s:
        return s
    digits = "".join(ch for ch in s if ch.isdigit())
    if len(digits) == 8:
        return f"{digits[:2]}/{digits[2:4]}/{digits[4:]}"
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

def parse_flexible_date(value):
    """A date from the ways DOBs are stored across databases: date/datetime
    objects, ISO 'YYYY-MM-DD' text (with optional trailing time), or
    'M/D/YYYY' text. None when it can't be parsed."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = format_date_only(value)          # trims and drops a trailing time
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def format_dob_display(value) -> str:
    """Render a stored DOB as MM/DD/YYYY however the database holds it (real
    DATETIME, ISO text, or M/D/YYYY text). Unparseable values come back
    trimmed but unchanged so bad data stays visible instead of vanishing."""
    d = parse_flexible_date(value)
    return f"{d:%m/%d/%Y}" if d else format_date_only(value)


def age_from_dob(value) -> int | None:
    """Whole-year age as of today from a stored DOB (any shape
    parse_flexible_date accepts); None when the DOB can't be parsed."""
    d = parse_flexible_date(value)
    if d is None:
        return None
    today = date.today()
    return today.year - d.year - ((today.month, today.day) < (d.month, d.day))


SET_LONG_LAT = "UPDATE [Contacts] SET [Long Lat]=? WHERE [Center ID]=?"

SET_ALT_ID = "UPDATE [Contacts] SET [alt_id]=? WHERE [Center ID]=?"

UPDATE_CONTACT = (
    "UPDATE [Contacts] SET "
    "[Last Name]=?, [First Name]=?, [Chinese Name]=?, [Gender]=?, [DOB]=?, "
    "[Member ID]=?, [Health Plan]=?, [Medicaid]=?, [Medicare]=?, [SSN]=?, "
    "[Language]=?, [Case Manager]=?, [Home Tell]=?, [Cell]=?, [Address]=?, "
    "[Emergency]=?, [PCP]=?, [Hospital]=?, [HHA]=?, [Admission Date]=?, "
    "[Notes]=?, [alt_id]=? "
    "WHERE [Center ID]=?"
)

INSERT_ENROLLMENT = (
    "INSERT INTO [Enrollment] ([Center ID], [start_date], [end_date]) "
    "VALUES (?, ?, ?)"
)

DELETE_ENROLLMENT = "DELETE FROM [Enrollment] WHERE [ID]=?"
UPDATE_ENROLLMENT_END = "UPDATE [Enrollment] SET [end_date]=? WHERE [ID]=?"
UPDATE_ENROLLMENT = (
    "UPDATE [Enrollment] SET [start_date]=?, [end_date]=? WHERE [ID]=?"
)

INSERT_AUTHORIZATION = (
    "INSERT INTO [Authorization] ([Center ID], [auth_start], [auth_end], "
    "[effective_start], [effective_end], [auth_days], [Health Plan], [created_at], "
    "[Member ID], [auth_number], [Plan Type]) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)

DELETE_AUTHORIZATION = "DELETE FROM [Authorization] WHERE [ID]=?"

UPDATE_AUTHORIZATION = (
    "UPDATE [Authorization] SET [auth_start]=?, [auth_end]=?, "
    "[auth_days]=?, [Health Plan]=?, [Member ID]=?, [auth_number]=?, "
    "[Plan Type]=?, "
    "[effective_start]=NULL, [effective_end]=NULL WHERE [ID]=?"
)

AUTHORIZATION_SELECT = (
    "SELECT [ID],[Center ID],[auth_start],[auth_end],"
    "[effective_start],[effective_end],[auth_days],[Health Plan],[created_at],"
    "[Member ID],[auth_number],[Plan Type] "
    "FROM [Authorization] WHERE [Center ID]=?"
)

# ── Transportation authorizations ───────────────────────────────────────────
# A separate [TransportAuthorization] table, structurally identical to
# [Authorization] (so _map_auth_row applies unchanged). The care<->transport
# relationship is stored in the [AuthEdge] junction table. Kept out of the
# scheduler's [Authorization] table so it never affects eligibility/scheduling.
INSERT_TRANSPORT_AUTH = (
    "INSERT INTO [TransportAuthorization] ([Center ID], [auth_start], [auth_end], "
    "[effective_start], [effective_end], [auth_days], [Health Plan], [created_at], "
    "[Member ID], [auth_number]) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)

DELETE_TRANSPORT_AUTH = "DELETE FROM [TransportAuthorization] WHERE [ID]=?"

UPDATE_TRANSPORT_AUTH = (
    "UPDATE [TransportAuthorization] SET [auth_start]=?, [auth_end]=?, "
    "[auth_days]=?, [Health Plan]=?, [Member ID]=?, [auth_number]=?, "
    "[effective_start]=NULL, [effective_end]=NULL WHERE [ID]=?"
)

TRANSPORT_AUTH_SELECT = (
    "SELECT [ID],[Center ID],[auth_start],[auth_end],"
    "[effective_start],[effective_end],[auth_days],[Health Plan],[created_at],"
    "[Member ID],[auth_number] "
    "FROM [TransportAuthorization] WHERE [Center ID]=?"
)

INSERT_AUTH_EDGE = (
    "INSERT INTO [AuthEdge] ([authorization_id], [transport_authorization_id]) "
    "VALUES (?, ?)"
)
DELETE_AUTH_EDGE_BY_TRANSPORT = (
    "DELETE FROM [AuthEdge] WHERE [transport_authorization_id]=?"
)
AUTH_EDGE_SELECT = (
    "SELECT [ID],[authorization_id],[transport_authorization_id] FROM [AuthEdge]"
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
    "INSERT INTO [Absences] ([Center ID], [Leave Type], [Start_Date], "
    "[End_Date], [Notes]) VALUES (?, ?, ?, ?, ?)"
)

DELETE_ABSENCE = "DELETE FROM [Absences] WHERE [ID]=?"

UPDATE_ABSENCE = (
    "UPDATE [Absences] SET [Leave Type]=?, [Start_Date]=?, [End_Date]=?, "
    "[Notes]=? WHERE [ID]=?"
)

ABSENCES_SELECT = (
    "SELECT [ID],[Center ID],[Leave Type],[Start_Date],[End_Date],[Notes] "
    "FROM [Absences] WHERE [Center ID]=?"
)

ABSENCES_ALL_SELECT = (
    "SELECT [Center ID],[Leave Type],[Start_Date],[End_Date],[Notes] "
    "FROM [Absences]"
)

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


def map_absence_row(row) -> dict:
    """Map an Absences row; [Notes] MEMO -> str ('' when null)."""
    return {
        "id": int(row[0]),
        "center_id": int(row[1]),
        "leave_type": row[2],
        "start_date": _access_date(row[3]),
        "end_date": _access_date(row[4]),
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


@contextmanager
def write_conn(db_path: str):
    """A transactional write: yields a cursor, commits on success, rolls back
    and re-raises on failure, always closes. Every write helper goes through
    this so the commit/rollback pattern can't drift between functions."""
    conn = _connect(db_path)
    try:
        yield conn.cursor()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _execute_write(db_path: str, sql: str, params: tuple) -> None:
    """Run one parameterized write statement in its own transaction."""
    with write_conn(db_path) as c:
        c.execute(sql, params)


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
                "dob": _access_date(row[4]),
                "alt_id": int(row[5]) if row[5] is not None else None,
            }
            for row in cursor.fetchall()
            if row[0] is not None  # skip Contacts rows with NULL Center ID
        ]
    finally:
        conn.close()


def extract_attachment_image(data: bytes) -> bytes:
    """Strip the Access attachment header from a Photo FileData blob.

    The blob is a small header followed by the original file, and the header's
    length lives in the first four bytes (little-endian) — so slicing there
    works for every image format, not just JPEG. When the offset doesn't land
    on a known image signature (malformed blob), fall back to hunting for a
    JPEG/PNG/GIF/BMP marker; as a last resort return the input unchanged so
    the caller's decoder can try its best."""
    import struct
    magics = (b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"GIF8", b"BM")
    if len(data) >= 8:
        offset = struct.unpack("<I", data[:4])[0]
        if 4 <= offset < len(data) and data[offset:].startswith(magics):
            return data[offset:]
    for magic in magics:
        i = data.find(magic)
        if i >= 0:
            return data[i:]
    return data


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
            # Access stores attachment metadata before the actual file data;
            # strip it by its declared length (works for PNG as well as JPEG).
            data = extract_attachment_image(bytes(raw))
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
    # DAO's LoadFromFile can't handle the forward slashes Qt file dialogs
    # return ("Could not find file 'C:/Users/…'") — normalize to backslashes.
    image_path = os.path.normpath(image_path)
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


def _set_document(table: str, record_id: int, file_path: str, db_path: str) -> None:
    """Store file_path in [table]'s [Document] attachment for one row, replacing any
    existing one. Uses a fresh writable DAO handle (the cached one is read-only).
    The file is stored as-is (PDFs/images preserved byte-for-byte)."""
    # DAO's LoadFromFile can't handle the forward slashes Qt file dialogs
    # return — normalize to backslashes or it reports "Could not find file".
    file_path = os.path.normpath(file_path)
    import win32com.client
    engine = win32com.client.Dispatch("DAO.DBEngine.120")
    db = engine.OpenDatabase(db_path, False, False)  # shared, read-write
    try:
        rs = db.OpenRecordset(
            f"SELECT * FROM [{table}] WHERE [ID]={int(record_id)}"
        )
        if rs.EOF:
            rs.Close()
            raise ValueError(f"No {table} row with ID {record_id}")
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


def _save_document(table: str, record_id: int, dest_dir: str, db_path: str) -> str | None:
    """Write [table]'s attached document for one row into dest_dir (using its
    original file name) and return the written path, or None if there is no
    document. Uses the cached read DAO handle (like get_member_photo)."""
    if not os.path.exists(db_path):
        return None
    for attempt in (1, 2):
        try:
            db = _dao_database(db_path)
            rs = db.OpenRecordset(
                f"SELECT * FROM [{table}] WHERE [ID]={int(record_id)}"
            )
            if rs.EOF:
                rs.Close()
                return None
            child = rs.Fields("Document").Value
            if child.EOF:
                child.Close()
                rs.Close()
                return None
            # normpath: SaveToFile rejects the forward slashes Qt dir pickers
            # return, same as LoadFromFile.
            dest = os.path.normpath(
                os.path.join(dest_dir, str(child.Fields("FileName").Value)))
            child.Fields("FileData").SaveToFile(dest)
            child.Close()
            rs.Close()
            return dest
        except Exception:
            _drop_dao_database(db_path)
            if attempt == 2:
                return None


def _ids_with_documents(table: str, center_id: int, db_path: str) -> set[int]:
    """Row ids in [table] (for a member) that have a [Document] attachment. Cached
    read DAO handle. Returns an empty set on any error (e.g. the [Document] column
    not present), so the UI still renders."""
    if not os.path.exists(db_path):
        return set()
    for attempt in (1, 2):
        try:
            db = _dao_database(db_path)
            rs = db.OpenRecordset(
                f"SELECT * FROM [{table}] WHERE [Center ID]={int(center_id)}"
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


def set_auth_document(auth_id: int, file_path: str, db_path: str) -> None:
    _set_document("Authorization", auth_id, file_path, db_path)


def save_auth_document(auth_id: int, dest_dir: str, db_path: str) -> str | None:
    return _save_document("Authorization", auth_id, dest_dir, db_path)


def get_auth_ids_with_documents(center_id: int, db_path: str) -> set[int]:
    return _ids_with_documents("Authorization", center_id, db_path)


def set_transport_document(transport_id: int, file_path: str, db_path: str) -> None:
    _set_document("TransportAuthorization", transport_id, file_path, db_path)


def save_transport_document(transport_id: int, dest_dir: str, db_path: str) -> str | None:
    return _save_document("TransportAuthorization", transport_id, dest_dir, db_path)


def get_transport_ids_with_documents(center_id: int, db_path: str) -> set[int]:
    return _ids_with_documents("TransportAuthorization", center_id, db_path)


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
            "[Hospital],[HHA],[Notes],[Gender],[Admission Date],[alt_id] "
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
                "alt_id":         int(row[22]) if row[22] is not None else None,
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

        c.execute(ABSENCES_SELECT, center_id)
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
    and [created_at] (row[8], a datetime or None for legacy rows). [Plan Type]
    (row[11]) exists only on [Authorization] — transport rows are one column
    shorter, hence the length guard."""
    d = map_authorization_row(row)
    d["health_plan"] = row[7] or ""
    d["created_at"] = row[8]
    d["member_id"] = row[9]
    d["auth_number"] = row[10]
    d["plan_type"] = (row[11] or "") if len(row) > 11 else ""
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


AUTH_ENDS_QUERY = "SELECT [Center ID], [auth_end] FROM [Authorization]"


def get_member_auth_ends(db_path: str, _retry: bool = True) -> list[tuple]:
    """All (center_id, auth_end) pairs from [Authorization] in one query, for
    the expiring/expired notifications. Cached read connection with the same
    stale-connection retry as get_member_context."""
    import pyodbc
    conn = _read_connection(db_path)
    try:
        c = conn.cursor()
        c.execute(AUTH_ENDS_QUERY)
        return [(r[0], r[1]) for r in c.fetchall()]
    except pyodbc.Error:
        _drop_read_connection(db_path)
        if _retry:
            return get_member_auth_ends(db_path, _retry=False)
        raise


def get_health_plans(db_path: str, _retry: bool = True) -> list[str]:
    """Distinct health plans present in the DB (Contacts + Authorization),
    sorted, for the add-member wizard's dropdown. Falls back to the static
    HEALTH_PLANS tuple when the DB has none or can't be read — an empty
    dropdown would block member creation entirely."""
    import pyodbc
    conn = _read_connection(db_path)
    try:
        c = conn.cursor()
        plans = set()
        for query in (HEALTH_PLANS_CONTACTS_QUERY, HEALTH_PLANS_AUTHS_QUERY):
            for row in c.execute(query).fetchall():
                value = ("" if row[0] is None else str(row[0])).strip()
                if value:
                    plans.add(value)
    except pyodbc.Error:
        _drop_read_connection(db_path)
        if _retry:
            return get_health_plans(db_path, _retry=False)
        return list(HEALTH_PLANS)
    return sorted(plans, key=str.upper) or list(HEALTH_PLANS)


def get_all_absences(db_path: str, _retry: bool = True) -> list[tuple]:
    """All (center_id, leave_type, start, end, notes) rows from [Absences]
    in one query, for the monthly absences report. Cached read connection
    with the same stale-connection retry as get_member_context."""
    import pyodbc
    conn = _read_connection(db_path)
    try:
        c = conn.cursor()
        c.execute(ABSENCES_ALL_SELECT)
        return [(r[0], r[1], r[2], r[3], r[4]) for r in c.fetchall()]
    except pyodbc.Error:
        _drop_read_connection(db_path)
        if _retry:
            return get_all_absences(db_path, _retry=False)
        raise


def classify_auth_notifications(rows, active_ids, today,
                                window_days: int = 35) -> dict:
    """Sort members into auth-notification buckets from raw (center_id,
    auth_end) rows.

    A member's effective end is the latest auth_end across their auths —
    the same rule as the header's "Authorization Expired" chip
    (gui.member_tabs.auth_warning), so a notification clears exactly when a
    new authorization with a later end date is added. Open-ended auths
    (null auth_end) are ignored the same way the chip ignores them.

    Only members in `active_ids` (active = not terminated) are considered;
    members with no dated auths at all are skipped — they have nothing to
    expire and already surface a "Missing: Authorizations" warning.

    Returns {"expiring": [(center_id, end_date, days_left)],
             "expired":  [(center_id, end_date, days_ago)]}
    with expiring sorted soonest-first and expired most-recent-first.
    Pure (no DB), so it is unit-testable.
    """
    latest: dict[int, date] = {}
    for cid, end in rows:
        if cid is None or end is None:
            continue
        cid = int(cid)
        if cid not in active_ids:
            continue
        end = end.date() if isinstance(end, datetime) else end
        if cid not in latest or end > latest[cid]:
            latest[cid] = end
    expiring, expired = [], []
    for cid, end in latest.items():
        days = (end - today).days
        if days < 0:
            expired.append((cid, end, -days))
        elif days <= window_days:
            expiring.append((cid, end, days))
    expiring.sort(key=lambda t: (t[2], t[0]))    # soonest end first
    expired.sort(key=lambda t: (t[2], t[0]))     # most recently expired first
    return {"expiring": expiring, "expired": expired}


def get_transport_authorizations(center_id: int, db_path: str,
                                 _retry: bool = True) -> list[dict]:
    """Transportation authorizations for a member (cached read connection).

    Same row shape as get_authorizations, so _map_auth_row applies. Returns []
    if the [TransportAuthorization] table is missing/unreadable, so member load
    and the rest of the UI keep working before the table exists.
    """
    import pyodbc
    try:
        conn = _read_connection(db_path)
        c = conn.cursor()
        c.execute(TRANSPORT_AUTH_SELECT, center_id)
        return [_map_auth_row(r) for r in c.fetchall()]
    except pyodbc.Error:
        _drop_read_connection(db_path)
        if _retry:
            return get_transport_authorizations(center_id, db_path, _retry=False)
        return []
    except FileNotFoundError:
        return []


def get_auth_edges(db_path: str, _retry: bool = True) -> list[dict]:
    """All care<->transport links from the [AuthEdge] junction table (small;
    filter in Python). Returns dicts with keys id, authorization_id,
    transport_authorization_id; [] on any error."""
    import pyodbc
    try:
        conn = _read_connection(db_path)
        c = conn.cursor()
        c.execute(AUTH_EDGE_SELECT)
        return [
            {"id": r[0], "authorization_id": r[1],
             "transport_authorization_id": r[2]}
            for r in c.fetchall()
        ]
    except pyodbc.Error:
        _drop_read_connection(db_path)
        if _retry:
            return get_auth_edges(db_path, _retry=False)
        return []
    except FileNotFoundError:
        return []


# Tables and columns the app queries unconditionally. Older databases predate
# some of them; missing ones make features fail with raw ODBC errors, so the
# main window checks once per database and lists anything absent up front.
REQUIRED_SCHEMA = {
    "Contacts": ["Center ID", "Last Name", "First Name", "Health Plan", "DOB",
                 "alt_id"],
    "Enrollment": ["Center ID", "start_date", "end_date"],
    "Authorization": ["Center ID", "auth_start", "auth_end", "auth_days",
                      "Health Plan", "created_at", "Member ID", "auth_number",
                      "Plan Type"],
    "Availability": ["Center ID", "Day Of Week", "avail_start", "avail_end"],
    "Absences": ["Center ID", "Leave Type", "Start_Date", "End_Date", "Notes"],
    "OneOffAvailability": ["Center ID", "date", "avail_start", "avail_end"],
    "EmergencyContact": ["Center ID", "Full Name", "Phone Number"],
    "TransportAuthorization": ["Center ID", "auth_start", "auth_end"],
    "AuthEdge": ["authorization_id", "transport_authorization_id"],
}


def missing_schema(db_path: str) -> list[str]:
    """Human-readable list of required tables/columns absent from db_path,
    e.g. ['table OneOffAvailability', 'column created_at on Authorization'].
    Empty list when the schema is complete."""
    conn = _read_connection(db_path)
    c = conn.cursor()
    tables = {row.table_name for row in c.tables(tableType="TABLE")}
    problems: list[str] = []
    for table, columns in REQUIRED_SCHEMA.items():
        if table not in tables:
            problems.append(f"table {table}")
            continue
        have = {row.column_name for row in c.columns(table=table)}
        problems += [f"column {col} on {table}"
                     for col in columns if col not in have]
    return problems


_transport_doc_col_cache: dict = {}


def transport_has_document_column(db_path: str) -> bool:
    """True if [TransportAuthorization] has a [Document] attachment column. Cached
    per db_path for the session; the Transportation tab shows the Document feature
    only when present (so the feature lights up once the user adds the column)."""
    if db_path in _transport_doc_col_cache:
        return _transport_doc_col_cache[db_path]
    result = False
    try:
        conn = _read_connection(db_path)
        cols = {row.column_name
                for row in conn.cursor().columns(table="TransportAuthorization")}
        result = "Document" in cols
    except Exception:
        result = False
    _transport_doc_col_cache[db_path] = result
    return result


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


def get_absences(center_id: int, db_path: str,
                 _retry: bool = True) -> list[dict]:
    """Absences for a member incl. Notes (cached read connection). Supersedes
    monthly_schedule.db.get_absences, whose row mapper drops [Notes].
    Mirrors get_member_context's stale-connection retry."""
    import pyodbc
    conn = _read_connection(db_path)
    try:
        c = conn.cursor()
        c.execute(ABSENCES_SELECT, center_id)
        return [map_absence_row(r) for r in c.fetchall()]
    except pyodbc.Error:
        _drop_read_connection(db_path)
        if _retry:
            return get_absences(center_id, db_path, _retry=False)
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
    _execute_write(db_path,
                   "UPDATE [Contacts] SET [Health Plan]=? WHERE [Center ID]=?",
                   (plan, center_id))
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
    _execute_write(db_path,
                   "UPDATE [Contacts] SET [Member ID]=? WHERE [Center ID]=?",
                   (member_id, center_id))
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
    transport_authorization: dict | None = None,
    db_path: str = "",
) -> None:
    """Insert a new member and all related records in one transaction.

    When a transport_authorization (e.g. {"auth_number": "..."}) is given along
    with an authorization, a transportation auth mirroring the care auth's
    dates/days/plan is inserted and linked to it via [AuthEdge].
    """
    with write_conn(db_path) as c:
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
                    authorization.get("auth_number", "") or "",
                    authorization.get("plan_type", "") or "",
                ),
            )
            # Optional transportation auth: mirrors the care auth's dates/days,
            # carries its own number, and is linked via [AuthEdge].
            if transport_authorization:
                c.execute("SELECT @@IDENTITY")
                care_id = int(c.fetchone()[0])
                c.execute(
                    INSERT_TRANSPORT_AUTH,
                    (
                        center_id,
                        authorization["auth_start"],
                        authorization["auth_end"],
                        None, None,
                        encode_auth_days(authorization["auth_days"]),
                        auth_plan,
                        datetime.now(),
                        member_id,
                        transport_authorization.get("auth_number", "") or "",
                    ),
                )
                c.execute("SELECT @@IDENTITY")
                transport_id = int(c.fetchone()[0])
                c.execute(INSERT_AUTH_EDGE, (care_id, transport_id))
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


def set_member_long_lat(center_id: int, long_lat: str, db_path: str) -> None:
    """Persist 'lng,lat' to a member's [Long Lat] (only when a place was picked)."""
    _execute_write(db_path, SET_LONG_LAT, (long_lat, center_id))


def set_member_alt_id(center_id: int, alt_id: int | None, db_path: str) -> None:
    """Persist a member's alternative id (None clears it)."""
    _execute_write(db_path, SET_ALT_ID, (alt_id, center_id))


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
    *,
    alt_id: int | None,
) -> None:
    _execute_write(db_path, UPDATE_CONTACT, (
        last_name, first_name, chinese_name, gender, dob,
        member_id, health_plan, medicaid, medicare, ssn,
        language, case_manager, home_tell, cell, address,
        emergency, pcp, hospital, hha, admission_date, notes,
        alt_id,
        center_id,
    ))


def insert_enrollment(center_id: int, start: date, end: date | None, db_path: str) -> None:
    _execute_write(db_path, INSERT_ENROLLMENT, (center_id, start, end))


def delete_enrollment(record_id: int, db_path: str) -> None:
    _execute_write(db_path, DELETE_ENROLLMENT, (record_id,))


def update_enrollment(record_id: int, start: date, end: date | None,
                      db_path: str) -> None:
    _execute_write(db_path, UPDATE_ENROLLMENT, (start, end, record_id))


def is_terminated(enrollments: list[dict], today=None) -> bool:
    """True when the member's latest enrollment (by start date) has ended —
    an end date that has passed. A future end date stays Active until the day
    arrives (an enrollment ending today reads as ended, matching
    enrollment_active). No enrollments -> False; latest ongoing -> False."""
    if not enrollments:
        return False
    if today is None:
        today = date.today()
    latest = max(enrollments, key=lambda e: e.get("start_date") or date.min)
    return not enrollment_active(latest, today)


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


def terminated_ids_from_rows(rows, today=None) -> set[int]:
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
    return {cid for cid, enrs in by_member.items() if is_terminated(enrs, today)}


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


def terminate_enrollment(record_id: int, db_path: str,
                         end_date: date | None = None) -> None:
    """Set an enrollment's end date (used by the Terminate button). Defaults
    to today when no date is given, e.g. when notified of a termination late."""
    _execute_write(db_path, UPDATE_ENROLLMENT_END,
                   (end_date or date.today(), record_id))


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
    auth_number: str = "",
    plan_type: str = "",
) -> None:
    _execute_write(db_path, INSERT_AUTHORIZATION, (
        center_id, auth_start, auth_end, effective_start, effective_end,
        encode_auth_days(auth_days), health_plan, datetime.now(), member_id,
        auth_number, plan_type,
    ))


def update_authorization(
    record_id: int,
    auth_start: date,
    auth_end: date,
    auth_days: set[int],
    health_plan: str,
    db_path: str,
    member_id: str = "",
    auth_number: str = "",
    plan_type: str = "",
) -> None:
    """Update an existing authorization's dates, days, plan, member id,
    auth number, and plan type. Also clears effective_start/effective_end: a non-null
    effective window overrides the auth dates when deciding which auth is in
    effect today, so leaving one behind after a date edit strands the row on
    its pre-edit period (empty day chips despite an "Active" pill). NULL makes
    the effective window follow the edited auth dates, matching how the Auths
    tab and wizard insert new rows."""
    _execute_write(db_path, UPDATE_AUTHORIZATION, (
        auth_start, auth_end, encode_auth_days(auth_days), health_plan,
        member_id, auth_number, plan_type, record_id,
    ))


def delete_authorization(record_id: int, db_path: str) -> None:
    _execute_write(db_path, DELETE_AUTHORIZATION, (record_id,))


def insert_transport_authorization(
    center_id: int,
    auth_start: date,
    auth_end: date,
    auth_days: set[int],
    health_plan: str,
    db_path: str,
    member_id: str = "",
    auth_number: str = "",
) -> int:
    """Insert a transportation authorization and return its new ID, so the caller
    can link it to a care auth via set_transport_link. effective_* are left NULL
    (nothing reads them for transport)."""
    with write_conn(db_path) as c:
        c.execute(
            INSERT_TRANSPORT_AUTH,
            (center_id, auth_start, auth_end, None, None,
             encode_auth_days(auth_days), health_plan, datetime.now(), member_id,
             auth_number),
        )
        c.execute("SELECT @@IDENTITY")
        return int(c.fetchone()[0])


def update_transport_authorization(
    record_id: int,
    auth_start: date,
    auth_end: date,
    auth_days: set[int],
    health_plan: str,
    db_path: str,
    member_id: str = "",
    auth_number: str = "",
) -> None:
    """Update a transport auth's dates, days, plan, member id, and auth number.
    Clears effective_start/effective_end for the same reason as
    update_authorization: the effective window must follow the edited dates."""
    _execute_write(db_path, UPDATE_TRANSPORT_AUTH, (
        auth_start, auth_end, encode_auth_days(auth_days), health_plan,
        member_id, auth_number, record_id,
    ))


def delete_transport_authorization(record_id: int, db_path: str) -> None:
    """Delete a transport auth and its [AuthEdge] links in one transaction."""
    with write_conn(db_path) as c:
        c.execute(DELETE_AUTH_EDGE_BY_TRANSPORT, (record_id,))
        c.execute(DELETE_TRANSPORT_AUTH, (record_id,))


def set_transport_link(transport_id: int, authorization_id, db_path: str) -> None:
    """Replace the care<->transport link for one transport auth: clear its existing
    [AuthEdge] rows, then add one for authorization_id (skipped when None)."""
    with write_conn(db_path) as c:
        c.execute(DELETE_AUTH_EDGE_BY_TRANSPORT, (transport_id,))
        if authorization_id is not None:
            c.execute(INSERT_AUTH_EDGE, (authorization_id, transport_id))


def insert_availability(
    center_id: int,
    day_of_week: int,
    avail_start: str,
    avail_end: str,
    effective_start: date,
    effective_end: date | None,
    db_path: str,
) -> None:
    _execute_write(db_path, INSERT_AVAILABILITY, (
        center_id, effective_start, effective_end, day_of_week,
        _hhmm_to_datetime(avail_start), _hhmm_to_datetime(avail_end),
    ))


def update_availability(record_id: int, avail_start: str, avail_end: str,
                        effective_start: date, effective_end: date | None,
                        db_path: str) -> None:
    """Update an availability row's start/end times (24-hour 'HH:mm') and its
    effective window. `effective_end` may be None for an open-ended window."""
    _execute_write(db_path, UPDATE_AVAILABILITY, (
        _hhmm_to_datetime(avail_start), _hhmm_to_datetime(avail_end),
        effective_start, effective_end, record_id,
    ))


def delete_availability(record_id: int, db_path: str) -> None:
    _execute_write(db_path, DELETE_AVAILABILITY, (record_id,))


def insert_one_off_availability(
    center_id: int,
    on_date: date,
    avail_start: str,
    avail_end: str,
    notes: str,
    db_path: str,
) -> None:
    _execute_write(db_path, INSERT_ONE_OFF_AVAILABILITY, (
        center_id, on_date, _hhmm_to_datetime(avail_start),
        _hhmm_to_datetime(avail_end), notes,
    ))


def update_one_off_availability(
    record_id: int,
    on_date: date,
    avail_start: str,
    avail_end: str,
    notes: str,
    db_path: str,
) -> None:
    _execute_write(db_path, UPDATE_ONE_OFF_AVAILABILITY, (
        on_date, _hhmm_to_datetime(avail_start),
        _hhmm_to_datetime(avail_end), notes, record_id,
    ))


def delete_one_off_availability(record_id: int, db_path: str) -> None:
    _execute_write(db_path, DELETE_ONE_OFF_AVAILABILITY, (record_id,))


def insert_emergency_contact(center_id: int, full_name: str, phone: str,
                             relationship: str, db_path: str) -> None:
    _execute_write(db_path, INSERT_EMERGENCY_CONTACT,
                   (center_id, full_name, phone, relationship))


def update_emergency_contact(record_id: int, full_name: str, phone: str,
                             relationship: str, db_path: str) -> None:
    _execute_write(db_path, UPDATE_EMERGENCY_CONTACT,
                   (full_name, phone, relationship, record_id))


def delete_emergency_contact(record_id: int, db_path: str) -> None:
    _execute_write(db_path, DELETE_EMERGENCY_CONTACT, (record_id,))


def insert_absence(
    center_id: int,
    leave_type: str,
    start: date,
    end: date,
    notes: str,
    db_path: str,
) -> None:
    _execute_write(db_path, INSERT_ABSENCE,
                   (center_id, leave_type, start, end, notes))


def update_absence(
    record_id: int,
    leave_type: str,
    start: date,
    end: date,
    notes: str,
    db_path: str,
) -> None:
    _execute_write(db_path, UPDATE_ABSENCE,
                   (leave_type, start, end, notes, record_id))


def delete_absence(record_id: int, db_path: str) -> None:
    _execute_write(db_path, DELETE_ABSENCE, (record_id,))
