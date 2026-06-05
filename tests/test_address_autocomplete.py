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
