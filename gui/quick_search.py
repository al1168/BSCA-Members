"""Ctrl+K command-palette member search.

A frameless, non-modal overlay: type to filter members (using the matcher passed
in, so the comma-triggered "Last, First" rule is preserved), arrow keys to move,
single-click or Enter to open the highlighted member, Esc to close. It is
non-modal and closes itself when it loses focus (clicking the window behind it),
so that click lands on — and focuses — the background window. Selection is
reported via the `chosen` signal. The matcher is injected to avoid importing
main_window (and a circular import)."""

from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
    QLabel, QGraphicsDropShadowEffect,
)
from PyQt6.QtCore import Qt, QEvent, pyqtSignal
from PyQt6.QtGui import QColor


class QuickSearchDialog(QDialog):
    MAX_RESULTS = 50

    # Emitted with the chosen member's center_id when a result is picked.
    chosen = pyqtSignal(object)

    def __init__(self, members, matcher, parent=None, ranker=None):
        super().__init__(parent)
        self._members = members
        self._matcher = matcher
        self._ranker = ranker   # optional (member, text) -> sort key
        self.chosen_center_id = None
        self._chosen_done = False

        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        # Non-modal so a click on the background window goes through (focusing it);
        # we close ourselves on deactivation (see event()).
        self.setModal(False)
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
        # Single click opens the member (the clicked item becomes current).
        self._list.itemClicked.connect(lambda _it: self._choose_current())
        v.addWidget(self._list)

        hint = QLabel("↑↓ navigate · click or Enter open · Esc close")
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
        if text.strip():
            members = [m for m in self._members if self._matcher(m, text)]
            if self._ranker is not None:
                members.sort(key=lambda m: self._ranker(m, text))
        else:
            members = self._members
        for m in members[:self.MAX_RESULTS]:
            label = (f"{m.get('last_name', '')}, {m.get('first_name', '')}"
                     f"      ·   {m.get('center_id', '')}")
            plan = m.get("health_plan")
            if plan:
                label += f"   ·   {plan}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, m.get("center_id"))
            self._list.addItem(item)
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
        cid = item.data(Qt.ItemDataRole.UserRole)
        self.chosen_center_id = cid
        self._chosen_done = True   # suppress the close-on-deactivate path
        self.accept()
        self.chosen.emit(cid)

    def event(self, e):
        # Close when the window loses activation (e.g. the user clicks the
        # background window) — but not when we're closing due to a selection.
        if e.type() == QEvent.Type.WindowDeactivate and not self._chosen_done:
            self.close()
        return super().event(e)

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
