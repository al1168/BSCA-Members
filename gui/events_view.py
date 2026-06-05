from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont

BADGE_COLORS = {
    "NEW":    ("#182e22", "#3d9e6e"),
    "EDIT":   ("#281f0a", "#c08a2a"),
    "AUTH":   ("#1c2040", "#92b4ff"),
    "ABS":    ("#1e1530", "#b090e8"),
    "AVAIL":  ("#0e2028", "#5eead4"),
    "ENROLL": ("#1a2030", "#80b0e8"),
}


class EventsTableWidget(QWidget):
    """Reusable events log table. Pass center_id=None for global view."""

    def __init__(self, events_path: str, center_id: int | None = None,
                 show_header: bool = True, parent=None):
        super().__init__(parent)
        self._events_path = events_path
        self._center_id = center_id
        self._show_header = show_header
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        if self._show_header:
            header_row = QHBoxLayout()
            title = QLabel("All Events" if self._center_id is None else "Events")
            title.setStyleSheet("font-size:15px; font-weight:600;")
            ttl_lbl = QLabel("Auto-deletes after 30 days")
            ttl_lbl.setStyleSheet("font-size:10px; color: gray;")
            header_row.addWidget(title)
            header_row.addStretch()
            header_row.addWidget(ttl_lbl)
            layout.addLayout(header_row)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter by member or action…")
        self._search.textChanged.connect(self._load)
        layout.addWidget(self._search)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Time", "Type", "Member", "Description"])
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self._table)

    def _load(self):
        if not self._events_path:
            self._table.clearSpans()
            self._table.setRowCount(1)
            self._table.setSpan(0, 0, 1, 4)
            msg = QTableWidgetItem(
                "No events log configured. Set an Events log path in "
                "Settings to start recording changes."
            )
            msg.setForeground(QColor("#888"))
            self._table.setItem(0, 0, msg)
            return
        from db.events import open_db, query_events, purge_old_events
        try:
            conn = open_db(self._events_path)
            purge_old_events(conn)
            rows = query_events(
                conn,
                center_id=self._center_id,
                filter_text=self._search.text().strip() or None,
            )
            conn.close()
        except Exception:
            return

        self._table.setRowCount(len(rows))
        self._table.clearSpans()
        mono_font = QFont("Cascadia Mono, Consolas", 10)
        for r, row in enumerate(rows):
            ts_item = QTableWidgetItem(row["ts"].replace("T", "  "))
            ts_item.setFont(mono_font)
            self._table.setItem(r, 0, ts_item)

            badge = QTableWidgetItem(row["event_type"])
            badge.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            bg, fg = BADGE_COLORS.get(row["event_type"], ("#333", "#ccc"))
            badge.setBackground(QColor(bg))
            badge.setForeground(QColor(fg))
            self._table.setItem(r, 1, badge)

            self._table.setItem(r, 2, QTableWidgetItem(row["member_name"]))
            self._table.setItem(r, 3, QTableWidgetItem(row["description"]))

    def refresh(self):
        """Reload events from the database."""
        self._load()


class GlobalEventsWidget(QWidget):
    def __init__(self, events_path: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 12)
        layout.addWidget(EventsTableWidget(events_path, center_id=None))
