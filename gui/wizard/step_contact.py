from datetime import date, datetime

from PyQt6.QtWidgets import (
    QWidget, QFormLayout, QLineEdit, QComboBox, QLabel, QVBoxLayout,
)
from db.members import HEALTH_PLANS
from gui.address_autocomplete import AddressAutocomplete

# DOB is a free-text field (so staff can type it) with a gray placeholder, not a
# date-picker dropdown. These are the formats we accept when parsing what they
# type; output is a datetime.date for the Access Date/Time [DOB] column.
_DOB_FORMATS = ("%m/%d/%Y", "%m-%d-%Y")


def parse_dob(text: str):
    """Parse a typed date of birth to a datetime.date, or None if blank/invalid.

    Accepts M/D/YYYY or M-D-YYYY (non-zero-padded months/days are fine)."""
    text = (text or "").strip()
    for fmt in _DOB_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


class StepContact(QWidget):
    def __init__(self, api_key: str = "", center_id: int | None = None, parent=None):
        super().__init__(parent)
        self._api_key = api_key or ""
        self._suggested_center_id = center_id
        self._error_label = QLabel("")
        self._error_label.setStyleSheet("color: #d05555; font-size: 11px;")
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(12)

        self.first_name = QLineEdit()
        self.first_name.setPlaceholderText("First name")
        self.last_name = QLineEdit()
        self.last_name.setPlaceholderText("Last name")
        self.center_id = QLineEdit()
        self.center_id.setPlaceholderText("e.g. 10042")
        if self._suggested_center_id is not None:
            # Auto-assigned next Center ID — locked so staff can't alter the
            # numbering scheme. Falls back to an editable field if no suggestion
            # could be computed (e.g. a DB hiccup).
            self.center_id.setText(str(self._suggested_center_id))
            self.center_id.setReadOnly(True)
        self.member_id = QLineEdit()
        self.member_id.setPlaceholderText("Health plan member / insurance ID")
        self.dob = QLineEdit()
        self.dob.setPlaceholderText("Select date of birth (MM/DD/YYYY)")
        self.health_plan = QComboBox()
        self.health_plan.addItem("")
        self.health_plan.addItems(HEALTH_PLANS)
        self.home_tell = QLineEdit()
        self.home_tell.setPlaceholderText("e.g. 212-555-0100")
        self.cell = QLineEdit()
        self.cell.setPlaceholderText("e.g. 646-555-0199")
        self.address = AddressAutocomplete(self._api_key)
        self.address.setPlaceholderText("Street, City, State ZIP")

        phone_hint = QLabel("Enter at least one phone number.")
        phone_hint.setStyleSheet("color: #7a7f93; font-size: 10px;")

        form.addRow("First Name *", self.first_name)
        form.addRow("Last Name *", self.last_name)
        form.addRow("Center ID *", self.center_id)
        form.addRow("Member ID *", self.member_id)
        form.addRow("Date of Birth *", self.dob)
        form.addRow("Health Plan *", self.health_plan)
        form.addRow("Home Phone", self.home_tell)
        form.addRow("Cell", self.cell)
        form.addRow("", phone_hint)
        form.addRow("Address *", self.address)

        layout.addLayout(form)
        layout.addWidget(self._error_label)
        layout.addStretch()

    def validate(self, db_path: str) -> bool:
        self._error_label.setText("")
        fn = self.first_name.text().strip()
        ln = self.last_name.text().strip()
        cid_text = self.center_id.text().strip()
        member_id = self.member_id.text().strip()
        plan = self.health_plan.currentText()
        home_tell = self.home_tell.text().strip()
        cell = self.cell.text().strip()
        address = self.address.text().strip()

        if not fn or not ln:
            self._error_label.setText("First and Last Name are required.")
            return False
        try:
            cid = int(cid_text)
            if cid <= 0:
                raise ValueError
        except ValueError:
            self._error_label.setText("Center ID must be a positive integer.")
            return False
        if not member_id:
            self._error_label.setText("Member ID is required.")
            return False
        dob_text = self.dob.text().strip()
        if not dob_text:
            self._error_label.setText("Date of Birth is required.")
            return False
        dob = parse_dob(dob_text)
        if dob is None:
            self._error_label.setText(
                "Date of Birth must be a valid date (MM/DD/YYYY)."
            )
            return False
        if dob > date.today():
            self._error_label.setText("Date of Birth can't be in the future.")
            return False
        if not plan:
            self._error_label.setText("Health Plan is required.")
            return False
        if not home_tell and not cell:
            self._error_label.setText(
                "Enter at least one phone number (Home Phone or Cell)."
            )
            return False
        if not address:
            self._error_label.setText("Address is required.")
            return False
        from db.members import center_id_exists
        if center_id_exists(cid, db_path):
            self._error_label.setText(f"Center ID {cid} already exists in the database.")
            return False
        return True

    def collect(self) -> dict:
        return {
            "first_name": self.first_name.text().strip(),
            "last_name": self.last_name.text().strip(),
            "center_id": int(self.center_id.text().strip()),
            "member_id": self.member_id.text().strip(),
            "dob": parse_dob(self.dob.text().strip()),
            "health_plan": self.health_plan.currentText(),
            "home_tell": self.home_tell.text().strip(),
            "cell": self.cell.text().strip(),
            "address": self.address.text().strip(),
            "long_lat": self.address.long_lat(),
        }
