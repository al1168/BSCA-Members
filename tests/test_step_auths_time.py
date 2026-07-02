import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_row_uses_free_text_time_and_ampm_dropdown(qapp):
    from PyQt6.QtWidgets import QComboBox
    from gui.wizard.step_auths import StepAuths, TimeLineEdit
    w = StepAuths()
    w._add_avail_row()
    r = w._avail_rows[0]
    assert isinstance(r["t_start"], TimeLineEdit)
    assert isinstance(r["ampm_start"], QComboBox)     # AM/PM is a separate dropdown
    assert isinstance(r["t_end"], TimeLineEdit)
    assert isinstance(r["ampm_end"], QComboBox)
    assert r["t_start"].text() == "8:00" and r["ampm_start"].currentText() == "AM"
    assert r["t_end"].text() == "4:00" and r["ampm_end"].currentText() == "PM"


def test_timelineedit_formats_as_you_type(qapp):
    from gui.wizard.step_auths import TimeLineEdit
    f = TimeLineEdit()
    f.setText("930")
    f._on_edited()            # the textEdited handler that runs on each keystroke
    assert f.text() == "9:30"


def test_collect_converts_time_and_ampm_to_24h(qapp):
    from gui.wizard.step_auths import StepAuths
    w = StepAuths()
    w._add_avail_row()
    r = w._avail_rows[0]
    r["combo"].setCurrentIndex(0)                     # Monday (day 1)
    r["t_start"].setText("9:30"); r["ampm_start"].setCurrentText("AM")
    r["t_end"].setText("5:00");  r["ampm_end"].setCurrentText("PM")
    avail = w.collect()["availability_rows"]
    mon = [a for a in avail if a["day_of_week"] == 1]
    assert any(a["avail_start"] == "09:30" and a["avail_end"] == "17:00"
               for a in mon)


def test_validate_flags_invalid_time(qapp):
    from gui.wizard.step_auths import StepAuths
    w = StepAuths()
    w._add_avail_row()
    w._avail_rows[0]["t_start"].setText("99")         # invalid hour
    assert w.validate() is False
    assert w._avail_rows[0]["t_start"].property("error") is True
    w._avail_rows[0]["t_start"].setText("9:30")
    assert w.validate() is True
