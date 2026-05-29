from PyQt6.QtWidgets import QWidget, QFormLayout, QDateEdit, QLabel, QVBoxLayout
from PyQt6.QtCore import QDate


class StepEnrollment(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(12)

        self.start_date = QDateEdit(QDate.currentDate())
        self.start_date.setCalendarPopup(True)

        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setSpecialValueText("Ongoing (leave blank)")
        self.end_date.setDate(QDate(2000, 1, 1))

        form.addRow("Enrollment Start *", self.start_date)
        form.addRow("Enrollment End (optional)", self.end_date)

        note = QLabel(
            "Enrollment begins on the start date. "
            "Leave End blank for ongoing enrollment."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: gray; font-size: 11px;")

        layout.addLayout(form)
        layout.addWidget(note)
        layout.addStretch()

    def collect(self) -> dict:
        end = self.end_date.date()
        return {
            "enrollment_start": self.start_date.date().toPyDate(),
            "enrollment_end": end.toPyDate() if end != QDate(2000, 1, 1) else None,
        }
