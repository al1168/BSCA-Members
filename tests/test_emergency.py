def test_map_emergency_contact_row():
    from db.members import map_emergency_contact_row
    row = (3, 25049, "Jane Doe", "917-555-0100", "Daughter")
    assert map_emergency_contact_row(row) == {
        "id": 3, "center_id": 25049, "full_name": "Jane Doe",
        "phone": "917-555-0100", "relationship": "Daughter",
    }


def test_map_emergency_contact_row_nulls():
    from db.members import map_emergency_contact_row
    d = map_emergency_contact_row((4, 25049, None, None, None))
    assert d["full_name"] == ""
    assert d["phone"] == ""
    assert d["relationship"] == ""
