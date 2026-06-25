import os
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


TODAY = date(2026, 6, 25)


def test_merge_defaults_all_seven_days_when_none_added():
    from db.members import merge_default_availability
    rows = merge_default_availability([], TODAY)
    assert [r["day_of_week"] for r in rows] == [1, 2, 3, 4, 5, 6, 7]
    assert all(r["avail_start"] == "08:00" and r["avail_end"] == "16:00"
               for r in rows)
    assert all(r["effective_start_date"] == TODAY for r in rows)
    assert all(r["effective_end_date"] is None for r in rows)


def test_added_row_substitutes_its_weekday():
    from db.members import merge_default_availability
    added = [{"day_of_week": 1, "avail_start": "10:00", "avail_end": "16:00",
              "effective_start_date": TODAY, "effective_end_date": None}]
    rows = merge_default_availability(added, TODAY)
    by_day = {r["day_of_week"]: r for r in rows}
    assert by_day[1]["avail_start"] == "10:00"        # Monday overridden
    assert by_day[2]["avail_start"] == "08:00"        # Tue–Sun keep the default
    assert by_day[7]["avail_start"] == "08:00"
    assert len(rows) == 7


def test_step_auths_collect_includes_default_availability(qapp):
    from gui.wizard.step_auths import StepAuths
    w = StepAuths()                       # nothing added, auth skipped
    data = w.collect()
    assert data["authorization"] is None  # no auth days checked
    days = sorted(r["day_of_week"] for r in data["availability_rows"])
    assert days == [1, 2, 3, 4, 5, 6, 7]  # defaults still added
