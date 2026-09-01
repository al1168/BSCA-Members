"""Monthly absences report: pick a month and year, get every absence for an
active member that overlaps it — one row per absence, sorted by start date —
as a ruled record sheet. An absence with no end date counts as ongoing."""
import calendar
import os
from datetime import date

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QSpinBox,
    QPushButton, QFileDialog, QMessageBox, QDialogButtonBox,
)


class AbsenceReportDialog(QDialog):
    """Pick a month; save the absences report as a spreadsheet. The absence
    count refreshes live as the month or year changes."""

    def __init__(self, db_path: str, members: list[dict],
                 terminated_ids: set, parent=None, today: date | None = None):
        super().__init__(parent)
        self._db_path = db_path
        self._members = members
        self._terminated = terminated_ids
        self.setWindowTitle("Absences Report")
        self.setMinimumWidth(400)

        today = today or date.today()   # default: this month (reviewing it)

        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel("Absences during:"))
        self._month = QComboBox()
        self._month.addItems(calendar.month_name[1:])
        self._month.setCurrentIndex(today.month - 1)
        self._year = QSpinBox()
        self._year.setRange(2000, 2100)
        self._year.setValue(today.year)
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
        buttons.addWidget(self._btn_save)
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
        import db.members
        from db.export import member_absences_in_month
        absence_rows = db.members.get_all_absences(self._db_path)
        return member_absences_in_month(
            self._members, self._terminated, absence_rows,
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
            f"{n} absence{'s' if n != 1 else ''} in {self._month_label()}")
        self._btn_save.setEnabled(n > 0)

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
            f"Absences {self._month_label()}.xlsx")
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Absences Report", default, "Excel Workbook (*.xlsx)")
        if not path:
            return
        from db.export import write_absence_xlsx
        try:
            write_absence_xlsx(path, rows, self._month_label())
        except PermissionError:
            QMessageBox.critical(self, "Save Failed",
                "The file couldn't be written.\n\nIt may be open in Excel — "
                "close it there and try again.")
            return
        done = QMessageBox(self)
        done.setWindowTitle("Report Saved")
        done.setIcon(QMessageBox.Icon.Information)
        done.setText(f"Saved {len(rows)} absences to:\n{path}")
        open_btn = done.addButton("Open Spreadsheet",
                                  QMessageBox.ButtonRole.AcceptRole)
        done.addButton(QMessageBox.StandardButton.Close)
        done.exec()
        if done.clickedButton() is open_btn:
            os.startfile(path)
