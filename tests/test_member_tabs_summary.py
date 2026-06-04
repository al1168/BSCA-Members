def test_summary_lists_only_changed_fields():
    from gui.member_tabs import build_change_summary
    old = {"first_name": "Mary", "cell": "", "address": "12 Elm St"}
    fields = {"first_name": "Marie", "cell": "", "address": "14 Oak Ave"}
    lines = build_change_summary(old, fields)
    joined = "\n".join(lines)
    assert any(line.startswith("First Name:") for line in lines)
    assert any(line.startswith("Address:") for line in lines)
    assert "Cell" not in joined  # unchanged -> excluded


def test_summary_uses_friendly_labels_and_arrow():
    from gui.member_tabs import build_change_summary
    lines = build_change_summary({"first_name": "Mary"}, {"first_name": "Marie"})
    assert lines == ["First Name: Mary → Marie"]


def test_summary_renders_empty_placeholder():
    from gui.member_tabs import build_change_summary
    lines = build_change_summary({"cell": ""}, {"cell": "917-555-0143"})
    assert lines == ["Cell: (empty) → 917-555-0143"]
    lines = build_change_summary({"address": "12 Elm St"}, {"address": ""})
    assert lines == ["Address: 12 Elm St → (empty)"]


def test_summary_empty_when_no_changes():
    from gui.member_tabs import build_change_summary
    assert build_change_summary({"first_name": "Mary"}, {"first_name": "Mary"}) == []


def test_summary_ignores_whitespace_and_newline_normalization():
    """Regression: stored values may have trailing spaces (Access) and CRLF
    notes, while widget read-back is stripped with LF. An untouched form must
    report no changes."""
    from gui.member_tabs import build_change_summary
    old = {
        "first_name": "Mary ",            # trailing space from storage
        "address": "  12 Elm St  ",       # surrounding whitespace
        "notes": "line1\r\nline2",        # Access CRLF
    }
    fields = {
        "first_name": "Mary",             # widget .text().strip()
        "address": "12 Elm St",
        "notes": "line1\nline2",          # QTextEdit .toPlainText() -> LF
    }
    assert build_change_summary(old, fields) == []


def test_format_auth_days_includes_weekend():
    """Regression: an auth covering Sat/Sun must not crash and must read
    'Sat'/'Sun' (KeyError: 6 previously crashed the member view)."""
    from gui.member_tabs import format_auth_days
    assert format_auth_days("1,3,5") == "Mon Wed Fri"
    assert format_auth_days("6,7") == "Sat Sun"
    assert format_auth_days("1,6") == "Mon Sat"
    assert format_auth_days("") == ""
    assert format_auth_days("9") == "9"  # unknown day falls back to the digit
