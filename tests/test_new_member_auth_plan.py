from datetime import date


def _capture_inserts(monkeypatch):
    """Patch db.members._connect with a fake connection that records every
    (sql, params) passed to cursor.execute. Returns the shared calls list."""
    import db.members as m
    calls = []

    class FakeCursor:
        def execute(self, sql, params=()):
            calls.append((sql, params))

    class FakeConn:
        def cursor(self):
            return FakeCursor()
        def commit(self):
            pass
        def rollback(self):
            pass
        def close(self):
            pass

    monkeypatch.setattr(m, "_connect", lambda db_path: FakeConn())
    return calls


def _auth_plan(calls):
    """Health plan (param index 6) from the Authorization insert."""
    for sql, params in calls:
        if "[Authorization]" in sql:
            return params[6]
    raise AssertionError("no Authorization insert was issued")


def test_new_member_auth_inherits_member_health_plan(monkeypatch):
    import db.members as m
    calls = _capture_inserts(monkeypatch)
    auth = {"auth_start": date(2026, 1, 1), "auth_end": date(2026, 12, 31),
            "auth_days": {1, 3, 5}}   # wizard supplies no health_plan
    m.insert_member(
        center_id=1, last_name="A", first_name="B",
        health_plan="HOF", address="",
        enrollment_start=date(2026, 1, 1), enrollment_end=None,
        authorization=auth, availability_rows=[], db_path="x",
    )
    assert _auth_plan(calls) == "HOF"   # not blank


def test_explicit_auth_plan_is_respected(monkeypatch):
    import db.members as m
    calls = _capture_inserts(monkeypatch)
    auth = {"auth_start": date(2026, 1, 1), "auth_end": date(2026, 12, 31),
            "auth_days": {1}, "health_plan": "Anthem"}
    m.insert_member(
        center_id=1, last_name="A", first_name="B",
        health_plan="HOF", address="",
        enrollment_start=date(2026, 1, 1), enrollment_end=None,
        authorization=auth, availability_rows=[], db_path="x",
    )
    assert _auth_plan(calls) == "Anthem"   # explicit plan wins over member's
