from PyQt6.QtWidgets import (
    QWidget, QFormLayout, QLineEdit, QComboBox, QLabel, QVBoxLayout,
)
from db.members import HEALTH_PLANS


class StepContact(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
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
        self.health_plan = QComboBox()
        self.health_plan.addItem("")
        self.health_plan.addItems(HEALTH_PLANS)
        self.address = QLineEdit()
        self.address.setPlaceholderText("Street, City, State ZIP")

        form.addRow("First Name *", self.first_name)
        form.addRow("Last Name *", self.last_name)
        form.addRow("Center ID *", self.center_id)
        form.addRow("Health Plan *", self.health_plan)
        form.addRow("Address", self.address)

        layout.addLayout(form)
        layout.addWidget(self._error_label)
        layout.addStretch()

    def validate(self, db_path: str) -> bool:
        self._error_label.setText("")
        fn = self.first_name.text().strip()
        ln = self.last_name.text().strip()
        cid_text = self.center_id.text().strip()
        plan = self.health_plan.currentText()

        if not fn or not ln:
            self._error_label.setText("First and Last Name are required.")
            return False
        if not plan:
            self._error_label.setText("Health Plan is required.")
            return False
        try:
            cid = int(cid_text)
            if cid <= 0:
                raise ValueError
        except ValueError:
            self._error_label.setText("Center ID must be a positive integer.")
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
            "health_plan": self.health_plan.currentText(),
            "address": self.address.text().strip(),
        }
