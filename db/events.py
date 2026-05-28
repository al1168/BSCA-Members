import sqlite3
from datetime import date, datetime, timedelta

EVENT_TYPES = ("NEW", "EDIT", "AUTH", "ABS", "AVAIL", "ENROLL")

_CREATE = """
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    event_type  TEXT NOT NULL,
    center_id   INTEGER NOT NULL,
    member_name TEXT NOT NULL,
    description TEXT NOT NULL
)
"""


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(_CREATE)
    conn.commit()


def open_db(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def insert_event(
    conn: sqlite3.Connection,
    event_type: str,
    center_id: int,
    member_name: str,
    description: str,
) -> None:
    ts = datetime.now().isoformat(timespec="seconds")
    conn.execute(
        "INSERT INTO events (ts, event_type, center_id, member_name, description) "
        "VALUES (?, ?, ?, ?, ?)",
        (ts, event_type, center_id, member_name, description),
    )
    conn.commit()


def query_events(
    conn: sqlite3.Connection,
    center_id: int | None = None,
    filter_text: str | None = None,
) -> list[dict]:
    sql = "SELECT id, ts, event_type, center_id, member_name, description FROM events"
    params: list = []
    clauses: list[str] = []
    if center_id is not None:
        clauses.append("center_id = ?")
        params.append(center_id)
    if filter_text:
        clauses.append("(member_name LIKE ? OR description LIKE ?)")
        like = f"%{filter_text}%"
        params += [like, like]
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY ts DESC"
    rows = conn.execute(sql, params).fetchall()

    # Handle both Row objects (when row_factory is set) and tuples (when not)
    result = []
    for r in rows:
        if isinstance(r, sqlite3.Row):
            result.append(dict(r))
        else:
            # Tuple case: convert to dict using column names
            cols = ["id", "ts", "event_type", "center_id", "member_name", "description"]
            result.append(dict(zip(cols, r)))
    return result


def purge_old_events(conn: sqlite3.Connection) -> None:
    cutoff = (date.today() - timedelta(days=30)).isoformat()
    conn.execute("DELETE FROM events WHERE ts < ?", (cutoff,))
    conn.commit()
