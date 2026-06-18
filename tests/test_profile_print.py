import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from gui.profile_print import build_profile_html


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def _member(**over):
    m = {
        "center_id": 10042, "last_name": "Doe", "first_name": "Jane",
        "chinese_name": "", "dob": "5/14/1948", "health_plan": "HF",
        "member_id": "M-1234", "medicaid": "MD1", "medicare": "MC1",
        "ssn": "123-45-6789", "language": "Cantonese", "case_manager": "Lee",
        "home_tell": "212-555-0100", "cell": "646-555-0199",
        "address": "1 Main St, NY", "emergency": "", "pcp": "Dr. Smith",
        "hospital": "Mt Sinai", "hha": "ABC HHA", "notes": "Prefers AM.",
        "gender": "F", "admission_date": "1/2/2026",
    }
    m.update(over)
    return m


def test_includes_member_name_and_id():
    html = build_profile_html(_member(), [], "2026-01-01")
    assert "Doe, Jane" in html
    assert "10042" in html


def test_includes_identity_contact_and_insurance_fields():
    html = build_profile_html(_member(), [], "2026-01-01")
    for value in ("5/14/1948", "M-1234", "(212)-555-0100", "1 Main St, NY",
                  "Cantonese", "Dr. Smith", "Mt Sinai"):
        assert value in html


def test_dob_strips_midnight_time():
    # Access stores some DOBs as a midnight datetime; the printout should show
    # just the date, not "... 00:00:00".
    html = build_profile_html(_member(dob="1941-06-04 00:00:00"), [], "2026-01-01")
    assert "1941-06-04" in html
    assert "00:00:00" not in html


def test_lists_emergency_contacts():
    ecs = [{"full_name": "John Doe", "phone": "917-555-0000",
            "relationship": "Son"}]
    html = build_profile_html(_member(), ecs, "2026-01-01")
    assert "John Doe" in html
    assert "(917)-555-0000" in html
    assert "Son" in html


def test_excludes_notes_authorization_and_printed_date():
    html = build_profile_html(_member(notes="SECRET NOTE TEXT"), [], "2026-01-01")
    assert "SECRET NOTE TEXT" not in html   # Notes content dropped
    assert "NOTES" not in html              # Notes section dropped
    assert "AUTHORIZATION" not in html      # Authorization section dropped
    assert "Printed" not in html            # printed-date footer dropped


def test_empty_field_renders_as_dash():
    html = build_profile_html(_member(chinese_name=""), [], "2026-01-01")
    assert "—" in html  # blank Chinese Name shown as an em-dash placeholder


def test_escapes_html_special_chars():
    html = build_profile_html(_member(last_name="Tom & <b>"), [], "2026-01-01")
    assert "Tom &amp; &lt;b&gt;" in html
    assert "Tom & <b>" not in html


def test_photo_tag_only_when_included():
    with_photo = build_profile_html(_member(), [], "2026-01-01", include_photo=True)
    without = build_profile_html(_member(), [], "2026-01-01", include_photo=False)
    assert 'src="profile://photo"' in with_photo
    assert 'src="profile://photo"' not in without


def test_layout_is_not_centered():
    # The sheet is left-aligned, not centered in a narrow column.
    html = build_profile_html(_member(), [], "2026-01-01")
    assert 'align="center"' not in html


def test_html_parses_cleanly_into_qtextdocument(qapp):
    from PyQt6.QtGui import QTextDocument
    doc = QTextDocument()
    doc.setHtml(build_profile_html(_member(), [], "2026-01-01", include_photo=True))
    assert "Doe, Jane" in doc.toPlainText()


def test_only_the_four_kept_sections_in_order():
    """Exactly Identity, Contact, Insurance/Medical, Emergency Contacts — in
    that order — and nothing else. (One-page fit is verified by rendering with
    real fonts; the offscreen fallback font over-wraps and can't measure it.)"""
    html = build_profile_html(_member(), [], "2026-01-01")
    headings = ["IDENTITY", "CONTACT", "INSURANCE / MEDICAL",
                "EMERGENCY CONTACTS"]
    positions = [html.find(h) for h in headings]
    assert all(p != -1 for p in positions)        # all present
    assert positions == sorted(positions)         # in order
    for absent in ("NOTES", "AUTHORIZATION"):
        assert absent not in html
