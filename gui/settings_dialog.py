from PyQt6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QPushButton, QHBoxLayout,
    QVBoxLayout, QRadioButton, QButtonGroup, QFileDialog, QDialogButtonBox,
    QLabel, QWidget, QCheckBox,
)
from PyQt6.QtCore import Qt

from gui.theme import px


class SettingsDialog(QDialog):
    def __init__(self, settings: dict, parent=None, alt_id_password: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(px(480))
        self._settings = dict(settings)
        # Session-only secret: shown/edited here but NEVER part of
        # result_settings(), so it can't reach the settings JSON on disk.
        self._alt_id_password = alt_id_password
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

        # Google API key: blocked off (masked, read-only) by default so the
        # secret isn't shown in the clear. "Edit" reveals + unlocks it.
        api_row = QWidget()
        api_hl = QHBoxLayout(api_row)
        api_hl.setContentsMargins(0, 0, 0, 0)
        self._api_key = QLineEdit(self._settings.get("google_api_key", ""))
        self._api_key.setPlaceholderText("Google Maps Platform API key (Places API)")
        self._api_edit_btn = QPushButton("Edit")
        self._api_edit_btn.clicked.connect(self._toggle_api_edit)
        api_hl.addWidget(self._api_key)
        api_hl.addWidget(self._api_edit_btn)
        form.addRow("Google API key:", api_row)
        # An existing key opens locked + masked; an empty one opens ready to type.
        self._set_api_locked(bool(self._settings.get("google_api_key", "")))

        # Alt ID password: decrypts the encrypted alt_id column for this
        # session only — deliberately kept out of result_settings() so it is
        # never written to disk. Same lock pattern as the API key.
        altpw_row = QWidget()
        altpw_hl = QHBoxLayout(altpw_row)
        altpw_hl.setContentsMargins(0, 0, 0, 0)
        self._altpw = QLineEdit(self._alt_id_password)
        self._altpw.setPlaceholderText("Session only — never saved to disk")
        self._altpw.setToolTip(
            "Enter the password you were given, if any. It applies to this "
            "session only. Leave empty otherwise.")
        self._altpw_edit_btn = QPushButton("Edit")
        self._altpw_edit_btn.clicked.connect(self._toggle_altpw_edit)
        altpw_hl.addWidget(self._altpw)
        altpw_hl.addWidget(self._altpw_edit_btn)
        form.addRow("Session password:", altpw_row)
        self._set_altpw_locked(bool(self._alt_id_password))

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

        # App-wide text size. Large/Extra Large enlarge every on-screen font
        # (and the rows/panels that hold text); the main window reopens to
        # apply it. Printouts are unaffected.
        size_row = QWidget()
        size_hl = QHBoxLayout(size_row)
        size_hl.setContentsMargins(0, 0, 0, 0)
        self._radio_size_normal = QRadioButton("Normal")
        self._radio_size_large = QRadioButton("Large")
        self._radio_size_xlarge = QRadioButton("Extra Large")
        self._size_radios = {"normal": self._radio_size_normal,
                             "large": self._radio_size_large,
                             "xlarge": self._radio_size_xlarge}
        self._text_size_group = QButtonGroup()
        for b in self._size_radios.values():
            self._text_size_group.addButton(b)
            size_hl.addWidget(b)
        current = self._settings.get("text_size", "normal")
        self._size_radios.get(current, self._radio_size_normal).setChecked(True)
        size_row.setToolTip(
            "Make all text in the program larger. The window reopens to apply "
            "the new size; printed reports keep their normal size.")
        form.addRow("Text size:", size_row)

        # Debug: reveal the internal row "ID" column in the member tables.
        self._show_row_ids = QCheckBox("Show row ID columns (debug)")
        self._show_row_ids.setChecked(bool(self._settings.get("show_row_ids", False)))
        self._show_row_ids.setToolTip(
            "Show each table row's internal database id (e.g. 442). "
            "Off by default; turn on only for debugging.")
        form.addRow("Debug:", self._show_row_ids)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _set_api_locked(self, locked: bool):
        """Locked = blocked off: masked and read-only. Unlocked = revealed and
        editable. The button always offers the opposite action."""
        self._api_key.setReadOnly(locked)
        self._api_key.setEchoMode(
            QLineEdit.EchoMode.Password if locked else QLineEdit.EchoMode.Normal)
        self._api_edit_btn.setText("Edit" if locked else "Hide")

    def _toggle_api_edit(self):
        was_locked = self._api_key.isReadOnly()
        self._set_api_locked(not was_locked)
        if was_locked:                 # just unlocked -> ready to edit
            self._api_key.setFocus()

    def _set_altpw_locked(self, locked: bool):
        self._altpw.setReadOnly(locked)
        self._altpw.setEchoMode(
            QLineEdit.EchoMode.Password if locked else QLineEdit.EchoMode.Normal)
        self._altpw_edit_btn.setText("Edit" if locked else "Hide")

    def _toggle_altpw_edit(self):
        was_locked = self._altpw.isReadOnly()
        self._set_altpw_locked(not was_locked)
        if was_locked:
            self._altpw.setFocus()

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
        # The alt-id password is intentionally absent: this dict is persisted
        # to the settings JSON, and the password must stay session-only.
        return {
            "db_path": self._db_path.text().strip(),
            "events_db_path": self._events_path.text().strip(),
            "theme": "light" if self._radio_light.isChecked() else "dark",
            "google_api_key": self._api_key.text().strip(),
            "show_row_ids": self._show_row_ids.isChecked(),
            "text_size": next((name for name, b in self._size_radios.items()
                               if b.isChecked()), "normal"),
        }

    def result_alt_id_password(self) -> str:
        # Verbatim (no strip) — must match the encryptor tool byte-for-byte.
        return self._altpw.text()
