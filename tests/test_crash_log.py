from datetime import datetime


def _sample_exc():
    """Raise and catch a real exception, returning (exc_type, exc_value, exc_tb)."""
    import sys
    try:
        raise ValueError("boom-message")
    except ValueError:
        return sys.exc_info()


def test_format_report_includes_message_traceback_and_header():
    from crash_log import format_report
    et, ev, tb = _sample_exc()
    now = datetime(2026, 6, 2, 14, 51, 20)
    text = format_report(et, ev, tb, now=now)
    assert "CRASH 2026-06-02 14:51:20" in text
    assert "boom-message" in text
    assert "Traceback (most recent call last)" in text
    assert "ValueError" in text


def test_write_crash_report_uses_dated_filename(tmp_path):
    from crash_log import write_crash_report
    now = datetime(2026, 6, 2, 14, 51, 20)
    path = write_crash_report(str(tmp_path), "hello\n", now=now)
    assert path.endswith("debug_2026-06-02.txt")
    import os
    assert os.path.exists(path)


def test_write_crash_report_appends(tmp_path):
    from crash_log import write_crash_report
    now = datetime(2026, 6, 2, 9, 0, 0)
    write_crash_report(str(tmp_path), "===== CRASH A =====\n", now=now)
    path = write_crash_report(str(tmp_path), "===== CRASH B =====\n", now=now)
    with open(path, encoding="utf-8") as f:
        content = f.read()
    assert "CRASH A" in content
    assert "CRASH B" in content
    assert content.count("CRASH") == 2
