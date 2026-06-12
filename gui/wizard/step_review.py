from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea
from PyQt6.QtCore import Qt


class StepReview(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        title = QLabel("Review your entries before saving.")
        title.setStyleSheet("font-size:12px; color:gray;")
        layout.addWidget(title)
        self._body = QLabel("")
        self._body.setWordWrap(True)
        self._body.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll = QScrollArea()
        scroll.setWidget(self._body)
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)

    def populate(self, data: dict):
        m = data.get("contact", {})
        auth = data.get("authorization")
        avail = data.get("availability_rows", [])
        lines = [
            "<b>Contact Info</b>",
            f"Name: {m.get('last_name')}, {m.get('first_name')}",
            f"Center ID: {m.get('center_id')}",
            f"Member ID: {m.get('member_id') or '—'}",
            f"Date of Birth: {m.get('dob') or '—'}",
            f"Health Plan: {m.get('health_plan')}",
            f"Home Phone: {m.get('home_tell') or '—'}",
            f"Cell: {m.get('cell') or '—'}",
            f"Address: {m.get('address') or '—'}",
            "",
            "<b>Enrollment</b>",
            f"Start: {data.get('enrollment_start')}",
            f"End: {data.get('enrollment_end') or 'Ongoing'}",
        ]
        if auth:
            from db.members import encode_auth_days
            lines += [
                "",
                "<b>Authorization</b>",
                f"Period: {auth['auth_start']} – {auth['auth_end']}",
                f"Days: {encode_auth_days(auth['auth_days'])}",
            ]
        if avail:
            day_names = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri"}
            lines += ["", "<b>Availability</b>"]
            for row in avail:
                lines.append(
                    f"{day_names.get(row['day_of_week'], '?')}: "
                    f"{row['avail_start']} – {row['avail_end']}"
                )
        self._body.setText("<br>".join(lines))
