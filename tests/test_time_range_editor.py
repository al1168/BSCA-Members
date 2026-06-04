import pytest


def test_hhmm_minutes_round_trip():
    from gui.time_range_editor import hhmm_to_minutes, minutes_to_hhmm
    assert hhmm_to_minutes("08:00") == 480
    assert hhmm_to_minutes("16:00") == 960
    assert hhmm_to_minutes("08:07") == 487
    assert minutes_to_hhmm(480) == "08:00"
    assert minutes_to_hhmm(960) == "16:00"
    assert minutes_to_hhmm(487) == "08:07"


@pytest.mark.parametrize("bad", ["8", "8:00:00", "abc", "8:"])
def test_hhmm_to_minutes_invalid(bad):
    from gui.time_range_editor import hhmm_to_minutes
    with pytest.raises(ValueError):
        hhmm_to_minutes(bad)


def test_clamp_minutes():
    from gui.time_range_editor import clamp_minutes
    assert clamp_minutes(470) == 480
    assert clamp_minutes(970) == 960
    assert clamp_minutes(600) == 600


def test_snap_minutes():
    from gui.time_range_editor import snap_minutes
    assert snap_minutes(487) == 480
    assert snap_minutes(488) == 495
    assert snap_minutes(953) == 960   # snaps to 960, within bounds
    assert snap_minutes(470) == 480   # clamped up first/after


def test_minutes_to_12h():
    from gui.time_range_editor import minutes_to_12h
    assert minutes_to_12h(480) == ("8:00", "AM")
    assert minutes_to_12h(487) == ("8:07", "AM")
    assert minutes_to_12h(720) == ("12:00", "PM")
    assert minutes_to_12h(960) == ("4:00", "PM")
