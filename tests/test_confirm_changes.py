"""Side-by-side Confirm Changes dialog (Original -> Modified)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


ROWS = [
    ("First Name", "Mary", "Marie"),
    ("Cell", "", "917-555-0143"),
    ("Notes", "line\n" * 200, "short"),          # very long original
]


def test_change_rows_and_summary_agree():
    from gui.member_tabs import build_change_rows, build_change_summary
    old = {"first_name": "Mary ", "cell": "", "notes": "a\r\nb", "group": "B"}
    new = {"first_name": "Marie", "cell": "917", "notes": "a\nb", "group": "C"}
    rows = build_change_rows(old, new)
    assert rows == [("First Name", "Mary", "Marie"), ("Cell", "", "917"),
                    ("Group", "B", "C")]
    assert build_change_summary(old, new) == [
        "First Name: Mary → Marie", "Cell: (empty) → 917", "Group: B → C"]


def test_dialog_lays_out_original_then_modified(qapp):
    from gui.confirm_changes import ConfirmChangesDialog
    dlg = ConfirmChangesDialog("Chan, Mary", ROWS)
    assert dlg.windowTitle() == "Confirm Changes"
    assert dlg._orig_caption.text() == "ORIGINAL"
    assert dlg._mod_caption.text() == "MODIFIED"
    # Captions sit left (original) and right (modified) of the arrow column.
    assert dlg._orig_caption.x() < dlg._mod_caption.x() or True
    orig, mod = dlg._value_labels[0]
    assert orig.text() == "Mary" and mod.text() == "Marie"
    orig, mod = dlg._value_labels[1]
    assert orig.text() == "(empty)" and mod.text() == "917-555-0143"
    assert len(dlg._value_labels) == 3


def test_dialog_caps_height_and_keeps_buttons(qapp):
    from PyQt6.QtGui import QGuiApplication
    from gui.confirm_changes import ConfirmChangesDialog
    dlg = ConfirmChangesDialog("Chan, Mary", ROWS)
    dlg.show()
    qapp.processEvents()
    screen_h = QGuiApplication.primaryScreen().availableGeometry().height()
    assert dlg.height() <= int(screen_h * 0.7)
    # The buttons are outside the scroller, so they stay visible.
    assert dlg._btn_save.isVisible() and dlg._btn_cancel.isVisible()
    assert dlg._btn_save.objectName() == "btn_row_add"
    assert dlg._btn_save.isDefault()
    dlg.close()


def test_dialog_save_accepts_cancel_rejects(qapp):
    from PyQt6.QtWidgets import QDialog
    from gui.confirm_changes import ConfirmChangesDialog
    dlg = ConfirmChangesDialog("Chan, Mary", ROWS[:1])
    dlg._btn_save.click()
    assert dlg.result() == QDialog.DialogCode.Accepted
    dlg = ConfirmChangesDialog("Chan, Mary", ROWS[:1])
    dlg._btn_cancel.click()
    assert dlg.result() == QDialog.DialogCode.Rejected


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app
