"""Printable member-profile sheet.

`build_profile_html` is a pure function that renders a member's profile as a
self-contained HTML document sized for Qt's rich-text engine (QTextDocument).
The layout is table-based (QTextDocument supports only a subset of CSS),
left-aligned and compact so the whole profile fits on a single page with a
slight margin. `open_profile_print_preview` loads that HTML into a QTextDocument,
attaches the photo as a document resource, and shows a QPrintPreviewDialog
(print or Save-as-PDF).
"""
import html as _html

from db.members import format_phone, format_date_only

# Subtle, print-friendly palette (white paper, dark text, calm accent).
_ACCENT = "#5b7cf4"
_LABEL = "#6b7280"
_VALUE = "#111827"
_RULE = "#d8dce6"
_PHOTO_URL = "profile://photo"
# Compact type scale so the sheet always fits one printed page.
_BODY_PT = "10.5pt"
_TITLE_PT = "11pt"


def _esc(value) -> str:
    """HTML-escape a value; blank/None becomes an em-dash placeholder."""
    text = "" if value is None else str(value).strip()
    return _html.escape(text) if text else "—"


def _date_only(value) -> str:
    """Print a DOB as MM/DD/YYYY however it's stored (datetime, ISO text,
    or M/D/YYYY text)."""
    from db.members import format_dob_display
    return format_dob_display(value)


def _fields_grid(pairs, cols: int = 2) -> str:
    """Lay label/value pairs out in `cols` even columns. Each cell holds its
    label and value together (gray label, then value) so the value sits right
    next to its label — no wide fixed label column leaving big gaps — and long
    values use the full half-width instead of wrapping in a narrow column."""
    col_w = 100 // cols
    rows = []
    for i in range(0, len(pairs), cols):
        cells = []
        for label, value in pairs[i:i + cols]:
            cells.append(
                f'<td width="{col_w}%" style="font-size:{_BODY_PT};">'
                f'<span style="color:{_LABEL};">{_html.escape(label)}</span>'
                f'&nbsp;&nbsp;'
                f'<span style="color:{_VALUE};">{_esc(value)}</span></td>'
            )
        while len(cells) < cols:          # pad the last row for even columns
            cells.append("<td></td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return f'<table width="100%" cellspacing="0" cellpadding="3">{"".join(rows)}</table>'


def _section(title: str, body_html: str) -> str:
    return (
        f'<p style="margin-top:10px; margin-bottom:1px; color:{_ACCENT}; '
        f'font-size:{_TITLE_PT};"><b>{_html.escape(title.upper())}</b></p>'
        f'<hr color="{_RULE}">'
        f'{body_html}'
    )


def build_profile_html(
    member: dict,
    emergency_contacts: list,
    enroll_start,
    include_photo: bool = False,
    active_auth: dict | None = None,
) -> str:
    """Render a member profile as a left-aligned one-page HTML document with
    Identity, Contact, Insurance/Medical, Authorization and Emergency
    Contacts sections.

    ``active_auth`` carries the current (in-effect-today) authorization as
    pre-formatted strings: sadc (day numbers like '1.2.3'), auth_start,
    auth_end, auth_number, trans_auth. None renders the section with a
    "no active authorization" note so a lapse is visible on paper.

    Pure: no Qt, no DB. When ``include_photo`` is set the header references the
    photo via ``profile://photo`` — the caller attaches the actual image as a
    QTextDocument resource at that URL.
    """
    m = member
    name = _esc(f"{m.get('last_name', '')}, {m.get('first_name', '')}".strip(", "))
    dob = _date_only(m.get("dob"))

    photo_cell = (
        f'<td width="120" valign="top">'
        f'<img src="{_PHOTO_URL}" width="108" height="108"></td>'
        if include_photo else ""
    )
    # Header: photo (left) + name and a single meta line, left-aligned.
    header = (
        f'<table width="100%" cellspacing="0" cellpadding="4">'
        f'<tr>{photo_cell}'
        f'<td valign="middle">'
        f'<span style="font-size:17pt; color:{_VALUE};"><b>{name}</b></span><br>'
        f'<span style="color:{_LABEL}; font-size:{_BODY_PT};">'
        f'Center ID {_esc(m.get("center_id"))}'
        f' &nbsp;·&nbsp; Health Plan {_esc(m.get("health_plan"))}'
        f' &nbsp;·&nbsp; DOB {_esc(dob)}'
        f' &nbsp;·&nbsp; Member ID {_esc(m.get("member_id"))}</span>'
        f'</td></tr></table>'
    )

    identity = _fields_grid([
        ("Chinese Name", m.get("chinese_name")),
        ("Gender", m.get("gender")),
        ("Date of Birth", dob),
        ("Language", m.get("language")),
        ("Enrollment Start", _date_only(enroll_start)),
    ], cols=2)
    contact = _fields_grid([
        ("Home Phone", format_phone(m.get("home_tell"))),
        ("Cell", format_phone(m.get("cell"))),
        ("Address", m.get("address")),
    ], cols=2)
    insurance = _fields_grid([
        ("Health Plan", m.get("health_plan")),
        ("Member ID", m.get("member_id")),
        ("Medicaid", m.get("medicaid")),
        ("Medicare", m.get("medicare")),
        ("SSN", m.get("ssn")),
        ("PCP", m.get("pcp")),
        ("HHA", m.get("hha")),
        ("Case Manager", m.get("case_manager")),
    ], cols=2)

    if active_auth:
        authorization = _fields_grid([
            ("SADC", active_auth.get("sadc")),
            ("Auth Number", active_auth.get("auth_number")),
            ("Auth BGN", active_auth.get("auth_start")),
            ("Auth END", active_auth.get("auth_end")),
            ("TRANS Auth", active_auth.get("trans_auth")),
        ], cols=2)
    else:
        authorization = (f'<p style="color:{_LABEL}; font-size:{_BODY_PT};">'
                         f'— No active authorization —</p>')

    if emergency_contacts:
        ec_rows = "".join(
            f'<tr>'
            f'<td width="36%" style="color:{_VALUE}; font-size:{_BODY_PT};">'
            f'{_esc(ec.get("full_name"))}</td>'
            f'<td style="color:{_VALUE}; font-size:{_BODY_PT};">{_esc(format_phone(ec.get("phone")))}</td>'
            f'<td style="color:{_VALUE}; font-size:{_BODY_PT};">'
            f'{_esc(ec.get("relationship"))}</td>'
            f'</tr>'
            for ec in emergency_contacts
        )
        emergency = (
            f'<table width="100%" cellspacing="0" cellpadding="3">'
            f'<tr>'
            f'<td width="36%" style="color:{_LABEL}; font-size:{_BODY_PT};"><b>Name</b></td>'
            f'<td style="color:{_LABEL}; font-size:{_BODY_PT};"><b>Phone</b></td>'
            f'<td style="color:{_LABEL}; font-size:{_BODY_PT};"><b>Relationship</b></td>'
            f'</tr>{ec_rows}</table>'
        )
    else:
        emergency = (f'<p style="color:{_LABEL}; font-size:{_BODY_PT};">'
                     f'— No emergency contacts on file —</p>')

    sections = [
        header,
        _section("Identity", identity),
        _section("Contact", contact),
        _section("Insurance / Medical", insurance),
        _section("Authorization", authorization),
        _section("Emergency Contacts", emergency),
    ]

    # Left-aligned, full-width (the page margins supply the slight frame).
    return (
        f'<html><body>'
        f'<p style="margin:0 0 4px 0; color:{_ACCENT}; font-size:{_TITLE_PT};">'
        f'<b>MEMBER PROFILE</b></p>'
        f'{"".join(sections)}'
        f'</body></html>'
    )


def open_profile_print_preview(
    parent,
    member: dict,
    emergency_contacts: list,
    enroll_start,
    photo_bytes: bytes | None = None,
    active_auth: dict | None = None,
) -> None:
    """Show a print-preview dialog (print or Save-as-PDF) for a member profile."""
    from PyQt6.QtCore import QUrl, QMarginsF
    from PyQt6.QtGui import QTextDocument, QImage, QPageLayout
    from PyQt6.QtPrintSupport import QPrinter, QPrintPreviewDialog

    doc = QTextDocument()
    if photo_bytes:
        img = QImage()
        if img.loadFromData(photo_bytes):
            doc.addResource(QTextDocument.ResourceType.ImageResource,
                            QUrl(_PHOTO_URL), img)
    doc.setHtml(build_profile_html(
        member, emergency_contacts, enroll_start,
        include_photo=bool(photo_bytes),
        active_auth=active_auth,
    ))

    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    # Slim, even margins — enough to look framed while keeping the whole
    # profile on a single page.
    printer.setPageMargins(QMarginsF(8, 8, 8, 8),
                           QPageLayout.Unit.Millimeter)

    preview = QPrintPreviewDialog(printer, parent)
    preview.setWindowTitle("Print Member Profile")
    # Wide enough that the full toolbar (incl. the Print button) shows instead
    # of collapsing into an overflow "…" menu.
    preview.resize(1040, 800)
    preview.paintRequested.connect(doc.print)  # PyQt6: print (not print_)
    preview.exec()
