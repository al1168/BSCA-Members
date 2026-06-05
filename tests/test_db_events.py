import sqlite3
from datetime import date, timedelta
from db.events import init_db, insert_event, query_events, purge_old_events, EVENT_TYPES


def make_db():
    conn = sqlite3.connect(":memory:")
    init_db(conn)
    return conn


def test_init_creates_table():
    conn = make_db()
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='events'")
    assert cursor.fetchone() is not None


def test_insert_and_query_all(tmp_path):
    conn = make_db()
    insert_event(conn, "NEW", 1001, "Smith, John", "Member added to system")
    rows = query_events(conn)
    assert len(rows) == 1
    assert rows[0]["event_type"] == "NEW"
    assert rows[0]["center_id"] == 1001
    assert rows[0]["member_name"] == "Smith, John"
    assert rows[0]["description"] == "Member added to system"


def test_query_by_center_id(tmp_path):
    conn = make_db()
    insert_event(conn, "AUTH", 1001, "Smith, John", "Auth added")
    insert_event(conn, "ABS",  1002, "Doe, Jane",  "Absence added")
    rows = query_events(conn, center_id=1001)
    assert len(rows) == 1
    assert rows[0]["center_id"] == 1001


def test_query_filter_text(tmp_path):
    conn = make_db()
    insert_event(conn, "EDIT", 1001, "Smith, John", "Health Plan changed: HOF → Anthem")
    insert_event(conn, "ABS",  1002, "Doe, Jane",   "Absence added: Medical")
    rows = query_events(conn, filter_text="Medical")
    assert len(rows) == 1
    assert rows[0]["center_id"] == 1002


def test_purge_deletes_old_rows():
    conn = make_db()
    old_ts = (date.today() - timedelta(days=31)).isoformat() + "T00:00:00"
    conn.execute(
        "INSERT INTO events (ts, event_type, center_id, member_name, description) VALUES (?,?,?,?,?)",
        (old_ts, "NEW", 999, "Old, Member", "old event"),
    )
    conn.commit()
    insert_event(conn, "NEW", 1001, "Smith, John", "recent event")
    purge_old_events(conn)
    rows = query_events(conn)
    assert len(rows) == 1
    assert rows[0]["center_id"] == 1001


def test_event_types_constants():
    for t in ("NEW", "EDIT", "AUTH", "ABS", "AVAIL", "ENROLL"):
        assert t in EVENT_TYPES


def test_delete_style_description_round_trips(tmp_path):
    from db.events import open_db, insert_event, query_events
    conn = open_db(str(tmp_path / "ev.db"))
    insert_event(conn, "AUTH", 25049, "Lee, Mary",
                 "Authorization deleted: 2025-01-01 – 2025-12-31 [Mon Wed Fri] · HF")
    rows = query_events(conn, center_id=25049)
    conn.close()
    assert len(rows) == 1
    assert rows[0]["event_type"] == "AUTH"
    assert "Authorization deleted" in rows[0]["description"]
    assert "[Mon Wed Fri]" in rows[0]["description"]
