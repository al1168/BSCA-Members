"""Member roster export: one spreadsheet row per member, joining Contacts,
the latest Enrollment, today's active Authorization, and the first
EmergencyContact on file.

Four bulk queries (not per-member lookups) keep the export fast over a
network-share database; assembling rows is pure Python so it's unit-testable.
"""
from datetime import date, datetime

from db.members import (
    _read_connection, _drop_read_connection, _access_date,
    format_phone, format_ssn, format_medicaid, format_medicare,
    decode_auth_days, parse_flexible_date,
)

COLUMNS = [
    "Center Id", "Last Name", "First Name", "Chinese Name", "DOB",
    "Health Plan", "Member ID", "Medicaid", "Medicare", "SSN", "Language",
    "Case Manager", "Home Tell", "Cell", "Address", "PCP", "Hospital",
    "Notes", "Gender", "Long Lat", "HHA",
    "Enrollment Date",
    "Auth Days", "Auth Start", "Auth End",
    "Emergency_Full Name", "Emergency_Phone Number", "Emergency_Relationship",
]

_CONTACTS_QUERY = (
    "SELECT [Center ID],[Last Name],[First Name],[Chinese Name],[DOB],"
    "[Health Plan],[Member ID],[Medicaid],[Medicare],[SSN],[Language],"
    "[Case Manager],[Home Tell],[Cell],[Address],[PCP],[Hospital],[Notes],"
    "[Gender],[Long Lat],[HHA] FROM [Contacts] "
    "ORDER BY [Center ID]"
)
_ENROLLMENTS_QUERY = "SELECT [Center ID],[start_date] FROM [Enrollment]"
_AUTHS_QUERY = ("SELECT [Center ID],[auth_start],[auth_end],[auth_days] "
                "FROM [Authorization]")
_EMERGENCY_QUERY = ("SELECT [ID],[Center ID],[Full Name],[Phone Number],"
                    "[Relationship] FROM [EmergencyContact]")

def _fetch_all(db_path: str, sql: str, _retry: bool = True) -> list:
    """One bulk SELECT over the cached read connection, with the same
    stale-connection retry as get_member_context."""
    import pyodbc
    conn = _read_connection(db_path)
    try:
        c = conn.cursor()
        c.execute(sql)
        return c.fetchall()
    except pyodbc.Error:
        _drop_read_connection(db_path)
        if _retry:
            return _fetch_all(db_path, sql, _retry=False)
        raise


def format_auth_days_dotted(auth_days) -> str:
    """Stored '1,3,5' -> '1.3.5' (day numbers, period-separated, sorted)."""
    days = decode_auth_days(auth_days or "")
    return ".".join(str(d) for d in sorted(days))


def pick_active_auth(auths: list[tuple], today) -> tuple | None:
    """The (start, end, days) auth in effect today: auth_start <= today <=
    auth_end, same rule as the Auths tab's 'active' status pill (a missing
    start or end doesn't disqualify). Latest start wins; None when nothing
    is active — the spreadsheet shows blank cells so lapsed coverage is
    easy to filter."""
    active = []
    for start, end, days in auths:
        start_d, end_d = _access_date(start), _access_date(end)
        if start_d is not None and start_d > today:
            continue
        if end_d is not None and end_d < today:
            continue
        active.append((start_d, end_d, days))
    if not active:
        return None
    return max(active, key=lambda a: (a[0] or date.min))


def build_export_rows(contacts, enrollments, auths, emergency, today) -> list[list]:
    """Assemble spreadsheet rows (matching COLUMNS) from raw table rows.

    contacts:    rows in _CONTACTS_QUERY order (drives row order)
    enrollments: (center_id, start_date) — latest start becomes Enrollment Date
    auths:       (center_id, auth_start, auth_end, auth_days)
    emergency:   (id, center_id, full_name, phone, relationship) — the row
                 with the lowest id (first on file) is used
    Pure (no DB), so it is unit-testable.
    """
    enroll_by_member: dict[int, date] = {}
    for cid, start in enrollments:
        if cid is None or start is None:
            continue
        start = _access_date(start)
        cid = int(cid)
        if cid not in enroll_by_member or start > enroll_by_member[cid]:
            enroll_by_member[cid] = start

    auths_by_member: dict[int, list] = {}
    for cid, start, end, days in auths:
        if cid is None:
            continue
        auths_by_member.setdefault(int(cid), []).append((start, end, days))

    emergency_by_member: dict[int, tuple] = {}
    for rec_id, cid, name, phone, rel in emergency:
        if cid is None:
            continue
        cid = int(cid)
        current = emergency_by_member.get(cid)
        if current is None or rec_id < current[0]:
            emergency_by_member[cid] = (rec_id, name, phone, rel)

    rows = []
    for r in contacts:
        if r[0] is None:            # skip Contacts rows with no Center ID
            continue
        cid = int(r[0])
        active = pick_active_auth(auths_by_member.get(cid, []), today)
        em = emergency_by_member.get(cid)
        rows.append([
            cid,
            r[1] or "", r[2] or "", r[3] or "",
            # DOB as a real date cell (MM/DD/YYYY) even when the column holds
            # text like '8/23/1953'; unparseable text passes through visibly.
            parse_flexible_date(r[4]) or (r[4] or ""),
            r[5] or "", r[6] or "",
            format_medicaid(r[7]), format_medicare(r[8]), format_ssn(r[9]),
            r[10] or "", r[11] or "",
            format_phone(r[12]), format_phone(r[13]),
            r[14] or "", r[15] or "", r[16] or "", r[17] or "",
            r[18] or "", r[19] or "", r[20] or "",
            enroll_by_member.get(cid),
            format_auth_days_dotted(active[2]) if active else "",
            active[0] if active else None,
            active[1] if active else None,
            (em[1] or "") if em else "",
            format_phone(em[2]) if em else "",
            (em[3] or "") if em else "",
        ])
    return rows


def write_members_xlsx(path: str, rows: list[list]) -> None:
    """Write COLUMNS + rows to `path`: bold frozen header, MM/DD/YYYY date
    cells, and column widths sized to their content."""
    from openpyxl import Workbook
    from openpyxl.styles import Font
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "Members"
    ws.append(COLUMNS)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    ws.freeze_panes = "A2"

    for row in rows:
        ws.append(row)
        for cell in ws[ws.max_row]:
            if isinstance(cell.value, (date, datetime)):
                cell.number_format = "MM/DD/YYYY"

    widths = {}
    for row in [COLUMNS] + rows:
        for i, v in enumerate(row, start=1):
            text = f"{v:%m/%d/%Y}" if isinstance(v, (date, datetime)) else str(v or "")
            # Notes can be paragraphs; cap so one memo doesn't blow up a column.
            widths[i] = min(max(widths.get(i, 0), len(text) + 2), 40)
    for i, w in widths.items():
        ws.column_dimensions[get_column_letter(i)].width = w

    wb.save(path)


EXPIRING_COLUMNS = ["Center Id", "Name", "Health Plan", "Expiring Date", "Notes"]


def members_expiring_in_month(members, terminated_ids, auth_rows,
                              year: int, month: int) -> list[dict]:
    """Active members whose coverage ends inside the given month, for the
    expiring-auths report.

    A member's coverage end is the latest auth_end across their auths — the
    same rule as the notification bell — so adding a renewal that pushes the
    end past the month drops them from the report. Rows are grouped by
    health plan (then soonest end, then name) so one continuous table keeps
    each plan's members together. Pure (no DB), so it is unit-testable.
    """
    latest: dict[int, date] = {}
    for cid, end in auth_rows:
        if cid is None or end is None:
            continue
        cid = int(cid)
        end = end.date() if isinstance(end, datetime) else end
        if cid not in latest or end > latest[cid]:
            latest[cid] = end
    rows = []
    for m in members:
        cid = m["center_id"]
        if cid in terminated_ids:
            continue
        end = latest.get(cid)
        if end is None or (end.year, end.month) != (year, month):
            continue
        rows.append({
            "center_id": cid,
            "name": f"{m.get('last_name', '')}, {m.get('first_name', '')}",
            "health_plan": m.get("health_plan") or "",
            "end": end,
        })
    rows.sort(key=lambda r: (r["health_plan"].lower(), r["end"],
                             r["name"].lower()))
    return rows


def write_expiring_xlsx(path: str, rows: list[dict], month_label: str) -> None:
    """Write the expiring-auths report as a printable record sheet: every
    cell ruled with borders (including the empty Notes boxes, so it can be
    filled in by hand), shaded header, roomy row heights, and page setup
    that fits all five columns to the sheet with the header repeating on
    each printed page."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    thin = Side(style="thin", color="000000")
    grid = Border(left=thin, right=thin, top=thin, bottom=thin)
    header_fill = PatternFill("solid", fgColor="E8E8E8")
    centered = Alignment(horizontal="center", vertical="center")
    vcenter = Alignment(vertical="center")

    wb = Workbook()
    ws = wb.active
    ws.title = f"Expiring {month_label}"[:31]
    ws.append(EXPIRING_COLUMNS)
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.border = grid
        cell.fill = header_fill
        cell.alignment = centered
    ws.row_dimensions[1].height = 20
    ws.freeze_panes = "A2"

    for r in rows:
        ws.append([r["center_id"], r["name"], r["health_plan"], r["end"], ""])
        row_i = ws.max_row
        ws.row_dimensions[row_i].height = 24      # room to write in Notes
        for col in range(1, len(EXPIRING_COLUMNS) + 1):
            cell = ws.cell(row=row_i, column=col)
            cell.border = grid
            cell.alignment = centered if col in (1, 3, 4) else vcenter
        ws.cell(row=row_i, column=4).number_format = "MM/DD/YYYY"

    for i, width in enumerate((10, 26, 12, 13, 44), start=1):
        ws.column_dimensions[get_column_letter(i)].width = width

    # Print like a form: all columns on one page wide, header row repeated.
    ws.print_title_rows = "1:1"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    wb.save(path)


def export_members_xlsx(db_path: str, out_path: str, today=None) -> int:
    """Query, assemble, and write the roster. Returns the number of rows."""
    today = today or date.today()
    rows = build_export_rows(
        _fetch_all(db_path, _CONTACTS_QUERY),
        _fetch_all(db_path, _ENROLLMENTS_QUERY),
        _fetch_all(db_path, _AUTHS_QUERY),
        _fetch_all(db_path, _EMERGENCY_QUERY),
        today,
    )
    write_members_xlsx(out_path, rows)
    return len(rows)
