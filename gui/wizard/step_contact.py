import re
from datetime import date, datetime

from PyQt6.QtWidgets import (
    QWidget, QFormLayout, QLineEdit, QComboBox, QLabel, QVBoxLayout,
)
from db.members import HEALTH_PLANS, format_phone
from gui.address_autocomplete import (
    AddressAutocomplete, PhoneLineEdit, set_widget_error,
)

# DOB is a free-text field (so staff can type it) with a gray placeholder, not a
# date-picker dropdown. The format is enforced: slash-separated, a 1-or-2-digit
# month and day, and a 4-digit year (MM/DD/YYYY or M/DD/YYYY, etc.). Output is a
# datetime.date for the Access Date/Time [DOB] column.
_DOB_RE = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")


def parse_dob(text: str):
    """Parse a typed date of birth to a datetime.date, or None if it doesn't
    match M/D/YYYY (1-2 digit month & day, slashes, 4-digit year) or isn't a
    real calendar date. Dashes, 2-digit years and out-of-range values are
    rejected."""
    text = (text or "").strip()
    if not _DOB_RE.match(text):
        return None
    try:
        return datetime.strptime(text, "%m/%d/%Y").date()
    except ValueError:
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
        self.gender = QComboBox()
        self.gender.addItems(["", "M", "F"])
        self.health_plan = QComboBox()
        self.health_plan.addItem("")
        self.health_plan.addItems(HEALTH_PLANS)
        # Phone fields: type just digits; they auto-format to (xxx)-xxx-xxxx on
        # leaving the field, and outline red if the entry isn't 10 digits.
        self.home_tell = PhoneLineEdit()
        self.cell = PhoneLineEdit()
        self.address = AddressAutocomplete(self._api_key)
        self.address.setPlaceholderText("Street, City, State ZIP")

        phone_hint = QLabel("Enter at least one phone number (just digits is fine).")
        phone_hint.setStyleSheet("color: #7a7f93; font-size: 10px;")

        # Clear a field's error outline as soon as the user edits it.
        for w in (self.first_name, self.last_name, self.center_id,
                  self.member_id, self.dob):
            w.textEdited.connect(lambda _t, w=w: set_widget_error(w, False))
        self.health_plan.currentIndexChanged.connect(
            lambda: set_widget_error(self.health_plan, False))

        form.addRow("First Name *", self.first_name)
        form.addRow("Last Name *", self.last_name)
        form.addRow("Center ID *", self.center_id)
        form.addRow("Member ID *", self.member_id)
        form.addRow("Date of Birth *", self.dob)
        form.addRow("Gender", self.gender)
        form.addRow("Health Plan *", self.health_plan)
        form.addRow("Home Phone", self.home_tell)
        form.addRow("Cell", self.cell)
        form.addRow("", phone_hint)
        form.addRow("Address *", self.address)

        layout.addLayout(form)
        layout.addWidget(self._error_label)
        layout.addStretch()

    def _clear_errors(self):
        for w in (self.first_name, self.last_name, self.center_id,
                  self.member_id, self.dob, self.health_plan,
                  self.home_tell, self.cell):
            set_widget_error(w, False)
        self.address.set_error(False)

    def _fail(self, message: str, *widgets) -> bool:
        """Show the message and outline the offending field(s); returns False."""
        self._error_label.setText(message)
        for w in widgets:
            (w.set_error(True) if isinstance(w, AddressAutocomplete)
             else set_widget_error(w, True))
        return False

    def validate(self, db_path: str) -> bool:
        self._error_label.setText("")
        self._clear_errors()
        fn = self.first_name.text().strip()
        ln = self.last_name.text().strip()
        cid_text = self.center_id.text().strip()
        member_id = self.member_id.text().strip()
        plan = self.health_plan.currentText()
        home_tell = self.home_tell.text().strip()
        cell = self.cell.text().strip()
        address = self.address.text().strip()

        if not fn or not ln:
            return self._fail(
                "First and Last Name are required.",
                *([self.first_name] if not fn else []),
                *([self.last_name] if not ln else []))
        try:
            cid = int(cid_text)
            if cid <= 0:
                raise ValueError
        except ValueError:
            return self._fail("Center ID must be a positive integer.", self.center_id)
        if not member_id:
            return self._fail("Member ID is required.", self.member_id)
        dob_text = self.dob.text().strip()
        if not dob_text:
            return self._fail("Date of Birth is required.", self.dob)
        dob = parse_dob(dob_text)
        if dob is None:
            return self._fail(
                "Date of Birth must be a valid date (MM/DD/YYYY).", self.dob)
        if dob > date.today():
            return self._fail("Date of Birth can't be in the future.", self.dob)
        if not plan:
            return self._fail("Health Plan is required.", self.health_plan)
        if not home_tell and not cell:
            return self._fail(
                "Enter at least one phone number (Home Phone or Cell).",
                self.home_tell, self.cell)
        # Any provided phone must be a valid 10-digit US number.
        for w in (self.home_tell, self.cell):
            if w.text().strip() and not w.is_valid():
                return self._fail(
                    "Phone numbers must be 10 digits.", w)
        if not address:
            return self._fail("Address is required.", self.address)
        from db.members import center_id_exists
        if center_id_exists(cid, db_path):
            return self._fail(
                f"Center ID {cid} already exists in the database.", self.center_id)
        return True

    def collect(self) -> dict:
        return {
            "first_name": self.first_name.text().strip(),
            "last_name": self.last_name.text().strip(),
            "center_id": int(self.center_id.text().strip()),
            "member_id": self.member_id.text().strip(),
            "dob": parse_dob(self.dob.text().strip()),
            "gender": self.gender.currentText(),
            "health_plan": self.health_plan.currentText(),
            "home_tell": format_phone(self.home_tell.text().strip()),
            "cell": format_phone(self.cell.text().strip()),
            "address": self.address.text().strip(),
            "long_lat": self.address.long_lat(),
        }
