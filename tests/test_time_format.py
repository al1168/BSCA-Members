from db.members import format_time_live, normalize_time_12h


def test_format_time_live_progressive():
    assert format_time_live("") == ""
    assert format_time_live("8") == "8"
    assert format_time_live("81") == "81"
    assert format_time_live("815") == "8:15"
    assert format_time_live("1230") == "12:30"
    assert format_time_live("12305") == "12:30"   # capped at 4 digits
    assert format_time_live("8:15") == "8:15"      # strips non-digits, reformats


def test_normalize_time_12h_valid():
    assert normalize_time_12h("8") == "8:00"       # hour only -> :00
    assert normalize_time_12h("12") == "12:00"
    assert normalize_time_12h("815") == "8:15"
    assert normalize_time_12h("1230") == "12:30"
    assert normalize_time_12h("8:15") == "8:15"


def test_normalize_time_12h_invalid():
    assert normalize_time_12h("") is None
    assert normalize_time_12h("0") is None         # hour 0 not valid in 12h
    assert normalize_time_12h("13") is None        # hour 13 not valid in 12h
    assert normalize_time_12h("1360") is None      # minute 60 out of range
    assert normalize_time_12h("875") is None       # 8:75 -> minute out of range
