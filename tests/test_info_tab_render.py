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


# ── renderer: the Info tab honors the layout model ─────────────────────────

def _make_tab(qapp, layout_cfg=None, member=None):
    """Build a real Info tab on a __new__-constructed widget (no DB)."""
    from PyQt6.QtWidgets import QLabel
    import gui.member_tabs as mt
    w = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)
    w._member = member or {"first_name": "Mary", "last_name": "Chan",
                           "alt_id": None}
    w._center_id = 7
    w._api_key = ""
    w._alt_id_key = None
    w._enrollments = []
    w._authorizations = []
    w._emergency_contacts = []
    w._emergency_badge = QLabel()
    w._layout_cfg = layout_cfg
    tab = w._make_info_tab()
    return w, tab


def _grid_positions(w):
    """{widget: (row, col, rowspan, colspan)} for the Info content grid."""
    grid = w._info_content_layout
    out = {}
    for i in range(grid.count()):
        item = grid.itemAt(i)
        if item.widget() is not None:
            out[item.widget()] = grid.getItemPosition(i)
    return out


def test_default_render_places_all_visible_fields(qapp):
    w, _tab = _make_tab(qapp)
    pos = _grid_positions(w)
    assert w._info_first in pos
    assert w._info_hha in pos
    # PCP/HHA keep their full-row span (wspan 3 -> colspan 5).
    assert pos[w._info_pcp][3] == 5
    # The legacy emergency text field exists but is not placed.
    assert w._info_emergency not in pos
    assert not w._info_emergency.isVisible()


def test_custom_layout_controls_sections_and_order(qapp):
    from gui.info_layout import default_layout
    lay = default_layout()
    # Move DOB into a renamed first section and hide SSN.
    lay["blocks"][1]["title"] = "Glance"
    for f in lay["blocks"][1]["fields"]:
        if f["key"] == "ssn":
            f["visible"] = False
    w, tab = _make_tab(qapp, layout_cfg=lay)
    from PyQt6.QtWidgets import QLabel
    headers = [lbl.text() for lbl in tab.findChildren(QLabel)
               if lbl.objectName() == "section_header"]
    assert "GLANCE" in headers
    pos = _grid_positions(w)
    assert w._info_ssn not in pos
    assert not w._info_ssn.isVisible()
    # Hidden widgets still hold their value for save/discard.
    assert w._info_ssn.text() == ""


def test_layout_styling_sets_dynamic_properties(qapp):
    from gui.info_layout import default_layout
    lay = default_layout()
    for f in lay["blocks"][1]["fields"]:
        if f["key"] == "dob":
            f.update(bold=True, size="large", color="amber", span=2)
    w, _tab = _make_tab(qapp, layout_cfg=lay)
    assert w._info_dob.property("fbold") == "true"
    assert w._info_dob.property("fsize") == "large"
    assert w._info_dob.property("hl") == "amber"
    assert _grid_positions(w)[w._info_dob][3] == 3   # span 2 -> colspan 3


def test_hidden_schedule_block_skips_card(qapp):
    from gui.info_layout import default_layout
    lay = default_layout()
    lay["blocks"][0]["visible"] = False
    w, _tab = _make_tab(qapp, layout_cfg=lay)
    assert w._schedule_card is None
    w._refresh_schedule_card()   # guard: must not raise


def test_garbage_layout_falls_back_to_default(qapp):
    w, _tab = _make_tab(qapp, layout_cfg={"blocks": "corrupt"})
    pos = _grid_positions(w)
    assert w._info_first in pos
    assert w._schedule_card in pos
