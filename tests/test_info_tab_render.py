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


# ── rendering: Info field styles actually render ────────────────────────────

def _styled_line_edit(object_name, props):
    from PyQt6.QtWidgets import QLineEdit
    from gui.theme import build_qss, DARK
    w = QLineEdit("value")
    if object_name:
        w.setObjectName(object_name)
    w.setReadOnly(True)
    for k, v in props.items():
        w.setProperty(k, v)
    w.setStyleSheet(build_qss(DARK))
    w.style().unpolish(w)
    w.style().polish(w)
    return w


def test_fbold_and_fsize_take_effect_on_info_field(qapp):
    w = _styled_line_edit("info_field", {"fbold": "true", "fsize": "large"})
    assert w.font().weight() == 800
    assert w.font().pixelSize() == 16


def test_highlight_background_renders_on_info_field(qapp):
    from PyQt6.QtGui import QColor
    from gui.theme import DARK
    w = _styled_line_edit("info_field", {"hl": "amber"})
    w.resize(120, 30)
    img = w.grab().toImage()
    sampled = QColor(img.pixel(100, 15))
    assert sampled.name() == DARK["hl_amber"]
