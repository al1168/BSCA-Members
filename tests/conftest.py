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

_CREATE_ONE_OFF = """
CREATE TABLE [OneOffAvailability] (
    [ID] AUTOINCREMENT PRIMARY KEY,
    [Center ID] LONG,
    [date] DATETIME,
    [avail_start] DATETIME,
    [avail_end] DATETIME,
    [Notes] MEMO
)
"""


@pytest.fixture(scope="session", autouse=True)
def ensure_one_off_availability_table():
    """Create [OneOffAvailability] in the test DB if it doesn't exist yet.

    Dropped at session end so the test DB stays at its original schema.
    This fixture is a no-op when the test DB is not present (integration
    tests are skipped by their own pytestmark in that case).
    """
    if not os.path.exists(_TEST_DB):
        yield
        return

    import pyodbc
    from monthly_schedule.db import build_connection_string

    conn = pyodbc.connect(build_connection_string(_TEST_DB), autocommit=True)
    c = conn.cursor()
    tables = {row.table_name for row in c.tables(tableType="TABLE")}
    created = False
    if "OneOffAvailability" not in tables:
        c.execute(_CREATE_ONE_OFF)
        created = True
    conn.close()

    yield

    if created:
        conn2 = pyodbc.connect(build_connection_string(_TEST_DB), autocommit=True)
        try:
            conn2.cursor().execute("DROP TABLE [OneOffAvailability]")
        except Exception:
            pass
        finally:
            conn2.close()
