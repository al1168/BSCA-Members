import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_load_data_drops_cache_before_reading(qapp, monkeypatch):
    """Opening a member must read the live DB (drop the cached connection first)
    so changes made elsewhere — e.g. in Microsoft Access — are reflected."""
    import gui.member_tabs as mt

    calls = []
    monkeypatch.setattr(mt, "close_connections",
                        lambda: calls.append("close"), raising=False)

    def fake_ctx(center_id, db_path, _retry=True):
        calls.append("read")
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

    # Cache dropped (fresh read) and dropped BEFORE the read happens.
    assert calls == ["close", "read"]
