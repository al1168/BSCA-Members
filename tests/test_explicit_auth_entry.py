# tests/test_explicit_auth_entry.py
"""Explicit-entry new authorizations: no auto-filled dates, all fields
required when creating (dialog + wizard); editing is exempt."""
import os
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


# ── pure helper: which required fields is a new auth missing ───────────────

def test_missing_fields_all_empty_lists_everything():
    from gui.member_tabs import missing_new_auth_fields
    missing = missing_new_auth_fields(
        start_valid=False, end_valid=False, has_day=False,
        health_plan="", plan_type="", member_id="", auth_number="")
    assert missing == ["Auth Start", "Auth End", "Days", "Health Plan",
                       "Plan Type", "Member ID", "Auth Number"]


def test_missing_fields_complete_returns_empty():
    from gui.member_tabs import missing_new_auth_fields
    assert missing_new_auth_fields(
        start_valid=True, end_valid=True, has_day=True,
        health_plan="HF", plan_type="MAP", member_id="M1",
        auth_number="A1") == []


def test_missing_fields_whitespace_counts_as_missing():
    from gui.member_tabs import missing_new_auth_fields
    missing = missing_new_auth_fields(
        start_valid=True, end_valid=True, has_day=True,
        health_plan="HF", plan_type="MAP", member_id="   ",
        auth_number=" ")
    assert missing == ["Member ID", "Auth Number"]


# ── Add Authorization dialog (create mode) ─────────────────────────────────

def _run_auth_dialog(monkeypatch, existing=None, fill=None,
                     member=None):
    """Open _open_auth_dialog with widget spies and a fake exec() that
    optionally fills the widgets, then clicks OK (emits accepted, which runs
    on_accept). Returns (result, cap, warnings).

    cap: dates (DateLineEdit, creation order start/end), combos (creation
    order: health plan, plan type), edits (all QLineEdits incl. dates —
    filter by placeholder), checks (7 day QCheckBoxes), boxes (button box).
    """
    from PyQt6.QtWidgets import (
        QDialog, QComboBox, QLineEdit, QCheckBox, QWidget,
        QDialogButtonBox, QMessageBox,
    )
    import gui.member_tabs as mt
    from gui.address_autocomplete import DateLineEdit

    cap = {"dates": [], "combos": [], "edits": [], "checks": [], "boxes": []}

    def spy(cls, bucket):
        orig = cls.__init__

        def spied(self, *a, **k):
            orig(self, *a, **k)
            cap[bucket].append(self)
        monkeypatch.setattr(cls, "__init__", spied)

    spy(DateLineEdit, "dates")
    spy(QComboBox, "combos")
    spy(QLineEdit, "edits")
    spy(QCheckBox, "checks")
    spy(QDialogButtonBox, "boxes")

    warnings = []
    monkeypatch.setattr(
        QMessageBox, "warning",
        staticmethod(lambda *a, **k: warnings.append(a)))

    def fake_exec(self):
        if fill is not None:
            fill(cap)
        cap["boxes"][-1].accepted.emit()          # runs on_accept
        return int(self.result()) == int(QDialog.DialogCode.Accepted)
    monkeypatch.setattr(QDialog, "exec", fake_exec)

    w = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)
    QWidget.__init__(w)          # C++ base only; QDialog(self) needs it
    w._member = member or {"member_id": "MBR-1"}
    result = w._open_auth_dialog(existing=existing)
    cap["_owner"] = w   # keep the dialog's C++ parent chain alive for
                        # post-return widget inspection (PyQt destroys a
                        # parentless QWidget's children once its last
                        # Python reference is dropped)
    return result, cap, warnings


def _edit_by_placeholder(cap, prefix):
    return [e for e in cap["edits"]
            if e.placeholderText().startswith(prefix)][0]


def test_new_dialog_starts_empty_and_blank(qapp, monkeypatch):
    from db.members import HEALTH_PLANS
    seen = {}

    def inspect(cap):
        start, end = cap["dates"][:2]
        plan, ptype = cap["combos"][:2]
        seen["start"] = start.text()
        seen["end"] = end.text()
        seen["plan_items"] = [plan.itemText(i) for i in range(plan.count())]
        seen["plan_current"] = plan.currentText()
        seen["ptype_current"] = ptype.currentText()
        seen["member_id"] = _edit_by_placeholder(
            cap, "Health plan member").text()
        seen["auth_number"] = _edit_by_placeholder(
            cap, "Authorization number").text()

    result, _cap, _warn = _run_auth_dialog(monkeypatch, fill=inspect)
    assert result is None                      # nothing filled -> rejected
    assert seen["start"] == "" and seen["end"] == ""
    assert seen["plan_items"] == [""] + list(HEALTH_PLANS)
    assert seen["plan_current"] == ""
    assert seen["ptype_current"] == ""
    assert seen["member_id"] == "MBR-1"        # pre-fill kept
    assert seen["auth_number"] == ""


def test_new_dialog_rejects_and_lists_all_missing(qapp, monkeypatch):
    result, cap, warnings = _run_auth_dialog(monkeypatch,
                                             member={"member_id": ""})
    assert result is None
    assert len(warnings) == 1
    text = warnings[0][2]                      # (parent, title, text)
    for name in ("Auth Start", "Auth End", "Days", "Health Plan",
                 "Plan Type", "Member ID", "Auth Number"):
        assert name in text
    # The combos and line edits got the red error outline.
    plan, ptype = cap["combos"][:2]
    assert plan.property("error") is True
    assert ptype.property("error") is True
    assert _edit_by_placeholder(cap, "Authorization number") \
        .property("error") is True


def _fill_everything(cap):
    start, end = cap["dates"][:2]
    start.setText("01/01/2026")
    end.setText("12/31/2026")
    cap["checks"][0].setChecked(True)          # Mon
    plan, ptype = cap["combos"][:2]
    plan.setCurrentText("HF")
    ptype.setCurrentText("MAP")
    _edit_by_placeholder(cap, "Authorization number").setText("A-123")


def test_new_dialog_accepts_when_complete(qapp, monkeypatch):
    result, _cap, warnings = _run_auth_dialog(monkeypatch,
                                              fill=_fill_everything)
    assert warnings == []
    assert result == {
        "auth_start": date(2026, 1, 1),
        "auth_end": date(2026, 12, 31),
        "days": {1},
        "health_plan": "HF",
        "plan_type": "MAP",
        "member_id": "MBR-1",
        "auth_number": "A-123",
    }


def test_new_dialog_rejects_when_only_health_plan_missing(qapp, monkeypatch):
    def fill_all_but_plan(cap):
        start, end = cap["dates"][:2]
        start.setText("01/01/2026")
        end.setText("12/31/2026")
        cap["checks"][0].setChecked(True)
        cap["combos"][1].setCurrentText("MAP")     # plan type only
        _edit_by_placeholder(cap, "Authorization number").setText("A-1")

    result, cap, warnings = _run_auth_dialog(monkeypatch,
                                             fill=fill_all_but_plan)
    assert result is None
    assert len(warnings) == 1
    assert "Health Plan" in warnings[0][2]
    assert cap["combos"][0].property("error") is True


def test_edit_mode_exempt_from_new_requirements(qapp, monkeypatch):
    """A legacy auth with blank plan type / auth number / member id still
    saves untouched — edit keeps today's dates+days validation only."""
    from db.members import HEALTH_PLANS
    existing = {"id": 9, "auth_start": date(2026, 1, 1),
                "auth_end": date(2026, 12, 31), "auth_days": "1,2",
                "health_plan": "HF", "member_id": "", "auth_number": "",
                "plan_type": ""}
    seen = {}

    def inspect(cap):
        plan = cap["combos"][0]
        seen["plan_items"] = [plan.itemText(i) for i in range(plan.count())]

    result, _cap, warnings = _run_auth_dialog(
        monkeypatch, existing=existing, fill=inspect)
    assert warnings == []
    # Edit mode: no blank entry injected into the Health Plan combo.
    assert seen["plan_items"] == list(HEALTH_PLANS)
    assert result is not None
    assert result["plan_type"] == ""
    assert result["auth_number"] == ""
    assert result["member_id"] == ""


def test_new_dialog_error_outline_clears_on_edit(qapp, monkeypatch):
    """After a failed OK, typing/choosing clears a field's red outline."""
    fixed = {}

    def fail_then_fix(cap):
        cap["boxes"][-1].accepted.emit()       # first OK: everything missing
        plan, ptype = cap["combos"][:2]
        num = _edit_by_placeholder(cap, "Authorization number")
        assert plan.property("error") is True
        plan.setCurrentText("HF")
        ptype.setCurrentText("MAP")
        num.setText("")
        from PyQt6.QtTest import QTest
        QTest.keyClicks(num, "A-1")
        fixed["plan"] = plan.property("error")
        fixed["ptype"] = ptype.property("error")
        fixed["num"] = num.property("error")

    _result, _cap, _warn = _run_auth_dialog(monkeypatch, fill=fail_then_fix)
    assert fixed["plan"] is False
    assert fixed["ptype"] is False
    assert fixed["num"] is False


# ── wizard auth step ───────────────────────────────────────────────────────

def _step(qapp):
    from gui.wizard.step_auths import StepAuths
    return StepAuths()


def test_wizard_dates_start_empty(qapp):
    s = _step(qapp)
    assert s.auth_start.text() == ""
    assert s.auth_end.text() == ""


def test_wizard_skipped_only_when_nothing_entered(qapp):
    s = _step(qapp)
    assert s.is_skipped() is True
    # Each kind of entry individually engages the step.
    s.auth_start.setText("01/01/2026")
    assert s.is_skipped() is False
    s.auth_start.setText("")
    s.auth_number.setText("A-1")
    assert s.is_skipped() is False
    s.auth_number.setText("")
    s.plan_type.setCurrentText("MAP")
    assert s.is_skipped() is False
    s.plan_type.setCurrentText("")
    s._day_checks[3].setChecked(True)
    assert s.is_skipped() is False


def test_wizard_empty_step_validates_and_collects_none(qapp):
    s = _step(qapp)
    assert s.validate() is True
    assert s.collect()["authorization"] is None


def test_wizard_engaged_step_requires_everything(qapp):
    s = _step(qapp)
    s._day_checks[1].setChecked(True)          # engaged, rest missing
    assert s.validate() is False
    assert s.auth_start.property("error") is True
    assert s.auth_end.property("error") is True
    assert s.plan_type.property("error") is True
    assert s.auth_number.property("error") is True


def test_wizard_engaged_without_days_fails(qapp):
    s = _step(qapp)
    s.auth_start.setText("01/01/2026")
    s.auth_end.setText("12/31/2026")
    s.plan_type.setCurrentText("MLTC")
    s.auth_number.setText("A-9")
    assert s.is_skipped() is False
    assert s.validate() is False               # no day checked


def test_wizard_complete_step_validates_and_collects(qapp):
    s = _step(qapp)
    s.auth_start.setText("01/01/2026")
    s.auth_end.setText("12/31/2026")
    s._day_checks[1].setChecked(True)
    s._day_checks[3].setChecked(True)
    s.plan_type.setCurrentText("MAP")
    s.auth_number.setText("A-9")
    assert s.validate() is True
    auth = s.collect()["authorization"]
    assert auth == {
        "auth_start": date(2026, 1, 1),
        "auth_end": date(2026, 12, 31),
        "auth_days": {1, 3},
        "auth_number": "A-9",
        "plan_type": "MAP",
    }


def test_wizard_error_outline_clears_on_edit(qapp):
    s = _step(qapp)
    s._day_checks[1].setChecked(True)
    s.validate()                               # paints everything red
    assert s.auth_number.property("error") is True
    from PyQt6.QtTest import QTest
    QTest.keyClicks(s.auth_number, "A")        # typing clears the outline
    assert s.auth_number.property("error") is False
    s.plan_type.setCurrentText("MAP")
    assert s.plan_type.property("error") is False


def test_wizard_next_message_matches_new_skip_rule(qapp):
    """The Next-blocked message must not claim unchecking days skips the
    step — under the explicit-entry rule it doesn't."""
    import inspect
    import gui.wizard.wizard as wz
    src = inspect.getsource(wz)
    assert "uncheck all days" not in src
    assert "clear all of it to skip" in src
