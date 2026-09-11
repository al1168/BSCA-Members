from datetime import date

from PyQt6.QtWidgets import QWidget, QFormLayout, QLabel, QVBoxLayout
from gui.address_autocomplete import DateLineEdit
from gui.theme import px


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

        form.addRow("Enrollment Start *", self.start_date)

        note = QLabel(
            "Enrollment begins on the start date and is ongoing. "
            "You can set an end date later from the Enrollments tab."
        )
        note.setWordWrap(True)
        note.setStyleSheet(f"color: gray; font-size: {px(11)}px;")

        layout.addLayout(form)
        layout.addWidget(note)
        layout.addStretch()

    def validate(self) -> bool:
        """Start is required; enrollment is created ongoing (no end date)."""
        return self.start_date.flag_validity(required=True)

    def collect(self) -> dict:
        return {
            "enrollment_start": self.start_date.to_pydate(),
            "enrollment_end": None,   # ongoing; an end date is set later if needed
        }
