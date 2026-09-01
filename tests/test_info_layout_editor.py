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
