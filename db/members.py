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

HEALTH_PLANS = ("AE", "Aetna", "Anthem", "BCBS", "ES", "HC", "HF", "HOF", "VCM")

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
    "[Health Plan], [Address]) VALUES (?, ?, ?, ?, ?)"
)

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

INSERT_AUTHORIZATION = (
    "INSERT INTO [Authorization] ([Center ID], [auth_start], [auth_end], "
    "[effective_start], [effective_end], [auth_days]) VALUES (?, ?, ?, ?, ?, ?)"
)

DELETE_AUTHORIZATION = "DELETE FROM [Authorization] WHERE [ID]=?"

INSERT_AVAILABILITY = (
    "INSERT INTO [Availability] ([Center ID], [effective_start_date], "
    "[effective_end_date], [Day Of Week], [avail_start], [avail_end]) "
    "VALUES (?, ?, ?, ?, ?, ?)"
)

DELETE_AVAILABILITY = "DELETE FROM [Availability] WHERE [ID]=?"

INSERT_ABSENCE = (
    "INSERT INTO [Absences] ([Center ID], [Leave Type], [Start_Date], [End_Date]) "
    "VALUES (?, ?, ?, ?)"
)

DELETE_ABSENCE = "DELETE FROM [Absences] WHERE [ID]=?"


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
    """Return a cached autocommit read connection for db_path, opening if needed."""
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found: {db_path}")
    conn = _read_conn_cache.get(db_path)
    if conn is None:
        import pyodbc
        try:
            conn = pyodbc.connect(build_connection_string(db_path), autocommit=True)
        except pyodbc.Error as exc:
            raise RuntimeError(f"Could not open Access database: {exc}") from exc
        _read_conn_cache[db_path] = conn
    return conn


def _drop_read_connection(db_path: str) -> None:
    conn = _read_conn_cache.pop(db_path, None)
    if conn is not None:
        try:
            conn.close()
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

        c.execute(
            "SELECT [ID],[Center ID],[auth_start],[auth_end],"
            "[effective_start],[effective_end],[auth_days] "
            "FROM [Authorization] WHERE [Center ID]=?",
            center_id,
        )
        authorizations = [map_authorization_row(r) for r in c.fetchall()]

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

        return {
            "member": member,
            "enrollments": enrollments,
            "authorizations": authorizations,
            "availability": availability,
            "absences": absences,
        }
    except pyodbc.Error:
        # Cached connection may be stale (file moved, lock dropped); reopen once.
        _drop_read_connection(db_path)
        if _retry:
            return get_member_context(center_id, db_path, _retry=False)
        raise


def center_id_exists(center_id: int, db_path: str) -> bool:
    conn = _connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM [Contacts] WHERE [Center ID]=?", center_id)
        return cursor.fetchone()[0] > 0
    finally:
        conn.close()


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
    db_path: str,
) -> None:
    """Insert a new member and all related records in one transaction."""
    conn = _connect(db_path)
    try:
        c = conn.cursor()
        c.execute(INSERT_CONTACT, (center_id, last_name, first_name, health_plan, address))
        c.execute(INSERT_ENROLLMENT, (center_id, enrollment_start, enrollment_end))
        if authorization:
            c.execute(
                INSERT_AUTHORIZATION,
                (
                    center_id,
                    authorization["auth_start"],
                    authorization["auth_end"],
                    authorization.get("effective_start"),
                    authorization.get("effective_end"),
                    encode_auth_days(authorization["auth_days"]),
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


def insert_authorization(
    center_id: int,
    auth_start: date,
    auth_end: date,
    auth_days: set[int],
    effective_start: date | None,
    effective_end: date | None,
    db_path: str,
) -> None:
    conn = _connect(db_path)
    try:
        conn.cursor().execute(
            INSERT_AUTHORIZATION,
            (center_id, auth_start, auth_end, effective_start, effective_end,
             encode_auth_days(auth_days)),
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
