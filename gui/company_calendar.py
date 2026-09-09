"""Company Calendar dialog: company holidays (add / delete, written
immediately) and the weekly operating hours (seven rows — Open
checkbox plus opening / closing time — saved together).

Reads and writes go through db.company_calendar; the tables themselves
are created by the BSCA Setup chain.
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget,
)

import crash_log
from db import company_calendar as cal
from gui.address_autocomplete import DateLineEdit


class _TimeEntry(QWidget):
    """'h:mm' box + AM/PM combo, the app's usual 12-hour time entry."""

    def __init__(self, hhmm: str, on_change, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("h:mm")
        self.edit.setFixedWidth(64)
        self.period = QComboBox()
        self.period.addItems(["AM", "PM"])
        layout.addWidget(self.edit)
        layout.addWidget(self.period)
        self.set_hhmm(hhmm)
        self.edit.textEdited.connect(self._live_format)
        self.edit.textEdited.connect(lambda _t: on_change())
        self.period.currentIndexChanged.connect(lambda _i: on_change())

    def _live_format(self, text: str) -> None:
        from db.members import format_time_live
        formatted = format_time_live(text)
        if formatted != text:
            self.edit.setText(formatted)

    def set_hhmm(self, hhmm: str) -> None:
        text, period = cal.hhmm_to_12h(hhmm)
        self.edit.setText(text)
        self.period.setCurrentText(period)

    def hhmm(self):
        """24-hour 'HH:MM', or None when the text isn't a valid time."""
        from db.members import time_12h_to_24h
        try:
            return time_12h_to_24h(self.edit.text(), self.period.currentText())
        except ValueError:
            return None


def _build_discard_box(parent):
    """The "unsaved hours" confirmation, as (box, discard_btn, keep_btn).

    Built apart from exec() so the default button can be asserted in a test:
    Qt makes the first button added the default, so Enter would discard the
    staff member's edits unless "Keep Editing" is set as the default.
    """
    box = QMessageBox(parent)
    box.setWindowTitle("Unsaved Hours")
    box.setIcon(QMessageBox.Icon.Warning)
    box.setText("Discard unsaved operating hours?")
    discard_btn = box.addButton("Discard",
                                QMessageBox.ButtonRole.DestructiveRole)
    keep_btn = box.addButton("Keep Editing",
                             QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(keep_btn)
    box.setEscapeButton(keep_btn)
    return box, discard_btn, keep_btn


class CompanyCalendarDialog(QDialog):
    """Holidays (written as soon as staff add or delete one) and the weekly
    operating hours (edited as a set, then saved together)."""

    def __init__(self, db_path: str, parent=None):
        super().__init__(parent)
        self._db_path = db_path
        self._dirty = False
        self._loading = False
        # A failed read must not be mistaken for "no holidays" or "closed all
        # week": until a load succeeds the matching editor stays locked, so a
        # Save can never overwrite rows we didn't manage to read.
        self._holidays_loaded = False
        self._hours_loaded = False
        # Against a database missing both tables the two loaders would stack
        # two identical modal errors; one is enough to explain the problem.
        self._db_error_shown = False
        self.setWindowTitle("Company Calendar")
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        self._holidays_group = self._build_holidays_group()
        self._hours_group = self._build_hours_group()
        layout.addWidget(self._holidays_group)
        layout.addWidget(self._hours_group)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        layout.addWidget(close)

        self._load_holidays()
        self._load_hours()

    def _report_load_error(self, exc: BaseException) -> None:
        """Report the first failed read only. The two loaders run back to back
        at open time, so on a database without the calendar tables both fail
        for the same reason and a second identical dialog only adds clicks.
        Saves and deletes still report every failure."""
        if self._db_error_shown:
            return
        self._db_error_shown = True
        from gui.errors import show_db_error
        show_db_error(self, exc)

    # -- holidays ------------------------------------------------------
    def _build_holidays_group(self) -> QGroupBox:
        group = QGroupBox("Holidays")
        v = QVBoxLayout(group)
        self._holidays_help = QLabel(
            "Days the center is closed for everyone. "
            "The scheduler leaves these days blank.")
        self._holidays_help.setWordWrap(True)
        v.addWidget(self._holidays_help)

        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["Holiday", "Date"])
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.itemSelectionChanged.connect(self._refresh_delete_enabled)
        v.addWidget(self._table)

        add_row = QHBoxLayout()
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Holiday name")
        self._date_edit = DateLineEdit()
        self._date_edit.setFixedWidth(110)
        self._btn_add = QPushButton("Add")
        self._btn_add.setObjectName("btn_row_add")
        self._btn_add.setEnabled(False)
        self._btn_add.clicked.connect(self._add_holiday)
        self._btn_delete = QPushButton("Delete")
        self._btn_delete.setObjectName("btn_row_delete")
        self._btn_delete.setEnabled(False)
        self._btn_delete.clicked.connect(self._delete_holiday)
        add_row.addWidget(self._name_edit)
        add_row.addWidget(self._date_edit)
        add_row.addWidget(self._btn_add)
        add_row.addStretch()
        add_row.addWidget(self._btn_delete)
        v.addLayout(add_row)

        self._name_edit.textChanged.connect(self._refresh_add_enabled)
        self._date_edit.textChanged.connect(self._refresh_add_enabled)
        return group

    def _load_holidays(self) -> None:
        try:
            rows = cal.get_holidays(self._db_path)
        except Exception as exc:
            self._report_load_error(exc)
            self._lock_holidays()
            return
        self._holidays_loaded = True
        self._table.setEnabled(True)
        self._name_edit.setEnabled(True)
        self._date_edit.setEnabled(True)
        self._table.setRowCount(0)
        for row in rows:
            r = self._table.rowCount()
            self._table.insertRow(r)
            name_item = QTableWidgetItem(row["name"])
            name_item.setData(Qt.ItemDataRole.UserRole, row["id"])
            date_item = QTableWidgetItem(row["date"].strftime("%m/%d/%Y"))
            date_item.setToolTip(row["date"].strftime("%A"))
            self._table.setItem(r, 0, name_item)
            self._table.setItem(r, 1, date_item)
        self._refresh_delete_enabled()

    def _lock_holidays(self) -> None:
        """Holidays couldn't be read: no adding or deleting in this dialog."""
        self._holidays_loaded = False
        self._table.setRowCount(0)
        self._table.setEnabled(False)
        self._name_edit.setEnabled(False)
        self._date_edit.setEnabled(False)
        self._btn_add.setEnabled(False)
        self._btn_delete.setEnabled(False)
        self._holidays_help.setText(
            "Couldn't read the holidays. Close this window and open it again.")

    def _refresh_add_enabled(self) -> None:
        ok = (self._holidays_loaded
              and bool(self._name_edit.text().strip())
              and self._date_edit.to_pydate() is not None)
        self._btn_add.setEnabled(ok)

    def _refresh_delete_enabled(self) -> None:
        self._btn_delete.setEnabled(self._holidays_loaded
                                    and self._table.currentRow() >= 0
                                    and bool(self._table.selectedItems()))

    def _add_holiday(self) -> None:
        name = self._name_edit.text().strip()
        day = self._date_edit.to_pydate()
        if not name or day is None:
            return
        try:
            cal.insert_holiday(name, day, self._db_path)
        except Exception as exc:
            from gui.errors import show_db_error
            show_db_error(self, exc)
            return
        crash_log.log_warning(f"Holiday added: {name} {day.isoformat()}")
        self._name_edit.clear()
        self._date_edit.clear()
        self._load_holidays()
        # Select the row we just added (newest row for that name+date).
        stamp = day.strftime("%m/%d/%Y")
        for r in range(self._table.rowCount() - 1, -1, -1):
            if (self._table.item(r, 0).text() == name
                    and self._table.item(r, 1).text() == stamp):
                self._table.selectRow(r)
                break

    def _delete_holiday(self) -> None:
        r = self._table.currentRow()
        if r < 0:
            return
        record_id = self._table.item(r, 0).data(Qt.ItemDataRole.UserRole)
        name = self._table.item(r, 0).text()
        when = self._table.item(r, 1).text()
        answer = QMessageBox.question(
            self, "Delete Holiday",
            f"Delete the holiday “{name}” on {when}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            cal.delete_holiday(record_id, self._db_path)
        except Exception as exc:
            from gui.errors import show_db_error
            show_db_error(self, exc)
            return
        crash_log.log_warning(
            f"Holiday deleted: {name} {when} (id {record_id})")
        self._load_holidays()

    # -- operating days ------------------------------------------------
    def _build_hours_group(self) -> QGroupBox:
        group = QGroupBox("Operating Days")
        v = QVBoxLayout(group)
        self._hours_help = QLabel(
            "Uncheck a day to close the center that day. "
            "Opening and closing times are the earliest "
            "Time-In and latest Time-Out on the schedule.")
        self._hours_help.setWordWrap(True)
        v.addWidget(self._hours_help)
        grid = QGridLayout()
        grid.addWidget(QLabel("Open"), 0, 0)
        grid.addWidget(QLabel("Opens"), 0, 1)
        grid.addWidget(QLabel("Closes"), 0, 2)
        self._day_rows: dict[int, tuple] = {}
        for dow, name in enumerate(cal.DAY_NAMES, start=1):
            check = QCheckBox(name)
            opening = _TimeEntry(cal.DEFAULT_OPENING, self._mark_dirty)
            closing = _TimeEntry(cal.DEFAULT_CLOSING, self._mark_dirty)
            check.toggled.connect(
                lambda on, o=opening, c=closing: self._toggle_day(on, o, c))
            grid.addWidget(check, dow, 0)
            grid.addWidget(opening, dow, 1)
            grid.addWidget(closing, dow, 2)
            self._day_rows[dow] = (check, opening, closing)
        grid.setColumnStretch(3, 1)
        v.addLayout(grid)

        buttons = QHBoxLayout()
        self._btn_save = QPushButton("Save Hours")
        self._btn_save.setObjectName("btn_row_add")
        self._btn_save.setEnabled(False)
        self._btn_save.clicked.connect(self._save_hours)
        buttons.addWidget(self._btn_save)
        buttons.addStretch()
        v.addLayout(buttons)
        return group

    def _toggle_day(self, on: bool, opening, closing) -> None:
        opening.setEnabled(on)
        closing.setEnabled(on)
        self._mark_dirty()

    def _mark_dirty(self) -> None:
        if self._loading or not self._hours_loaded:
            return
        self._dirty = True
        self._btn_save.setEnabled(True)

    def _load_hours(self) -> None:
        try:
            days = cal.get_operating_days(self._db_path)
        except Exception as exc:
            self._report_load_error(exc)
            self._lock_hours()
            return
        self._hours_loaded = True
        self._hours_group.setEnabled(True)
        self._loading = True
        try:
            for dow, (check, opening, closing) in self._day_rows.items():
                row = days.get(dow)
                check.setChecked(row is not None)
                opening.set_hhmm(row["opening_time"] if row
                                 else cal.DEFAULT_OPENING)
                closing.set_hhmm(row["closing_time"] if row
                                 else cal.DEFAULT_CLOSING)
                opening.setEnabled(row is not None)
                closing.setEnabled(row is not None)
        finally:
            self._loading = False
        self._dirty = False
        self._btn_save.setEnabled(False)

    def _lock_hours(self) -> None:
        """Hours couldn't be read: the whole editor is off for this dialog, so
        an empty grid can never be saved over the real rows."""
        self._hours_loaded = False
        self._dirty = False
        self._btn_save.setEnabled(False)
        self._hours_group.setEnabled(False)
        self._hours_help.setText(
            "Couldn't read the operating hours. "
            "Close this window and open it again.")

    def _collect_rows(self) -> list[dict]:
        rows = []
        for dow, (check, opening, closing) in self._day_rows.items():
            if check.isChecked():
                rows.append({"day_of_week": dow,
                             "opening_time": opening.hhmm(),
                             "closing_time": closing.hhmm()})
        return rows

    def _save_hours(self) -> None:
        rows = self._collect_rows()
        problems = cal.validate_hours(rows)
        if problems:
            QMessageBox.warning(self, "Check the Hours", "\n".join(problems))
            return
        if not rows:
            answer = QMessageBox.question(
                self, "No Open Days",
                "No days are marked open, so the scheduler will produce "
                "no times for anyone. Save anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                return
        try:
            cal.save_operating_days(rows, self._db_path)
        except Exception as exc:
            from gui.errors import show_db_error
            show_db_error(self, exc)
            return
        crash_log.log_warning(f"OperatingDays rewritten: {rows}")
        self._load_hours()

    # -- closing -------------------------------------------------------
    def _confirm_discard(self) -> bool:
        box, discard_btn, _keep_btn = _build_discard_box(self)
        box.exec()
        return box.clickedButton() is discard_btn

    def reject(self) -> None:
        """The one gate for every way out — the Close button, Esc, and the
        window's X (QDialog.closeEvent calls reject() and keeps the window
        open when it doesn't close)."""
        if self._dirty and not self._confirm_discard():
            return
        super().reject()
