from datetime import date

from db.members import (
    enrollment_active, sort_enrollments_active_first, has_active_enrollment,
)

TODAY = date(2026, 6, 19)


def _e(id, start, end):
    return {"id": id, "start_date": start, "end_date": end}


def test_enrollment_active():
    assert enrollment_active(_e(1, date(2025, 1, 1), None), TODAY) is True        # ongoing
    assert enrollment_active(_e(2, date(2025, 1, 1), date(2027, 1, 1)), TODAY) is True   # future end
    assert enrollment_active(_e(3, date(2024, 1, 1), date(2024, 12, 31)), TODAY) is False  # ended
    assert enrollment_active(_e(4, date(2024, 1, 1), TODAY), TODAY) is False      # ends today -> ended


def test_sort_active_first_then_start_desc():
    es = [
        _e(1, date(2022, 1, 1), date(2022, 12, 31)),  # ended, old
        _e(2, date(2026, 1, 1), None),                # active, recent
        _e(3, date(2024, 1, 1), date(2024, 12, 31)),  # ended, newer
        _e(4, date(2023, 1, 1), None),                # active, older
    ]
    out = sort_enrollments_active_first(es, TODAY)
    assert [e["id"] for e in out] == [2, 4, 3, 1]
    assert [e["id"] for e in es] == [1, 2, 3, 4]   # input not mutated


def test_has_active_enrollment():
    assert has_active_enrollment([_e(1, date(2024, 1, 1), date(2024, 12, 31))], TODAY) is False
    assert has_active_enrollment([_e(1, date(2026, 1, 1), None)], TODAY) is True
    assert has_active_enrollment([], TODAY) is False
