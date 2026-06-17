"""Integration tests against the real populate_real_members.accdb test fixture.

These tests require the Microsoft Access ODBC driver and the test DB file.
They are skipped automatically if the file is not found.

Test DB: BSCA/scripts/test_dbs/populate_real_members.accdb
  - Contains the real Contacts table (including rows with NULL Center IDs)
  - Supporting tables (Enrollment, Authorization, etc.) are empty
"""
import os
import pytest

TEST_DB = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..", "..", "BSCA", "scripts", "test_dbs", "populate_real_members.accdb",
    )
)

pytestmark = pytest.mark.skipif(
    not os.path.exists(TEST_DB),
    reason=f"Test DB not found: {TEST_DB}",
)


# ── get_all_members ────────────────────────────────────────────────────

def test_get_all_members_returns_list():
    from db.members import get_all_members
    members = get_all_members(TEST_DB)
    assert isinstance(members, list)
    assert len(members) > 0


def test_get_all_members_no_none_center_ids():
    """NULL Center IDs in Contacts must be silently skipped."""
    from db.members import get_all_members
    members = get_all_members(TEST_DB)
    for m in members:
        assert m["center_id"] is not None
        assert isinstance(m["center_id"], int)


def test_get_all_members_no_none_strings():
    """last_name, first_name, health_plan must never be None (empty string ok)."""
    from db.members import get_all_members
    members = get_all_members(TEST_DB)
    for m in members:
        assert m["last_name"] is not None
        assert m["first_name"] is not None
        assert m["health_plan"] is not None


def test_get_all_members_sorted_by_last_name():
    from db.members import get_all_members
    members = get_all_members(TEST_DB)
    last_names = [m["last_name"].lower() for m in members]
    assert last_names == sorted(last_names)


def test_get_all_members_required_keys():
    from db.members import get_all_members
    members = get_all_members(TEST_DB)
    for m in members:
        assert set(m.keys()) == {"center_id", "last_name", "first_name", "health_plan"}


# ── center_id_exists ───────────────────────────────────────────────────

def test_center_id_exists_returns_true_for_real_member():
    from db.members import get_all_members, center_id_exists
    members = get_all_members(TEST_DB)
    first_id = members[0]["center_id"]
    assert center_id_exists(first_id, TEST_DB) is True


def test_center_id_exists_returns_false_for_missing():
    from db.members import center_id_exists
    # Use an implausibly large ID that won't exist
    assert center_id_exists(999999999, TEST_DB) is False


def test_suggest_next_center_id_is_free_non4_5digit_above_active_max():
    from db.members import (
        suggest_next_center_id, get_all_members, get_terminated_center_ids,
    )
    all_ids = {m["center_id"] for m in get_all_members(TEST_DB)}
    active_5digit = {i for i in all_ids if 10000 <= i <= 99999} \
        - get_terminated_center_ids(TEST_DB)

    nid = suggest_next_center_id(TEST_DB)
    assert nid not in all_ids        # never reuse an existing Center ID
    assert nid % 10 != 4             # never ends in 4
    assert 10000 <= nid <= 99999     # stays a 5-digit Center ID
    if active_5digit:
        # counts up from the highest 5-digit active member (ignores 7-digit ids)
        assert nid > max(active_5digit)


# ── read-connection caching (mtime-based) ──────────────────────────────

def test_read_connection_reconnects_only_when_db_changes():
    """The cached read connection is reused while the DB file is unchanged
    (fast member browsing) and reopened when the file's mtime changes — e.g.
    after an edit from another connection/Access — so reads stay live."""
    import pyodbc
    from monthly_schedule.db import build_connection_string
    from db.members import _read_connection, close_connections

    close_connections()
    c1 = _read_connection(TEST_DB)
    assert _read_connection(TEST_DB) is c1          # reused while unchanged

    ext = pyodbc.connect(build_connection_string(TEST_DB), autocommit=True)
    try:
        ext.cursor().execute(
            "INSERT INTO [EmergencyContact] ([Center ID],[Full Name],"
            "[Phone Number],[Relationship]) VALUES (?,?,?,?)",
            (987001, "RC", "1", "T"))
    finally:
        ext.close()
    try:
        assert _read_connection(TEST_DB) is not c1  # reconnected on change
    finally:
        clean = pyodbc.connect(build_connection_string(TEST_DB), autocommit=True)
        clean.cursor().execute(
            "DELETE FROM [EmergencyContact] WHERE [Center ID]=987001")
        clean.close()
        close_connections()


# ── bsca-core read functions ───────────────────────────────────────────

def test_get_member_returns_dict_for_valid_id():
    from db.members import get_all_members
    from monthly_schedule.db import get_member
    members = get_all_members(TEST_DB)
    first = members[0]
    result = get_member(first["center_id"], TEST_DB)
    assert result is not None
    assert result["center_id"] == first["center_id"]
    assert result["last_name"] == first["last_name"]


def test_get_member_returns_none_for_missing_id():
    from monthly_schedule.db import get_member
    result = get_member(999999999, TEST_DB)
    assert result is None


def test_get_enrollments_returns_list():
    """Supporting tables are empty in this fixture — list should be empty, not crash."""
    from db.members import get_all_members
    from monthly_schedule.db import get_enrollments
    members = get_all_members(TEST_DB)
    result = get_enrollments(members[0]["center_id"], TEST_DB)
    assert isinstance(result, list)


def test_get_authorizations_returns_list():
    from db.members import get_all_members
    from monthly_schedule.db import get_authorizations
    members = get_all_members(TEST_DB)
    result = get_authorizations(members[0]["center_id"], TEST_DB)
    assert isinstance(result, list)


def test_get_availability_returns_list():
    from db.members import get_all_members
    from monthly_schedule.db import get_availability
    members = get_all_members(TEST_DB)
    result = get_availability(members[0]["center_id"], TEST_DB)
    assert isinstance(result, list)


def test_get_absences_returns_list():
    from db.members import get_all_members
    from monthly_schedule.db import get_absences
    members = get_all_members(TEST_DB)
    result = get_absences(members[0]["center_id"], TEST_DB)
    assert isinstance(result, list)


# ── get_member_photo ──────────────────────────────────────────────────

def test_get_member_photo_returns_bytes_or_none():
    from db.members import get_all_members, get_member_photo
    members = get_all_members(TEST_DB)
    first = members[0]
    result = get_member_photo(first["center_id"], TEST_DB)
    assert result is None or isinstance(result, bytes)


def test_get_member_photo_bytes_start_with_jpeg_header():
    """If a photo exists it must be a valid JPEG (starts with FF D8)."""
    from db.members import get_all_members, get_member_photo
    members = get_all_members(TEST_DB)
    for m in members[:20]:
        data = get_member_photo(m["center_id"], TEST_DB)
        if data is not None:
            assert data[:2] == b'\xff\xd8', f"Not a JPEG for center_id={m['center_id']}"
            return


def test_get_member_photo_missing_id_returns_none():
    from db.members import get_member_photo
    result = get_member_photo(999999999, TEST_DB)
    assert result is None


def test_get_member_context_returns_all_contact_fields():
    from db.members import get_all_members, get_member_context
    members = get_all_members(TEST_DB)
    ctx = get_member_context(members[0]["center_id"], TEST_DB)
    m = ctx["member"]
    for key in (
        "center_id", "last_name", "first_name", "chinese_name",
        "gender", "dob", "member_id", "health_plan",
        "medicaid", "medicare", "ssn", "language",
        "case_manager", "home_tell", "cell", "address",
        "emergency", "pcp", "hospital", "hha",
        "admission_date", "notes",
    ):
        assert key in m, f"Missing key in member context: {key}"
        assert m[key] is not None, f"Key {key!r} is None (should be '' for missing)"


# ── connection caching ─────────────────────────────────────────────────

def test_repeated_context_reads_are_consistent():
    """Reusing the cached read connection must return stable data."""
    from db.members import get_all_members, get_member_context, close_connections
    close_connections()
    cid = get_all_members(TEST_DB)[0]["center_id"]
    first = get_member_context(cid, TEST_DB)["member"]
    for _ in range(3):
        again = get_member_context(cid, TEST_DB)["member"]
        assert again == first


def test_write_is_visible_through_cached_read_connection():
    """A committed update_contact() must be visible to the cached read
    connection (regression: ACE does not propagate commits across connections,
    so _connect() invalidates the cached read connection)."""
    import time
    from db.members import (
        get_all_members, get_member_context, update_contact, close_connections,
    )
    close_connections()
    cid = get_all_members(TEST_DB)[0]["center_id"]
    m = get_member_context(cid, TEST_DB)["member"]  # prime the cache
    original = m["notes"]
    marker = f"CACHETEST-{int(time.time())}"

    def write(notes):
        update_contact(
            cid, m["last_name"], m["first_name"], m["chinese_name"], m["gender"],
            m["dob"], m["member_id"], m["health_plan"], m["medicaid"], m["medicare"],
            m["ssn"], m["language"], m["case_manager"], m["home_tell"], m["cell"],
            m["address"], m["emergency"], m["pcp"], m["hospital"], m["hha"],
            m["admission_date"], notes, TEST_DB,
        )

    try:
        write(marker)
        assert get_member_context(cid, TEST_DB)["member"]["notes"] == marker
    finally:
        write(original)
    assert get_member_context(cid, TEST_DB)["member"]["notes"] == original


def test_terminate_enrollment_sets_end_to_today():
    from datetime import date
    from db.members import (
        get_all_members, insert_enrollment, terminate_enrollment, delete_enrollment,
    )
    from monthly_schedule.db import get_enrollments

    cid = get_all_members(TEST_DB)[0]["center_id"]
    before = {e["id"] for e in get_enrollments(cid, TEST_DB)}
    insert_enrollment(cid, date(2020, 1, 1), None, TEST_DB)
    new_id = ({e["id"] for e in get_enrollments(cid, TEST_DB)} - before).pop()
    try:
        terminate_enrollment(new_id, TEST_DB)
        row = next(e for e in get_enrollments(cid, TEST_DB) if e["id"] == new_id)
        assert row["end_date"] == date.today()
    finally:
        delete_enrollment(new_id, TEST_DB)


def test_insert_authorization_persists_health_plan():
    from datetime import date
    from db.members import (
        get_all_members, insert_authorization, get_authorizations,
        delete_authorization,
    )
    cid = get_all_members(TEST_DB)[0]["center_id"]
    before = {a["id"] for a in get_authorizations(cid, TEST_DB)}
    insert_authorization(
        cid, date(2026, 1, 1), date(2026, 12, 31), {1, 3, 5},
        None, None, "Aetna", TEST_DB,
    )
    new_id = ({a["id"] for a in get_authorizations(cid, TEST_DB)} - before).pop()
    try:
        row = next(a for a in get_authorizations(cid, TEST_DB) if a["id"] == new_id)
        assert row["health_plan"] == "Aetna"
    finally:
        delete_authorization(new_id, TEST_DB)


def test_insert_authorization_stamps_created_at():
    from datetime import date, datetime
    from db.members import (
        get_all_members, insert_authorization, get_authorizations,
        delete_authorization,
    )
    cid = get_all_members(TEST_DB)[0]["center_id"]
    before = {a["id"] for a in get_authorizations(cid, TEST_DB)}
    insert_authorization(
        cid, date(2026, 1, 1), date(2026, 12, 31), {1, 3, 5},
        None, None, "Aetna", TEST_DB,
    )
    new_id = ({a["id"] for a in get_authorizations(cid, TEST_DB)} - before).pop()
    try:
        row = next(a for a in get_authorizations(cid, TEST_DB) if a["id"] == new_id)
        assert isinstance(row["created_at"], datetime)
        # Stamped at insert time, so it should be very recent.
        assert abs((datetime.now() - row["created_at"]).total_seconds()) < 300
    finally:
        delete_authorization(new_id, TEST_DB)


def test_sync_writes_latest_auth_plan_into_contacts():
    from datetime import date
    from db.members import (
        get_all_members, get_member_context, insert_authorization,
        delete_authorization, get_authorizations, update_contact,
        sync_health_plan_from_latest_auth,
    )
    cid = get_all_members(TEST_DB)[0]["center_id"]
    m = get_member_context(cid, TEST_DB)["member"]
    original_plan = m["health_plan"]
    before = {a["id"] for a in get_authorizations(cid, TEST_DB)}
    # Insert an authorization with a far-future start so it is the latest.
    insert_authorization(
        cid, date(2099, 1, 1), date(2099, 12, 31), {1}, None, None, "VCM", TEST_DB,
    )
    new_id = ({a["id"] for a in get_authorizations(cid, TEST_DB)} - before).pop()
    try:
        returned = sync_health_plan_from_latest_auth(cid, TEST_DB)
        assert returned == "VCM"
        assert get_member_context(cid, TEST_DB)["member"]["health_plan"] == "VCM"
    finally:
        delete_authorization(new_id, TEST_DB)
        # Restore the member's original Contacts plan.
        update_contact(
            cid, m["last_name"], m["first_name"], m["chinese_name"], m["gender"],
            m["dob"], m["member_id"], original_plan, m["medicaid"], m["medicare"],
            m["ssn"], m["language"], m["case_manager"], m["home_tell"], m["cell"],
            m["address"], m["emergency"], m["pcp"], m["hospital"], m["hha"],
            m["admission_date"], m["notes"], TEST_DB,
        )


def test_sync_noop_when_no_authorizations():
    from db.members import get_all_members, get_authorizations, sync_health_plan_from_latest_auth
    members = get_all_members(TEST_DB)
    for mem in members:
        if not get_authorizations(mem["center_id"], TEST_DB):
            assert sync_health_plan_from_latest_auth(mem["center_id"], TEST_DB) is None
            return


def test_update_authorization_round_trips_changes():
    from datetime import date
    from db.members import (
        get_all_members, insert_authorization, update_authorization,
        get_authorizations, delete_authorization,
    )
    cid = get_all_members(TEST_DB)[0]["center_id"]
    before = {a["id"] for a in get_authorizations(cid, TEST_DB)}
    insert_authorization(
        cid, date(2026, 1, 1), date(2026, 6, 30), {1, 2}, None, None, "AE", TEST_DB,
    )
    new_id = ({a["id"] for a in get_authorizations(cid, TEST_DB)} - before).pop()
    try:
        update_authorization(
            new_id, date(2026, 2, 1), date(2026, 7, 31), {3, 4, 5}, "HF", TEST_DB,
        )
        row = next(a for a in get_authorizations(cid, TEST_DB) if a["id"] == new_id)
        assert row["auth_start"] == date(2026, 2, 1)
        assert row["auth_end"] == date(2026, 7, 31)
        assert row["auth_days"] == "3,4,5"
        assert row["health_plan"] == "HF"
    finally:
        delete_authorization(new_id, TEST_DB)


def test_update_availability_round_trips_changes():
    from datetime import date
    from db.members import (
        get_all_members, insert_availability, update_availability,
        delete_availability,
    )
    from monthly_schedule.db import get_availability

    cid = get_all_members(TEST_DB)[0]["center_id"]
    before = {a["id"] for a in get_availability(cid, TEST_DB)}
    insert_availability(cid, 1, "08:00", "16:00", date(2026, 1, 1), None, TEST_DB)
    new_id = ({a["id"] for a in get_availability(cid, TEST_DB)} - before).pop()
    try:
        update_availability(new_id, "09:30", "14:45", TEST_DB)
        row = next(a for a in get_availability(cid, TEST_DB) if a["id"] == new_id)
        assert row["avail_start"] == "09:30"
        assert row["avail_end"] == "14:45"
    finally:
        delete_availability(new_id, TEST_DB)


def test_insert_member_persists_member_id_phones_and_dob():
    """insert_member writes Member ID, Home Tell, Cell and DOB into Contacts.

    DOB is passed as a datetime.date (the production [DOB] is Access Date/Time).
    The shared fixture's [DOB] is still legacy Short Text, so we only assert the
    year survives the round-trip here — the Date/Time storage itself is proven in
    test_dob_round_trips_as_access_datetime below."""
    from datetime import date
    from db.members import (
        insert_member, center_id_exists, get_member_context, _connect,
    )

    cid = 880099  # implausible test id
    if center_id_exists(cid, TEST_DB):
        return  # don't clobber real data; skip
    insert_member(
        center_id=cid, last_name="PHONETEST", first_name="Pat",
        health_plan="HF", address="9 Pine St, New York, NY",
        enrollment_start=date(2026, 1, 1), enrollment_end=None,
        authorization=None, availability_rows=[],
        member_id="M-880099", home_tell="212-555-0100", cell="646-555-0199",
        dob=date(1948, 5, 14),
        db_path=TEST_DB,
    )
    try:
        member = get_member_context(cid, TEST_DB)["member"]
        assert member["member_id"] == "M-880099"
        assert member["home_tell"] == "212-555-0100"
        assert member["cell"] == "646-555-0199"
        assert "1948" in member["dob"]  # date forwarded through to [DOB]
    finally:
        conn = _connect(TEST_DB)
        try:
            cc = conn.cursor()
            cc.execute("DELETE FROM [Enrollment] WHERE [Center ID]=?", cid)
            cc.execute("DELETE FROM [Contacts] WHERE [Center ID]=?", cid)
            conn.commit()
        finally:
            conn.close()


def test_insert_member_with_authorization_stamps_created_at():
    """Regression: the new-member flow inserts the authorization inline, and that
    statement must supply [created_at] too (8 markers, not 7)."""
    from datetime import date, datetime
    from db.members import (
        insert_member, center_id_exists, get_authorizations, _connect,
    )

    cid = 880100  # implausible test id
    if center_id_exists(cid, TEST_DB):
        return  # don't clobber real data; skip
    insert_member(
        center_id=cid, last_name="AUTHTEST", first_name="Avi",
        health_plan="HF", address="3 Elm St, New York, NY",
        enrollment_start=date(2026, 1, 1), enrollment_end=None,
        authorization={
            "auth_start": date(2026, 1, 1), "auth_end": date(2026, 12, 31),
            "auth_days": {3, 6}, "health_plan": "HF",
        },
        availability_rows=[],
        member_id="M-880100", dob=date(1950, 2, 2),
        db_path=TEST_DB,
    )
    try:
        auths = get_authorizations(cid, TEST_DB)
        assert len(auths) == 1
        assert isinstance(auths[0]["created_at"], datetime)
    finally:
        conn = _connect(TEST_DB)
        try:
            cc = conn.cursor()
            cc.execute("DELETE FROM [Authorization] WHERE [Center ID]=?", cid)
            cc.execute("DELETE FROM [Enrollment] WHERE [Center ID]=?", cid)
            cc.execute("DELETE FROM [Contacts] WHERE [Center ID]=?", cid)
            conn.commit()
        finally:
            conn.close()


def test_dob_round_trips_as_access_datetime():
    """A datetime.date binds correctly to an Access Date/Time column — the type
    Contacts.[DOB] will have in production — and reads back as a real date, not
    text. Uses a dedicated Date/Time table because the shared fixture's [DOB] is
    still legacy Short Text."""
    from datetime import date, datetime
    import pyodbc
    from monthly_schedule.db import build_connection_string

    conn = pyodbc.connect(build_connection_string(TEST_DB), autocommit=True)
    c = conn.cursor()
    existing = {row.table_name for row in c.tables(tableType="TABLE")}
    if "DOBTypeTest" in existing:
        c.execute("DROP TABLE [DOBTypeTest]")
    c.execute("CREATE TABLE [DOBTypeTest] ([ID] LONG, [DOB] DATETIME)")
    try:
        c.execute("INSERT INTO [DOBTypeTest] ([ID],[DOB]) VALUES (?,?)",
                  (1, date(1948, 5, 14)))
        stored = c.execute(
            "SELECT [DOB] FROM [DOBTypeTest] WHERE [ID]=1"
        ).fetchone()[0]
        # Stored as a real temporal value, not a string, preserving the date.
        assert isinstance(stored, (date, datetime))
        assert (stored.year, stored.month, stored.day) == (1948, 5, 14)
    finally:
        c.execute("DROP TABLE [DOBTypeTest]")
        conn.close()


def test_long_lat_insert_and_set_round_trip():
    from datetime import date
    from db.members import (
        insert_member, set_member_long_lat, center_id_exists, _connect,
    )

    cid = 880088  # implausible test id
    if center_id_exists(cid, TEST_DB):
        return  # don't clobber real data; skip
    insert_member(
        center_id=cid, last_name="LLTEST", first_name="Geo",
        health_plan="HF", address="12 Monroe St, New York, NY",
        enrollment_start=date(2026, 1, 1), enrollment_end=None,
        authorization=None, availability_rows=[],
        long_lat="-73.99,40.69", db_path=TEST_DB,
    )
    conn = _connect(TEST_DB)
    try:
        c = conn.cursor()
        c.execute("SELECT [Long Lat] FROM [Contacts] WHERE [Center ID]=?", cid)
        assert c.fetchone()[0] == "-73.99,40.69"
        set_member_long_lat(cid, "-74.00,40.70", TEST_DB)
        conn2 = _connect(TEST_DB)
        try:
            c2 = conn2.cursor()
            c2.execute("SELECT [Long Lat] FROM [Contacts] WHERE [Center ID]=?", cid)
            assert c2.fetchone()[0] == "-74.00,40.70"
        finally:
            conn2.close()
    finally:
        conn.close()
        conn3 = _connect(TEST_DB)
        try:
            cc = conn3.cursor()
            cc.execute("DELETE FROM [Enrollment] WHERE [Center ID]=?", cid)
            cc.execute("DELETE FROM [Contacts] WHERE [Center ID]=?", cid)
            conn3.commit()
        finally:
            conn3.close()
