"""Expiring-auths monthly report: pick a month, get every active member whose
coverage ends in it — grouped by health plan — as a spreadsheet or a printout
with a wide blank Notes column for working the renewals by hand."""
import calendar
import html as _html
import os
from datetime import date

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QSpinBox,
    QPushButton, QFileDialog, QMessageBox, QDialogButtonBox,
)
from PyQt6.QtCore import Qt


def build_expiring_report_html(rows: list[dict], month_label: str,
                               generated_on: str) -> str:
    """The printable report: a full-width table (ID, Name, Plan, Expiring
    Date, Notes) where Notes takes ~40% of the page for handwriting. Rows
    arrive already grouped by health plan; the plan cell is bolded on each
    group's first row so the groups read at a glance. Pure — unit-testable."""
    body_rows = []
    prev_plan = object()
    for r in rows:
        plan = r["health_plan"]
        plan_cell = (f"<b>{_html.escape(plan or '—')}</b>"
                     if plan != prev_plan else _html.escape(plan or "—"))
        prev_plan = plan
        body_rows.append(
            "<tr>"
            f'<td align="center">{r["center_id"]}</td>'
            f"<td>{_html.escape(r['name'])}</td>"
            f'<td align="center">{plan_cell}</td>'
            f'<td align="center">{r["end"]:%m/%d/%Y}</td>'
            "<td></td>"
            "</tr>"
        )
    if not body_rows:
        body_rows.append(
            '<tr><td colspan="5" align="center" style="color:#666666;">'
            "No members have authorizations expiring this month.</td></tr>")
    return f"""
    <h2 style="margin-bottom:2px;">Expiring Authorizations — {_html.escape(month_label)}</h2>
    <p style="color:#666666; margin-top:0;">Active members whose coverage ends in
    {_html.escape(month_label)}, grouped by health plan · generated {generated_on}
    · {len(rows)} member{"s" if len(rows) != 1 else ""}</p>
    <table width="100%" border="0.5" cellspacing="0" cellpadding="6"
           style="border-collapse:collapse; font-size:11pt;">
      <tr bgcolor="#eeeeee">
        <th width="10%">ID</th><th width="26%" align="left">Name</th>
        <th width="12%">Health Plan</th><th width="14%">Expiring Date</th>
        <th width="38%" align="left">Notes</th>
      </tr>
      {"".join(body_rows)}
    </table>
    """


def _open_print_preview(parent, html: str) -> None:
    """Print-preview (print or Save-as-PDF), same setup as the member
    profile printout."""
    from PyQt6.QtCore import QMarginsF
    from PyQt6.QtGui import QTextDocument, QPageLayout
    from PyQt6.QtPrintSupport import QPrinter, QPrintPreviewDialog

    doc = QTextDocument()
    doc.setHtml(html)
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setPageMargins(QMarginsF(10, 10, 10, 10),
                           QPageLayout.Unit.Millimeter)
    preview = QPrintPreviewDialog(printer, parent)
    preview.resize(1000, 800)
    preview.paintRequested.connect(
        lambda p: (doc.setPageSize(p.pageRect(
            QPrinter.Unit.DevicePixel).size()), doc.print(p)))
    preview.exec()


class ExpiringReportDialog(QDialog):
    """Pick a month; save the expiring-auths report as a spreadsheet or
    print it. The row count refreshes live as the month changes."""

    def __init__(self, db_path: str, members: list[dict],
                 terminated_ids: set, parent=None, today: date | None = None):
        super().__init__(parent)
        self._db_path = db_path
        self._members = members
        self._terminated = terminated_ids
        self.setWindowTitle("Expiring Auths Report")
        self.setMinimumWidth(420)

        today = today or date.today()
        nxt = date(today.year + (today.month == 12),
                   today.month % 12 + 1, 1)         # default: next month

        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel("Authorizations expiring in:"))
        self._month = QComboBox()
        self._month.addItems(calendar.month_name[1:])
        self._month.setCurrentIndex(nxt.month - 1)
        self._year = QSpinBox()
        self._year.setRange(2000, 2100)
        self._year.setValue(nxt.year)
        self._year.setGroupSeparatorShown(False)
        row.addWidget(self._month)
        row.addWidget(self._year)
        row.addStretch()
        layout.addLayout(row)

        self._count = QLabel("")
        self._count.setStyleSheet("font-weight:600;")
        layout.addWidget(self._count)

        buttons = QHBoxLayout()
        self._btn_save = QPushButton("Save Spreadsheet…")
        self._btn_save.setObjectName("btn_row_add")
        self._btn_save.clicked.connect(self._save)
        self._btn_print = QPushButton("Print…")
        self._btn_print.clicked.connect(self._print)
        buttons.addWidget(self._btn_save)
        buttons.addWidget(self._btn_print)
        buttons.addStretch()
        layout.addLayout(buttons)

        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        layout.addWidget(close)

        self._month.currentIndexChanged.connect(self._refresh_count)
        self._year.valueChanged.connect(self._refresh_count)
        self._refresh_count()

    # ── data ────────────────────────────────────────────────────────────
    def _rows(self) -> list[dict]:
        from db.members import get_member_auth_ends
        from db.export import members_expiring_in_month
        auth_rows = get_member_auth_ends(self._db_path)
        return members_expiring_in_month(
            self._members, self._terminated, auth_rows,
            self._year.value(), self._month.currentIndex() + 1)

    def _month_label(self) -> str:
        return f"{self._month.currentText()} {self._year.value()}"

    def _refresh_count(self):
        try:
            n = len(self._rows())
        except Exception as exc:
            from gui.errors import show_db_error
            show_db_error(self, exc)
            return
        self._count.setText(
            f"{n} member{'s' if n != 1 else ''} with coverage ending in "
            f"{self._month_label()}")
        self._btn_save.setEnabled(n > 0)
        self._btn_print.setEnabled(n > 0)

    # ── actions ─────────────────────────────────────────────────────────
    def _save(self):
        try:
            rows = self._rows()
        except Exception as exc:
            from gui.errors import show_db_error
            show_db_error(self, exc)
            return
        default = os.path.join(
            os.path.expanduser("~/Documents"),
            f"Expiring Auths {self._month_label()}.xlsx")
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Expiring Auths Report", default,
            "Excel Workbook (*.xlsx)")
        if not path:
            return
        from db.export import write_expiring_xlsx
        try:
            write_expiring_xlsx(path, rows, self._month_label())
        except PermissionError:
            QMessageBox.critical(self, "Save Failed",
                "The file couldn't be written.\n\nIt may be open in Excel — "
                "close it there and try again.")
            return
        done = QMessageBox(self)
        done.setWindowTitle("Report Saved")
        done.setIcon(QMessageBox.Icon.Information)
        done.setText(f"Saved {len(rows)} members to:\n{path}")
        open_btn = done.addButton("Open Spreadsheet",
                                  QMessageBox.ButtonRole.AcceptRole)
        done.addButton(QMessageBox.StandardButton.Close)
        done.exec()
        if done.clickedButton() is open_btn:
            os.startfile(path)

    def _print(self):
        try:
            rows = self._rows()
        except Exception as exc:
            from gui.errors import show_db_error
            show_db_error(self, exc)
            return
        html = build_expiring_report_html(
            rows, self._month_label(), f"{date.today():%m/%d/%Y}")
        _open_print_preview(self, html)
