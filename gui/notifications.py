"""Toolbar notifications popup: active members whose latest authorization is
expiring soon or has expired.

The panel is a small popup anchored under the toolbar bell. Two tabs —
Expiring and Expired — each list members with when their coverage ends/ended;
clicking a row jumps to that member (the main window opens their Auths tab so
the notification can be resolved by adding a new authorization).
"""
from datetime import date

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QScrollArea, QWidget, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal

from gui.theme import current_tokens, px


def format_notification_line(end: date, days: int, expired: bool) -> str:
    """'Expires Jul 12 · in 3 days' / 'Expires Jul 9 · today' /
    'Expired Jun 27 · 6 days ago' — mirrors the mock's phrasing."""
    when = f"{end.strftime('%b')} {end.day}"      # no leading zero, any OS
    if expired:
        unit = "day" if days == 1 else "days"
        return f"Expired {when} · {days} {unit} ago"
    if days == 0:
        return f"Expires {when} · today"
    unit = "day" if days == 1 else "days"
    return f"Expires {when} · in {days} {unit}"


class _NotifRow(QFrame):
    """One clickable member row: name + id on top, the expiry line under it."""

    clicked = pyqtSignal(object)

    def __init__(self, center_id, name: str, subtitle: str, sub_color: str,
                 parent=None):
        super().__init__(parent)
        self._center_id = center_id
        self.setObjectName("notif_row")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        t = current_tokens()
        col = QVBoxLayout(self)
        col.setContentsMargins(16, 9, 16, 9)
        col.setSpacing(2)
        title = QLabel(
            f"<span style='color:{t['accent_text']}; font-weight:600'>{name}</span>"
            f"&nbsp;&nbsp;<span style='color:{t['text2']}'>ID {center_id}</span>")
        title.setTextFormat(Qt.TextFormat.RichText)
        sub = QLabel(subtitle)
        sub.setStyleSheet(f"color:{sub_color}; font-size:{px(11)}px;")
        col.addWidget(title)
        col.addWidget(sub)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._center_id)
        super().mouseReleaseEvent(e)


class NotificationsPanel(QDialog):
    """Popup listing expiring/expired authorizations for active members."""

    member_chosen = pyqtSignal(object)

    def __init__(self, expiring, expired, names: dict, parent=None,
                 today: date | None = None):
        """expiring/expired: [(center_id, end_date, days)], from
        db.members.classify_auth_notifications. names: center_id -> display."""
        super().__init__(parent)
        self._expiring = expiring
        self._expired = expired
        self._names = names
        self._today = today or date.today()
        self.setWindowFlags(Qt.WindowType.Popup |
                            Qt.WindowType.FramelessWindowHint)
        self.setObjectName("notif_panel")
        self.setFixedWidth(px(360))
        self._build_ui()
        self._show_tab("expiring" if expiring or not expired else "expired")

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

        title = QLabel("Notifications")
        title.setObjectName("notif_title")
        pad = QHBoxLayout()
        pad.setContentsMargins(16, 0, 16, 8)
        pad.addWidget(title)
        root.addLayout(pad)

        # Tabs with count pills, underlined when active (like the mock).
        tabs = QHBoxLayout()
        tabs.setContentsMargins(12, 0, 12, 0)
        tabs.setSpacing(4)
        self._btn_expiring = QPushButton(
            f"Expiring   {len(self._expiring)}")
        self._btn_expired = QPushButton(
            f"Expired   {len(self._expired)}")
        for b, key in ((self._btn_expiring, "expiring"),
                       (self._btn_expired, "expired")):
            b.setObjectName("notif_tab")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=key: self._show_tab(k))
            tabs.addWidget(b)
        tabs.addStretch()
        root.addLayout(tabs)

        rule = QFrame()
        rule.setFixedHeight(1)
        rule.setStyleSheet(f"background:{t['border_mid']};")
        root.addWidget(rule)

        # One scroll area; its content is rebuilt when the tab changes.
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setFixedHeight(px(220))
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        root.addWidget(self._scroll)

    def _show_tab(self, key: str):
        self._tab = key
        for b, k in ((self._btn_expiring, "expiring"),
                     (self._btn_expired, "expired")):
            b.setProperty("active", k == key)
            b.style().unpolish(b)
            b.style().polish(b)

        t = current_tokens()
        content = QWidget()
        col = QVBoxLayout(content)
        col.setContentsMargins(0, 4, 0, 4)
        col.setSpacing(0)

        items = self._expiring if key == "expiring" else self._expired
        if not items:
            empty = QLabel("✓   " + ("Nothing expiring in the next 35 days"
                                     if key == "expiring"
                                     else "No expired authorizations"))
            empty.setObjectName("empty_state")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col.addStretch()
            col.addWidget(empty)
            col.addStretch()
        else:
            for cid, end, days in items:
                expired = key == "expired"
                if expired:
                    sub_color = t["error_text"]
                elif days <= 7:
                    sub_color = t["warning"]
                else:
                    sub_color = t["text2"]
                row = _NotifRow(
                    cid, self._names.get(cid, str(cid)),
                    format_notification_line(end, days, expired), sub_color)
                row.clicked.connect(self._choose)
                col.addWidget(row)
            col.addStretch()
        self._scroll.setWidget(content)

    def _choose(self, center_id):
        self.accept()
        self.member_chosen.emit(center_id)

    def open_under(self, widget):
        """Show anchored under `widget` (the toolbar bell), right-aligned."""
        pos = widget.mapToGlobal(widget.rect().bottomRight())
        self.adjustSize()
        self.move(pos.x() - self.width(), pos.y() + 6)
        self.show()
