import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_load_data_drops_read_connection_before_reading(qapp, monkeypatch):
    """Opening a member must read the live DB so changes made elsewhere — e.g.
    in Microsoft Access — are reflected. We drop only the pyodbc *read*
    connection (fresh member data) and keep the DAO photo handle cached for
    speed, so the drop targets the read connection for this db_path."""
    import gui.member_tabs as mt

    calls = []
    monkeypatch.setattr(mt, "_drop_read_connection",
                        lambda db_path: calls.append(("drop", db_path)),
                        raising=False)

    def fake_ctx(center_id, db_path, _retry=True):
        calls.append(("read", db_path))
        return {
            "member": {}, "enrollments": [], "authorizations": [],
            "availability": [], "absences": [], "one_off_availability": [],
            "emergency_contacts": [],
        }

    monkeypatch.setattr(mt, "get_member_context", fake_ctx)

    w = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)  # bypass __init__/UI
    w._center_id = 1
    w._db_path = "dummy.accdb"
    w._load_data()

    # Read connection dropped for this db_path BEFORE reading (fresh data);
    # the DAO cache is left intact (not close_connections).
    assert calls == [("drop", "dummy.accdb"), ("read", "dummy.accdb")]
