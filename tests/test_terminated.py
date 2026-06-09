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


def test_is_terminated_latest_ended_future():
    enrs = [{"start_date": date(2026, 1, 1), "end_date": date(2099, 1, 1)}]
    assert is_terminated(enrs) is True


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
