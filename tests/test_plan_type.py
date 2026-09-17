"""Plan Type (MAP/MLTC/N/A) on authorizations: table column, hidden Created column,
dialog/wizard plumbing."""
import os
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _col(table, label):
    for c in range(table.columnCount()):
        it = table.horizontalHeaderItem(c)
        if it is not None and it.text() == label:
            return c
    raise AssertionError(f"no column titled {label!r}")


def _auth(i, plan_type=""):
    return {"id": i, "auth_start": date(2026, 1, 1), "auth_end": date(2026, 12, 31),
            "auth_days": "12", "health_plan": "HF", "created_at": None,
            "member_id": "", "auth_number": "", "plan_type": plan_type}


def _build_auths_tab(monkeypatch, auths, show_row_ids=False):
    import db.members as dbm
    monkeypatch.setattr(dbm, "get_auth_ids_with_documents", lambda cid, path: set())
    monkeypatch.setattr(dbm, "get_auth_edges", lambda path: [])
    import gui.member_tabs as mt
    w = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)
    w._authorizations = auths
    w._transport_auths = []
    w._center_id = 1
    w._db_path = "x"
    w._show_row_ids = show_row_ids
    tab = w._make_auths_tab()          # keep ref so the table isn't GC'd
    return w, w._auth_table, tab


# ── constants ──────────────────────────────────────────────────────────────

def test_plan_types_constant():
    from db.members import PLAN_TYPES
    assert PLAN_TYPES == ("", "MAP", "MLTC", "N/A")


# ── the Authorizations table ───────────────────────────────────────────────

def test_plan_type_column_next_to_health_plan(qapp, monkeypatch):
    w, table, _tab = _build_auths_tab(monkeypatch, [_auth(1, "MAP")])
    assert _col(table, "Plan Type") == _col(table, "Health Plan") + 1


def test_plan_type_cell_populated(qapp, monkeypatch):
    w, table, _tab = _build_auths_tab(monkeypatch, [_auth(1, "MLTC")])
    assert table.item(0, _col(table, "Plan Type")).text() == "MLTC"


def test_plan_type_cell_blank_for_legacy_rows(qapp, monkeypatch):
    # Rows that predate the column (mapper yields "") render blank, not "None".
    a = _auth(1)
    del a["plan_type"]
    w, table, _tab = _build_auths_tab(monkeypatch, [a])
    assert table.item(0, _col(table, "Plan Type")).text() == ""


# ── Created column hidden with the row-ID debug toggle ─────────────────────

def test_created_column_hidden_by_default(qapp, monkeypatch):
    w, table, _tab = _build_auths_tab(monkeypatch, [_auth(1)], show_row_ids=False)
    assert table.isColumnHidden(_col(table, "Created")) is True
    # Plan Type stays visible — only the bookkeeping columns hide.
    assert table.isColumnHidden(_col(table, "Plan Type")) is False


def test_created_column_shown_when_row_ids_on(qapp, monkeypatch):
    w, table, _tab = _build_auths_tab(monkeypatch, [_auth(1)], show_row_ids=True)
    assert table.isColumnHidden(_col(table, "Created")) is False


def test_created_column_toggles_live(qapp, monkeypatch):
    w, table, _tab = _build_auths_tab(monkeypatch, [_auth(1)], show_row_ids=False)
    created = _col(table, "Created")
    w.set_show_row_ids(True)
    assert table.isColumnHidden(created) is False
    w.set_show_row_ids(False)
    assert table.isColumnHidden(created) is True


def test_apply_id_column_hides_both_id_and_created(qapp):
    from PyQt6.QtWidgets import QTableWidget
    import gui.member_tabs as mt
    w = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)
    w._show_row_ids = False
    table = QTableWidget(1, 4)
    table.setHorizontalHeaderLabels(["ID", "Auth Start", "Created", "Status"])
    w._apply_id_column(table)
    assert table.isColumnHidden(0) is True      # ID
    assert table.isColumnHidden(2) is True      # Created
    assert table.isColumnHidden(1) is False
    assert table.isColumnHidden(3) is False


# ── new-member wizard ──────────────────────────────────────────────────────

def test_wizard_collects_plan_type(qapp):
    from gui.wizard.step_auths import StepAuths
    w = StepAuths()
    w._day_checks[1].setChecked(True)
    w.plan_type.setCurrentText("MAP")
    data = w.collect()
    assert data["authorization"]["plan_type"] == "MAP"


def test_wizard_plan_type_defaults_blank(qapp):
    from gui.wizard.step_auths import StepAuths
    w = StepAuths()
    w._day_checks[1].setChecked(True)
    data = w.collect()
    assert data["authorization"]["plan_type"] == ""


def test_review_shows_plan_type(qapp):
    from gui.wizard.step_review import StepReview
    r = StepReview()
    r.populate({
        "contact": {"last_name": "Doe", "first_name": "J", "center_id": 1,
                    "health_plan": "HF"},
        "enrollment_start": "2026-01-01", "enrollment_end": None,
        "authorization": {"auth_start": "2026-01-01", "auth_end": "2026-12-31",
                          "auth_days": {1, 3}, "auth_number": "A-1",
                          "plan_type": "MLTC"},
    })
    assert "MLTC" in r._body.text()


# ── add/edit dialog ────────────────────────────────────────────────────────

def test_auth_dialog_has_plan_type_combo(qapp, monkeypatch):
    """The dialog offers a MAP/MLTC/N-A dropdown, pre-selected from the existing
    auth, and its selection lands in the returned dict."""
    from PyQt6.QtWidgets import QDialog, QComboBox, QWidget
    import gui.member_tabs as mt

    combos = []
    orig_combo_init = QComboBox.__init__

    def spy_init(self, *a, **k):
        orig_combo_init(self, *a, **k)
        combos.append(self)

    monkeypatch.setattr(QComboBox, "__init__", spy_init)
    monkeypatch.setattr(QDialog, "exec", lambda self: True)

    w = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)
    QWidget.__init__(w)      # init the C++ base only; QDialog(self) needs it
    w._member = {"member_id": ""}
    existing = _auth(1, plan_type="MLTC")
    result = w._open_auth_dialog(existing=existing)

    plan_type_combos = [c for c in combos
                        if [c.itemText(i) for i in range(c.count())]
                        == ["", "MAP", "MLTC", "N/A"]]
    assert len(plan_type_combos) == 1
    assert plan_type_combos[0].currentText() == "MLTC"
    assert result["plan_type"] == "MLTC"
