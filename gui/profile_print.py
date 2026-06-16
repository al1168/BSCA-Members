"""Printable member-profile sheet.

`build_profile_html` is a pure function that renders a member's profile as a
self-contained HTML document sized for Qt's rich-text engine (QTextDocument).
The layout is table-based (QTextDocument supports only a subset of CSS), centred
on the page and generously spaced. `open_profile_print_preview` loads that HTML
into a QTextDocument, attaches the photo as a document resource, and shows a
QPrintPreviewDialog (print or Save-as-PDF).
"""
import html as _html
from datetime import date

# Subtle, print-friendly palette (white paper, dark text, calm accent).
_ACCENT = "#5b7cf4"
_LABEL = "#6b7280"
_VALUE = "#111827"
_RULE = "#d8dce6"
_PHOTO_URL = "profile://photo"


def _esc(value) -> str:
    """HTML-escape a value; blank/None becomes an em-dash placeholder."""
    text = "" if value is None else str(value).strip()
    return _html.escape(text) if text else "—"


def _fields_table(pairs) -> str:
    rows = "".join(
        f'<tr>'
        f'<td width="36%" style="color:{_LABEL};">{_html.escape(label)}</td>'
        f'<td style="color:{_VALUE};">{_esc(value)}</td>'
        f'</tr>'
        for label, value in pairs
    )
    return (f'<table width="100%" cellspacing="0" cellpadding="4">{rows}</table>')


def _section(title: str, body_html: str) -> str:
    return (
        f'<p style="margin-top:20px; margin-bottom:2px; color:{_ACCENT}; '
        f'font-size:10pt;"><b>{_html.escape(title.upper())}</b></p>'
        f'<hr color="{_RULE}">'
        f'{body_html}'
    )


def build_profile_html(
    member: dict,
    emergency_contacts: list,
    auth_summary: dict | None,
    enroll_start,
    include_photo: bool = False,
    printed_on: str = "",
) -> str:
    """Render a member profile as a centred, well-spaced HTML document.

    Pure: no Qt, no DB. When ``include_photo`` is set the header references the
    photo via ``profile://photo`` — the caller attaches the actual image as a
    QTextDocument resource at that URL.
    """
    m = member
    name = _esc(f"{m.get('last_name', '')}, {m.get('first_name', '')}".strip(", "))
    printed = printed_on or date.today().isoformat()

    photo_cell = (
        f'<td width="104" valign="top">'
        f'<img src="{_PHOTO_URL}" width="88" height="88"></td>'
        if include_photo else ""
    )

    header = (
        f'<table width="100%" cellspacing="0" cellpadding="6">'
        f'<tr>{photo_cell}'
        f'<td valign="middle" align="center">'
        f'<p style="font-size:18pt; color:{_VALUE};"><b>{name}</b></p>'
        f'<p style="color:{_LABEL};">Center ID {_esc(m.get("center_id"))}'
        f' &nbsp;·&nbsp; Health Plan {_esc(m.get("health_plan"))}</p>'
        f'<p style="color:{_LABEL};">DOB {_esc(m.get("dob"))}'
        f' &nbsp;·&nbsp; Member ID {_esc(m.get("member_id"))}</p>'
        f'</td></tr></table>'
    )

    identity = _fields_table([
        ("Chinese Name", m.get("chinese_name")),
        ("Gender", m.get("gender")),
        ("Date of Birth", m.get("dob")),
        ("Language", m.get("language")),
        ("Enrollment Start", enroll_start),
        ("Admission Date", m.get("admission_date")),
    ])
    contact = _fields_table([
        ("Home Phone", m.get("home_tell")),
        ("Cell", m.get("cell")),
        ("Address", m.get("address")),
    ])
    insurance = _fields_table([
        ("Health Plan", m.get("health_plan")),
        ("Member ID", m.get("member_id")),
        ("Medicaid", m.get("medicaid")),
        ("Medicare", m.get("medicare")),
        ("SSN", m.get("ssn")),
        ("PCP", m.get("pcp")),
        ("Hospital", m.get("hospital")),
        ("HHA", m.get("hha")),
        ("Case Manager", m.get("case_manager")),
    ])

    if emergency_contacts:
        ec_rows = "".join(
            f'<tr>'
            f'<td style="color:{_VALUE};">{_esc(ec.get("full_name"))}</td>'
            f'<td style="color:{_VALUE};">{_esc(ec.get("phone"))}</td>'
            f'<td style="color:{_VALUE};">{_esc(ec.get("relationship"))}</td>'
            f'</tr>'
            for ec in emergency_contacts
        )
        emergency = (
            f'<table width="100%" cellspacing="0" cellpadding="4">'
            f'<tr>'
            f'<td width="36%" style="color:{_LABEL};"><b>Name</b></td>'
            f'<td style="color:{_LABEL};"><b>Phone</b></td>'
            f'<td style="color:{_LABEL};"><b>Relationship</b></td>'
            f'</tr>{ec_rows}</table>'
        )
    else:
        emergency = f'<p style="color:{_LABEL};">— No emergency contacts on file —</p>'

    sections = [
        header,
        _section("Identity", identity),
        _section("Contact", contact),
        _section("Insurance / Medical", insurance),
        _section("Emergency Contacts", emergency),
    ]
    if auth_summary:
        auth = _fields_table([
            ("Period", auth_summary.get("period")),
            ("Authorized Days", auth_summary.get("days")),
            ("Plan", auth_summary.get("plan")),
        ])
        sections.append(_section("Current Authorization", auth))
    sections.append(_section("Notes", (
        f'<p style="color:{_VALUE};">{_esc(m.get("notes"))}</p>'
    )))

    footer = (
        f'<p align="center" style="margin-top:24px; color:{_LABEL}; '
        f'font-size:8pt;">Printed {_html.escape(printed)}</p>'
    )

    body = "".join(sections) + footer
    # Outer table centres the whole sheet on the page with balanced whitespace.
    return (
        f'<html><body>'
        f'<table align="center" width="86%" cellspacing="0" cellpadding="0">'
        f'<tr><td>'
        f'<p align="center" style="color:{_ACCENT}; font-size:11pt;">'
        f'<b>BSCA &nbsp;·&nbsp; MEMBER PROFILE</b></p>'
        f'{body}'
        f'</td></tr></table>'
        f'</body></html>'
    )


def open_profile_print_preview(
    parent,
    member: dict,
    emergency_contacts: list,
    auth_summary: dict | None,
    enroll_start,
    photo_bytes: bytes | None = None,
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
        member, emergency_contacts, auth_summary, enroll_start,
        include_photo=bool(photo_bytes),
    ))

    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    # Generous, symmetric margins so the centred sheet is framed evenly.
    printer.setPageMargins(QMarginsF(18, 18, 18, 18),
                           QPageLayout.Unit.Millimeter)

    preview = QPrintPreviewDialog(printer, parent)
    preview.setWindowTitle("Print Member Profile")
    preview.paintRequested.connect(doc.print)  # PyQt6: print (not print_)
    preview.exec()
