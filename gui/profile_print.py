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


def _fields_grid(pairs, cols: int = 2) -> str:
    """Lay label/value pairs out in `cols` columns. Label columns are wide
    enough that two-word labels ("Enrollment Start") stay on one line."""
    label_w = "23%" if cols >= 2 else "30%"
    rows = []
    for i in range(0, len(pairs), cols):
        cells = []
        for label, value in pairs[i:i + cols]:
            cells.append(
                f'<td width="{label_w}" style="color:{_LABEL}; font-size:12pt;">'
                f'{_html.escape(label)}</td>'
                f'<td style="color:{_VALUE}; font-size:12pt;">{_esc(value)}</td>'
            )
        while len(cells) < cols:          # pad the last row for even columns
            cells.append("<td></td><td></td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return f'<table width="100%" cellspacing="0" cellpadding="5">{"".join(rows)}</table>'


def _section(title: str, body_html: str) -> str:
    return (
        f'<p style="margin-top:18px; margin-bottom:2px; color:{_ACCENT}; '
        f'font-size:13pt;"><b>{_html.escape(title.upper())}</b></p>'
        f'<hr color="{_RULE}">'
        f'{body_html}'
    )


def build_profile_html(
    member: dict,
    emergency_contacts: list,
    enroll_start,
    include_photo: bool = False,
) -> str:
    """Render a member profile as a left-aligned one-page HTML document with
    Identity, Contact, Insurance/Medical and Emergency Contacts sections.

    Pure: no Qt, no DB. When ``include_photo`` is set the header references the
    photo via ``profile://photo`` — the caller attaches the actual image as a
    QTextDocument resource at that URL.
    """
    m = member
    name = _esc(f"{m.get('last_name', '')}, {m.get('first_name', '')}".strip(", "))

    photo_cell = (
        f'<td width="150" valign="top">'
        f'<img src="{_PHOTO_URL}" width="132" height="132"></td>'
        if include_photo else ""
    )
    # Header: photo (left) + name and a single meta line, left-aligned.
    header = (
        f'<table width="100%" cellspacing="0" cellpadding="6">'
        f'<tr>{photo_cell}'
        f'<td valign="middle">'
        f'<span style="font-size:22pt; color:{_VALUE};"><b>{name}</b></span><br>'
        f'<span style="color:{_LABEL}; font-size:12pt;">'
        f'Center ID {_esc(m.get("center_id"))}'
        f' &nbsp;·&nbsp; Health Plan {_esc(m.get("health_plan"))}'
        f' &nbsp;·&nbsp; DOB {_esc(m.get("dob"))}'
        f' &nbsp;·&nbsp; Member ID {_esc(m.get("member_id"))}</span>'
        f'</td></tr></table>'
    )

    identity = _fields_grid([
        ("Chinese Name", m.get("chinese_name")),
        ("Gender", m.get("gender")),
        ("Date of Birth", m.get("dob")),
        ("Language", m.get("language")),
        ("Enrollment Start", enroll_start),
        ("Admission Date", m.get("admission_date")),
    ], cols=2)
    contact = _fields_grid([
        ("Home Phone", m.get("home_tell")),
        ("Cell", m.get("cell")),
        ("Address", m.get("address")),
    ], cols=2)
    insurance = _fields_grid([
        ("Health Plan", m.get("health_plan")),
        ("Member ID", m.get("member_id")),
        ("Medicaid", m.get("medicaid")),
        ("Medicare", m.get("medicare")),
        ("SSN", m.get("ssn")),
        ("PCP", m.get("pcp")),
        ("Hospital", m.get("hospital")),
        ("HHA", m.get("hha")),
        ("Case Manager", m.get("case_manager")),
    ], cols=2)

    if emergency_contacts:
        ec_rows = "".join(
            f'<tr>'
            f'<td width="36%" style="color:{_VALUE}; font-size:12pt;">'
            f'{_esc(ec.get("full_name"))}</td>'
            f'<td style="color:{_VALUE}; font-size:12pt;">{_esc(ec.get("phone"))}</td>'
            f'<td style="color:{_VALUE}; font-size:12pt;">'
            f'{_esc(ec.get("relationship"))}</td>'
            f'</tr>'
            for ec in emergency_contacts
        )
        emergency = (
            f'<table width="100%" cellspacing="0" cellpadding="5">'
            f'<tr>'
            f'<td width="36%" style="color:{_LABEL}; font-size:12pt;"><b>Name</b></td>'
            f'<td style="color:{_LABEL}; font-size:12pt;"><b>Phone</b></td>'
            f'<td style="color:{_LABEL}; font-size:12pt;"><b>Relationship</b></td>'
            f'</tr>{ec_rows}</table>'
        )
    else:
        emergency = (f'<p style="color:{_LABEL}; font-size:12pt;">'
                     f'— No emergency contacts on file —</p>')

    sections = [
        header,
        _section("Identity", identity),
        _section("Contact", contact),
        _section("Insurance / Medical", insurance),
        _section("Emergency Contacts", emergency),
    ]

    # Left-aligned, full-width (the page margins supply the slight frame).
    return (
        f'<html><body>'
        f'<p style="margin:0 0 6px 0; color:{_ACCENT}; font-size:13pt;">'
        f'<b>BSCA &nbsp;·&nbsp; MEMBER PROFILE</b></p>'
        f'{"".join(sections)}'
        f'</body></html>'
    )


def open_profile_print_preview(
    parent,
    member: dict,
    emergency_contacts: list,
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
        member, emergency_contacts, enroll_start,
        include_photo=bool(photo_bytes),
    ))

    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    # A slight, even margin so the sheet looks framed without wasting space.
    printer.setPageMargins(QMarginsF(10, 10, 10, 10),
                           QPageLayout.Unit.Millimeter)

    preview = QPrintPreviewDialog(printer, parent)
    preview.setWindowTitle("Print Member Profile")
    # Wide enough that the full toolbar (incl. the Print button) shows instead
    # of collapsing into an overflow "…" menu.
    preview.resize(1040, 800)
    preview.paintRequested.connect(doc.print)  # PyQt6: print (not print_)
    preview.exec()
