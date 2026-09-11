"""Toolbar bookmarks popup: the members the user has bookmarked, each with its
saved note and when it was saved.

The panel is a small popup anchored under the toolbar Bookmarks button (same
pattern as the notifications bell). Clicking a row jumps to that member; the
✕ removes the bookmark in place. Rows reuse the notif_* object names so the
popup inherits the notifications styling.
"""
from datetime import date
from html import escape as html_escape

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QScrollArea, QWidget,
)
from PyQt6.QtCore import Qt, pyqtSignal

from gui.theme import current_tokens, px


def format_bookmark_date(iso: str) -> str:
    """'2026-07-21' -> 'Jul 21, 2026'; anything unparseable passes through."""
    try:
        d = date.fromisoformat(iso)
    except (TypeError, ValueError):
        return iso or ""
    return f"{d.strftime('%b')} {d.day}, {d.year}"    # no leading zero, any OS


class _BookmarkRow(QFrame):
    """One clickable row: name + id, the saved note under it, then the date."""

    clicked = pyqtSignal(object)
    removed = pyqtSignal(object)

    def __init__(self, bm: dict, parent=None):
        super().__init__(parent)
        self._center_id = bm.get("center_id")
        self.setObjectName("notif_row")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        t = current_tokens()
        row = QHBoxLayout(self)
        row.setContentsMargins(16, 9, 10, 9)
        row.setSpacing(8)

        col = QVBoxLayout()
        col.setSpacing(2)
        title = QLabel(
            f"<span style='color:{t['accent_text']}; font-weight:600'>"
            f"{html_escape(bm.get('name') or '')}</span>"
            f"&nbsp;&nbsp;<span style='color:{t['text2']}'>"
            f"ID {self._center_id}</span>")
        title.setTextFormat(Qt.TextFormat.RichText)
        col.addWidget(title)
        note = (bm.get("note") or "").strip()
        if note:
            note_lbl = QLabel(note)
            note_lbl.setWordWrap(True)
            note_lbl.setStyleSheet(f"color:{t['text']}; font-size:{px(11)}px;")
            col.addWidget(note_lbl)
        date_lbl = QLabel(format_bookmark_date(bm.get("date", "")))
        date_lbl.setStyleSheet(f"color:{t['text3']}; font-size:{px(10)}px;")
        col.addWidget(date_lbl)
        row.addLayout(col, 1)

        # The button consumes its own mouse events, so ✕ never also fires the
        # row's jump-to-member click.
        btn = QPushButton("✕")
        btn.setObjectName("btn_icon_delete")
        btn.setFixedWidth(px(26))
        btn.setToolTip("Remove bookmark")
        btn.clicked.connect(lambda: self.removed.emit(self._center_id))
        row.addWidget(btn, alignment=Qt.AlignmentFlag.AlignTop)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._center_id)
        super().mouseReleaseEvent(e)


class BookmarksPanel(QDialog):
    """Popup listing bookmarked members; removal persists via the store."""

    member_chosen = pyqtSignal(object)
    bookmarks_edited = pyqtSignal()

    def __init__(self, bookmarks: list[dict], parent=None):
        super().__init__(parent)
        self._bookmarks = list(bookmarks)
        self.setWindowFlags(Qt.WindowType.Popup |
                            Qt.WindowType.FramelessWindowHint)
        self.setObjectName("bookmarks_panel")
        self.setFixedWidth(px(380))
        self._build_ui()
        self._rebuild()

    def _build_ui(self):
        t = current_tokens()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        frame = QFrame()
        frame.setObjectName("notif_frame")
        outer.addWidget(frame)
        root = QVBoxLayout(frame)
        root.setContentsMargins(0, 12, 0, 0)
        root.setSpacing(0)

        self._title = QLabel()
        self._title.setObjectName("notif_title")
        pad = QHBoxLayout()
        pad.setContentsMargins(16, 0, 16, 8)
        pad.addWidget(self._title)
        root.addLayout(pad)

        rule = QFrame()
        rule.setFixedHeight(1)
        rule.setStyleSheet(f"background:{t['border_mid']};")
        root.addWidget(rule)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setFixedHeight(px(260))
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        root.addWidget(self._scroll)

    def _rebuild(self):
        n = len(self._bookmarks)
        self._title.setText(f"Bookmarks   ·   {n} saved" if n else "Bookmarks")

        content = QWidget()
        col = QVBoxLayout(content)
        col.setContentsMargins(0, 4, 0, 4)
        col.setSpacing(0)

        if not self._bookmarks:
            empty = QLabel("No bookmarks yet — open a member and click "
                           "🔖 Bookmark.")
            empty.setObjectName("empty_state")
            empty.setWordWrap(True)
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col.addStretch()
            col.addWidget(empty)
            col.addStretch()
        else:
            for bm in self._bookmarks:
                row = _BookmarkRow(bm)
                row.clicked.connect(self._choose)
                row.removed.connect(self._remove)
                col.addWidget(row)
            col.addStretch()
        self._scroll.setWidget(content)

    def _choose(self, center_id):
        self.accept()
        self.member_chosen.emit(center_id)

    def _remove(self, center_id):
        from bookmarks import load_bookmarks, remove_bookmark, save_bookmarks
        try:
            save_bookmarks(remove_bookmark(load_bookmarks(), center_id))
        except OSError:
            return                      # file locked/unwritable: keep the row
        self._bookmarks = [
            b for b in self._bookmarks if b.get("center_id") != center_id
        ]
        self._rebuild()
        self.bookmarks_edited.emit()

    def open_under(self, widget):
        """Show anchored under `widget` (the toolbar button), right-aligned."""
        pos = widget.mapToGlobal(widget.rect().bottomRight())
        self.adjustSize()
        self.move(pos.x() - self.width(), pos.y() + 6)
        self.show()
