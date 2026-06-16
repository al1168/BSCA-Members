import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _info_tab_with(contacts):
    from PyQt6.QtWidgets import QLabel
    import gui.member_tabs as mt
    w = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)
    w._member = {"first_name": "A", "last_name": "B"}
    w._center_id = 1
    w._db_path = ""
    w._api_key = ""
    w._enrollments = []
    w._authorizations = []
    w._emergency_contacts = contacts
    w._emergency_badge = QLabel()
    w._test_outer = w._make_info_tab()  # keep a ref so children aren't GC'd
    return w


def test_emergency_table_has_fixed_height_fitting_its_rows(qapp):
    """The emergency table must not be vertically squeezable (Expanding policy
    let it collapse inside the Info scroll area, hiding contacts until the window
    was enlarged). It gets a fixed height that fits all its rows so the outer
    scroll bar reveals it instead."""
    contacts = [
        {"id": 1, "full_name": "Szeto LaiSan", "phone": "(917) 685-1838",
         "relationship": "Daughter"},
        {"id": 2, "full_name": "Andy Lau", "phone": "(917) 628-0459",
         "relationship": "Son"},
    ]
    w = _info_tab_with(contacts)
    t = w._emergency_table
    assert t.minimumHeight() == t.maximumHeight()       # fixed, not squeezable
    assert t.minimumHeight() >= 34 * len(contacts)      # all rows fit


def test_emergency_table_fixed_even_when_empty(qapp):
    w = _info_tab_with([])
    t = w._emergency_table
    assert t.minimumHeight() == t.maximumHeight()
