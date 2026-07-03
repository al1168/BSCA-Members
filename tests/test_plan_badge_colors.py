def test_readable_text_dark_on_light_white_on_dark():
    from gui.theme import _readable_text
    assert _readable_text("#f2ce1b") == "#1c1e26"   # yellow -> dark text
    assert _readable_text("#e6912f") == "#1c1e26"   # orange -> dark text
    assert _readable_text("#3f9e35") == "#f4f6fd"   # green  -> white text
    assert _readable_text("#2f5fd0") == "#f4f6fd"   # blue   -> white text
    assert _readable_text("#d02f63") == "#f4f6fd"   # pink   -> white text
    assert _readable_text("#6a2fa0") == "#f4f6fd"   # purple -> white text


def test_plan_colors_match_the_legend():
    from gui.theme import PLAN_COLORS
    assert PLAN_COLORS["AE"] == "#3f9e35"      # green
    assert PLAN_COLORS["BCBS"] == "#f2ce1b"    # yellow
    assert PLAN_COLORS["VCM"] == "#e6912f"     # orange
    assert PLAN_COLORS["ES"] == "#d83a30"      # red
    assert PLAN_COLORS["HOF"] == "#2f5fd0"     # blue
    assert PLAN_COLORS["HF"] == "#d02f63"      # pink
    assert PLAN_COLORS["HC"] == "#6a2fa0"      # purple


def test_yellow_badge_rule_uses_dark_text():
    from gui.theme import build_qss, DARK
    qss = build_qss(DARK)
    assert 'plan_badge[plan="BCBS"]' in qss
    rule = qss.split('plan_badge[plan="BCBS"]')[1].split("}")[0]
    assert "#f2ce1b" in rule      # yellow background
    assert "#1c1e26" in rule      # dark text for legibility
