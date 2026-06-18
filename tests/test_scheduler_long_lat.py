"""Guard the app<->scheduler coordinate contract.

The app writes the Contacts.[Long Lat] column as 'longitude,latitude' (see
gui/address_autocomplete.parse_place_location). The schedule generator
(monthly_schedule.travel) must read it in that same order and return a
(lat, long) tuple. If the deployed bsca-core ever reverts to the old
'lat,long' parsing, travel times are computed with swapped coordinates — this
test fails before that ships.
"""


def test_scheduler_reads_long_lat_in_app_storage_order():
    from monthly_schedule.travel import parse_long_lat
    # NYC: longitude -73.99 (first), latitude 40.69 (second).
    assert parse_long_lat("-73.993455,40.695925") == (40.695925, -73.993455)


def test_scheduler_parse_long_lat_blank_is_none():
    from monthly_schedule.travel import parse_long_lat
    assert parse_long_lat("") is None
    assert parse_long_lat(None) is None
