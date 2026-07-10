"""Expiring-auths monthly report: pick a month and health plans, get every
active member whose coverage ends in it — grouped by plan — as a spreadsheet
with a wide blank Notes column. Printing happens from Excel, which renders
the ruled table correctly."""
import calendar
import os
from datetime import date

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QComboBox,
    QSpinBox, QCheckBox, QPushButton, QFileDialog, QMessageBox,
    QDialogButtonBox,
)
from PyQt6.QtCore import Qt


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

        # Health-plan filter: one checkbox per plan that appears among the
        # active members (all on by default), so a report can be run for a
        # single plan's renewals.
        plans_row = QHBoxLayout()
        plans_row.addWidget(QLabel("Health plans:"))
        btn_all = QPushButton("All")
        btn_none = QPushButton("None")
        for b in (btn_all, btn_none):
            b.setFlat(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet("font-size:11px; padding:1px 8px;")
        btn_all.clicked.connect(lambda: self._set_all_plans(True))
        btn_none.clicked.connect(lambda: self._set_all_plans(False))
        plans_row.addWidget(btn_all)
        plans_row.addWidget(btn_none)
        plans_row.addStretch()
        layout.addLayout(plans_row)

        plans = sorted(
            {(m.get("health_plan") or "") for m in members
             if m["center_id"] not in terminated_ids},
            key=lambda p: (p == "", p))          # blanks last
        self._plan_checks: dict[str, QCheckBox] = {}
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        for i, plan in enumerate(plans):
            cb = QCheckBox(plan if plan else "(No plan)")
            cb.setChecked(True)
            cb.toggled.connect(self._refresh_count)
            self._plan_checks[plan] = cb
            grid.addWidget(cb, i // 4, i % 4)
        layout.addLayout(grid)

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
    def _set_all_plans(self, checked: bool):
        for cb in self._plan_checks.values():
            cb.blockSignals(True)
            cb.setChecked(checked)
            cb.blockSignals(False)
        self._refresh_count()

    def _selected_plans(self) -> set:
        return {plan for plan, cb in self._plan_checks.items()
                if cb.isChecked()}

    def _rows(self) -> list[dict]:
        from db.members import get_member_auth_ends
        from db.export import members_expiring_in_month
        auth_rows = get_member_auth_ends(self._db_path)
        rows = members_expiring_in_month(
            self._members, self._terminated, auth_rows,
            self._year.value(), self._month.currentIndex() + 1)
        plans = self._selected_plans()
        return [r for r in rows if (r["health_plan"] or "") in plans]

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
