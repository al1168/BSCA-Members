import pytest

from db.members import format_date_only


@pytest.mark.parametrize("raw,expected", [
    ("2000-03-15 00:00:00", "2000-03-15"),
    ("2000-03-15 14:30:00", "2000-03-15"),   # strips any time, not just midnight
    ("2000-03-15 00:00:00.000000", "2000-03-15"),
    ("2000-03-15", "2000-03-15"),
    ("03/15/2000", "03/15/2000"),
    ("", ""),
    (None, ""),
])
def test_format_date_only(raw, expected):
    assert format_date_only(raw) == expected
