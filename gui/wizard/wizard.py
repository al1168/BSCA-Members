from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QStackedWidget, QLabel, QWidget, QMessageBox, QScrollArea, QFrame,
)
from PyQt6.QtCore import Qt
from gui.theme import px
from gui.wizard.step_contact import StepContact
from gui.wizard.step_enrollment import StepEnrollment
from gui.wizard.step_auths import StepAuths
from gui.wizard.step_review import StepReview

STEP_LABELS = ["Contact Info", "Enrollment", "Auths & Availability", "Review & Save"]

_BASE_W, _BASE_H = 880, 660   # dialog size at Normal text size


def _scrolled(page: QWidget) -> QScrollArea:
    """Let a step page shrink below its content height (needed at Large /
    Extra Large text, where the form would otherwise force the dialog past
    the work area) — the page scrolls instead."""
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    area.setWidget(page)
    return area


class AddMemberWizard(QDialog):
    def __init__(self, db_path: str, events_path: str, api_key: str = "", parent=None):
        super().__init__(parent)
        self._db_path = db_path
        self._events_path = events_path
        self._api_key = api_key or ""
        self.setWindowTitle("Add New Member")
        self._current = 0
        self._build_ui()
        # Open at the Normal-scale 880x660 scaled with the text size, but never
        # larger than the work area (Extra Large would otherwise exceed 1080p);
        # the step pages scroll (see _scrolled) so the dialog can be this small.
        w, h = px(_BASE_W), px(_BASE_H)
        screen = QApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            w, h = min(w, avail.width() - 40), min(h, avail.height() - 80)
        self.setMinimumSize(min(_BASE_W, w), min(_BASE_H, h))
        self.resize(w, h)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 20)
        layout.setSpacing(16)

        self._progress_widget = self._build_progress()
        layout.addWidget(self._progress_widget)

        self._stack = QStackedWidget()
        # Auto-assign the next Center ID (locked field). Degrade to an editable
        # field if it can't be computed, so member creation is never blocked.
        try:
            from db.members import suggest_next_center_id
            suggested_cid = suggest_next_center_id(self._db_path)
        except Exception as exc:
            import crash_log
            crash_log.log_warning(f"suggest_next_center_id failed: {exc!r}")
            suggested_cid = None
        # Health plans come from the DB so new insurances show up without a
        # code change; StepContact falls back to the static tuple on None.
        try:
            import db.members
            plans = db.members.get_health_plans(self._db_path)
        except Exception as exc:
            import crash_log
            crash_log.log_warning(f"get_health_plans failed: {exc!r}")
            plans = None
        self._step_contact = StepContact(self._api_key, center_id=suggested_cid,
                                         plans=plans)
        self._step_enrollment = StepEnrollment()
        self._step_auths = StepAuths()
        self._step_review = StepReview()
        # Steps 0-2 have no internal scroll area, so they're wrapped here;
        # StepReview already scrolls its own body and is added as-is. Only
        # the scroll wrappers go on the stack — self._step_* keeps pointing
        # at the actual page objects for validate()/collect()/populate().
        for step in (self._step_contact, self._step_enrollment, self._step_auths):
            self._stack.addWidget(_scrolled(step))
        self._stack.addWidget(self._step_review)
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
            dot.setFixedSize(px(28), px(28))
            dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            dot.setStyleSheet(self._dot_style(i, 0))
            self._dots.append(dot)
            dot_row.addWidget(dot)
            if i < 3:
                line = QLabel()
                line.setFixedHeight(1)
                line.setFixedWidth(px(64))
                line.setStyleSheet("background: #282c38;")
                dot_row.addWidget(line)

        lbl_row = QHBoxLayout()
        for label in STEP_LABELS:
            lbl = QLabel(label)
            lbl.setFixedWidth(px(84))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setWordWrap(True)
            lbl.setStyleSheet(f"font-size:{px(10)}px; color:#31354a;")
            lbl_row.addWidget(lbl)

        layout.addLayout(dot_row)
        layout.addLayout(lbl_row)
        return widget

    def _dot_style(self, dot_index: int, current: int) -> str:
        r, fs = px(14), px(11)     # radius = half the dot so it stays a circle
        if dot_index < current:
            return (f"background:#3d9e6e; color:white; border-radius:{r}px;"
                    f"font-weight:700; font-size:{fs}px;")
        if dot_index == current:
            return (f"background:#5b7cf4; color:white; border-radius:{r}px;"
                    f"font-weight:700; font-size:{fs}px; border:3px solid #1c2040;")
        return (f"background:#1e2128; color:#31354a; border-radius:{r}px;"
                f"border:1px solid #282c38; font-size:{fs}px;")

    def _update_progress(self):
        for i, dot in enumerate(self._dots):
            dot.setStyleSheet(self._dot_style(i, self._current))

    def _go_next(self):
        if self._current == 0:
            if not self._step_contact.validate(self._db_path):
                return
        if self._current == 1:
            if not self._step_enrollment.validate():
                QMessageBox.warning(self, "Validation",
                    "Enter a valid Enrollment Start date (MM/DD/YYYY); "
                    "leave End blank for ongoing.")
                return
        if self._current == 2:
            if not self._step_auths.validate():
                QMessageBox.warning(self, "Validation",
                    "Complete the authorization — valid Auth Start and Auth "
                    "End dates (MM/DD/YYYY), at least one day, a plan type, "
                    "and an auth number — or clear all of it to skip this "
                    "step.")
                return
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
                gender=c.get("gender", ""),
                transport_authorization=data.get("transport_authorization"),
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
            from gui.errors import show_db_error
            show_db_error(self, exc, "Could Not Create Member")
