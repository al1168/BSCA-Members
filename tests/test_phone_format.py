import pytest

from db.members import format_phone


@pytest.mark.parametrize("raw,expected", [
    ("2125550100", "(212)-555-0100"),
    ("212-555-0100", "(212)-555-0100"),
    ("(212)-555-0100", "(212)-555-0100"),   # idempotent
    ("212 555 0100", "(212)-555-0100"),
    ("646.555.0199", "(646)-555-0199"),
    ("", ""),
    (None, ""),
    ("555-0100", "555-0100"),               # 7 digits: left as-is
    ("12125550100", "12125550100"),         # 11 digits: left as-is
])
def test_format_phone(raw, expected):
    assert format_phone(raw) == expected
