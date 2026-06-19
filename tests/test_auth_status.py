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


# ── overlap detection (conflicting auth date ranges) ───────────────────────
def test_auth_overlap_map_flags_overlapping_ranges():
    from gui.member_tabs import auth_overlap_map
    auths = [
        {"id": 1, "auth_start": date(2026, 1, 1), "auth_end": date(2026, 6, 30)},
        {"id": 2, "auth_start": date(2026, 6, 1), "auth_end": date(2026, 12, 31)},  # overlaps 1
        {"id": 3, "auth_start": date(2027, 1, 1), "auth_end": date(2027, 6, 30)},   # clear
    ]
    m = auth_overlap_map(auths)
    assert {a["id"] for a in m[1]} == {2}
    assert {a["id"] for a in m[2]} == {1}
    assert m[3] == []


def test_auth_overlap_touching_endpoints_counts():
    from gui.member_tabs import auth_overlap_map
    auths = [
        {"id": 1, "auth_start": date(2026, 1, 1), "auth_end": date(2026, 6, 30)},
        {"id": 2, "auth_start": date(2026, 6, 30), "auth_end": date(2026, 12, 31)},
    ]
    m = auth_overlap_map(auths)
    assert {a["id"] for a in m[1]} == {2}   # shared day = both active that day


def test_auth_overlap_skips_undated():
    from gui.member_tabs import auth_overlap_map
    auths = [
        {"id": 1, "auth_start": date(2026, 1, 1), "auth_end": None},   # no end
        {"id": 2, "auth_start": date(2026, 1, 1), "auth_end": date(2026, 12, 31)},
    ]
    m = auth_overlap_map(auths)
    assert 1 not in m            # undated rows are not flagged
    assert m[2] == []


def test_auths_overlapping_a_candidate_range():
    from gui.member_tabs import auths_overlapping
    auths = [
        {"id": 1, "auth_start": date(2026, 1, 1), "auth_end": date(2026, 6, 30)},
        {"id": 2, "auth_start": date(2027, 1, 1), "auth_end": date(2027, 6, 30)},
    ]
    hit = auths_overlapping(auths, date(2026, 5, 1), date(2026, 8, 1))
    assert {a["id"] for a in hit} == {1}
    # excluding the row being edited
    assert auths_overlapping(auths, date(2026, 1, 1), date(2026, 6, 30),
                             exclude_id=1) == []


# ── header/Info overlay uses the in-effect auth, not the latest ────────────
def test_overlay_current_auth_uses_in_effect_values():
    from datetime import timedelta
    import gui.member_tabs as mt
    today = date.today()
    w = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)
    w._member = {"health_plan": "Anthem", "member_id": "23457"}  # stale latest
    w._authorizations = [
        {"effective_start": today - timedelta(days=10),
         "effective_end": today + timedelta(days=10),
         "health_plan": "AE", "member_id": "123456"},            # current
        {"effective_start": today + timedelta(days=30),
         "effective_end": today + timedelta(days=300),
         "health_plan": "Anthem", "member_id": "23457"},          # upcoming
    ]
    w._overlay_current_auth()
    assert w._member["health_plan"] == "AE"
    assert w._member["member_id"] == "123456"

