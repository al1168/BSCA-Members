def test_theme_has_plan_badge_style():
    from gui.theme import build_qss, DARK, LIGHT
    for tokens in (DARK, LIGHT):
        qss = build_qss(tokens)
        assert "QLabel#plan_badge" in qss
