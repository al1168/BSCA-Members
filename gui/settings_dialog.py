from PyQt6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QPushButton, QHBoxLayout,
    QVBoxLayout, QRadioButton, QButtonGroup, QFileDialog, QDialogButtonBox,
    QLabel, QWidget,
)
from PyQt6.QtCore import Qt


class SettingsDialog(QDialog):
    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(480)
        self._settings = dict(settings)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)

        # DB path
        db_row = QWidget()
        db_hl = QHBoxLayout(db_row)
        db_hl.setContentsMargins(0, 0, 0, 0)
        self._db_path = QLineEdit(self._settings.get("db_path", ""))
        btn_browse_db = QPushButton("Browse…")
        btn_browse_db.clicked.connect(self._browse_db)
        db_hl.addWidget(self._db_path)
        db_hl.addWidget(btn_browse_db)
        form.addRow("Database path:", db_row)

        # Events DB path
        ev_row = QWidget()
        ev_hl = QHBoxLayout(ev_row)
        ev_hl.setContentsMargins(0, 0, 0, 0)
        self._events_path = QLineEdit(self._settings.get("events_db_path", ""))
        btn_browse_ev = QPushButton("Browse…")
        btn_browse_ev.clicked.connect(self._browse_events)
        ev_hl.addWidget(self._events_path)
        ev_hl.addWidget(btn_browse_ev)
        form.addRow("Events log path:", ev_row)

        # Google API key
        self._api_key = QLineEdit(self._settings.get("google_api_key", ""))
        self._api_key.setPlaceholderText("Google Maps Platform API key (Places API)")
        form.addRow("Google API key:", self._api_key)

        # Theme
        theme_row = QWidget()
        theme_hl = QHBoxLayout(theme_row)
        theme_hl.setContentsMargins(0, 0, 0, 0)
        self._radio_dark = QRadioButton("Dark")
        self._radio_light = QRadioButton("Light")
        self._theme_group = QButtonGroup()
        self._theme_group.addButton(self._radio_dark)
        self._theme_group.addButton(self._radio_light)
        if self._settings.get("theme", "dark") == "light":
            self._radio_light.setChecked(True)
        else:
            self._radio_dark.setChecked(True)
        theme_hl.addWidget(self._radio_dark)
        theme_hl.addWidget(self._radio_light)
        form.addRow("Theme:", theme_row)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse_db(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Database", "", "Access Databases (*.accdb *.mdb)"
        )
        if path:
            self._db_path.setText(path)

    def _browse_events(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Events Log Location", "events.db", "SQLite (*.db)"
        )
        if path:
            self._events_path.setText(path)

    def result_settings(self) -> dict:
        return {
            "db_path": self._db_path.text().strip(),
            "events_db_path": self._events_path.text().strip(),
            "theme": "light" if self._radio_light.isChecked() else "dark",
            "google_api_key": self._api_key.text().strip(),
        }
