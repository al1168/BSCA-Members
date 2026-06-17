import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_empty_editable_field_shows_box_and_pencil(qapp):
    from gui.member_tabs import _ViewEditLineEdit
    f = _ViewEditLineEdit("", editable=True)
    assert f.property("empty") is True          # styled as a visible box
    assert f._pencil.isVisible() is True         # pencil shown so it's discoverable


def test_nonempty_field_is_flat_with_hover_only_pencil(qapp):
    from gui.member_tabs import _ViewEditLineEdit
    f = _ViewEditLineEdit("Wood", editable=True)
    assert not f.property("empty")
    assert f._pencil.isVisible() is False        # pencil only appears on hover


def test_typing_a_value_clears_the_empty_box(qapp):
    from gui.member_tabs import _ViewEditLineEdit
    f = _ViewEditLineEdit("", editable=True)
    assert f.property("empty") is True
    f.setText("Wood")
    assert f.property("empty") is False


def test_clearing_a_value_shows_the_empty_box(qapp):
    from gui.member_tabs import _ViewEditLineEdit
    f = _ViewEditLineEdit("Wood", editable=True)
    f.setText("")
    assert f.property("empty") is True


def test_non_editable_empty_field_is_not_a_box(qapp):
    from gui.member_tabs import _ViewEditLineEdit
    f = _ViewEditLineEdit("", editable=False)
    assert not f.property("empty")               # read-only blanks stay flat
    assert f.actions() == []


def test_empty_address_shows_box_and_pencil(qapp):
    from gui.address_autocomplete import AddressAutocomplete
    addr = AddressAutocomplete(view_edit=True)   # empty
    assert addr._edit.property("empty") is True
    assert addr._pencil.isVisible() is True


def test_filled_address_is_flat(qapp):
    from gui.address_autocomplete import AddressAutocomplete
    addr = AddressAutocomplete(view_edit=True)
    addr.set_address("123 Main St")
    assert not addr._edit.property("empty")
    assert addr._pencil.isVisible() is False
