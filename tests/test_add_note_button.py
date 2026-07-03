import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _widget_with_notes_bits():
    from PyQt6.QtWidgets import QPushButton, QLabel
    import gui.member_tabs as mt
    w = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)
    w._btn_add_note = QPushButton("+ Add note")
    w._notes_label = QLabel("Notes")
    w._info_notes = mt._NotesEdit()
    return w


def test_no_note_shows_button_hides_editor(qapp):
    w = _widget_with_notes_bits()
    w._init_notes_visibility(has_note=False)
    assert w._btn_add_note.isHidden() is False   # button visible
    assert w._info_notes.isHidden() is True       # editor hidden
    assert w._notes_label.isHidden() is True


def test_existing_note_shows_editor_hides_button(qapp):
    w = _widget_with_notes_bits()
    w._init_notes_visibility(has_note=True)
    assert w._btn_add_note.isHidden() is True      # button hidden
    assert w._info_notes.isHidden() is False       # editor visible
    assert w._notes_label.isHidden() is False


def test_reveal_notes_flips_button_to_editor(qapp):
    w = _widget_with_notes_bits()
    w._init_notes_visibility(has_note=False)       # start as button-only
    w._reveal_notes()
    assert w._btn_add_note.isHidden() is True
    assert w._info_notes.isHidden() is False
    assert w._notes_label.isHidden() is False
