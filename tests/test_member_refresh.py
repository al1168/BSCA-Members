import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_load_data_populates_from_member_context(qapp, monkeypatch):
    """Opening a member loads its data via get_member_context. Freshness after
    external edits is handled by the mtime-aware read-connection cache (see
    test_read_connection_reconnects_only_when_db_changes), so _load_data simply
    reads — no per-click reconnect needed."""
    import gui.member_tabs as mt

    ec = [{"id": 1, "full_name": "Jo", "phone": "1", "relationship": "Son"}]

    def fake_ctx(center_id, db_path, _retry=True):
        assert (center_id, db_path) == (24067, "dummy.accdb")
        return {
            "member": {"first_name": "On Kok"}, "enrollments": [],
            "authorizations": [], "availability": [], "absences": [],
            "one_off_availability": [], "emergency_contacts": ec,
        }

    monkeypatch.setattr(mt, "get_member_context", fake_ctx)

    w = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)  # bypass __init__/UI
    w._center_id = 24067
    w._db_path = "dummy.accdb"
    w._load_data()

    assert w._member == {"first_name": "On Kok"}
    assert w._emergency_contacts == ec
