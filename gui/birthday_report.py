"""Monthly birthdays report: pick a month, get every active member born in
it — sorted by day — as a ruled record sheet with an empty Sign column."""
import calendar
import os
from datetime import date

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QFileDialog, QMessageBox, QDialogButtonBox,
)


class BirthdayReportDialog(QDialog):
    """Pick a month; save the birthdays report as a spreadsheet. The member
    count refreshes live as the month changes."""

    def __init__(self, members: list[dict], terminated_ids: set,
                 parent=None, today: date | None = None):
        super().__init__(parent)
        self._members = members
        self._terminated = terminated_ids
        self.setWindowTitle("Birthdays Report")
        self.setMinimumWidth(380)
        today = today or date.today()

        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel("Birthdays in:"))
        self._month = QComboBox()
        self._month.addItems(calendar.month_name[1:])
        self._month.setCurrentIndex(today.month - 1)   # default: this month
        row.addWidget(self._month)
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
        self._refresh_count()

    def _rows(self) -> list[dict]:
        from db.export import members_with_birthday_in_month
        return members_with_birthday_in_month(
            self._members, self._terminated, self._month.currentIndex() + 1)

    def _refresh_count(self):
        n = len(self._rows())
        self._count.setText(
            f"{n} member{'s' if n != 1 else ''} with a "
            f"{self._month.currentText()} birthday")
        self._btn_save.setEnabled(n > 0)

    def _save(self):
        rows = self._rows()
        default = os.path.join(
            os.path.expanduser("~/Documents"),
            f"Birthdays {self._month.currentText()}.xlsx")
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Birthdays Report", default, "Excel Workbook (*.xlsx)")
        if not path:
            return
        from db.export import write_birthday_xlsx
        try:
            write_birthday_xlsx(path, rows, self._month.currentText())
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
