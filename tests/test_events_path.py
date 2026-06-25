import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_default_events_path_is_events_db_in_a_real_dir():
    from member_manager import default_events_db_path
    p = default_events_db_path()
    assert os.path.basename(p) == "events.db"
    assert os.path.isdir(os.path.dirname(p))   # base dir is created


def test_ensure_events_path_defaults_when_empty():
    from member_manager import ensure_events_path, default_events_db_path
    s = {"events_db_path": ""}
    assert ensure_events_path(s) is True
    assert s["events_db_path"] == default_events_db_path()


def test_ensure_events_path_respects_existing():
    from member_manager import ensure_events_path
    s = {"events_db_path": r"C:/custom/events.db"}
    assert ensure_events_path(s) is False
    assert s["events_db_path"] == r"C:/custom/events.db"
