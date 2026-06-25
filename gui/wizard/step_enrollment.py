from datetime import date

from PyQt6.QtWidgets import QWidget, QFormLayout, QLabel, QVBoxLayout
from gui.address_autocomplete import DateLineEdit


class StepEnrollment(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(12)

        self.start_date = DateLineEdit()
        self.start_date.set_pydate(date.today())

        self.end_date = DateLineEdit()   # blank = ongoing

        form.addRow("Enrollment Start *", self.start_date)
        form.addRow("Enrollment End (blank = ongoing)", self.end_date)

        note = QLabel(
            "Enrollment begins on the start date. "
            "Leave End blank for ongoing enrollment."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: gray; font-size: 11px;")

        layout.addLayout(form)
        layout.addWidget(note)
        layout.addStretch()

    def validate(self) -> bool:
        """Start is required; End is optional (blank = ongoing)."""
        ok = self.start_date.flag_validity(required=True)
        ok = self.end_date.flag_validity() and ok
        return ok

    def collect(self) -> dict:
        return {
            "enrollment_start": self.start_date.to_pydate(),
            "enrollment_end": self.end_date.to_pydate(),   # None when blank
        }
