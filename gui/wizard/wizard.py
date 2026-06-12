from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QStackedWidget,
    QLabel, QWidget, QMessageBox,
)
from PyQt6.QtCore import Qt
from gui.wizard.step_contact import StepContact
from gui.wizard.step_enrollment import StepEnrollment
from gui.wizard.step_auths import StepAuths
from gui.wizard.step_review import StepReview

STEP_LABELS = ["Contact Info", "Enrollment", "Auths & Availability", "Review & Save"]


class AddMemberWizard(QDialog):
    def __init__(self, db_path: str, events_path: str, api_key: str = "", parent=None):
        super().__init__(parent)
        self._db_path = db_path
        self._events_path = events_path
        self._api_key = api_key or ""
        self.setWindowTitle("Add New Member")
        self.setMinimumSize(880, 660)
        self._current = 0
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 20)
        layout.setSpacing(16)

        self._progress_widget = self._build_progress()
        layout.addWidget(self._progress_widget)

        self._stack = QStackedWidget()
        self._step_contact = StepContact(self._api_key)
        self._step_enrollment = StepEnrollment()
        self._step_auths = StepAuths()
        self._step_review = StepReview()
        for step in (self._step_contact, self._step_enrollment,
                     self._step_auths, self._step_review):
            self._stack.addWidget(step)
        layout.addWidget(self._stack)

        nav = QHBoxLayout()
        self._btn_cancel = QPushButton("Cancel")
        self._btn_cancel.clicked.connect(self.reject)
        self._btn_back = QPushButton("← Back")
        self._btn_back.clicked.connect(self._go_back)
        self._btn_back.setEnabled(False)
        self._btn_next = QPushButton("Next →")
        self._btn_next.setObjectName("btn_primary")
        self._btn_next.clicked.connect(self._go_next)
        nav.addWidget(self._btn_cancel)
        nav.addStretch()
        nav.addWidget(self._btn_back)
        nav.addWidget(self._btn_next)
        layout.addLayout(nav)

    def _build_progress(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(6)

        dot_row = QHBoxLayout()
        dot_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._dots: list[QLabel] = []
        for i in range(4):
            dot = QLabel(str(i + 1))
            dot.setFixedSize(28, 28)
            dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            dot.setStyleSheet(self._dot_style(i, 0))
            self._dots.append(dot)
            dot_row.addWidget(dot)
            if i < 3:
                line = QLabel()
                line.setFixedHeight(1)
                line.setFixedWidth(64)
                line.setStyleSheet("background: #282c38;")
                dot_row.addWidget(line)

        lbl_row = QHBoxLayout()
        for label in STEP_LABELS:
            lbl = QLabel(label)
            lbl.setFixedWidth(84)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setWordWrap(True)
            lbl.setStyleSheet("font-size:10px; color:#31354a;")
            lbl_row.addWidget(lbl)

        layout.addLayout(dot_row)
        layout.addLayout(lbl_row)
        return widget

    def _dot_style(self, dot_index: int, current: int) -> str:
        if dot_index < current:
            return ("background:#3d9e6e; color:white; border-radius:14px;"
                    "font-weight:700; font-size:11px;")
        if dot_index == current:
            return ("background:#5b7cf4; color:white; border-radius:14px;"
                    "font-weight:700; font-size:11px; border:3px solid #1c2040;")
        return ("background:#1e2128; color:#31354a; border-radius:14px;"
                "border:1px solid #282c38; font-size:11px;")

    def _update_progress(self):
        for i, dot in enumerate(self._dots):
            dot.setStyleSheet(self._dot_style(i, self._current))

    def _go_next(self):
        if self._current == 0:
            if not self._step_contact.validate(self._db_path):
                return
        if self._current == 2:
            data = self._collect_all()
            self._step_review.populate(data)
        if self._current == 3:
            self._save()
            return
        self._current += 1
        self._stack.setCurrentIndex(self._current)
        self._btn_back.setEnabled(True)
        if self._current == 3:
            self._btn_next.setText("Create Member")
        self._update_progress()

    def _go_back(self):
        self._current -= 1
        self._stack.setCurrentIndex(self._current)
        self._btn_next.setText("Next →")
        self._btn_back.setEnabled(self._current > 0)
        self._update_progress()

    def _collect_all(self) -> dict:
        data = {"contact": self._step_contact.collect()}
        data.update(self._step_enrollment.collect())
        data.update(self._step_auths.collect())
        return data

    def _save(self):
        data = self._collect_all()
        c = data["contact"]
        try:
            from db.members import insert_member
            from db.events import open_db, insert_event
            insert_member(
                center_id=c["center_id"],
                last_name=c["last_name"],
                first_name=c["first_name"],
                health_plan=c["health_plan"],
                address=c["address"],
                enrollment_start=data["enrollment_start"],
                enrollment_end=data["enrollment_end"],
                authorization=data.get("authorization"),
                availability_rows=data.get("availability_rows", []),
                long_lat=c.get("long_lat", ""),
                member_id=c.get("member_id", ""),
                home_tell=c.get("home_tell", ""),
                cell=c.get("cell", ""),
                dob=c.get("dob"),
                db_path=self._db_path,
            )
            if self._events_path:
                conn = open_db(self._events_path)
                try:
                    insert_event(
                        conn, "NEW", c["center_id"],
                        f"{c['last_name']}, {c['first_name']}",
                        "Member added to system",
                    )
                finally:
                    conn.close()
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Save Failed",
                f"Could not create member:\n{exc}")
