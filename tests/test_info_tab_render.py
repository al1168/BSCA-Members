# tests/test_info_tab_render.py
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


# ── theme: per-field style rules exist in both themes ──────────────────────

def test_qss_has_highlight_rules_both_themes():
    from gui.theme import build_qss, DARK, LIGHT
    for tokens in (DARK, LIGHT):
        qss = build_qss(tokens)
        for color in ("amber", "blue", "green", "red"):
            assert f'QLineEdit[hl="{color}"]' in qss
            assert tokens[f"hl_{color}"] in qss
        assert 'QLineEdit[fbold="true"]' in qss
        assert 'QLineEdit[fsize="large"]' in qss


def test_highlight_tokens_differ_between_themes():
    from gui.theme import DARK, LIGHT
    for color in ("amber", "blue", "green", "red"):
        assert DARK[f"hl_{color}"] != LIGHT[f"hl_{color}"]
