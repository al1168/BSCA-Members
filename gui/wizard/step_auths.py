from datetime import date

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QCheckBox, QPushButton, QGridLayout, QLineEdit, QComboBox,
)
from PyQt6.QtCore import QRegularExpression
from PyQt6.QtGui import QRegularExpressionValidator
from gui.address_autocomplete import DateLineEdit, set_widget_error
from db.members import format_time_live, normalize_time_12h


class TimeLineEdit(QLineEdit):
    """Free-text 12-hour time (AM/PM is a separate dropdown). Type digits and it
    auto-formats to H:MM as you go ('815' -> '8:15'); the field can be cleared
    and retyped. Outlines red on focus-out if the entry isn't a valid time."""

    def __init__(self, default: str = "8:00", parent=None):
        super().__init__(default, parent)
        self.setValidator(
            QRegularExpressionValidator(QRegularExpression(r"[0-9:]*"), self))
        self.setFixedWidth(64)
        self.textEdited.connect(self._on_edited)

    def _on_edited(self):
        new = format_time_live(self.text())
        if new != self.text():
            self.setText(new)                     # format as you type
            self.setCursorPosition(len(new))
        set_widget_error(self, False)

    def focusOutEvent(self, e):
        norm = normalize_time_12h(self.text())
        if norm is not None:
            self.setText(norm)                    # pad '8' -> '8:00' on blur
        set_widget_error(self, bool(self.text().strip()) and norm is None)
        super().focusOutEvent(e)

    def is_valid(self) -> bool:
        return normalize_time_12h(self.text()) is not None


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
            "until this information is filled in. If you start an "
            "authorization, every field of it is required before continuing."
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

        # Dates start empty: an authorization here is an explicit act (the
        # whole step can still be skipped by leaving everything blank).
        self.auth_start = DateLineEdit()
        self.auth_end = DateLineEdit()
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

        # Plan type (MAP/MLTC). The blank first entry is the untouched state
        # that keeps the whole step skippable; once the step is engaged,
        # validate() requires a real choice.
        from db.members import PLAN_TYPES
        self.plan_type = QComboBox()
        self.plan_type.addItems(PLAN_TYPES)
        self.plan_type.currentIndexChanged.connect(
            lambda _i: set_widget_error(self.plan_type, False))
        auth_layout.addRow("Plan Type:", self.plan_type)

        self.auth_number = QLineEdit()
        self.auth_number.setPlaceholderText("Authorization number")
        self.auth_number.textEdited.connect(
            lambda _t: set_widget_error(self.auth_number, False))
        auth_layout.addRow("Auth #:", self.auth_number)

        # ── Transportation (optional) ────────────────────────────
        # A transport auth shares the care auth's dates/days but carries its own
        # number. Filled in here, it's created alongside and linked to the care
        # auth; left blank, no transport auth is created. Days/dates can be
        # adjusted later in the member's Transportation tab.
        title_transport = QLabel("Transportation")
        title_transport.setStyleSheet("font-weight:600; font-size:11px;")
        auth_layout.addRow(title_transport)

        self.transport_number = QLineEdit()
        self.transport_number.setPlaceholderText(
            "Transport auth number (optional)")
        auth_layout.addRow("Transport Auth #:", self.transport_number)

        caption_transport = QLabel("Uses the same dates & days as the authorization.")
        caption_transport.setObjectName("quick_search_hint")
        caption_transport.setWordWrap(True)
        auth_layout.addRow(caption_transport)

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
        row_widget = QWidget()
        hl = QHBoxLayout(row_widget)
        hl.setContentsMargins(0, 0, 0, 0)

        day_combo = QComboBox()
        for num, name in [(1, "Mon"), (2, "Tue"), (3, "Wed"), (4, "Thu"),
                          (5, "Fri"), (6, "Sat"), (7, "Sun")]:
            day_combo.addItem(name, num)
        # Wide enough for the day name plus the dropdown arrow + input padding
        # (60px clipped the last letter, e.g. "Mon" -> "Mor").
        day_combo.setMinimumWidth(90)

        # Free-text time + a separate AM/PM dropdown (defaults 8:00 AM–4:00 PM).
        t_start = TimeLineEdit("8:00")
        ampm_start = QComboBox()
        ampm_start.addItems(["AM", "PM"])
        t_end = TimeLineEdit("4:00")
        ampm_end = QComboBox()
        ampm_end.addItems(["AM", "PM"])
        ampm_end.setCurrentText("PM")

        hl.addWidget(day_combo)
        hl.addWidget(t_start)
        hl.addWidget(ampm_start)
        hl.addWidget(QLabel("–"))
        hl.addWidget(t_end)
        hl.addWidget(ampm_end)
        hl.addStretch()

        self._avail_container.addWidget(row_widget)
        self._avail_rows.append({
            "combo": day_combo, "t_start": t_start, "ampm_start": ampm_start,
            "t_end": t_end, "ampm_end": ampm_end,
        })

    @staticmethod
    def _row_time_24h(field, ampm, default: str) -> str:
        """Convert a row's TimeLineEdit + AM/PM combo to 24-hour 'HH:mm',
        falling back to `default` if the entry isn't a valid time."""
        from db.members import time_12h_to_24h
        norm = normalize_time_12h(field.text())
        if norm is None:
            return default
        try:
            return time_12h_to_24h(norm, ampm.currentText())
        except ValueError:
            return default

    def is_skipped(self) -> bool:
        """The step counts as skipped only when nothing at all was entered —
        typing a date or number without checking days no longer silently
        discards the entry."""
        return (not any(cb.isChecked() for cb in self._day_checks.values())
                and not self.auth_start.text().strip()
                and not self.auth_end.text().strip()
                and not self.auth_number.text().strip()
                and not self.plan_type.currentText())

    def validate(self) -> bool:
        """When the step is engaged, every authorization field is required:
        both dates, at least one day, a plan type, and an auth number. Added
        availability times must always be valid. Flags the bad fields red."""
        ok = True
        if not self.is_skipped():
            ok = self.auth_start.flag_validity(required=True) and ok
            ok = self.auth_end.flag_validity(required=True) and ok
            ok = any(cb.isChecked()
                     for cb in self._day_checks.values()) and ok
            plan_ok = bool(self.plan_type.currentText())
            set_widget_error(self.plan_type, not plan_ok)
            ok = plan_ok and ok
            num_ok = bool(self.auth_number.text().strip())
            set_widget_error(self.auth_number, not num_ok)
            ok = num_ok and ok
        for r in self._avail_rows:
            for field in (r["t_start"], r["t_end"]):
                valid = field.is_valid()
                set_widget_error(field, not valid)
                ok = ok and valid
        return ok

    def collect(self) -> dict:
        from db.members import merge_default_availability

        # Authorization is optional (gated by the day checkboxes).
        auth = None
        if not self.is_skipped():
            auth = {
                "auth_start": self.auth_start.to_pydate(),
                "auth_end": self.auth_end.to_pydate(),
                "auth_days": {n for n, cb in self._day_checks.items()
                              if cb.isChecked()},
                "auth_number": self.auth_number.text().strip(),
                "plan_type": self.plan_type.currentText(),
            }
        # Availability: default Mon–Sun 8a–4p, with any added rows substituting
        # their weekday's default. Times come from the free-text field + AM/PM.
        added = [
            {
                "day_of_week": r["combo"].currentData(),
                "avail_start": self._row_time_24h(r["t_start"], r["ampm_start"], "08:00"),
                "avail_end":   self._row_time_24h(r["t_end"], r["ampm_end"], "16:00"),
                "effective_start_date": date.today(),
                "effective_end_date": None,
            }
            for r in self._avail_rows
        ]
        avail = merge_default_availability(added, date.today())
        # Transportation auth (optional): only when a care auth exists and a
        # transport number was entered. Mirrors the care auth's dates/days.
        transport = None
        if auth is not None:
            num = self.transport_number.text().strip()
            if num:
                transport = {"auth_number": num}
        return {"authorization": auth, "availability_rows": avail,
                "transport_authorization": transport}
