from datetime import date

from gui.member_tabs import sort_auths_latest_first


def test_sort_latest_end_first():
    auths = [
        {"id": 1, "auth_end": date(2025, 1, 1)},
        {"id": 2, "auth_end": date(2026, 12, 31)},
        {"id": 3, "auth_end": date(2025, 6, 1)},
    ]
    assert [a["id"] for a in sort_auths_latest_first(auths)] == [2, 3, 1]


def test_sort_none_end_last():
    auths = [{"id": 1, "auth_end": None}, {"id": 2, "auth_end": date(2025, 1, 1)}]
    assert [a["id"] for a in sort_auths_latest_first(auths)] == [2, 1]


def test_sort_does_not_mutate_input():
    auths = [{"id": 1, "auth_end": date(2025, 1, 1)},
             {"id": 2, "auth_end": date(2026, 1, 1)}]
    snapshot = list(auths)
    sort_auths_latest_first(auths)
    assert auths == snapshot
