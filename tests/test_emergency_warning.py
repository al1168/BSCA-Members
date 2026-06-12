def test_warning_when_no_emergency_contacts():
    from gui.member_tabs import emergency_contact_warning
    assert emergency_contact_warning([]) == "Missing: Emergency Contact"


def test_no_warning_when_emergency_contact_present():
    from gui.member_tabs import emergency_contact_warning
    contacts = [{"id": 1, "full_name": "Jane Doe", "phone": "212-555-0100",
                 "relationship": "Daughter"}]
    assert emergency_contact_warning(contacts) is None
