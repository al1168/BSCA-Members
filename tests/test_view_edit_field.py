import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_starts_read_only_in_view_mode(qapp):
    from gui.member_tabs import _ViewEditLineEdit
    f = _ViewEditLineEdit("Wood")
    assert f.text() == "Wood"
    assert f.isReadOnly() is True          # selectable/copyable, not editable


def test_begin_edit_makes_editable(qapp):
    from gui.member_tabs import _ViewEditLineEdit
    f = _ViewEditLineEdit("Wood")
    f._begin_edit()
    assert f.isReadOnly() is False


def test_finish_edit_returns_to_view(qapp):
    from gui.member_tabs import _ViewEditLineEdit
    f = _ViewEditLineEdit("Wood")
    f._begin_edit()
    f.setText("Woody")
    f._finish_edit()
    assert f.isReadOnly() is True
    assert f.text() == "Woody"             # the edit is kept


def test_escape_reverts_in_progress_edit(qapp):
    from PyQt6.QtCore import Qt, QEvent
    from PyQt6.QtGui import QKeyEvent
    from gui.member_tabs import _ViewEditLineEdit
    f = _ViewEditLineEdit("Wood")
    f._begin_edit()
    f.setText("Wo")
    f.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape,
                              Qt.KeyboardModifier.NoModifier))
    assert f.text() == "Wood"              # reverted to value at edit start
    assert f.isReadOnly() is True          # and back in view mode


def test_changed_flag_tracks_baseline(qapp):
    from gui.member_tabs import _ViewEditLineEdit
    f = _ViewEditLineEdit("Wood")
    assert not f.property("changed")       # unchanged at load
    f.setText("Woody")
    assert f.property("changed") is True   # differs from baseline -> highlight
    f.set_baseline()                       # e.g. after a save
    assert f.property("changed") is False


def test_non_editable_field_has_no_pencil_and_stays_view(qapp):
    from gui.member_tabs import _ViewEditLineEdit
    f = _ViewEditLineEdit("HOF", editable=False)
    assert f.isReadOnly() is True
    assert f.actions() == []               # no pencil affordance
    f._begin_edit()                        # no-op for non-editable fields
    assert f.isReadOnly() is True
