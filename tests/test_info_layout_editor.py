# tests/test_info_layout_editor.py
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


MEMBER = {"first_name": "Mary", "last_name": "Chan", "dob": "1/2/1950",
          "cell": "9175550143"}


def test_editor_starts_from_normalized_copy(qapp):
    from gui.info_layout_editor import InfoLayoutEditor
    from gui.info_layout import default_layout
    dlg = InfoLayoutEditor(None, MEMBER)
    assert dlg.result_layout() == default_layout()
    # A layout dict passed in must not be mutated by editing.
    src = default_layout()
    dlg2 = InfoLayoutEditor(src, MEMBER)
    dlg2._layout["blocks"][1]["title"] = "Changed"
    assert src["blocks"][1]["title"] == "Identity"


def test_preview_shows_hidden_fields_dimmed(qapp):
    from gui.info_layout_editor import InfoLayoutEditor
    dlg = InfoLayoutEditor(None, MEMBER)
    # The legacy emergency field is hidden by default but must appear in the
    # preview (else it could never be re-shown).
    assert "emergency" in dlg._preview_cells


def test_clicking_a_preview_cell_selects_the_field(qapp):
    from gui.info_layout_editor import InfoLayoutEditor
    dlg = InfoLayoutEditor(None, MEMBER)
    dlg._select(("field", "dob"))
    assert dlg._selection == ("field", "dob")
    # Selecting a block works the same way.
    dlg._select(("block", 0))
    assert dlg._selection == ("block", 0)


def test_preview_rebuild_preserves_selection(qapp):
    from gui.info_layout_editor import InfoLayoutEditor
    dlg = InfoLayoutEditor(None, MEMBER)
    dlg._select(("field", "dob"))
    dlg._rebuild_preview()
    assert dlg._selection == ("field", "dob")
    assert "dob" in dlg._preview_cells


def test_real_mouse_click_on_preview_cell_does_not_crash(qapp):
    """Regression: QScrollArea.setWidget() deletes the old preview; a rebuild
    triggered from inside a cell's own mousePressEvent must defer that
    deletion (deleteLater), or the click handler returns into a freed
    widget and the process dies."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    from gui.info_layout_editor import InfoLayoutEditor
    dlg = InfoLayoutEditor(None, MEMBER)
    QTest.mouseClick(dlg._preview_cells["dob"], Qt.MouseButton.LeftButton)
    assert dlg._selection == ("field", "dob")
    # And again on a cell of the rebuilt preview (fresh widget map).
    QTest.mouseClick(dlg._preview_cells["cell"], Qt.MouseButton.LeftButton)
    assert dlg._selection == ("field", "cell")


# ── properties panel drives the model ──────────────────────────────────────

def _dlg(qapp):
    from gui.info_layout_editor import InfoLayoutEditor
    return InfoLayoutEditor(None, MEMBER)


def test_field_props_change_model(qapp):
    from gui.info_layout import find_field
    dlg = _dlg(qapp)
    dlg._select(("field", "dob"))
    dlg._set_prop("bold", True)
    dlg._set_prop("span", 2)
    dlg._set_prop("color", "amber")
    dlg._set_prop("visible", False)
    bi, fi = find_field(dlg._layout, "dob")
    f = dlg._layout["blocks"][bi]["fields"][fi]
    assert (f["bold"], f["span"], f["color"], f["visible"]) \
        == (True, 2, "amber", False)


def test_move_field_to_other_section(qapp):
    from gui.info_layout import find_field
    dlg = _dlg(qapp)
    dlg._select(("field", "dob"))
    contact_bi = [i for i, b in enumerate(dlg._layout["blocks"])
                  if b.get("title") == "Contact"][0]
    dlg._move_to_section(contact_bi)
    assert find_field(dlg._layout, "dob")[0] == contact_bi
    assert dlg._selection == ("field", "dob")   # selection survives


def test_section_ops(qapp):
    dlg = _dlg(qapp)
    identity_bi = [i for i, b in enumerate(dlg._layout["blocks"])
                   if b.get("title") == "Identity"][0]
    dlg._select(("block", identity_bi))
    dlg._rename("My Stuff")
    assert dlg._layout["blocks"][identity_bi]["title"] == "My Stuff"
    n_before = len(dlg._layout["blocks"])
    dlg._add_section()
    assert len(dlg._layout["blocks"]) == n_before + 1
    dlg._delete_section()   # deletes "My Stuff"; fields migrate
    titles = [b.get("title") for b in dlg._layout["blocks"]
              if b["type"] == "section"]
    assert "My Stuff" not in titles
    all_keys = [f["key"] for b in dlg._layout["blocks"]
                if b["type"] == "section" for f in b["fields"]]
    assert "dob" in all_keys   # nothing lost


def test_block_move_and_visibility(qapp):
    dlg = _dlg(qapp)
    dlg._select(("block", 0))          # schedule card
    dlg._set_block_visible(False)
    assert dlg._layout["blocks"][0]["visible"] is False
    dlg._move_selected_block(1)
    assert dlg._layout["blocks"][1]["type"] == "schedule"
    assert dlg._selection == ("block", 1)


def test_result_layout_is_normalized(qapp):
    from gui.info_layout import normalize
    dlg = _dlg(qapp)
    dlg._select(("field", "dob"))
    dlg._set_prop("bold", True)
    out = dlg.result_layout()
    assert out == normalize(out)


def test_delete_last_section_short_circuits(qapp):
    dlg = _dlg(qapp)
    section_idxs = [i for i, b in enumerate(dlg._layout["blocks"])
                    if b["type"] == "section"]
    # Delete all but one section.
    for _ in section_idxs[1:]:
        idx = [i for i, b in enumerate(dlg._layout["blocks"])
               if b["type"] == "section"][-1]
        dlg._select(("block", idx))
        dlg._delete_section()
    remaining = [i for i, b in enumerate(dlg._layout["blocks"])
                 if b["type"] == "section"]
    assert len(remaining) == 1
    dlg._select(("block", remaining[0]))
    dlg._delete_section()   # no-op, no confirm, no crash
    assert sum(1 for b in dlg._layout["blocks"]
               if b["type"] == "section") == 1


def test_blank_rename_resyncs_panel(qapp):
    dlg = _dlg(qapp)
    identity_bi = [i for i, b in enumerate(dlg._layout["blocks"])
                   if b.get("title") == "Identity"][0]
    dlg._select(("block", identity_bi))
    dlg._rename("   ")
    assert dlg._layout["blocks"][identity_bi]["title"] == "Identity"
    from PyQt6.QtWidgets import QLineEdit
    name = dlg._props_host.findChild(QLineEdit)
    assert name is not None and name.text() == "Identity"


# ── font sizes in the editor ───────────────────────────────────────────────

def test_text_size_dropdown_sets_field_size(qapp):
    from gui.info_layout import find_field
    dlg = _dlg(qapp)
    dlg._select(("field", "dob"))
    dlg._set_prop("size", "xlarge")
    bi, fi = find_field(dlg._layout, "dob")
    assert dlg._layout["blocks"][bi]["fields"][fi]["size"] == "xlarge"
    # The props panel offers a Text size dropdown with all six steps.
    from PyQt6.QtWidgets import QComboBox
    dlg._rebuild_props()
    combos = dlg._props_host.findChildren(QComboBox)
    size_combos = [c for c in combos
                   if [c.itemData(i) for i in range(c.count())]
                   == ["small", "normal", "large", "xlarge", "xxlarge", "xxxlarge"]]
    assert len(size_combos) == 1
    assert size_combos[0].currentData() == "xlarge"


def test_global_label_size_dropdown(qapp):
    dlg = _dlg(qapp)
    assert dlg._layout["label_size"] == "normal"
    dlg._label_size_combo.setCurrentIndex(2)          # "large"
    assert dlg._layout["label_size"] == "large"
    # Survives selection changes and preview rebuilds.
    dlg._select(("field", "dob"))
    assert dlg._label_size_combo.currentData() == "large"
    assert dlg._layout["label_size"] == "large"
    assert dlg.result_layout()["label_size"] == "large"


def test_reset_resyncs_label_size_combo(qapp):
    dlg = _dlg(qapp)
    dlg._label_size_combo.setCurrentIndex(0)          # "small"
    dlg._reset()
    assert dlg._layout["label_size"] == "normal"
    assert dlg._label_size_combo.currentData() == "normal"


def test_preview_cells_render_both_sizes_as_rich_text(qapp):
    from gui.info_layout import find_field
    dlg = _dlg(qapp)
    dlg._layout["label_size"] = "large"               # 13px labels
    bi, fi = find_field(dlg._layout, "dob")
    dlg._layout["blocks"][bi]["fields"][fi]["size"] = "xlarge"   # 20px value
    dlg._rebuild_preview()
    cell_text = dlg._preview_cells["dob"].text()
    assert "font-size:13px" in cell_text
    assert "font-size:20px" in cell_text
    # A normal field's value renders at the 13px base: its cell has the
    # 13px label span AND a 13px value span.
    assert dlg._preview_cells["first_name"].text().count("font-size:13px") == 2


def test_label_size_dropdown_offers_six_steps_with_display_names(qapp):
    dlg = _dlg(qapp)
    combo = dlg._label_size_combo
    assert [combo.itemData(i) for i in range(combo.count())] == [
        "small", "normal", "large", "xlarge", "xxlarge", "xxxlarge"]
    assert [combo.itemText(i) for i in range(combo.count())] == [
        "Small", "Normal", "Large", "X-Large", "2X-Large", "3X-Large"]
    combo.setCurrentIndex(5)
    assert dlg._layout["label_size"] == "xxxlarge"


def test_preview_uses_scaled_pixels(qapp):
    from gui import theme
    dlg = _dlg(qapp)
    dlg._select(("field", "dob"))
    dlg._set_prop("size", "xxxlarge")
    theme.set_text_size("xlarge")          # conftest resets to Normal afterwards
    dlg._rebuild_preview()
    from PyQt6.QtWidgets import QLabel
    texts = [w.text() for w in dlg._preview_scroll.widget().findChildren(QLabel)]
    assert any("font-size:69px" in t for t in texts)      # value 30 × 30/13
    assert any("font-size:25px" in t for t in texts)      # label 11 × 30/13
