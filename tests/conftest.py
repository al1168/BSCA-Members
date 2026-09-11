"""Session-scoped fixtures for integration tests.

Creates tables that exist in production but may not exist in older test DB
fixtures, then drops them at the end of the session to keep the test DB clean.
"""
import os
import pytest


@pytest.fixture(autouse=True)
def _normal_text_scale():
    """The app-wide text scale is module state in gui.theme; pin it to Normal
    before and after every test so scale-changing tests cannot leak."""
    from gui import theme
    theme.set_text_size("normal")
    yield
    theme.set_text_size("normal")


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
    "Holidays": """
        CREATE TABLE [Holidays] (
            [ID] AUTOINCREMENT PRIMARY KEY,
            [holiday_name] TEXT(255),
            [date] DATETIME
        )
    """,
    "OperatingDays": """
        CREATE TABLE [OperatingDays] (
            [ID] AUTOINCREMENT PRIMARY KEY,
            [day_name] TEXT(20),
            [Day Of Week] LONG,
            [opening_time] DATETIME,
            [closing_time] DATETIME
        )
    """,
}


# Columns that newer code queries but older test DB fixtures may lack:
# {table: [(column, type), ...]}. Added if missing and dropped at session end.
_ADD_COLUMNS = {
    "Authorization": [("created_at", "DATETIME"), ("Member ID", "TEXT(255)"),
                      ("Plan Type", "TEXT(255)")],
    "Absences": [("Notes", "MEMO")],
    "Contacts": [("alt_id", "LONG"), ("Group", "TEXT(255)")],
}


@pytest.fixture(scope="session", autouse=True)
def ensure_optional_tables():
    """Create tables and columns that newer code queries but older test DBs may
    lack; drop the ones we created at session end. No-op when the test DB is
    absent (integration tests skip themselves in that case)."""
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

    added_columns = []
    for table, coldefs in _ADD_COLUMNS.items():
        cols = {row.column_name for row in c.columns(table=table)}
        for column, coltype in coldefs:
            if column not in cols:
                c.execute(f"ALTER TABLE [{table}] ADD COLUMN [{column}] {coltype}")
                added_columns.append((table, column))
    conn.close()

    yield

    if created or added_columns:
        conn2 = pyodbc.connect(build_connection_string(_TEST_DB), autocommit=True)
        try:
            for table, column in added_columns:
                try:
                    conn2.cursor().execute(
                        f"ALTER TABLE [{table}] DROP COLUMN [{column}]")
                except Exception:
                    pass
            for name in created:
                try:
                    conn2.cursor().execute(f"DROP TABLE [{name}]")
                except Exception:
                    pass
        finally:
            conn2.close()
