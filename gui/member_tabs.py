from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel,
    QPushButton, QMessageBox,
)
from PyQt6.QtCore import Qt

from monthly_schedule.db import (
    get_member, get_enrollments, get_authorizations,
    get_availability, get_absences,
)


class MemberTabsWidget(QWidget):
    def __init__(self, center_id: int, db_path: str, events_path: str, parent=None):
        super().__init__(parent)
        self._center_id = center_id
        self._db_path = db_path
        self._events_path = events_path
        self._member = None
        self._load_data()
        self._build_ui()
        self._dirty = False
        self._setup_dirty_tracking()

    def _load_data(self):
        self._member = {}
        self._enrollments = []
        self._authorizations = []
        self._availability = []
        self._absences = []
        errors = []
        try:
            self._member = get_member(self._center_id, self._db_path) or {}
        except Exception as exc:
            errors.append(str(exc))
        try:
            self._enrollments = get_enrollments(self._center_id, self._db_path)
        except Exception as exc:
            errors.append(str(exc))
        try:
            self._authorizations = get_authorizations(self._center_id, self._db_path)
        except Exception as exc:
            errors.append(str(exc))
        try:
            self._availability = get_availability(self._center_id, self._db_path)
        except Exception as exc:
            errors.append(str(exc))
        try:
            self._absences = get_absences(self._center_id, self._db_path)
        except Exception as exc:
            errors.append(str(exc))
        if errors:
            QMessageBox.critical(self, "Load Error", "\n".join(errors))

    def _missing(self) -> list[str]:
        missing = []
        if not self._authorizations:
            missing.append("Authorizations")
        if not self._availability:
            missing.append("Availability")
        return missing

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 12)
        layout.setSpacing(12)

        # Header row
        header = QHBoxLayout()
        name = f"{self._member.get('last_name', '')}, {self._member.get('first_name', '')}"
        cid = str(self._center_id)
        name_label = QLabel(f"<b style='font-size:15px'>{name}</b>"
                            f"<span style='color:gray;font-size:12px'> &nbsp;ID {cid}</span>")
        name_label.setTextFormat(Qt.TextFormat.RichText)
        header.addWidget(name_label)
        header.addStretch()

        missing = self._missing()
        if missing:
            badge = QLabel("⚠ Missing: " + ", ".join(missing))
            badge.setObjectName("warning_badge")
            header.addWidget(badge)

        layout.addLayout(header)

        # Tabs
        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        self._tab_info = self._make_info_tab()
        self._tab_enrollments = self._make_enrollments_tab()
        self._tab_auths = self._make_auths_tab()
        self._tab_avail = self._make_avail_tab()
        self._tab_absences = self._make_absences_tab()

        self._tabs.addTab(self._tab_info, "Info")
        self._tabs.addTab(self._tab_enrollments, "Enrollments")
        self._tabs.addTab(self._tab_auths,
            "Auths ⚠" if "Authorizations" in missing else "Authorizations")
        self._tabs.addTab(self._tab_avail,
            "Availability ⚠" if "Availability" in missing else "Availability")
        self._tabs.addTab(self._tab_absences, "Absences")

        # Events tab added after (Task 11 wires it in)
        from gui.events_view import EventsTableWidget
        self._tab_events = EventsTableWidget(
            self._events_path, center_id=self._center_id, show_header=False
        )
        self._tabs.addTab(self._tab_events, "Events")

    # ── Info tab (Task 9) ──────────────────────────────────────────────────

    def _make_info_tab(self) -> QWidget:
        from PyQt6.QtWidgets import QFormLayout, QLineEdit, QComboBox
        from db.members import HEALTH_PLANS

        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 12, 0, 0)

        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._info_first = QLineEdit(self._member.get("first_name", "") or "")
        self._info_last = QLineEdit(self._member.get("last_name", "") or "")
        self._info_plan = QComboBox()
        self._info_plan.addItems(HEALTH_PLANS)
        current_plan = self._member.get("health_plan", "")
        idx = self._info_plan.findText(current_plan)
        if idx >= 0:
            self._info_plan.setCurrentIndex(idx)
        else:
            self._info_plan.setCurrentIndex(0)
        self._info_cid = QLineEdit(str(self._center_id))
        self._info_cid.setReadOnly(True)
        self._info_address = QLineEdit(self._member.get("address", "") or "")

        for lbl, widget in [
            ("First Name", self._info_first),
            ("Last Name", self._info_last),
            ("Health Plan", self._info_plan),
            ("Center ID", self._info_cid),
            ("Address", self._info_address),
        ]:
            form.addRow(lbl, widget)

        outer.addLayout(form)
        outer.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_discard = QPushButton("Discard")
        btn_discard.clicked.connect(self._discard_info)
        btn_save = QPushButton("Save Changes")
        btn_save.setObjectName("btn_save")
        btn_save.clicked.connect(self._save_info)
        btn_row.addWidget(btn_discard)
        btn_row.addWidget(btn_save)
        outer.addLayout(btn_row)
        return w

    def _discard_info(self):
        self._info_first.setText(self._member.get("first_name", "") or "")
        self._info_last.setText(self._member.get("last_name", "") or "")
        self._info_address.setText(self._member.get("address", "") or "")
        plan = self._member.get("health_plan", "")
        idx = self._info_plan.findText(plan)
        if idx >= 0:
            self._info_plan.setCurrentIndex(idx)
        else:
            self._info_plan.setCurrentIndex(0)
        self._dirty = False

    def _save_info(self):
        from db.members import update_contact
        from db.events import open_db, insert_event
        old = self._member
        new_first = self._info_first.text().strip()
        new_last = self._info_last.text().strip()
        new_plan = self._info_plan.currentText()
        new_address = self._info_address.text().strip()

        changes = []
        if new_first != (old.get("first_name") or ""):
            changes.append(f"First Name: {old.get('first_name')} → {new_first}")
        if new_last != (old.get("last_name") or ""):
            changes.append(f"Last Name: {old.get('last_name')} → {new_last}")
        if new_plan != (old.get("health_plan") or ""):
            changes.append(f"Health Plan: {old.get('health_plan')} → {new_plan}")
        if new_address != (old.get("address") or ""):
            changes.append("Address updated")

        if not changes:
            self._dirty = False
            return

        try:
            update_contact(self._center_id, new_last, new_first, new_plan,
                           new_address, self._db_path)
            self._member["first_name"] = new_first
            self._member["last_name"] = new_last
            self._member["health_plan"] = new_plan
            self._member["address"] = new_address
            self._dirty = False
            if self._events_path:
                conn = open_db(self._events_path)
                try:
                    insert_event(conn, "EDIT", self._center_id,
                        f"{new_last}, {new_first}", "; ".join(changes))
                finally:
                    conn.close()
        except Exception as exc:
            QMessageBox.critical(self, "Save Error", str(exc))

    # ── Dirty tracking ─────────────────────────────────────────────────────

    def _setup_dirty_tracking(self):
        self._dirty = False
        for widget in (self._info_first, self._info_last, self._info_address):
            widget.textChanged.connect(lambda: setattr(self, '_dirty', True))
        self._info_plan.currentIndexChanged.connect(lambda: setattr(self, '_dirty', True))

    def is_dirty(self) -> bool:
        return self._dirty

    # ── Table tab helper ───────────────────────────────────────────────────

    def _make_table_tab(self, columns, rows, on_add, on_delete):
        from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QAbstractItemView
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 12, 0, 0)

        table = QTableWidget(len(rows), len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setVisible(False)

        for r, row_data in enumerate(rows):
            for c, val in enumerate(row_data):
                table.setItem(r, c, QTableWidgetItem(str(val) if val is not None else ""))

        layout.addWidget(table)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("+ Add")
        btn_add.clicked.connect(on_add)
        btn_del = QPushButton("Delete Selected")
        btn_del.clicked.connect(lambda: on_delete(table))
        btn_row.addWidget(btn_add)
        btn_row.addStretch()
        btn_row.addWidget(btn_del)
        layout.addLayout(btn_row)
        return w, table

    def _refresh_tab(self, index: int, new_widget: QWidget):
        old = self._tabs.widget(index)
        label = self._tabs.tabText(index)
        self._tabs.removeTab(index)
        self._tabs.insertTab(index, new_widget, label)
        self._tabs.setCurrentIndex(index)
        if old:
            old.deleteLater()

    # ── Enrollments tab ────────────────────────────────────────────────────

    def _make_enrollments_tab(self) -> QWidget:
        rows = [
            [e["id"], str(e["start_date"]), str(e["end_date"]) if e["end_date"] else "ongoing"]
            for e in self._enrollments
        ]
        w, self._enroll_table = self._make_table_tab(
            ["ID", "Start Date", "End Date"],
            rows, self._add_enrollment, self._delete_enrollment,
        )
        return w

    def _add_enrollment(self):
        from PyQt6.QtWidgets import QDialog, QFormLayout, QDateEdit, QDialogButtonBox
        from PyQt6.QtCore import QDate
        from db.members import insert_enrollment
        from db.events import open_db, insert_event
        from monthly_schedule.db import get_enrollments

        dlg = QDialog(self)
        dlg.setWindowTitle("Add Enrollment")
        form = QFormLayout(dlg)
        start = QDateEdit(QDate.currentDate())
        start.setCalendarPopup(True)
        end = QDateEdit()
        end.setCalendarPopup(True)
        end.setSpecialValueText("Ongoing")
        end.setDate(QDate(2000, 1, 1))
        form.addRow("Start Date:", start)
        form.addRow("End Date (optional):", end)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)
        if dlg.exec():
            s = start.date().toPyDate()
            e = end.date().toPyDate() if end.date() != QDate(2000, 1, 1) else None
            try:
                insert_enrollment(self._center_id, s, e, self._db_path)
                self._enrollments = get_enrollments(self._center_id, self._db_path)
                self._refresh_tab(1, self._make_enrollments_tab())
                if self._events_path:
                    conn = open_db(self._events_path)
                    try:
                        m = self._member
                        insert_event(conn, "ENROLL", self._center_id,
                            f"{m.get('last_name')}, {m.get('first_name')}",
                            f"Enrollment added: {s} – {e or 'ongoing'}")
                    finally:
                        conn.close()
            except Exception as exc:
                QMessageBox.critical(self, "Error", str(exc))

    def _delete_enrollment(self, table):
        row = table.currentRow()
        if row < 0:
            return
        record_id = int(table.item(row, 0).text())
        if QMessageBox.question(self, "Confirm", "Delete this enrollment record?") \
                == QMessageBox.StandardButton.Yes:
            from db.members import delete_enrollment
            from monthly_schedule.db import get_enrollments
            try:
                delete_enrollment(record_id, self._db_path)
                self._enrollments = get_enrollments(self._center_id, self._db_path)
                self._refresh_tab(1, self._make_enrollments_tab())
            except Exception as exc:
                QMessageBox.critical(self, "Error", str(exc))

    # ── Authorizations tab ─────────────────────────────────────────────────

    def _make_auths_tab(self) -> QWidget:
        rows = [
            [a["id"], str(a["auth_start"]), str(a["auth_end"]), a["auth_days"] or ""]
            for a in self._authorizations
        ]
        w, self._auth_table = self._make_table_tab(
            ["ID", "Auth Start", "Auth End", "Days (1=Mon…5=Fri)"],
            rows, self._add_auth, self._delete_auth,
        )
        return w

    def _add_auth(self):
        from PyQt6.QtWidgets import (
            QDialog, QFormLayout, QDateEdit, QCheckBox,
            QHBoxLayout, QDialogButtonBox, QWidget,
        )
        from PyQt6.QtCore import QDate
        from db.members import insert_authorization, encode_auth_days
        from db.events import open_db, insert_event
        from monthly_schedule.db import get_authorizations

        dlg = QDialog(self)
        dlg.setWindowTitle("Add Authorization")
        form = QFormLayout(dlg)

        auth_start = QDateEdit(QDate.currentDate())
        auth_start.setCalendarPopup(True)
        auth_end = QDateEdit(QDate.currentDate().addYears(1))
        auth_end.setCalendarPopup(True)

        day_checks = {}
        days_widget = QWidget()
        days_hl = QHBoxLayout(days_widget)
        days_hl.setContentsMargins(0, 0, 0, 0)
        for num, label in [(1, "Mon"), (2, "Tue"), (3, "Wed"), (4, "Thu"), (5, "Fri")]:
            cb = QCheckBox(label)
            day_checks[num] = cb
            days_hl.addWidget(cb)

        form.addRow("Auth Start:", auth_start)
        form.addRow("Auth End:", auth_end)
        form.addRow("Days:", days_widget)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)
        # Override accepted to validate before closing
        btns.accepted.connect(lambda: dlg.accept() if any(cb.isChecked() for cb in day_checks.values())
                               else QMessageBox.warning(dlg, "Validation", "Select at least one day."))

        if dlg.exec():
            selected_days = {n for n, cb in day_checks.items() if cb.isChecked()}
            try:
                insert_authorization(
                    self._center_id,
                    auth_start.date().toPyDate(),
                    auth_end.date().toPyDate(),
                    selected_days, None, None, self._db_path,
                )
                self._authorizations = get_authorizations(self._center_id, self._db_path)
                self._refresh_tab(2, self._make_auths_tab())
                if self._events_path:
                    conn = open_db(self._events_path)
                    try:
                        m = self._member
                        insert_event(conn, "AUTH", self._center_id,
                            f"{m.get('last_name')}, {m.get('first_name')}",
                            f"Auth added: {auth_start.date().toString('MM/dd/yyyy')} – "
                            f"{auth_end.date().toString('MM/dd/yyyy')} · "
                            f"{encode_auth_days(selected_days)}")
                    finally:
                        conn.close()
            except Exception as exc:
                QMessageBox.critical(self, "Error", str(exc))

    def _delete_auth(self, table):
        row = table.currentRow()
        if row < 0:
            return
        record_id = int(table.item(row, 0).text())
        if QMessageBox.question(self, "Confirm", "Delete this authorization?") \
                == QMessageBox.StandardButton.Yes:
            from db.members import delete_authorization
            from monthly_schedule.db import get_authorizations
            try:
                delete_authorization(record_id, self._db_path)
                self._authorizations = get_authorizations(self._center_id, self._db_path)
                self._refresh_tab(2, self._make_auths_tab())
            except Exception as exc:
                QMessageBox.critical(self, "Error", str(exc))

    # ── Availability tab ───────────────────────────────────────────────────

    def _make_avail_tab(self) -> QWidget:
        day_names = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri"}
        rows = [
            [a["id"], day_names.get(a["day_of_week"], str(a["day_of_week"])),
             a["avail_start"] or "", a["avail_end"] or "",
             str(a["effective_start_date"])]
            for a in self._availability
        ]
        w, self._avail_table = self._make_table_tab(
            ["ID", "Day", "Start", "End", "Effective From"],
            rows, self._add_avail, self._delete_avail,
        )
        return w

    def _add_avail(self):
        from PyQt6.QtWidgets import (
            QDialog, QFormLayout, QComboBox, QTimeEdit, QDateEdit, QDialogButtonBox,
        )
        from PyQt6.QtCore import QDate, QTime
        from db.members import insert_availability
        from db.events import open_db, insert_event
        from monthly_schedule.db import get_availability

        dlg = QDialog(self)
        dlg.setWindowTitle("Add Availability")
        form = QFormLayout(dlg)

        day_combo = QComboBox()
        for num, name in [(1, "Mon"), (2, "Tue"), (3, "Wed"), (4, "Thu"), (5, "Fri")]:
            day_combo.addItem(name, num)

        t_start = QTimeEdit(QTime(8, 0))
        t_end = QTimeEdit(QTime(16, 0))
        eff_start = QDateEdit(QDate.currentDate())
        eff_start.setCalendarPopup(True)

        form.addRow("Day:", day_combo)
        form.addRow("Start Time:", t_start)
        form.addRow("End Time:", t_end)
        form.addRow("Effective From:", eff_start)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)

        if dlg.exec():
            day = day_combo.currentData()
            day_name = day_combo.currentText()
            ts = t_start.time().toString("HH:mm")
            te = t_end.time().toString("HH:mm")
            try:
                insert_availability(
                    self._center_id, day, ts, te,
                    eff_start.date().toPyDate(), None, self._db_path,
                )
                self._availability = get_availability(self._center_id, self._db_path)
                self._refresh_tab(3, self._make_avail_tab())
                if self._events_path:
                    conn = open_db(self._events_path)
                    try:
                        m = self._member
                        insert_event(conn, "AVAIL", self._center_id,
                            f"{m.get('last_name')}, {m.get('first_name')}",
                            f"Availability added: {day_name} {ts}–{te}")
                    finally:
                        conn.close()
            except Exception as exc:
                QMessageBox.critical(self, "Error", str(exc))

    def _delete_avail(self, table):
        row = table.currentRow()
        if row < 0:
            return
        record_id = int(table.item(row, 0).text())
        if QMessageBox.question(self, "Confirm", "Delete this availability row?") \
                == QMessageBox.StandardButton.Yes:
            from db.members import delete_availability
            from monthly_schedule.db import get_availability
            try:
                delete_availability(record_id, self._db_path)
                self._availability = get_availability(self._center_id, self._db_path)
                self._refresh_tab(3, self._make_avail_tab())
            except Exception as exc:
                QMessageBox.critical(self, "Error", str(exc))

    # ── Absences tab ───────────────────────────────────────────────────────

    def _make_absences_tab(self) -> QWidget:
        rows = [
            [a["id"], a["leave_type"], str(a["start_date"]), str(a["end_date"])]
            for a in self._absences
        ]
        w, self._abs_table = self._make_table_tab(
            ["ID", "Leave Type", "Start", "End"],
            rows, self._add_absence, self._delete_absence,
        )
        return w

    def _add_absence(self):
        from PyQt6.QtWidgets import (
            QDialog, QFormLayout, QComboBox, QDateEdit, QDialogButtonBox,
        )
        from PyQt6.QtCore import QDate
        from db.members import insert_absence, LEAVE_TYPES
        from db.events import open_db, insert_event
        from monthly_schedule.db import get_absences

        dlg = QDialog(self)
        dlg.setWindowTitle("Add Absence")
        form = QFormLayout(dlg)

        leave_combo = QComboBox()
        leave_combo.addItems(LEAVE_TYPES)
        start = QDateEdit(QDate.currentDate())
        start.setCalendarPopup(True)
        end = QDateEdit(QDate.currentDate())
        end.setCalendarPopup(True)

        form.addRow("Leave Type:", leave_combo)
        form.addRow("Start Date:", start)
        form.addRow("End Date:", end)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)

        if dlg.exec():
            lt = leave_combo.currentText()
            s = start.date().toPyDate()
            e = end.date().toPyDate()
            try:
                insert_absence(self._center_id, lt, s, e, self._db_path)
                self._absences = get_absences(self._center_id, self._db_path)
                self._refresh_tab(4, self._make_absences_tab())
                if self._events_path:
                    conn = open_db(self._events_path)
                    try:
                        m = self._member
                        insert_event(conn, "ABS", self._center_id,
                            f"{m.get('last_name')}, {m.get('first_name')}",
                            f"Absence added: {lt} · {s} – {e}")
                    finally:
                        conn.close()
            except Exception as exc:
                QMessageBox.critical(self, "Error", str(exc))

    def _delete_absence(self, table):
        row = table.currentRow()
        if row < 0:
            return
        record_id = int(table.item(row, 0).text())
        if QMessageBox.question(self, "Confirm", "Delete this absence?") \
                == QMessageBox.StandardButton.Yes:
            from db.members import delete_absence
            from monthly_schedule.db import get_absences
            try:
                delete_absence(record_id, self._db_path)
                self._absences = get_absences(self._center_id, self._db_path)
                self._refresh_tab(4, self._make_absences_tab())
            except Exception as exc:
                QMessageBox.critical(self, "Error", str(exc))
