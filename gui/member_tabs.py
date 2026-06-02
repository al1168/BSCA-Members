from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel,
    QPushButton, QMessageBox,
)
from PyQt6.QtCore import Qt

from db.members import get_member_context


FIELD_LABELS = {
    "first_name": "First Name", "last_name": "Last Name",
    "chinese_name": "Chinese Name", "gender": "Gender", "dob": "DOB",
    "member_id": "Member ID", "medicaid": "Medicaid", "medicare": "Medicare",
    "ssn": "SSN", "language": "Language", "case_manager": "Case Manager",
    "home_tell": "Home Phone", "cell": "Cell", "address": "Address",
    "emergency": "Emergency", "pcp": "PCP", "hospital": "Hospital",
    "hha": "HHA", "admission_date": "Admission Date", "notes": "Notes",
}


def _normalize_value(v) -> str:
    """Normalize a field value for change comparison/display.

    Stored values may carry trailing whitespace (Access) and CRLF line
    endings (memo fields), while widget read-back is stripped with LF. Unify
    both so cosmetic-only differences are not reported as changes.
    """
    return (v or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def build_change_summary(old: dict, fields: dict) -> list[str]:
    """Friendly 'Label: old → new' lines for each field whose value changed.

    Values are normalized (newlines unified, surrounding whitespace stripped)
    before comparison, so trailing spaces or CRLF/LF differences do not count
    as changes. Blank values render as '(empty)'. Order follows `fields`.
    """
    lines = []
    for key, new_val in fields.items():
        old_norm = _normalize_value(old.get(key))
        new_norm = _normalize_value(new_val)
        if new_norm != old_norm:
            label = FIELD_LABELS.get(key, key)
            lines.append(f"{label}: {old_norm or '(empty)'} → {new_norm or '(empty)'}")
    return lines


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
        try:
            ctx = get_member_context(self._center_id, self._db_path)
            self._member = ctx["member"]
            self._enrollments = ctx["enrollments"]
            self._authorizations = ctx["authorizations"]
            self._availability = ctx["availability"]
            self._absences = ctx["absences"]
        except Exception as exc:
            QMessageBox.critical(self, "Load Error", str(exc))

    def _make_photo_label(self) -> QLabel:
        """Return an 80×80 QLabel showing the member photo or a gray placeholder."""
        from PyQt6.QtGui import QPixmap, QPainter, QColor, QBrush
        from PyQt6.QtCore import Qt as QtCore
        from db.members import get_member_photo

        lbl = QLabel()
        lbl.setFixedSize(80, 80)
        lbl.setStyleSheet("border-radius: 40px; overflow: hidden;")

        photo_bytes = get_member_photo(self._center_id, self._db_path)
        if photo_bytes:
            pix = QPixmap()
            pix.loadFromData(photo_bytes)
            pix = pix.scaled(80, 80, QtCore.AspectRatioMode.KeepAspectRatioByExpanding,
                             QtCore.TransformationMode.SmoothTransformation)
            if pix.width() > 80 or pix.height() > 80:
                x = (pix.width() - 80) // 2
                y = (pix.height() - 80) // 2
                pix = pix.copy(x, y, 80, 80)
            lbl.setPixmap(pix)
        else:
            pix = QPixmap(80, 80)
            pix.fill(QtCore.GlobalColor.transparent)
            painter = QPainter(pix)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QBrush(QColor("#3a3a3a")))
            painter.setPen(QtCore.PenStyle.NoPen)
            painter.drawEllipse(0, 0, 80, 80)
            painter.setBrush(QBrush(QColor("#888888")))
            painter.drawEllipse(28, 12, 24, 24)
            painter.drawEllipse(12, 46, 56, 40)
            painter.end()
            lbl.setPixmap(pix)

        return lbl

    @staticmethod
    def decode_auth_days_static(value: str) -> set[int]:
        if not value:
            return set()
        return {int(x) for x in value.split(",") if x.strip()}

    @staticmethod
    def _active_authorization(authorizations: list[dict]) -> dict | None:
        """Return the auth row covering today, preferring latest start. None if none."""
        from datetime import date
        today = date.today()
        candidates = [
            a for a in authorizations
            if a.get("effective_start") and a.get("effective_end")
            and a["effective_start"] <= today <= a["effective_end"]
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda a: a["effective_start"])

    @staticmethod
    def _enrollment_start(enrollments: list[dict]):
        """Return the earliest enrollment start_date, or None."""
        dates = [e["start_date"] for e in enrollments if e.get("start_date")]
        return min(dates) if dates else None

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
        header.setSpacing(14)

        # Photo
        header.addWidget(self._make_photo_label())

        # Name + ID
        name_col = QVBoxLayout()
        name = f"{self._member.get('last_name', '')}, {self._member.get('first_name', '')}"
        cid = str(self._center_id)
        name_label = QLabel(f"<b style='font-size:15px'>{name}</b>"
                            f"<span style='color:gray;font-size:12px'> &nbsp;ID {cid}</span>")
        name_label.setTextFormat(Qt.TextFormat.RichText)
        name_col.addWidget(name_label)
        name_col.addStretch()
        header.addLayout(name_col)
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
        from PyQt6.QtWidgets import (
            QFormLayout, QLineEdit, QTextEdit,
            QGroupBox, QScrollArea,
        )

        m = self._member

        def field(key: str) -> QLineEdit:
            return QLineEdit(m.get(key, "") or "")

        # ── Identity ─────────────────────────────────────────────────────
        grp_identity = QGroupBox("Identity")
        f_identity = QFormLayout(grp_identity)
        f_identity.setSpacing(8)

        self._info_first    = field("first_name")
        self._info_last     = field("last_name")
        self._info_chinese  = field("chinese_name")
        self._info_gender   = field("gender")
        self._info_dob      = field("dob")
        self._info_cid      = QLineEdit(str(self._center_id))
        self._info_cid.setReadOnly(True)
        self._info_member_id = field("member_id")

        for lbl, w in [
            ("First Name",   self._info_first),
            ("Last Name",    self._info_last),
            ("Chinese Name", self._info_chinese),
            ("Gender",       self._info_gender),
            ("DOB",          self._info_dob),
            ("Center ID",    self._info_cid),
            ("Member ID",    self._info_member_id),
        ]:
            f_identity.addRow(lbl, w)

        # ── Contact ──────────────────────────────────────────────────────
        grp_contact = QGroupBox("Contact")
        f_contact = QFormLayout(grp_contact)
        f_contact.setSpacing(8)

        self._info_address   = field("address")
        self._info_home_tell = field("home_tell")
        self._info_cell      = field("cell")
        self._info_emergency = field("emergency")

        for lbl, w in [
            ("Address",    self._info_address),
            ("Home Phone", self._info_home_tell),
            ("Cell",       self._info_cell),
            ("Emergency",  self._info_emergency),
        ]:
            f_contact.addRow(lbl, w)

        # ── Medical ──────────────────────────────────────────────────────
        grp_medical = QGroupBox("Medical")
        f_medical = QFormLayout(grp_medical)
        f_medical.setSpacing(8)

        self._info_plan = QLineEdit(m.get("health_plan", "") or "")
        self._info_plan.setReadOnly(True)

        self._info_medicaid = field("medicaid")
        self._info_medicare = field("medicare")
        self._info_ssn      = field("ssn")
        self._info_pcp      = field("pcp")
        self._info_hospital = field("hospital")
        self._info_hha      = field("hha")
        self._info_language = field("language")

        for lbl, w in [
            ("Health Plan", self._info_plan),
            ("Medicaid",    self._info_medicaid),
            ("Medicare",    self._info_medicare),
            ("SSN",         self._info_ssn),
            ("PCP",         self._info_pcp),
            ("Hospital",    self._info_hospital),
            ("HHA",         self._info_hha),
            ("Language",    self._info_language),
        ]:
            f_medical.addRow(lbl, w)

        # ── Care ─────────────────────────────────────────────────────────
        grp_care = QGroupBox("Care")
        f_care = QFormLayout(grp_care)
        f_care.setSpacing(8)

        self._info_case_manager   = field("case_manager")
        self._info_admission_date = field("admission_date")
        self._info_notes = QTextEdit()
        # Load as plain text: the QTextEdit(text) constructor auto-detects rich
        # text and collapses newlines into spaces, which loses line breaks and
        # makes an untouched note read back differently than it was stored.
        self._info_notes.setPlainText(m.get("notes", "") or "")
        self._info_notes.setFixedHeight(72)

        f_care.addRow("Case Manager",   self._info_case_manager)
        f_care.addRow("Admission Date", self._info_admission_date)
        f_care.addRow("Notes",          self._info_notes)

        # ── Schedule Summary (read-only) ──────────────────────────────────
        grp_sched = QGroupBox("Schedule Summary")
        f_sched = QFormLayout(grp_sched)
        f_sched.setSpacing(8)

        enroll_start = self._enrollment_start(self._enrollments)
        enroll_lbl = QLineEdit(str(enroll_start) if enroll_start else "—")
        enroll_lbl.setReadOnly(True)

        active_auth = self._active_authorization(self._authorizations)
        if active_auth:
            day_map = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri"}
            days_str = " ".join(
                day_map[d] for d in sorted(
                    self.decode_auth_days_static(active_auth.get("auth_days", ""))
                )
            )
            plan = active_auth.get("health_plan", "")
            auth_text = (f"{active_auth['effective_start']} – "
                         f"{active_auth['effective_end']}  [{days_str}]"
                         + (f"  ·  {plan}" if plan else ""))
        else:
            auth_text = "None"
        auth_lbl = QLineEdit(auth_text)
        auth_lbl.setReadOnly(True)

        f_sched.addRow("Enrollment Start", enroll_lbl)
        f_sched.addRow("Active Auth",      auth_lbl)

        # ── Assemble in scroll area ───────────────────────────────────────
        scroll_content = QWidget()
        vbox = QVBoxLayout(scroll_content)
        vbox.setSpacing(10)
        vbox.setContentsMargins(0, 8, 8, 8)
        for grp in (grp_identity, grp_contact, grp_medical, grp_care, grp_sched):
            vbox.addWidget(grp)
        vbox.addStretch()

        scroll = QScrollArea()
        scroll.setWidget(scroll_content)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        outer = QWidget()
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(0, 8, 0, 0)
        outer_layout.setSpacing(8)
        outer_layout.addWidget(scroll)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_discard = QPushButton("Discard")
        btn_discard.clicked.connect(self._discard_info)
        btn_save = QPushButton("Save Changes")
        btn_save.setObjectName("btn_save")
        btn_save.clicked.connect(self._save_info)
        btn_row.addWidget(btn_discard)
        btn_row.addWidget(btn_save)
        outer_layout.addLayout(btn_row)

        return outer

    def _discard_info(self):
        m = self._member
        self._info_first.setText(m.get("first_name", "") or "")
        self._info_last.setText(m.get("last_name", "") or "")
        self._info_chinese.setText(m.get("chinese_name", "") or "")
        self._info_gender.setText(m.get("gender", "") or "")
        self._info_dob.setText(m.get("dob", "") or "")
        self._info_member_id.setText(m.get("member_id", "") or "")
        self._info_medicaid.setText(m.get("medicaid", "") or "")
        self._info_medicare.setText(m.get("medicare", "") or "")
        self._info_ssn.setText(m.get("ssn", "") or "")
        self._info_pcp.setText(m.get("pcp", "") or "")
        self._info_hospital.setText(m.get("hospital", "") or "")
        self._info_hha.setText(m.get("hha", "") or "")
        self._info_language.setText(m.get("language", "") or "")
        self._info_address.setText(m.get("address", "") or "")
        self._info_home_tell.setText(m.get("home_tell", "") or "")
        self._info_cell.setText(m.get("cell", "") or "")
        self._info_emergency.setText(m.get("emergency", "") or "")
        self._info_case_manager.setText(m.get("case_manager", "") or "")
        self._info_admission_date.setText(m.get("admission_date", "") or "")
        self._info_notes.setPlainText(m.get("notes", "") or "")
        self._dirty = False

    def _save_info(self):
        from db.members import update_contact
        from db.events import open_db, insert_event

        old = self._member
        fields = {
            "last_name":      self._info_last.text().strip(),
            "first_name":     self._info_first.text().strip(),
            "chinese_name":   self._info_chinese.text().strip(),
            "gender":         self._info_gender.text().strip(),
            "dob":            self._info_dob.text().strip(),
            "member_id":      self._info_member_id.text().strip(),
            "health_plan":    self._member.get("health_plan", "") or "",
            "medicaid":       self._info_medicaid.text().strip(),
            "medicare":       self._info_medicare.text().strip(),
            "ssn":            self._info_ssn.text().strip(),
            "language":       self._info_language.text().strip(),
            "case_manager":   self._info_case_manager.text().strip(),
            "home_tell":      self._info_home_tell.text().strip(),
            "cell":           self._info_cell.text().strip(),
            "address":        self._info_address.text().strip(),
            "emergency":      self._info_emergency.text().strip(),
            "pcp":            self._info_pcp.text().strip(),
            "hospital":       self._info_hospital.text().strip(),
            "hha":            self._info_hha.text().strip(),
            "admission_date": self._info_admission_date.text().strip(),
            "notes":          self._info_notes.toPlainText().strip(),
        }

        summary = build_change_summary(old, fields)
        if not summary:
            self._dirty = False
            return

        name = f"{old.get('last_name', '')}, {old.get('first_name', '')}"
        confirm = QMessageBox(self)
        confirm.setWindowTitle("Confirm Changes")
        confirm.setIcon(QMessageBox.Icon.Question)
        confirm.setText(f"Confirm changes for {name}?")
        confirm.setInformativeText("\n".join(summary))
        confirm.setStandardButtons(
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Cancel
        )
        confirm.setDefaultButton(QMessageBox.StandardButton.Save)
        if confirm.exec() != QMessageBox.StandardButton.Save:
            return  # user cancelled — keep edits, stay dirty

        try:
            update_contact(
                center_id=self._center_id,
                last_name=fields["last_name"],
                first_name=fields["first_name"],
                chinese_name=fields["chinese_name"],
                gender=fields["gender"],
                dob=fields["dob"],
                member_id=fields["member_id"],
                health_plan=fields["health_plan"],
                medicaid=fields["medicaid"],
                medicare=fields["medicare"],
                ssn=fields["ssn"],
                language=fields["language"],
                case_manager=fields["case_manager"],
                home_tell=fields["home_tell"],
                cell=fields["cell"],
                address=fields["address"],
                emergency=fields["emergency"],
                pcp=fields["pcp"],
                hospital=fields["hospital"],
                hha=fields["hha"],
                admission_date=fields["admission_date"],
                notes=fields["notes"],
                db_path=self._db_path,
            )
            self._member.update(fields)
            self._dirty = False
            if self._events_path:
                conn = open_db(self._events_path)
                try:
                    insert_event(
                        conn, "EDIT", self._center_id,
                        f"{fields['last_name']}, {fields['first_name']}",
                        "; ".join(summary[:5]),
                    )
                finally:
                    conn.close()
        except Exception as exc:
            QMessageBox.critical(self, "Save Error", str(exc))

    # ── Dirty tracking ─────────────────────────────────────────────────────

    def _setup_dirty_tracking(self):
        self._dirty = False
        line_edits = (
            self._info_first, self._info_last, self._info_chinese,
            self._info_gender, self._info_dob, self._info_member_id,
            self._info_medicaid, self._info_medicare, self._info_ssn,
            self._info_language, self._info_case_manager,
            self._info_home_tell, self._info_cell, self._info_address,
            self._info_emergency, self._info_pcp, self._info_hospital,
            self._info_hha, self._info_admission_date,
        )
        for w in line_edits:
            w.textChanged.connect(lambda: setattr(self, '_dirty', True))
        self._info_notes.textChanged.connect(lambda: setattr(self, '_dirty', True))

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
        from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QAbstractItemView
        from datetime import date

        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 12, 0, 0)

        columns = ["ID", "Start Date", "End Date", "Status"]
        table = QTableWidget(len(self._enrollments), len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setVisible(False)

        today = date.today()
        for r, e in enumerate(self._enrollments):
            end = e["end_date"]
            table.setItem(r, 0, QTableWidgetItem(str(e["id"])))
            table.setItem(r, 1, QTableWidgetItem(str(e["start_date"])))
            table.setItem(r, 2, QTableWidgetItem(str(end) if end else "ongoing"))
            if end is None or end > today:
                btn = QPushButton("Terminate")
                btn.setObjectName("btn_terminate")
                btn.clicked.connect(
                    lambda _=False, rid=e["id"]: self._terminate_enrollment(rid)
                )
                table.setCellWidget(r, 3, btn)
            else:
                table.setItem(r, 3, QTableWidgetItem("Ended"))

        self._enroll_table = table
        layout.addWidget(table)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("+ Add")
        btn_add.clicked.connect(self._add_enrollment)
        btn_del = QPushButton("Delete Selected")
        btn_del.clicked.connect(lambda: self._delete_enrollment(table))
        btn_row.addWidget(btn_add)
        btn_row.addStretch()
        btn_row.addWidget(btn_del)
        layout.addLayout(btn_row)
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

    def _terminate_enrollment(self, record_id: int):
        from datetime import date
        from db.members import terminate_enrollment
        from db.events import open_db, insert_event
        from monthly_schedule.db import get_enrollments

        today = date.today()
        reply = QMessageBox.question(
            self, "Terminate Enrollment",
            f"Terminate this enrollment? The end date will be set to today "
            f"({today.isoformat()}). This can't be undone.",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            terminate_enrollment(record_id, self._db_path)
            self._enrollments = get_enrollments(self._center_id, self._db_path)
            self._refresh_tab(1, self._make_enrollments_tab())
            if self._events_path:
                conn = open_db(self._events_path)
                try:
                    m = self._member
                    insert_event(conn, "ENROLL", self._center_id,
                        f"{m.get('last_name')}, {m.get('first_name')}",
                        f"Enrollment terminated: end set to {today.isoformat()}")
                finally:
                    conn.close()
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    # ── Authorizations tab ─────────────────────────────────────────────────

    def _make_auths_tab(self) -> QWidget:
        from PyQt6.QtWidgets import (
            QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView,
        )
        from db.members import latest_authorization

        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 12, 0, 0)

        columns = ["ID", "Auth Start", "Auth End", "Days", "Health Plan", "Action"]
        table = QTableWidget(len(self._authorizations), len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.horizontalHeaderItem(3).setToolTip("1=Mon  2=Tue  3=Wed  4=Thu  5=Fri")
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        hdr = table.horizontalHeader()
        hdr.setStretchLastSection(False)
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        table.verticalHeader().setVisible(False)

        latest = latest_authorization(self._authorizations)
        latest_id = latest["id"] if latest else None
        for r, a in enumerate(self._authorizations):
            table.setItem(r, 0, QTableWidgetItem(str(a["id"])))
            table.setItem(r, 1, QTableWidgetItem(str(a["auth_start"])))
            table.setItem(r, 2, QTableWidgetItem(str(a["auth_end"])))
            table.setItem(r, 3, QTableWidgetItem(a["auth_days"] or ""))
            table.setItem(r, 4, QTableWidgetItem(a.get("health_plan", "") or ""))
            if a["id"] == latest_id:
                btn = QPushButton("Edit")
                btn.setObjectName("btn_edit")
                btn.clicked.connect(lambda _=False, auth=a: self._edit_auth(auth))
                table.setCellWidget(r, 5, btn)

        self._auth_table = table
        layout.addWidget(table)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("+ Add")
        btn_add.clicked.connect(self._add_auth)
        btn_del = QPushButton("Delete Selected")
        btn_del.clicked.connect(lambda: self._delete_auth(table))
        btn_row.addWidget(btn_add)
        btn_row.addStretch()
        btn_row.addWidget(btn_del)
        layout.addLayout(btn_row)
        return w

    def _after_auth_change(self, description: str | None):
        """Re-sync the plan, reload auths, refresh the tab, and (optionally)
        log an AUTH event. Called after add/edit/delete of an authorization."""
        from db.members import get_authorizations, sync_health_plan_from_latest_auth
        from db.events import open_db, insert_event

        synced = sync_health_plan_from_latest_auth(self._center_id, self._db_path)
        if synced:
            self._member["health_plan"] = synced
            if hasattr(self, "_info_plan"):
                self._info_plan.setText(synced)
        self._authorizations = get_authorizations(self._center_id, self._db_path)
        self._refresh_tab(2, self._make_auths_tab())
        if description and self._events_path:
            m = self._member
            conn = open_db(self._events_path)
            try:
                insert_event(conn, "AUTH", self._center_id,
                    f"{m.get('last_name')}, {m.get('first_name')}", description)
            finally:
                conn.close()

    def _open_auth_dialog(self, existing: dict | None = None) -> dict | None:
        """Build the Add/Edit Authorization dialog. Returns a dict with
        auth_start, auth_end, days, health_plan — or None if cancelled.
        Pre-fills from `existing` when editing."""
        from PyQt6.QtWidgets import (
            QDialog, QFormLayout, QDateEdit, QCheckBox, QComboBox,
            QHBoxLayout, QDialogButtonBox, QWidget,
        )
        from PyQt6.QtCore import QDate
        from db.members import HEALTH_PLANS

        dlg = QDialog(self)
        dlg.setWindowTitle("Edit Authorization" if existing else "Add Authorization")
        form = QFormLayout(dlg)

        auth_start = QDateEdit()
        auth_start.setCalendarPopup(True)
        auth_end = QDateEdit()
        auth_end.setCalendarPopup(True)
        if existing:
            s, e = existing["auth_start"], existing["auth_end"]
            auth_start.setDate(QDate(s.year, s.month, s.day))
            auth_end.setDate(QDate(e.year, e.month, e.day))
        else:
            auth_start.setDate(QDate.currentDate())
            auth_end.setDate(QDate.currentDate().addYears(1))

        existing_days = (
            self.decode_auth_days_static(existing["auth_days"]) if existing else set()
        )
        day_checks = {}
        days_widget = QWidget()
        days_hl = QHBoxLayout(days_widget)
        days_hl.setContentsMargins(0, 0, 0, 0)
        for num, label in [(1, "Mon"), (2, "Tue"), (3, "Wed"), (4, "Thu"), (5, "Fri")]:
            cb = QCheckBox(label)
            cb.setChecked(num in existing_days)
            day_checks[num] = cb
            days_hl.addWidget(cb)

        plan_combo = QComboBox()
        plan_combo.addItems(HEALTH_PLANS)
        if existing:
            idx = plan_combo.findText(existing.get("health_plan", ""))
            if idx >= 0:
                plan_combo.setCurrentIndex(idx)

        form.addRow("Auth Start:", auth_start)
        form.addRow("Auth End:", auth_end)
        form.addRow("Days:", days_widget)
        form.addRow("Health Plan:", plan_combo)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)
        btns.accepted.connect(
            lambda: dlg.accept() if any(cb.isChecked() for cb in day_checks.values())
            else QMessageBox.warning(dlg, "Validation", "Select at least one day.")
        )

        if not dlg.exec():
            return None
        return {
            "auth_start": auth_start.date().toPyDate(),
            "auth_end": auth_end.date().toPyDate(),
            "days": {n for n, cb in day_checks.items() if cb.isChecked()},
            "health_plan": plan_combo.currentText(),
        }

    def _add_auth(self):
        from db.members import insert_authorization, encode_auth_days

        result = self._open_auth_dialog()
        if not result:
            return
        try:
            insert_authorization(
                self._center_id, result["auth_start"], result["auth_end"],
                result["days"], None, None, result["health_plan"], self._db_path,
            )
            self._after_auth_change(
                f"Auth added: {result['auth_start']} – {result['auth_end']} · "
                f"{encode_auth_days(result['days'])} · {result['health_plan']}"
            )
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _edit_auth(self, auth: dict):
        from db.members import update_authorization, encode_auth_days

        result = self._open_auth_dialog(existing=auth)
        if not result:
            return
        try:
            update_authorization(
                auth["id"], result["auth_start"], result["auth_end"],
                result["days"], result["health_plan"], self._db_path,
            )
            self._after_auth_change(
                f"Auth edited: {result['auth_start']} – {result['auth_end']} · "
                f"{encode_auth_days(result['days'])} · {result['health_plan']}"
            )
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
            try:
                delete_authorization(record_id, self._db_path)
                self._after_auth_change(None)
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
            QDialog, QFormLayout, QComboBox, QLineEdit, QDateEdit,
            QDialogButtonBox, QWidget, QHBoxLayout,
        )
        from PyQt6.QtCore import QDate
        from db.members import insert_availability, time_12h_to_24h
        from db.events import open_db, insert_event
        from monthly_schedule.db import get_availability

        dlg = QDialog(self)
        dlg.setWindowTitle("Add Availability")
        form = QFormLayout(dlg)

        day_combo = QComboBox()
        for num, name in [(1, "Mon"), (2, "Tue"), (3, "Wed"), (4, "Thu"), (5, "Fri")]:
            day_combo.addItem(name, num)

        def time_row(default_text: str, default_period: str):
            container = QWidget()
            hl = QHBoxLayout(container)
            hl.setContentsMargins(0, 0, 0, 0)
            edit = QLineEdit(default_text)
            edit.setPlaceholderText("h:mm")
            period = QComboBox()
            period.addItems(["AM", "PM"])
            period.setCurrentText(default_period)
            hl.addWidget(edit)
            hl.addWidget(period)
            return container, edit, period

        start_row, start_edit, start_period = time_row("8:00", "AM")
        end_row, end_edit, end_period = time_row("4:00", "PM")
        eff_start = QDateEdit(QDate.currentDate())
        eff_start.setCalendarPopup(True)

        form.addRow("Day:", day_combo)
        form.addRow("Start Time:", start_row)
        form.addRow("End Time:", end_row)
        form.addRow("Effective From:", eff_start)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)

        def on_accept():
            try:
                time_12h_to_24h(start_edit.text(), start_period.currentText())
                time_12h_to_24h(end_edit.text(), end_period.currentText())
            except ValueError:
                QMessageBox.warning(dlg, "Validation",
                    "Enter times as h:mm with hour 1-12 and minute 00-59.")
                return
            dlg.accept()

        btns.accepted.connect(on_accept)

        if dlg.exec():
            day = day_combo.currentData()
            day_name = day_combo.currentText()
            ts = time_12h_to_24h(start_edit.text(), start_period.currentText())
            te = time_12h_to_24h(end_edit.text(), end_period.currentText())
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
