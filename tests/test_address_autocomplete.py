def test_parse_place_location_well_formed():
    # Places API (New) Place Details shape: top-level "location".
    from gui.address_autocomplete import parse_place_location
    details = {"location": {"latitude": 40.695925, "longitude": -73.993455}}
    assert parse_place_location(details) == "-73.993455,40.695925"


def test_parse_place_location_missing_returns_empty():
    from gui.address_autocomplete import parse_place_location
    assert parse_place_location({}) == ""
    assert parse_place_location({"location": {}}) == ""
    assert parse_place_location(None) == ""


def test_no_key_is_plain_field(qtbot):
    from gui.address_autocomplete import AddressAutocomplete
    w = AddressAutocomplete("")
    qtbot.addWidget(w)
    w.set_address("123 Main St, New York, NY")
    assert w.text() == "123 Main St, New York, NY"
    assert w.address() == "123 Main St, New York, NY"
    assert w.long_lat() == ""
    assert w._completer is None  # no autocomplete machinery without a key


def test_view_edit_mode_starts_read_only_and_can_edit(qtbot):
    """In view_edit mode (member Info tab) the address shows as read-only,
    selectable text and only becomes editable on _begin_edit; the default mode
    (Add Member wizard) stays editable."""
    from gui.address_autocomplete import AddressAutocomplete
    view = AddressAutocomplete("", view_edit=True)
    qtbot.addWidget(view)
    assert view._edit.isReadOnly() is True
    view._begin_edit()
    assert view._edit.isReadOnly() is False

    editable = AddressAutocomplete("")          # wizard default
    qtbot.addWidget(editable)
    assert editable._edit.isReadOnly() is False


def test_inner_field_not_squeezed_when_widget_constrained(qtbot):
    """Regression: at high-DPI / short windows the wrapper can be allocated too
    little vertical space; its inner QLineEdit must NOT be compressed below its
    natural height (that clipped the address text). The status label yields."""
    from PyQt6.QtWidgets import QWidget, QVBoxLayout
    from gui.address_autocomplete import AddressAutocomplete
    host = QWidget()
    lay = QVBoxLayout(host)
    w = AddressAutocomplete("")
    lay.addWidget(w)
    lay.addStretch()
    qtbot.addWidget(host)
    w.setText("123 Main St, Brooklyn, NY, USA")
    w._show_status("coordinates captured")
    host.show()
    natural = w._edit.sizeHint().height()
    # Wrapper given less height than line edit + status label need (DPI pressure).
    w.setMaximumHeight(natural + 4)
    qtbot.wait(10)
    assert w._edit.height() >= natural


def test_setplaceholder_and_textchanged_proxy(qtbot):
    from gui.address_autocomplete import AddressAutocomplete
    w = AddressAutocomplete("")
    qtbot.addWidget(w)
    seen = []
    w.textChanged.connect(seen.append)
    w.setPlaceholderText("Street, City, State ZIP")
    w.setText("hello")
    assert seen == ["hello"]
    assert w.long_lat() == ""
