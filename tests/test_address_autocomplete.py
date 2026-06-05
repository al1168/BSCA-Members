def test_parse_place_location_well_formed():
    from gui.address_autocomplete import parse_place_location
    details = {"result": {"geometry": {"location":
              {"lat": 40.695925, "lng": -73.993455}}}}
    assert parse_place_location(details) == "-73.993455,40.695925"


def test_parse_place_location_missing_returns_empty():
    from gui.address_autocomplete import parse_place_location
    assert parse_place_location({}) == ""
    assert parse_place_location({"result": {}}) == ""
    assert parse_place_location({"result": {"geometry": {}}}) == ""
    assert parse_place_location(None) == ""
