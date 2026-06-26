"""Ctrl+K command-palette member search.

A frameless, modal overlay: type to filter members (using the matcher passed in,
so the comma-triggered "Last, First" rule is preserved), arrow keys to move,
Enter to open the highlighted member, Esc to close. The matcher is injected to
avoid importing main_window (and a circular import)."""

from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
    QLabel, QGraphicsDropShadowEffect,
)
from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtGui import QColor


class QuickSearchDialog(QDialog):
    MAX_RESULTS = 50

    def __init__(self, members, matcher, parent=None):
        super().__init__(parent)
        self._members = members
        self._matcher = matcher
        self.chosen_center_id = None

        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setModal(True)
        self.resize(620, 460)

        # Transparent window; the rounded card lives inside so the corners render
        # cleanly and we can drop a shadow under it.
        shell = QVBoxLayout(self)
        shell.setContentsMargins(30, 30, 30, 30)   # room for the shadow
        card = QWidget()
        card.setObjectName("quick_search")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(40)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 130))
        card.setGraphicsEffect(shadow)
        shell.addWidget(card)

        v = QVBoxLayout(card)
        v.setContentsMargins(14, 14, 14, 12)
        v.setSpacing(8)

        self._search = QLineEdit()
        self._search.setObjectName("quick_search_input")
        self._search.setPlaceholderText(
            "Search members…   (Last, First  ·  or DOB like 1/1/2000)")
        self._search.textChanged.connect(self._refresh)
        self._search.returnPressed.connect(self._choose_current)
        self._search.installEventFilter(self)
        v.addWidget(self._search)

        self._list = QListWidget()
        self._list.setObjectName("quick_search_list")
        self._list.itemDoubleClicked.connect(lambda _it: self._choose_current())
        v.addWidget(self._list)

        hint = QLabel("↑↓ navigate · Enter open · Esc close")
        hint.setObjectName("quick_search_hint")
        v.addWidget(hint)

        self._refresh("")
        self._center_on_parent(parent)

    def _center_on_parent(self, parent):
        if parent is None:
            return
        pg = parent.frameGeometry()
        x = pg.x() + (pg.width() - self.width()) // 2
        y = pg.y() + max(60, pg.height() // 7)
        self.move(x, y)

    def _refresh(self, _text=""):
        text = self._search.text()
        self._list.clear()
        shown = 0
        for m in self._members:
            if text.strip() and not self._matcher(m, text):
                continue
            label = (f"{m.get('last_name', '')}, {m.get('first_name', '')}"
                     f"      ·   {m.get('center_id', '')}")
            plan = m.get("health_plan")
            if plan:
                label += f"   ·   {plan}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, m.get("center_id"))
            self._list.addItem(item)
            shown += 1
            if shown >= self.MAX_RESULTS:
                break
        if self._list.count():
            self._list.setCurrentRow(0)   # first hit selected so Enter just works

    def _move(self, delta: int):
        n = self._list.count()
        if not n:
            return
        row = self._list.currentRow()
        row = 0 if row < 0 else max(0, min(n - 1, row + delta))
        self._list.setCurrentRow(row)

    def _choose_current(self):
        item = self._list.currentItem()
        if item is None:
            return
        self.chosen_center_id = item.data(Qt.ItemDataRole.UserRole)
        self.accept()

    def eventFilter(self, obj, event):
        # Route Up/Down from the text box to the results list (keeps typing focus).
        if obj is self._search and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Down:
                self._move(1)
                return True
            if event.key() == Qt.Key.Key_Up:
                self._move(-1)
                return True
        return super().eventFilter(obj, event)
