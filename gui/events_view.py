from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont

from gui.theme import event_badge_colors, format_member_counts, current_tokens, px


class EventsTableWidget(QWidget):
    """Reusable events log table. Pass center_id=None for global view."""

    def __init__(self, events_path: str, center_id: int | None = None,
                 show_header: bool = True, member_count: int | None = None,
                 active_count: int | None = None, parent=None):
        super().__init__(parent)
        self._events_path = events_path
        self._center_id = center_id
        self._show_header = show_header
        self._member_count = member_count
        self._active_count = active_count
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        if self._show_header:
            header_row = QHBoxLayout()
            title = QLabel("All Events" if self._center_id is None else "Events")
            title.setStyleSheet(f"font-size:{px(15)}px; font-weight:600;")
            ttl_lbl = QLabel("Auto-deletes after 30 days")
            ttl_lbl.setStyleSheet(f"font-size:{px(10)}px; color: gray;")
            header_row.addWidget(title)
            header_row.addStretch()
            header_row.addWidget(ttl_lbl)
            layout.addLayout(header_row)

            # Under "All Events": total members and (in green) how many are
            # active (not terminated). Only the global view carries these counts.
            if self._center_id is None and self._member_count is not None:
                counts = QLabel(format_member_counts(
                    self._member_count, self._active_count))
                counts.setObjectName("events_member_counts")
                counts.setTextFormat(Qt.TextFormat.RichText)
                counts.setStyleSheet(f"font-size:{px(12)}px;")
                layout.addWidget(counts)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter by member or action…")
        self._search.textChanged.connect(self._load)
        layout.addWidget(self._search)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Time", "Type", "Member", "Description"])
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        hdr = self._table.horizontalHeader()
        # Time / Type / Member hug their content (so the full timestamp shows);
        # Description takes the remaining width.
        for col in (0, 1, 2):
            hdr.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
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
            msg.setForeground(QColor(current_tokens()["text3"]))
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
        except Exception as exc:
            import crash_log
            crash_log.log_warning(f"events load failed: {exc!r}")
            return

        self._table.setRowCount(len(rows))
        self._table.clearSpans()
        if not rows:
            # Empty log or a filter with no hits — say which, never a bare void.
            self._table.setRowCount(1)
            self._table.setSpan(0, 0, 1, 4)
            text = ("No events match your filter."
                    if self._search.text().strip()
                    else "No events recorded in the last 30 days. Changes made "
                         "in this app will show up here.")
            msg = QTableWidgetItem(text)
            msg.setFlags(Qt.ItemFlag.NoItemFlags)
            msg.setForeground(QColor(current_tokens()["text3"]))
            self._table.setItem(0, 0, msg)
            return
        mono_font = QFont("Cascadia Mono, Consolas", px(10))
        for r, row in enumerate(rows):
            ts_item = QTableWidgetItem(row["ts"].replace("T", "  "))
            ts_item.setFont(mono_font)
            self._table.setItem(r, 0, ts_item)

            badge = QTableWidgetItem(row["event_type"])
            badge.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            bg, fg = event_badge_colors(row["event_type"])
            badge.setBackground(QColor(bg))
            badge.setForeground(QColor(fg))
            self._table.setItem(r, 1, badge)

            self._table.setItem(r, 2, QTableWidgetItem(row["member_name"]))
            self._table.setItem(r, 3, QTableWidgetItem(row["description"]))

    def refresh(self):
        """Reload events from the database."""
        self._load()


class GlobalEventsWidget(QWidget):
    def __init__(self, events_path: str, on_back=None, member_count: int | None = None,
                 active_count: int | None = None, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 12)
        if on_back is not None:
            from PyQt6.QtWidgets import QPushButton
            back_row = QHBoxLayout()
            btn_back = QPushButton("← Back")
            btn_back.clicked.connect(on_back)
            back_row.addWidget(btn_back)
            back_row.addStretch()
            layout.addLayout(back_row)
        layout.addWidget(EventsTableWidget(
            events_path, center_id=None,
            member_count=member_count, active_count=active_count))
