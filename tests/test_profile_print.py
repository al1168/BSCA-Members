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
        "gender": "F", "admission_date": "1/2/2026", "alt_id": 987654,
    }
    m.update(over)
    return m


def test_includes_member_name_and_id():
    html = build_profile_html(_member(), [], "2026-01-01")
    assert "Doe, Jane" in html
    assert "10042" in html


def test_center_id_sits_on_the_name_line():
    html = build_profile_html(_member(), [], "2026-01-01")
    name_i = html.find("Doe, Jane")
    br_i = html.find("<br>", name_i)
    cid_i = html.find("Center ID 10042", name_i)
    assert -1 < cid_i < br_i   # before the line break → same line as the name


def test_age_shown_next_to_dob():
    from datetime import date
    html = build_profile_html(_member(), [], "2026-01-01")
    d, today = date(1948, 5, 14), date.today()
    years = today.year - d.year - ((today.month, today.day) < (d.month, d.day))
    # Header meta line and the Identity section both carry the age.
    assert html.count(f"05/14/1948 (Age {years})") == 2


def test_no_age_when_dob_unparseable():
    html = build_profile_html(_member(dob="not-a-date"), [], "2026-01-01")
    assert "Age" not in html


def test_includes_identity_contact_and_insurance_fields():
    html = build_profile_html(_member(), [], "2026-01-01")
    for value in ("05/14/1948", "M-1234", "(212)-555-0100", "1 Main St, NY",
                  "Cantonese", "Dr. Smith"):
        assert value in html


def test_hospital_and_admission_date_removed():
    html = build_profile_html(_member(), [], "2026-01-01")
    assert "Mt Sinai" not in html and "Hospital" not in html
    assert "Admission Date" not in html and "1/2/2026" not in html


def test_active_auth_section_with_values():
    auth = {"sadc": "1.2.3", "auth_start": "01/01/2026",
            "auth_end": "12/31/2026", "auth_number": "AUTH-77",
            "trans_auth": "TR-42"}
    html = build_profile_html(_member(), [], "2026-01-01", active_auth=auth)
    assert "AUTHORIZATION" in html
    for label in ("SADC", "Auth BGN", "Auth END", "Auth Number", "TRANS Auth"):
        assert label in html
    for value in ("1.2.3", "01/01/2026", "12/31/2026", "AUTH-77", "TR-42"):
        assert value in html


def test_no_active_auth_notes_the_lapse():
    html = build_profile_html(_member(), [], "2026-01-01", active_auth=None)
    assert "AUTHORIZATION" in html
    assert "No active authorization" in html


def test_dob_prints_mmddyyyy_without_time():
    # Access stores some DOBs as a midnight datetime; the printout shows
    # MM/DD/YYYY, never "... 00:00:00".
    html = build_profile_html(_member(dob="1941-06-04 00:00:00"), [], "2026-01-01")
    assert "06/04/1941" in html
    assert "00:00:00" not in html


def test_lists_emergency_contacts():
    ecs = [{"full_name": "John Doe", "phone": "917-555-0000",
            "relationship": "Son"}]
    html = build_profile_html(_member(), ecs, "2026-01-01")
    assert "John Doe" in html
    assert "(917)-555-0000" in html
    assert "Son" in html


def test_excludes_alt_id():
    html = build_profile_html(_member(), [], "2026-01-01")
    assert "987654" not in html
    assert "Alt ID" not in html


def test_excludes_notes_and_printed_date():
    html = build_profile_html(_member(notes="SECRET NOTE TEXT"), [], "2026-01-01")
    assert "SECRET NOTE TEXT" not in html   # Notes content dropped
    assert "NOTES" not in html              # Notes section dropped
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


def test_print_active_auth_picks_todays_auth(qapp, monkeypatch):
    from datetime import date, timedelta
    from gui.member_tabs import MemberTabsWidget
    today = date.today()
    w = MemberTabsWidget.__new__(MemberTabsWidget)
    w._db_path = "fake.accdb"
    w._authorizations = [
        {"id": 1, "auth_start": today - timedelta(days=400),
         "auth_end": today - timedelta(days=30),          # expired
         "auth_days": "1,2", "auth_number": "OLD"},
        {"id": 2, "auth_start": today - timedelta(days=10),
         "auth_end": today + timedelta(days=300),         # active
         "auth_days": "3,1,5", "auth_number": "NEW-1"},
    ]
    w._transport_auths = [{"id": 9, "auth_number": "TR-9"},
                          {"id": 8, "auth_number": "TR-OTHER"}]
    monkeypatch.setattr(
        "db.members.get_auth_edges",
        lambda _db: [{"id": 1, "authorization_id": 2,
                      "transport_authorization_id": 9}])
    info = w._print_active_auth()
    assert info["sadc"] == "1.3.5"
    assert info["auth_number"] == "NEW-1"
    assert info["trans_auth"] == "TR-9"                   # linked, not TR-OTHER
    assert info["auth_start"] == f"{today - timedelta(days=10):%m/%d/%Y}"
    assert info["auth_end"] == f"{today + timedelta(days=300):%m/%d/%Y}"


def test_print_active_auth_none_when_all_expired(qapp, monkeypatch):
    from datetime import date, timedelta
    from gui.member_tabs import MemberTabsWidget
    today = date.today()
    w = MemberTabsWidget.__new__(MemberTabsWidget)
    w._db_path = "fake.accdb"
    w._transport_auths = []
    w._authorizations = [
        {"id": 1, "auth_start": today - timedelta(days=400),
         "auth_end": today - timedelta(days=30),
         "auth_days": "1", "auth_number": "OLD"},
    ]
    assert w._print_active_auth() is None


# The selector tests use a fake printer and a plain dialog+toolbar: a real
# QPrinter/QPrintPreviewDialog talks to the Windows print spooler, which
# blocks indefinitely on machines whose default printer is unreachable
# (e.g. the office RICOH from a dev laptop).
class _FakePrinter:
    def __init__(self):
        self._name = ""
        self._layout = object()
        self.layouts_set = []

    def setPrinterName(self, name): self._name = name
    def printerName(self): return self._name
    def pageLayout(self): return self._layout
    def setPageLayout(self, layout): self.layouts_set.append(layout)


def _selector_fixture(names, default):
    from PyQt6.QtWidgets import QComboBox, QDialog, QToolBar
    from gui.profile_print import _attach_printer_selector
    printer = _FakePrinter()
    preview = QDialog()
    QToolBar(preview)                       # stands in for the dialog's toolbar
    _attach_printer_selector(preview, printer, names=names, default_name=default)
    return printer, preview, preview.findChild(QComboBox, "printer_select")


def test_printer_selector_defaults_to_system_default(qapp):
    printer, _preview, combo = _selector_fixture(
        ["Office Laser", "PDF Writer"], "PDF Writer")
    assert combo is not None
    assert combo.currentText() == "PDF Writer"
    assert printer.printerName() == "PDF Writer"
    # Retargeting carried our page layout (margins) over to the new printer.
    assert printer.layouts_set == [printer.pageLayout()]


def test_printer_selector_switches_print_target(qapp):
    printer, _preview, combo = _selector_fixture(
        ["Office Laser", "PDF Writer"], "PDF Writer")
    combo.setCurrentText("Office Laser")
    assert printer.printerName() == "Office Laser"


def test_printer_selector_absent_without_printers(qapp):
    printer, preview, combo = _selector_fixture([], "")
    assert combo is None                    # nothing to choose from
    assert printer.printerName() == ""      # printer left untouched


def test_printer_selector_unknown_default_keeps_first(qapp):
    printer, _preview, combo = _selector_fixture(
        ["Office Laser", "PDF Writer"], "Gone Printer")
    assert combo.currentText() == "Office Laser"
    assert printer.printerName() == "Office Laser"


def test_html_parses_cleanly_into_qtextdocument(qapp):
    from PyQt6.QtGui import QTextDocument
    doc = QTextDocument()
    doc.setHtml(build_profile_html(_member(), [], "2026-01-01", include_photo=True))
    assert "Doe, Jane" in doc.toPlainText()


def test_only_the_five_kept_sections_in_order():
    """Exactly Identity, Contact, Insurance/Medical, Authorization, Emergency
    Contacts — in that order — and nothing else. (One-page fit is verified by
    rendering with real fonts; the offscreen fallback font over-wraps and
    can't measure it.)"""
    html = build_profile_html(_member(), [], "2026-01-01")
    headings = ["IDENTITY", "CONTACT", "INSURANCE / MEDICAL",
                "AUTHORIZATION", "EMERGENCY CONTACTS"]
    positions = [html.find(h) for h in headings]
    assert all(p != -1 for p in positions)        # all present
    assert positions == sorted(positions)         # in order
    assert "NOTES" not in html
