from PyQt6.QtWidgets import (
    QWidget, QFormLayout, QLineEdit, QComboBox, QLabel, QVBoxLayout, QDateEdit,
)
from PyQt6.QtCore import QDate
from db.members import HEALTH_PLANS
from gui.address_autocomplete import AddressAutocomplete

# DOB is required, but a QDateEdit always holds a value. We start it on this
# sentinel (= its minimumDate, shown as "Select date of birth") and treat the
# field as unset until the user moves off it. Same trick as the Enrollment End
# date in step_enrollment.
DOB_SENTINEL = QDate(1900, 1, 1)


class StepContact(QWidget):
    def __init__(self, api_key: str = "", parent=None):
        super().__init__(parent)
        self._api_key = api_key or ""
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
        self.member_id = QLineEdit()
        self.member_id.setPlaceholderText("Health plan member / insurance ID")
        self.dob = QDateEdit()
        self.dob.setCalendarPopup(True)
        self.dob.setDisplayFormat("M/d/yyyy")
        self.dob.setMinimumDate(DOB_SENTINEL)
        self.dob.setMaximumDate(QDate.currentDate())  # no future birth dates
        self.dob.setSpecialValueText("Select date of birth")
        self.dob.setDate(DOB_SENTINEL)
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
        if self.dob.date() == DOB_SENTINEL:
            self._error_label.setText("Date of Birth is required.")
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
            "dob": (self.dob.date().toPyDate()
                    if self.dob.date() != DOB_SENTINEL else None),
            "health_plan": self.health_plan.currentText(),
            "home_tell": self.home_tell.text().strip(),
            "cell": self.cell.text().strip(),
            "address": self.address.text().strip(),
            "long_lat": self.address.long_lat(),
        }
