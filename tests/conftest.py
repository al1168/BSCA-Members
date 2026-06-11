"""Session-scoped fixtures for integration tests.

Creates tables that exist in production but may not exist in older test DB
fixtures, then drops them at the end of the session to keep the test DB clean.
"""
import os
import pytest

_TEST_DB = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..", "..", "BSCA", "scripts", "test_dbs", "populate_real_members.accdb",
    )
)

_CREATE_SQL = {
    "OneOffAvailability": """
        CREATE TABLE [OneOffAvailability] (
            [ID] AUTOINCREMENT PRIMARY KEY,
            [Center ID] LONG,
            [date] DATETIME,
            [avail_start] DATETIME,
            [avail_end] DATETIME,
            [Notes] MEMO
        )
    """,
    "EmergencyContact": """
        CREATE TABLE [EmergencyContact] (
            [ID] AUTOINCREMENT PRIMARY KEY,
            [Center ID] LONG,
            [Full Name] TEXT(255),
            [Phone Number] TEXT(255),
            [Relationship] TEXT(255)
        )
    """,
}


@pytest.fixture(scope="session", autouse=True)
def ensure_optional_tables():
    """Create tables that newer code queries but older test DBs may lack; drop the
    ones we created at session end. No-op when the test DB is absent (integration
    tests skip themselves in that case)."""
    if not os.path.exists(_TEST_DB):
        yield
        return

    import pyodbc
    from monthly_schedule.db import build_connection_string

    conn = pyodbc.connect(build_connection_string(_TEST_DB), autocommit=True)
    c = conn.cursor()
    existing = {row.table_name for row in c.tables(tableType="TABLE")}
    created = []
    for name, sql in _CREATE_SQL.items():
        if name not in existing:
            c.execute(sql)
            created.append(name)
    conn.close()

    yield

    if created:
        conn2 = pyodbc.connect(build_connection_string(_TEST_DB), autocommit=True)
        try:
            for name in created:
                try:
                    conn2.cursor().execute(f"DROP TABLE [{name}]")
                except Exception:
                    pass
        finally:
            conn2.close()
