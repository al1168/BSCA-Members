import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_double_click_starts_edit_on_view_field(qapp):
    from PyQt6.QtTest import QTest
    from PyQt6.QtCore import Qt
    from gui.member_tabs import _ViewEditLineEdit
    f = _ViewEditLineEdit("hello")
    f.show()
    assert f.isReadOnly()                       # flat/view by default
    QTest.mouseDClick(f, Qt.MouseButton.LeftButton)
    assert not f.isReadOnly()                   # double-click enters edit mode


def test_double_click_noop_on_locked_field(qapp):
    from PyQt6.QtTest import QTest
    from PyQt6.QtCore import Qt
    from gui.member_tabs import _ViewEditLineEdit
    f = _ViewEditLineEdit("12345", editable=False)
    f.show()
    QTest.mouseDClick(f, Qt.MouseButton.LeftButton)
    assert f.isReadOnly()                       # non-editable stays read-only


def test_double_click_starts_edit_on_address_field(qapp):
    from PyQt6.QtTest import QTest
    from PyQt6.QtCore import Qt
    from gui.address_autocomplete import AddressAutocomplete
    a = AddressAutocomplete(api_key="", view_edit=True)
    a.set_address("123 Main St")
    a.show()
    assert a._edit.isReadOnly()
    QTest.mouseDClick(a._edit, Qt.MouseButton.LeftButton)
    assert not a._edit.isReadOnly()
