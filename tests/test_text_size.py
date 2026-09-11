"""App-wide text size mode: one scale factor drives every on-screen font size
and the fixed dimensions that hold text."""
import os
import re

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


# ── scale model ────────────────────────────────────────────────────────────

def test_text_sizes_and_factors():
    from gui.theme import TEXT_SIZES, BASE_PX, text_scale_for
    assert TEXT_SIZES == {"normal": 13, "large": 25, "xlarge": 30}
    assert BASE_PX == 13
    assert text_scale_for("normal") == 1.0
    assert text_scale_for("large") == pytest.approx(25 / 13)
    assert text_scale_for("xlarge") == pytest.approx(30 / 13)
    assert text_scale_for("bogus") == 1.0


def test_px_rounds_to_nearest_pixel():
    from gui.theme import set_text_size, px, current_text_scale
    assert current_text_scale() == 1.0
    assert px(13) == 13 and px(9) == 9
    set_text_size("large")
    assert [px(n) for n in (9, 10, 12, 13, 20)] == [17, 19, 23, 25, 38]
    set_text_size("xlarge")
    assert [px(n) for n in (9, 10, 12, 13, 20)] == [21, 23, 28, 30, 46]
    assert px(220) == 508          # sidebar width at Extra Large (Task 6)


def test_set_text_size_returns_scale_and_ignores_unknown():
    from gui.theme import set_text_size, current_text_scale
    assert set_text_size("xlarge") == pytest.approx(30 / 13)
    assert set_text_size("nonsense") == 1.0
    assert current_text_scale() == 1.0


def test_apply_theme_sets_scale_only_when_asked(qapp):
    from gui import theme
    theme.apply_theme(qapp, "dark", "xlarge")
    assert theme.current_text_scale() == pytest.approx(30 / 13)
    theme.apply_theme(qapp, "light")               # theme-only change
    assert theme.current_text_scale() == pytest.approx(30 / 13)
    theme.apply_theme(qapp, "dark", "normal")
    assert theme.current_text_scale() == 1.0
