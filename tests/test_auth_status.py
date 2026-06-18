import os
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

TODAY = date(2026, 6, 18)


# ── auth_status: active / upcoming / expired ───────────────────────────────
def test_auth_status_expired():
    from gui.member_tabs import auth_status
    assert auth_status(
        {"auth_start": date(2025, 1, 1), "auth_end": date(2025, 12, 31)}, TODAY
    ) == "expired"


def test_auth_status_upcoming():
    from gui.member_tabs import auth_status
    assert auth_status(
        {"auth_start": date(2026, 7, 1), "auth_end": date(2027, 6, 30)}, TODAY
    ) == "upcoming"


def test_auth_status_active_and_boundaries():
    from gui.member_tabs import auth_status
    assert auth_status(
        {"auth_start": date(2026, 1, 1), "auth_end": date(2026, 12, 31)}, TODAY
    ) == "active"
    # start today / end today still count as active (in effect)
    assert auth_status({"auth_start": TODAY, "auth_end": TODAY}, TODAY) == "active"


# ── current_authorization: in effect today, latest start wins ──────────────
def test_current_authorization_picks_in_effect_latest_start():
    from db.members import current_authorization
    auths = [
        {"effective_start": date(2026, 1, 1), "effective_end": date(2026, 12, 31),
         "health_plan": "A"},
        {"effective_start": date(2026, 3, 1), "effective_end": date(2026, 9, 30),
         "health_plan": "B"},   # later start, still in effect today
        {"effective_start": date(2026, 7, 1), "effective_end": date(2027, 1, 1),
         "health_plan": "C"},   # upcoming, not in effect
    ]
    assert current_authorization(auths, TODAY)["health_plan"] == "B"


def test_current_authorization_none_when_no_in_effect():
    from db.members import current_authorization
    auths = [
        {"effective_start": date(2099, 1, 1), "effective_end": date(2099, 12, 31)},
        {"effective_start": date(2000, 1, 1), "effective_end": date(2000, 12, 31)},
    ]
    assert current_authorization(auths, TODAY) is None
