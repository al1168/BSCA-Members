import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_only_one_view_edit_field_edits_at_a_time(qapp):
    from gui.member_tabs import _ViewEditLineEdit
    a = _ViewEditLineEdit("A")
    b = _ViewEditLineEdit("B")
    a._begin_edit()
    assert not a.isReadOnly()
    b._begin_edit()
    assert a.isReadOnly()          # A was finished when B began
    assert not b.isReadOnly()


def test_editing_address_finishes_an_open_field(qapp):
    from gui.member_tabs import _ViewEditLineEdit
    from gui.address_autocomplete import AddressAutocomplete
    f = _ViewEditLineEdit("A")
    addr = AddressAutocomplete("", view_edit=True)
    f._begin_edit()
    assert not f.isReadOnly()
    addr._begin_edit()
    assert f.isReadOnly()          # the field finished when address began
    assert not addr._edit.isReadOnly()


def test_editing_field_finishes_an_open_address(qapp):
    from gui.member_tabs import _ViewEditLineEdit
    from gui.address_autocomplete import AddressAutocomplete
    addr = AddressAutocomplete("", view_edit=True)
    f = _ViewEditLineEdit("A")
    addr._begin_edit()
    assert not addr._edit.isReadOnly()
    f._begin_edit()
    assert addr._edit.isReadOnly()  # address finished when the field began
    assert not f.isReadOnly()


def test_address_escape_reverts_and_stops_editing(qapp):
    from PyQt6.QtCore import Qt, QEvent
    from PyQt6.QtGui import QKeyEvent
    from gui.address_autocomplete import AddressAutocomplete
    addr = AddressAutocomplete(view_edit=True)
    addr.set_address("123 Main St")
    addr._begin_edit()
    addr.setText("xxx")
    addr.eventFilter(addr._edit, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape,
                                           Qt.KeyboardModifier.NoModifier))
    assert addr.text() == "123 Main St"   # reverted to value at edit start
    assert addr._edit.isReadOnly()        # back to view mode
