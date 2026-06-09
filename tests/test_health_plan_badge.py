def test_theme_has_plan_badge_style():
    from gui.theme import build_qss, DARK, LIGHT
    for tokens in (DARK, LIGHT):
        qss = build_qss(tokens)
        assert "QLabel#plan_badge" in qss


def test_plan_colors_cover_all_health_plans():
    from gui.theme import PLAN_COLORS
    from db.members import HEALTH_PLANS
    assert set(HEALTH_PLANS) <= set(PLAN_COLORS)


def test_theme_has_per_plan_rules():
    from gui.theme import build_qss, DARK, LIGHT
    from db.members import HEALTH_PLANS
    for tokens in (DARK, LIGHT):
        qss = build_qss(tokens)
        for code in HEALTH_PLANS:
            assert f'[plan="{code}"]' in qss
