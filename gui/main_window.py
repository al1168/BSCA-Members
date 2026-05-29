from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QListWidget, QListWidgetItem, QPushButton, QLineEdit, QLabel,
    QStackedWidget, QApplication, QMessageBox,
)
from PyQt6.QtCore import Qt

from settings import save_settings
from gui.settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    def __init__(self, settings: dict, settings_path: str):
        super().__init__()
        self._settings = settings
        self._settings_path = settings_path
        self.setWindowTitle("BSCA Member Manager")
        self.resize(1000, 640)
        self._build_ui()
        self._load_members()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Sidebar ──────────────────────────────────────────
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(10, 10, 10, 10)
        sidebar_layout.setSpacing(6)

        self._btn_add = QPushButton("+ Add New Member")
        self._btn_add.setObjectName("btn_add")
        self._btn_add.clicked.connect(self._open_wizard)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search members…")
        self._search.textChanged.connect(self._filter_members)

        self._member_list = QListWidget()
        self._member_list.currentRowChanged.connect(self._on_member_selected)

        self._btn_events = QPushButton("All Events")
        self._btn_events.clicked.connect(self._show_global_events)

        sidebar_layout.addWidget(self._btn_add)
        sidebar_layout.addWidget(self._search)
        sidebar_layout.addWidget(self._member_list)
        sidebar_layout.addWidget(self._btn_events)

        # ── Detail panel ─────────────────────────────────────
        self._detail_stack = QStackedWidget()
        self._detail_stack.setObjectName("detail")

        self._placeholder = QLabel("No database configured.\nOpen ⚙ Settings to set the database path.")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._detail_stack.addWidget(self._placeholder)  # index 0

        # ── Toolbar with settings gear ────────────────────────
        toolbar = self.addToolBar("Main")
        toolbar.setMovable(False)
        btn_settings = QPushButton("⚙")
        btn_settings.setFixedSize(32, 32)
        btn_settings.clicked.connect(self._open_settings)
        toolbar.addWidget(btn_settings)

        root.addWidget(sidebar)
        root.addWidget(self._detail_stack)

    def _load_members(self):
        self._all_members = []
        db_path = self._settings.get("db_path", "")
        if not db_path:
            self._placeholder.setText(
                "No database configured.\nOpen ⚙ Settings to set the database path."
            )
            return
        try:
            from db.members import get_all_members
            self._all_members = get_all_members(db_path)
        except Exception as exc:
            QMessageBox.critical(self, "Database Error",
                f"Could not load members:\n{exc}\n\nCheck Settings.")
        self._populate_list(self._all_members)

    def _populate_list(self, members: list[dict]):
        self._member_list.clear()
        for m in members:
            label = f"{m['last_name']}, {m['first_name']}\n{m['center_id']} · {m['health_plan']}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, m["center_id"])
            self._member_list.addItem(item)

    def _filter_members(self, text: str):
        q = text.lower()
        filtered = [
            m for m in self._all_members
            if q in m["last_name"].lower()
            or q in m["first_name"].lower()
            or q in str(m["center_id"])
        ]
        self._populate_list(filtered)

    def _on_member_selected(self, row: int):
        if row < 0:
            return
        # Guard: check if current detail widget has unsaved changes
        if self._detail_stack.count() > 1:
            current = self._detail_stack.widget(1)
            if hasattr(current, "is_dirty") and current.is_dirty():
                reply = QMessageBox.question(
                    self, "Unsaved Changes",
                    "You have unsaved changes. Discard them?",
                    QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                )
                if reply != QMessageBox.StandardButton.Discard:
                    self._member_list.blockSignals(True)
                    self._member_list.setCurrentRow(-1)
                    self._member_list.blockSignals(False)
                    return
        item = self._member_list.item(row)
        if item is None:
            return
        center_id = item.data(Qt.ItemDataRole.UserRole)
        self._show_member(center_id)

    def _show_member(self, center_id: int):
        from gui.member_tabs import MemberTabsWidget
        db_path = self._settings.get("db_path", "")
        events_path = self._settings.get("events_db_path", "")
        widget = MemberTabsWidget(center_id, db_path, events_path)
        self._set_detail(widget)

    def _set_detail(self, widget: QWidget):
        while self._detail_stack.count() > 1:
            w = self._detail_stack.widget(1)
            self._detail_stack.removeWidget(w)
            w.deleteLater()
        self._detail_stack.addWidget(widget)
        self._detail_stack.setCurrentIndex(1)

    def _show_global_events(self):
        from gui.events_view import GlobalEventsWidget
        events_path = self._settings.get("events_db_path", "")
        widget = GlobalEventsWidget(events_path)
        self._set_detail(widget)

    def _open_wizard(self):
        db_path = self._settings.get("db_path", "")
        if not db_path:
            QMessageBox.warning(self, "No Database",
                "Set a database path in Settings before adding members.")
            return
        from gui.wizard.wizard import AddMemberWizard
        events_path = self._settings.get("events_db_path", "")
        dlg = AddMemberWizard(db_path, events_path, self)
        if dlg.exec():
            self._load_members()

    def _open_settings(self):
        dlg = SettingsDialog(self._settings, self)
        if dlg.exec():
            self._settings.update(dlg.result_settings())
            save_settings(self._settings, self._settings_path)
            from gui.theme import apply_theme
            apply_theme(QApplication.instance(), self._settings["theme"])
            self._load_members()
