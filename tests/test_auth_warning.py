from datetime import date

from gui.member_tabs import auth_warning

TODAY = date(2026, 6, 5)


def test_no_authorizations_is_missing():
    assert auth_warning([], TODAY) == "Missing: Authorizations"


def test_single_expired_auth():
    auths = [{"auth_end": date(2026, 6, 4)}]
    assert auth_warning(auths, TODAY) == "Authorization Expired"


def test_auth_ending_today_is_valid():
    auths = [{"auth_end": date(2026, 6, 5)}]
    assert auth_warning(auths, TODAY) is None


def test_auth_ending_tomorrow_is_valid():
    auths = [{"auth_end": date(2026, 6, 6)}]
    assert auth_warning(auths, TODAY) is None


def test_mix_expired_and_valid_is_none():
    auths = [{"auth_end": date(2025, 1, 1)}, {"auth_end": date(2026, 12, 31)}]
    assert auth_warning(auths, TODAY) is None


def test_null_end_date_is_not_expired():
    auths = [{"auth_end": None}]
    assert auth_warning(auths, TODAY) is None
