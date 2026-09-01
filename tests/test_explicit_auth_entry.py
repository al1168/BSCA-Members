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
