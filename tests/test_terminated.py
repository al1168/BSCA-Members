from datetime import date

from db.members import is_terminated, terminated_ids_from_rows


def test_is_terminated_no_enrollments():
    assert is_terminated([]) is False


def test_is_terminated_latest_ongoing():
    enrs = [
        {"start_date": date(2025, 1, 1), "end_date": date(2025, 6, 1)},
        {"start_date": date(2025, 7, 1), "end_date": None},
    ]
    assert is_terminated(enrs) is False


def test_is_terminated_latest_ended_past():
    enrs = [{"start_date": date(2025, 1, 1), "end_date": date(2025, 12, 1)}]
    assert is_terminated(enrs) is True


def test_future_end_date_stays_active_until_the_day():
    # Terminated is decided by the enrollment *day*: an end date that hasn't
    # arrived yet keeps the member Active; the day itself reads as ended.
    enrs = [{"start_date": date(2026, 1, 1), "end_date": date(2099, 1, 1)}]
    assert is_terminated(enrs, today=date(2026, 7, 17)) is False
    assert is_terminated(enrs, today=date(2099, 1, 1)) is True
    assert is_terminated(enrs, today=date(2099, 1, 2)) is True


def test_terminated_ids_from_rows():
    rows = [
        (100, date(2025, 1, 1), date(2025, 6, 1)),   # only enrollment, ended
        (200, date(2025, 1, 1), None),               # ongoing
        (300, date(2025, 1, 1), date(2025, 3, 1)),   # old ended
        (300, date(2025, 9, 1), None),               # newer ongoing (re-enroll)
        (None, date(2025, 1, 1), date(2025, 2, 1)),  # null center id -> skipped
    ]
    assert terminated_ids_from_rows(rows) == {100}


def test_theme_has_terminated_badge():
    from gui.theme import build_qss, DARK, LIGHT
    for tokens in (DARK, LIGHT):
        assert "QLabel#terminated_badge" in build_qss(tokens)


def test_active_first_orders_terminated_last():
    from gui.main_window import active_first
    members = [
        {"center_id": 1, "last_name": "Adams"},
        {"center_id": 2, "last_name": "Brown"},
        {"center_id": 3, "last_name": "Clark"},
    ]
    out = active_first(members, {2})
    # Active 1 and 3 keep alphabetical order; terminated 2 sinks to the bottom.
    assert [m["center_id"] for m in out] == [1, 3, 2]


def test_active_first_no_terminated_preserves_order():
    from gui.main_window import active_first
    members = [{"center_id": 1}, {"center_id": 2}, {"center_id": 3}]
    out = active_first(members, set())
    assert [m["center_id"] for m in out] == [1, 2, 3]
