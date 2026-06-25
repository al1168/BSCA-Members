from datetime import date

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QCheckBox, QTimeEdit, QPushButton, QAbstractSpinBox, QGridLayout,
)
from PyQt6.QtCore import QTime
from gui.address_autocomplete import DateLineEdit


class StepAuths(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._avail_rows: list[dict] = []
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)

        warning = QLabel(
            "⚠  This step is optional. You can skip it and add authorizations "
            "and availability later, but the member won't appear on schedules "
            "until this information is filled in."
        )
        warning.setWordWrap(True)
        warning.setObjectName("wizard_warning")
        layout.addWidget(warning)

        panels = QHBoxLayout()

        # ── Authorization sub-panel ──────────────────────────────
        auth_box = QWidget()
        auth_box.setObjectName("wizard_panel")
        auth_layout = QFormLayout(auth_box)
        auth_layout.setContentsMargins(14, 14, 14, 14)
        auth_layout.setSpacing(10)

        title_auth = QLabel("Authorization")
        title_auth.setStyleSheet("font-weight:600; font-size:11px;")
        auth_layout.addRow(title_auth)

        today = date.today()
        self.auth_start = DateLineEdit()
        self.auth_start.set_pydate(today)
        self.auth_end = DateLineEdit()
        self.auth_end.set_pydate(today.replace(year=today.year + 1))
        auth_layout.addRow("Auth Start:", self.auth_start)
        auth_layout.addRow("Auth End:", self.auth_end)

        days_widget = QWidget()
        days_grid = QGridLayout(days_widget)
        days_grid.setContentsMargins(0, 0, 0, 0)
        days_grid.setHorizontalSpacing(8)
        days_grid.setVerticalSpacing(4)
        self._day_checks: dict[int, QCheckBox] = {}
        day_list = [(1, "Mon"), (2, "Tue"), (3, "Wed"), (4, "Thu"),
                    (5, "Fri"), (6, "Sat"), (7, "Sun")]
        for i, (num, lbl) in enumerate(day_list):
            cb = QCheckBox(lbl)
            self._day_checks[num] = cb
            days_grid.addWidget(cb, i // 4, i % 4)   # 4 per row -> Mon-Thu / Fri-Sun
        auth_layout.addRow("Days:", days_widget)

        panels.addWidget(auth_box)

        # ── Availability sub-panel ───────────────────────────────
        avail_box = QWidget()
        avail_box.setObjectName("wizard_panel")
        avail_layout = QVBoxLayout(avail_box)
        avail_layout.setContentsMargins(14, 14, 14, 14)

        title_avail = QLabel("Time Slot Availability")
        title_avail.setStyleSheet("font-weight:600; font-size:11px;")
        avail_layout.addWidget(title_avail)

        self._avail_container = QVBoxLayout()
        avail_layout.addLayout(self._avail_container)

        btn_add_day = QPushButton("+ Add day")
        btn_add_day.setFlat(True)
        btn_add_day.setStyleSheet("color: #5b7cf4; font-size:10px; text-align:left;")
        btn_add_day.clicked.connect(self._add_avail_row)
        avail_layout.addWidget(btn_add_day)
        avail_layout.addStretch()

        panels.addWidget(avail_box)
        layout.addLayout(panels)
        layout.addStretch()

    def _add_avail_row(self):
        from PyQt6.QtWidgets import QComboBox
        row_widget = QWidget()
        hl = QHBoxLayout(row_widget)
        hl.setContentsMargins(0, 0, 0, 0)

        day_combo = QComboBox()
        for num, name in [(1, "Mon"), (2, "Tue"), (3, "Wed"), (4, "Thu"),
                          (5, "Fri"), (6, "Sat"), (7, "Sun")]:
            day_combo.addItem(name, num)
        day_combo.setFixedWidth(60)

        t_start = QTimeEdit(QTime(8, 0))
        t_end = QTimeEdit(QTime(16, 0))
        for te in (t_start, t_end):
            # Drop the native up/down spin arrows (they clash with the theme);
            # the time is typed or adjusted with the keyboard.
            te.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
            te.setFixedWidth(88)

        hl.addWidget(day_combo)
        hl.addWidget(t_start)
        hl.addWidget(QLabel("–"))
        hl.addWidget(t_end)
        hl.addStretch()

        self._avail_container.addWidget(row_widget)
        self._avail_rows.append({
            "combo": day_combo, "t_start": t_start, "t_end": t_end,
        })

    def is_skipped(self) -> bool:
        return not any(cb.isChecked() for cb in self._day_checks.values())

    def validate(self) -> bool:
        """When not skipped, the auth dates must be valid. Flags bad fields."""
        if self.is_skipped():
            return True
        ok = self.auth_start.flag_validity(required=True)
        ok = self.auth_end.flag_validity(required=True) and ok
        return ok

    def collect(self) -> dict:
        if self.is_skipped():
            return {"authorization": None, "availability_rows": []}

        selected_days = {n for n, cb in self._day_checks.items() if cb.isChecked()}
        auth = {
            "auth_start": self.auth_start.to_pydate(),
            "auth_end": self.auth_end.to_pydate(),
            "auth_days": selected_days,
        }
        avail = [
            {
                "day_of_week": r["combo"].currentData(),
                "avail_start": r["t_start"].time().toString("HH:mm"),
                "avail_end":   r["t_end"].time().toString("HH:mm"),
                "effective_start_date": date.today(),
                "effective_end_date": None,
            }
            for r in self._avail_rows
        ]
        return {"authorization": auth, "availability_rows": avail}
