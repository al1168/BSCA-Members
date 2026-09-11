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
    # The DOB is placed via its row container (edit + age label).
    assert _grid_positions(w)[w._info_dob_row][3] == 3   # span 2 -> colspan 3


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


# ── wiring: apply a new layout, persist, rebuild in place ──────────────────

def test_apply_layout_persists_and_rebuilds(qapp, tmp_path):
    import json
    from PyQt6.QtWidgets import QTabWidget, QWidget
    from gui.info_layout import default_layout
    w, tab = _make_tab(qapp)
    # Give the widget a tab bar + settings the way _build_ui/__init__ do.
    w._tabs = QTabWidget()
    w._tabs.addTab(tab, "Info")
    w._tabs.addTab(QWidget(), "Other")
    w._tab_info = tab
    w._info_tab_index = 0
    w._prev_tab_index = 0
    w._lazy_tabs = {}
    w._dirty = False
    path = str(tmp_path / "settings.json")
    w._settings = {}
    w._settings_path = path
    new_layout = default_layout()
    new_layout["blocks"][1]["title"] = "Rearranged"
    w._apply_layout(new_layout)
    # Persisted:
    with open(path, "r", encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["info_tab_layout"]["blocks"][1]["title"] == "Rearranged"
    # Rebuilt in place at the same index, same count:
    assert w._tabs.count() == 2
    assert w._tabs.widget(0) is w._tab_info
    assert w._tab_info is not tab
    from PyQt6.QtWidgets import QLabel
    headers = [lbl.text() for lbl in w._tab_info.findChildren(QLabel)
               if lbl.objectName() == "section_header"]
    assert "REARRANGED" in headers


def test_open_layout_editor_blocked_while_dirty(qapp, monkeypatch):
    w, _tab = _make_tab(qapp)
    w._dirty = True
    called = {}
    from PyQt6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda *a, **k: called.setdefault("x", 1)))
    w._open_layout_editor()
    assert called   # told the user; no dialog attempted


def test_customize_button_present_on_info_tab(qapp):
    from PyQt6.QtWidgets import QPushButton
    _w, tab = _make_tab(qapp)
    texts = [b.text() for b in tab.findChildren(QPushButton)]
    assert any("Customize" in t for t in texts)


def test_layout_editor_gets_display_member_values(qapp, monkeypatch):
    captured = {}
    import gui.info_layout_editor as ed

    class FakeDlg:
        def __init__(self, layout_cfg, member, parent=None):
            captured["member"] = member
        def exec(self):
            return 0   # rejected
    monkeypatch.setattr(ed, "InfoLayoutEditor", FakeDlg)
    w, _tab = _make_tab(qapp, member={"first_name": "Mary", "alt_id": 987654321})
    w._dirty = False
    w._open_layout_editor()
    m = captured["member"]
    assert m["center_id"] == "7"
    # No alt-id key set on the widget -> displays the stored value as text.
    assert m["alt_id"] == "987654321"


# ── Group: editable Contacts.[Group] value (meal-sheet Location) ───────────

def test_group_field_renders_editable(qapp):
    w, _tab = _make_tab(qapp, member={"first_name": "Mary", "last_name": "Chan",
                                      "group": "B2", "alt_id": None})
    pos = _grid_positions(w)
    assert w._info_group in pos
    assert w._info_group.text() == "B2"
    # Editable like Case Manager: the hover pencil is present.
    assert w._info_group._pencil is not None


def test_group_change_appears_in_confirm_summary():
    from gui.member_tabs import build_change_summary
    lines = build_change_summary({"group": "B"}, {"group": "C"})
    assert lines == ["Group: B → C"]
    assert build_change_summary({"group": ""}, {"group": "C"}) == [
        "Group: (empty) → C"]


def test_group_field_blank_when_member_lacks_it(qapp):
    w, _tab = _make_tab(qapp)
    assert w._info_group.text() == ""


# ── age readout beside the DOB ──────────────────────────────────────────────

def _expected_age(y, mo, d):
    from datetime import date
    dob, today = date(y, mo, d), date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def test_age_label_shows_next_to_dob(qapp):
    w, _tab = _make_tab(qapp, member={"first_name": "Mary", "last_name": "Chan",
                                      "dob": "5/14/1948", "alt_id": None})
    assert w._info_age.text() == f"(Age {_expected_age(1948, 5, 14)})"
    # Placed via the row container; the edit itself keeps the bare date so
    # saving never picks up the age text.
    pos = _grid_positions(w)
    assert w._info_dob_row in pos
    assert w._info_dob.text() == "05/14/1948"


def test_age_label_tracks_dob_edits(qapp):
    w, _tab = _make_tab(qapp, member={"first_name": "Mary", "last_name": "Chan",
                                      "dob": "5/14/1948", "alt_id": None})
    w._info_dob.setText("01/01/2000")
    assert w._info_age.text() == f"(Age {_expected_age(2000, 1, 1)})"
    w._info_dob.setText("")
    assert w._info_age.text() == ""          # no DOB -> no age
    w._info_dob.setText("not a date")
    assert w._info_age.text() == ""          # unparseable -> no age


# ── font-size steps: value fsize small/xlarge + label lsize rules ──────────

def test_qss_has_size_step_rules_both_themes():
    from gui.theme import build_qss, DARK, LIGHT
    for tokens in (DARK, LIGHT):
        qss = build_qss(tokens)
        assert 'QLineEdit#info_field[fsize="small"]' in qss
        assert 'QLineEdit#info_field[fsize="xlarge"]' in qss
        assert 'QLineEdit[fsize="small"]' in qss
        assert 'QLineEdit[fsize="xlarge"]' in qss
        assert 'QLabel#field_label[lsize="small"]' in qss
        assert 'QLabel#field_label[lsize="large"]' in qss


def test_xlarge_value_and_large_label_render(qapp):
    from PyQt6.QtWidgets import QLabel
    from gui.theme import build_qss, DARK
    w = _styled_line_edit("info_field", {"fsize": "xlarge"})
    assert w.font().pixelSize() == 20
    lab = QLabel("DOB")
    lab.setObjectName("field_label")
    lab.setProperty("lsize", "large")
    lab.setStyleSheet(build_qss(DARK))
    lab.style().unpolish(lab)
    lab.style().polish(lab)
    assert lab.font().pixelSize() == 13


def test_qss_pixel_values_match_editor_maps():
    """The editor's preview px maps must track the theme QSS rules."""
    from gui.theme import build_qss, DARK
    from gui.info_layout_editor import VALUE_PX, LABEL_PX
    qss = build_qss(DARK)
    for s in ("small", "large", "xlarge", "xxlarge", "xxxlarge"):
        assert f'[fsize="{s}"] {{ font-size: {VALUE_PX[s]}px' in qss
    for s in ("small", "large", "xlarge", "xxlarge", "xxxlarge"):
        assert f'[lsize="{s}"] {{ font-size: {LABEL_PX[s]}px' in qss


def test_labels_carry_global_label_size(qapp):
    from gui.info_layout import default_layout
    lay = default_layout()
    lay["label_size"] = "large"
    w, tab = _make_tab(qapp, layout_cfg=lay)
    from PyQt6.QtWidgets import QLabel
    # Only the grid's field labels take the layout size; the Schedule
    # card's labels are out of scope by design (spec: Out of scope).
    labels = [l for l in tab.findChildren(QLabel)
              if l.objectName() == "field_label"
              and not (w._schedule_card is not None
                       and w._schedule_card.isAncestorOf(l))]
    assert labels
    assert all(l.property("lsize") == "large" for l in labels)
    card_labels = [l for l in w._schedule_card.findChildren(QLabel)
                   if l.objectName() == "field_label"]
    assert card_labels
    assert all(l.property("lsize") is None for l in card_labels)


def test_field_small_size_sets_fsize_property(qapp):
    from gui.info_layout import default_layout
    lay = default_layout()
    for f in lay["blocks"][1]["fields"]:
        if f["key"] == "dob":
            f["size"] = "small"
    w, _tab = _make_tab(qapp, layout_cfg=lay)
    assert w._info_dob.property("fsize") == "small"


def test_editing_group_marks_form_dirty(qapp):
    """Regression: Group was missing from the dirty-tracking list, so editing
    it never lit the Save / Discard buttons."""
    from PyQt6.QtWidgets import QPushButton
    w, _tab = _make_tab(qapp, member={"first_name": "Mary", "last_name": "Chan",
                                      "group": "B", "alt_id": None})
    w._btn_save = QPushButton()
    w._btn_discard = QPushButton()
    w._setup_dirty_tracking()
    assert not w._dirty
    w._info_group.setText("C")
    assert w._dirty
    assert w._btn_save.isEnabled() and w._btn_discard.isEnabled()
