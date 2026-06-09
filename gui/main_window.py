import os

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QListWidget, QListWidgetItem, QPushButton, QLineEdit, QLabel,
    QStackedWidget, QApplication, QMessageBox, QSizePolicy,
    QStyledItemDelegate, QStyle, QStyleOptionViewItem,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextDocument, QAbstractTextDocumentLayout

from settings import save_settings
from gui.settings_dialog import SettingsDialog


TERMINATED_ROLE = Qt.ItemDataRole.UserRole + 1


def active_first(members: list[dict], terminated_ids: set) -> list[dict]:
    """Stable-sort members so active ones precede terminated ones, preserving the
    input order (alphabetical) within each group."""
    return sorted(members, key=lambda m: m["center_id"] in terminated_ids)


class _MemberItemDelegate(QStyledItemDelegate):
    """Paints terminated member rows with a dimmed name and a red TERMINATED tag.
    Active rows fall through to the default rendering."""

    def __init__(self, parent=None, muted="#888888", tag="#d05555"):
        super().__init__(parent)
        self._muted = muted
        self._tag = tag

    def set_colors(self, muted: str, tag: str) -> None:
        self._muted = muted
        self._tag = tag

    def paint(self, painter, option, index):
        if not index.data(TERMINATED_ROLE):
            super().paint(painter, option, index)
            return
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        name, _, sub = opt.text.partition("\n")
        opt.text = ""
        style = opt.widget.style() if opt.widget else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)
        html = (
            f"<span style='color:{self._muted}'>{name}<br>{sub}</span>"
            f"&nbsp;&nbsp;<span style='color:{self._tag}; font-weight:700'>"
            f"⊘ TERMINATED</span>"
        )
        doc = QTextDocument()
        doc.setDefaultFont(opt.font)
        doc.setHtml(html)
        doc.setTextWidth(opt.rect.width() - 12)
        painter.save()
        painter.translate(opt.rect.left() + 6, opt.rect.top() + 3)
        doc.documentLayout().draw(painter, QAbstractTextDocumentLayout.PaintContext())
        painter.restore()


class MainWindow(QMainWindow):
    def __init__(self, settings: dict, settings_path: str):
        super().__init__()
        self._settings = settings
        self._settings_path = settings_path
        self._last_center_id = None
        self._terminated_ids = set()
        self.setWindowTitle("BSCA Member Manager")
        self.resize(1240, 800)
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
        self._member_delegate = _MemberItemDelegate(self._member_list)
        self._member_list.setItemDelegate(self._member_delegate)
        self._refresh_list_theme()

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

        # ── Toolbar: current DB indicator + settings ──────────
        toolbar = self.addToolBar("Main")
        toolbar.setObjectName("main_toolbar")
        toolbar.setMovable(False)

        self._db_indicator = QLabel()
        self._db_indicator.setObjectName("db_indicator")
        toolbar.addWidget(self._db_indicator)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)

        btn_settings = QPushButton("⚙  Settings")
        btn_settings.setObjectName("btn_settings")
        btn_settings.clicked.connect(self._open_settings)
        toolbar.addWidget(btn_settings)

        self._update_db_indicator()

        root.addWidget(sidebar)
        root.addWidget(self._detail_stack)

    def _update_db_indicator(self):
        """Show the current database filename in the toolbar."""
        db_path = self._settings.get("db_path", "")
        if db_path:
            self._db_indicator.setText(f"  📁  {os.path.basename(db_path)}")
            self._db_indicator.setToolTip(db_path)
            self._db_indicator.setProperty("connected", True)
        else:
            self._db_indicator.setText("  ⚠  No database selected")
            self._db_indicator.setToolTip("Open Settings to choose a database")
            self._db_indicator.setProperty("connected", False)
        # Re-polish so the [connected] property selector restyles the label.
        self._db_indicator.style().unpolish(self._db_indicator)
        self._db_indicator.style().polish(self._db_indicator)

    def _refresh_list_theme(self):
        from gui.theme import DARK, LIGHT
        tokens = DARK if self._settings.get("theme") == "dark" else LIGHT
        self._member_delegate.set_colors(tokens["text2"], tokens["error"])
        self._member_list.viewport().update()

    def _load_members(self):
        self._all_members = []
        db_path = self._settings.get("db_path", "")
        if not db_path:
            self._placeholder.setText(
                "No database configured.\nOpen ⚙ Settings to set the database path."
            )
            return
        try:
            from db.members import get_all_members, get_terminated_center_ids
            self._all_members = get_all_members(db_path)
            try:
                self._terminated_ids = get_terminated_center_ids(db_path)
            except Exception:
                self._terminated_ids = set()
        except Exception as exc:
            QMessageBox.critical(self, "Database Error",
                f"Could not load members:\n{exc}\n\nCheck Settings.")
        self._populate_list(self._all_members)

    def _populate_list(self, members: list[dict]):
        self._member_list.clear()
        for m in active_first(members, self._terminated_ids):
            label = f"{m['last_name']}, {m['first_name']}\n{m['center_id']} · {m['health_plan']}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, m["center_id"])
            item.setData(TERMINATED_ROLE, m["center_id"] in self._terminated_ids)
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
        self._last_center_id = center_id
        from gui.member_tabs import MemberTabsWidget
        db_path = self._settings.get("db_path", "")
        events_path = self._settings.get("events_db_path", "")
        api_key = self._settings.get("google_api_key", "")
        widget = MemberTabsWidget(center_id, db_path, events_path, api_key)
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
        widget = GlobalEventsWidget(events_path, on_back=self._back_from_events)
        self._set_detail(widget)

    def _back_from_events(self):
        if self._last_center_id is not None:
            self._show_member(self._last_center_id)
        else:
            while self._detail_stack.count() > 1:
                w = self._detail_stack.widget(1)
                self._detail_stack.removeWidget(w)
                w.deleteLater()
            self._detail_stack.setCurrentIndex(0)

    def _open_wizard(self):
        db_path = self._settings.get("db_path", "")
        if not db_path:
            QMessageBox.warning(self, "No Database",
                "Set a database path in Settings before adding members.")
            return
        from gui.wizard.wizard import AddMemberWizard
        events_path = self._settings.get("events_db_path", "")
        api_key = self._settings.get("google_api_key", "")
        dlg = AddMemberWizard(db_path, events_path, api_key, self)
        if dlg.exec():
            self._load_members()

    def _open_settings(self):
        dlg = SettingsDialog(self._settings, self)
        if dlg.exec():
            self._settings.update(dlg.result_settings())
            save_settings(self._settings, self._settings_path)
            # Drop cached DB handles so the new path is used on next access.
            from db.members import close_connections
            close_connections()
            from gui.theme import apply_theme
            apply_theme(QApplication.instance(), self._settings["theme"])
            self._refresh_list_theme()
            self._update_db_indicator()
            self._load_members()
