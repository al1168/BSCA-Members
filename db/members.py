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
    "UPDATE [Contacts] SET [Last Name]=?, [First Name]=?, "
    "[Health Plan]=?, [Address]=? WHERE [Center ID]=?"
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
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found: {db_path}")
    import pyodbc
    try:
        return pyodbc.connect(build_connection_string(db_path), autocommit=False)
    except pyodbc.Error as exc:
        raise RuntimeError(f"Could not open Access database: {exc}") from exc


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
    try:
        import win32com.client
        dao = win32com.client.Dispatch("DAO.DBEngine.120")
        db = dao.OpenDatabase(db_path)
        try:
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
        finally:
            db.Close()
    except Exception:
        return None


def get_member_context(center_id: int, db_path: str) -> dict:
    """Fetch member + all 4 supporting tables in one connection.

    Returns dict with keys: member, enrollments, authorizations,
    availability, absences.  Reusing one connection cuts the per-click
    latency from ~5 × 230 ms to ~230 ms (5× speedup).
    """
    conn = _connect(db_path)
    try:
        c = conn.cursor()

        c.execute(
            "SELECT [Center ID],[Last Name],[First Name],[Health Plan],"
            "[Address],[Long Lat] FROM [Contacts] WHERE [Center ID]=?",
            center_id,
        )
        row = c.fetchone()
        member = map_member_row(row) if row else {}

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
    finally:
        conn.close()


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
    health_plan: str,
    address: str,
    db_path: str,
) -> None:
    conn = _connect(db_path)
    try:
        conn.cursor().execute(
            UPDATE_CONTACT, (last_name, first_name, health_plan, address, center_id)
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
