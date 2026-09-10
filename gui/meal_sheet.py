"""Monthly meal sheet: pick a month and year, save a blank workbook — three
identical sheets (breakfast, meal ticket, lunch) — listing every member
enrolled and authorized at some point in that month, one column per day,
day cells shaded by whether the member is authorized that weekday."""
import calendar
import os
from datetime import date

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QSpinBox,
    QPushButton, QFileDialog, QMessageBox, QDialogButtonBox,
)


class MealSheetDialog(QDialog):
    """Pick a month; save the meal sheet as a spreadsheet. The member count
    refreshes live as the month or year changes. The bulk DB reads happen
    once, the first time a count is needed."""

    def __init__(self, db_path: str, members: list[dict], parent=None,
                 today: date | None = None, alt_ids_unlocked: bool = False):
        super().__init__(parent)
        self._db_path = db_path
        self._members = members
        self._alt_ids_unlocked = alt_ids_unlocked
        self._cached_inputs = None
        self.setWindowTitle("Meal Sheet")
        self.setMinimumWidth(400)

        today = today or date.today()   # default: this month

        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel("Meal sheet for:"))
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
    def _inputs(self) -> dict:
        if self._cached_inputs is None:
            import db.export
            self._cached_inputs = db.export.load_meal_sheet_inputs(
                self._db_path)
        return self._cached_inputs

    def _year_month(self) -> tuple[int, int]:
        return self._year.value(), self._month.currentIndex() + 1

    def _rows(self) -> list[dict]:
        from db.export import members_for_meal_sheet
        inputs = self._inputs()
        year, month = self._year_month()
        return members_for_meal_sheet(
            self._members, inputs["groups"], inputs["enrollments"],
            inputs["auths"], year, month, self._alt_ids_unlocked)

    def _month_label(self) -> str:
        return f"{self._month.currentText()} {self._year.value()}"

    def _refresh_count(self):
        try:
            n = len(self._rows())
        except Exception as exc:
            from gui.errors import show_db_error
            self._btn_save.setEnabled(False)
            show_db_error(self, exc)
            return
        self._count.setText(
            f"{n} member{'s' if n != 1 else ''} in {self._month_label()}")
        self._btn_save.setEnabled(n > 0)

    # ── actions ─────────────────────────────────────────────────────────
    def _save(self):
        from db.export import closed_days_in_month, write_meal_sheet_xlsx
        try:
            rows = self._rows()
            inputs = self._inputs()
        except Exception as exc:
            from gui.errors import show_db_error
            show_db_error(self, exc)
            return
        default = os.path.join(
            os.path.expanduser("~/Documents"),
            f"Meal Sheet {self._month_label()}.xlsx")
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Meal Sheet", default, "Excel Workbook (*.xlsx)")
        if not path:
            return
        year, month = self._year_month()
        closed = closed_days_in_month(year, month, inputs["holidays"],
                                      inputs["operating_days"])
        try:
            write_meal_sheet_xlsx(path, rows, year, month, closed)
        except PermissionError:
            QMessageBox.critical(self, "Save Failed",
                "The file couldn't be written.\n\nIt may be open in Excel — "
                "close it there and try again.")
            return
        done = QMessageBox(self)
        done.setWindowTitle("Meal Sheet Saved")
        done.setIcon(QMessageBox.Icon.Information)
        done.setText(f"Saved {len(rows)} members to:\n{path}")
        open_btn = done.addButton("Open Spreadsheet",
                                  QMessageBox.ButtonRole.AcceptRole)
        done.addButton(QMessageBox.StandardButton.Close)
        done.exec()
        if done.clickedButton() is open_btn:
            os.startfile(path)
