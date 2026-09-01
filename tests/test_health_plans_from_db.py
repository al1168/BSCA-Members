"""Health plans for the add-member wizard come from the database, not the
hard-coded HEALTH_PLANS tuple: get_health_plans() collects the distinct plans
present in Contacts and Authorization, and the wizard feeds them to
StepContact's Health Plan dropdown."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


class _FakeCursor:
    """Maps a substring of the executed SQL to the rows returned."""
    def __init__(self, rows_by_table):
        self._rows_by_table = rows_by_table
        self._rows = []

    def execute(self, sql):
        for table, rows in self._rows_by_table.items():
            if f"[{table}]" in sql:
                self._rows = rows
                return self
        self._rows = []
        return self

    def fetchall(self):
        return self._rows


class _FakeConn:
    def __init__(self, rows_by_table):
        self._rows_by_table = rows_by_table

    def cursor(self):
        return _FakeCursor(self._rows_by_table)


def _patch_read_conn(monkeypatch, rows_by_table):
    import db.members as dbm
    monkeypatch.setattr(dbm, "_read_connection",
                        lambda path: _FakeConn(rows_by_table))


# ── get_health_plans ───────────────────────────────────────────────────────

def test_distinct_sorted_union_of_contacts_and_authorization(monkeypatch):
    from db.members import get_health_plans
    _patch_read_conn(monkeypatch, {
        "Contacts": [("HF",), ("BCBS",), ("HF",)],
        "Authorization": [("VCM",), ("BCBS",)],
    })
    assert get_health_plans("x") == ["BCBS", "HF", "VCM"]


def test_blanks_nulls_and_whitespace_filtered(monkeypatch):
    from db.members import get_health_plans
    _patch_read_conn(monkeypatch, {
        "Contacts": [(None,), ("",), ("  ",), (" HF ",), ("HF",)],
        "Authorization": [],
    })
    assert get_health_plans("x") == ["HF"]


def test_plan_not_in_hardcoded_tuple_is_included(monkeypatch):
    """The whole point: a new insurance present only in the DB shows up."""
    from db.members import get_health_plans, HEALTH_PLANS
    assert "UHC" not in HEALTH_PLANS
    _patch_read_conn(monkeypatch, {
        "Contacts": [("UHC",), ("HF",)],
        "Authorization": [],
    })
    assert get_health_plans("x") == ["HF", "UHC"]


def test_empty_db_falls_back_to_hardcoded_tuple(monkeypatch):
    from db.members import get_health_plans, HEALTH_PLANS
    _patch_read_conn(monkeypatch, {"Contacts": [], "Authorization": []})
    assert get_health_plans("x") == list(HEALTH_PLANS)


def test_db_error_falls_back_to_hardcoded_tuple(monkeypatch):
    """A DB hiccup must never block opening the wizard."""
    import pyodbc
    import db.members as dbm
    from db.members import get_health_plans, HEALTH_PLANS

    def boom(path):
        raise pyodbc.Error("gone")

    class _ErrConn:
        def cursor(self):
            raise pyodbc.Error("gone")

    monkeypatch.setattr(dbm, "_read_connection", lambda path: _ErrConn())
    monkeypatch.setattr(dbm, "_drop_read_connection", lambda path: None)
    assert get_health_plans("x") == list(HEALTH_PLANS)


# ── StepContact dropdown ───────────────────────────────────────────────────

def _combo_items(combo):
    return [combo.itemText(i) for i in range(combo.count())]


def test_step_contact_uses_passed_plans(qapp):
    from gui.wizard.step_contact import StepContact
    step = StepContact(plans=["BCBS", "HF", "UHC"])
    assert _combo_items(step.health_plan) == ["", "BCBS", "HF", "UHC"]


def test_step_contact_defaults_to_hardcoded_without_plans(qapp):
    from db.members import HEALTH_PLANS
    from gui.wizard.step_contact import StepContact
    step = StepContact()
    assert _combo_items(step.health_plan) == [""] + list(HEALTH_PLANS)


# ── wizard wiring ──────────────────────────────────────────────────────────

def test_wizard_populates_dropdown_from_db(qapp, monkeypatch):
    import db.members as dbm
    monkeypatch.setattr(dbm, "suggest_next_center_id", lambda path: 10001)
    monkeypatch.setattr(dbm, "get_health_plans", lambda path: ["ES", "UHC"])
    from gui.wizard.wizard import AddMemberWizard
    wiz = AddMemberWizard("x", "y")
    assert _combo_items(wiz._step_contact.health_plan) == ["", "ES", "UHC"]
