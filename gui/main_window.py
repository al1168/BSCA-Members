import os
from html import escape as html_escape

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QListWidget, QListWidgetItem, QPushButton, QLineEdit, QLabel,
    QStackedWidget, QApplication, QMessageBox, QSizePolicy,
    QStyledItemDelegate, QStyle, QStyleOptionViewItem,
)
from PyQt6.QtCore import Qt, QEvent, QObject
from PyQt6.QtGui import (
    QTextDocument, QAbstractTextDocumentLayout, QShortcut, QKeySequence,
    QGuiApplication,
)

from settings import save_settings
from gui.settings_dialog import SettingsDialog


TERMINATED_ROLE = Qt.ItemDataRole.UserRole + 1


def active_first(members: list[dict], terminated_ids: set) -> list[dict]:
    """Stable-sort members so active ones precede terminated ones, preserving the
    input order (alphabetical) within each group."""
    return sorted(members, key=lambda m: m["center_id"] in terminated_ids)


def _dob_matches(dob, query: str) -> bool:
    """Whether a member's `dob` (a date or None) matches a date `query` that uses
    '/' separators. The query is a prefix of MM/DD/YYYY: month/day are zero-padded
    to two digits so '1/1' matches Jan 1, and a partial year works as a prefix
    ('1/1/20' matches any Jan 1 in 2000–2009). Non-numeric segments never match."""
    if dob is None:
        return False
    if not any(ch.isdigit() for ch in query):
        return False                     # just '/', nothing to match yet
    target = f"{dob.month:02d}/{dob.day:02d}/{dob.year:04d}"
    parts = []
    for i, seg in enumerate(query.split("/")):
        seg = seg.strip()
        if seg == "":
            parts.append("")
        elif seg.isdigit():
            parts.append(f"{int(seg):02d}" if i < 2 else seg)
        else:
            return False
    return target.startswith("/".join(parts))


def matches_search(member: dict, text: str) -> bool:
    """Whether `member` matches the search box `text`.

    A comma is the trigger for last-name mode ('Last, Firstprefix'): the text
    before the first comma is an exact, case-insensitive last-name match, and
    the text after it is a first-name prefix (empty -> last-name only). A slash
    is the trigger for date-of-birth mode (e.g. '1/1/2000' or a prefix like
    '1/1'). Otherwise, a substring match over last name, first name, center
    id, and alt id.
    """
    q = text.strip()
    if "," in q:
        last_part, first_part = q.split(",", 1)
        last = last_part.strip().lower()
        first = first_part.strip().lower()
        if (member.get("last_name") or "").strip().lower() != last:
            return False
        if first:
            return (member.get("first_name") or "").strip().lower().startswith(first)
        return True
    if "/" in q:
        return _dob_matches(member.get("dob"), q)
    ql = q.lower()
    alt = member.get("alt_id")
    return (ql in (member.get("last_name") or "").lower()
            or ql in (member.get("first_name") or "").lower()
            or ql in str(member.get("center_id", ""))
            or (alt is not None and ql in str(alt)))


def decrypt_corpus_alt_ids(members: list, key) -> None:
    """Replace each corpus member's alt_id with its decrypted display value,
    in place, so search/matching sees what the user sees when a session
    decryption key is set. No-op when key is None. The DB itself always
    keeps the ciphertext — this touches only the in-memory search corpus."""
    if key is None:
        return
    from db.alt_id_crypto import decrypt_or_raw
    for m in members:
        m["alt_id"] = decrypt_or_raw(key, m.get("alt_id"))


def search_rank_key(member: dict, text: str):
    """Sort key ranking search results by relevance to `text`.

    A digit-only query is an ID search: the member whose center id (or alt id)
    equals the query sorts first, then id-prefix matches, then everything else,
    numerically by center id within each tier. Any other query is a name
    search: members whose last or first name starts with the query sort before
    mid-string matches, alphabetically within each tier. Keys from different
    queries use different tuple shapes, so a key is only comparable to others
    produced with the same query (fine — sorting always fixes the query).
    """
    q = text.strip().lower()
    if q.isdigit():
        cid = member.get("center_id")
        cid_s = "" if cid is None else str(cid)
        alt = member.get("alt_id")
        alt_s = "" if alt is None else str(alt)
        if q in (cid_s, alt_s):
            tier = 0
        elif cid_s.startswith(q) or alt_s.startswith(q):
            tier = 1
        else:
            tier = 2
        return (tier, int(cid_s) if cid_s.isdigit() else float("inf"))
    last = (member.get("last_name") or "").strip().lower()
    first = (member.get("first_name") or "").strip().lower()
    tier = 0 if (last.startswith(q) or first.startswith(q)) else 1
    return (tier, last, first)


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
        name, sub = html_escape(name), html_escape(sub)  # names may contain & or <
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


class _FirstPaintLogger(QObject):
    """Logs how long a member click took, measured to the profile's first
    paint (what the user actually experiences), then uninstalls itself.

    Lines land in logs/clicks_<date>.txt via crash_log.log_perf so per-click
    times can be compared across computers in the field.
    """

    def __init__(self, widget, t0: float, center_id):
        super().__init__(widget)          # dies with the widget
        self._t0 = t0
        self._center_id = center_id
        widget.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Paint:
            obj.removeEventFilter(self)
            import time
            import crash_log
            total = (time.perf_counter() - self._t0) * 1000
            load = getattr(obj, "perf_load_ms", 0.0)
            build = getattr(obj, "perf_build_ms", 0.0)
            paint = max(0.0, total - load - build)
            crash_log.log_perf(
                f"center {self._center_id}: click-to-paint {total:.0f} ms "
                f"(db {load:.0f} + ui {build:.0f} + paint {paint:.0f})")
        return False


class MainWindow(QMainWindow):
    def __init__(self, settings: dict, settings_path: str):
        super().__init__()
        self._settings = settings
        self._settings_path = settings_path
        self._last_center_id = None
        self._terminated_ids = set()
        # Session-only alt-id decryption password — never persisted; typed in
        # the Settings dialog and gone when the app closes.
        self._alt_id_password = ""
        from version import app_version
        self.setWindowTitle(f"Care Manager — {app_version()}")
        self._apply_default_geometry()
        self._build_ui()
        self._load_members()

    def _apply_default_geometry(self):
        """Open wide enough to show the widest tab (the Authorizations table
        needs ~1780px with the sidebar), but never larger than the screen, and
        centered on it."""
        desired_w, desired_h = 1800, 920
        screen = QApplication.primaryScreen()
        avail = screen.availableGeometry() if screen else None
        if avail is not None:
            w = min(desired_w, avail.width())
            h = min(desired_h, avail.height())
            self.resize(w, h)
            self.move(avail.x() + (avail.width() - w) // 2,
                      avail.y() + (avail.height() - h) // 2)
        else:
            self.resize(desired_w, desired_h)

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
        self._search.setPlaceholderText("Search members…   (Ctrl+K)")
        self._search.textChanged.connect(self._filter_members)
        # Enter opens the highlighted result (or the first one); ↑/↓ move the
        # highlight without leaving the box — same feel as the Ctrl+K palette.
        self._search.returnPressed.connect(self._open_from_search)
        self._search.installEventFilter(self)

        # Ctrl+K opens the command-palette member search from anywhere.
        quick = QShortcut(QKeySequence("Ctrl+K"), self)
        quick.activated.connect(self._open_quick_search)

        self._member_list = QListWidget()
        self._member_list.currentRowChanged.connect(self._on_member_selected)
        # Coalesce rapid selection changes (fast clicking, holding an arrow
        # key): each change restarts this short timer and only the row the
        # user lands on gets its profile built. Without it every intermediate
        # member is loaded in full, which freezes the app ("Not responding")
        # when clicks arrive faster than profiles can build.
        from PyQt6.QtCore import QTimer
        self._select_timer = QTimer(self)
        self._select_timer.setSingleShot(True)
        self._select_timer.setInterval(80)
        self._select_timer.timeout.connect(self._load_selected_member)
        self._member_delegate = _MemberItemDelegate(self._member_list)
        self._member_list.setItemDelegate(self._member_delegate)
        self._refresh_list_theme()

        self._btn_events = QPushButton("All Events")
        self._btn_events.clicked.connect(self._show_global_events)

        # Always-visible tally under the All Events button: total members and how
        # many are active (not terminated), in green.
        self._member_counts = QLabel("")
        self._member_counts.setObjectName("sidebar_member_counts")
        self._member_counts.setTextFormat(Qt.TextFormat.RichText)
        self._member_counts.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._member_counts.setStyleSheet("font-size:12px;")

        sidebar_layout.addWidget(self._btn_add)
        sidebar_layout.addWidget(self._search)
        sidebar_layout.addWidget(self._member_list)
        sidebar_layout.addWidget(self._btn_events)
        sidebar_layout.addWidget(self._member_counts)

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

        btn_birthdays = QPushButton("🎂  Birthdays")
        btn_birthdays.setObjectName("btn_birthday_report")
        btn_birthdays.setToolTip(
            "Spreadsheet of active members with a birthday in a chosen month")
        btn_birthdays.clicked.connect(self._open_birthday_report)
        toolbar.addWidget(btn_birthdays)

        btn_expiring = QPushButton("📅  Expiring Report")
        btn_expiring.setObjectName("btn_expiring_report")
        btn_expiring.setToolTip(
            "Spreadsheet/printout of members whose auths expire in a chosen "
            "month, grouped by health plan")
        btn_expiring.clicked.connect(self._open_expiring_report)
        toolbar.addWidget(btn_expiring)

        btn_absences = QPushButton("🏥  Absences")
        btn_absences.setObjectName("btn_absence_report")
        btn_absences.setToolTip(
            "Spreadsheet of active members' absences overlapping a chosen "
            "month")
        btn_absences.clicked.connect(self._open_absence_report)
        toolbar.addWidget(btn_absences)

        btn_export = QPushButton("⬇  Export")
        btn_export.setObjectName("btn_export")
        btn_export.setToolTip(
            "Save a spreadsheet of every member's info, enrollment, "
            "current auth, and emergency contact")
        btn_export.clicked.connect(self._export_members)
        toolbar.addWidget(btn_export)

        # Members the user bookmarked (stored per-user in %APPDATA%), with a
        # live count. Clicking a row in the popup jumps to that member.
        self._btn_bookmarks = QPushButton()
        self._btn_bookmarks.setObjectName("btn_bookmarks")
        self._btn_bookmarks.setToolTip(
            "Members you bookmarked, with your notes")
        self._btn_bookmarks.clicked.connect(self._open_bookmarks)
        toolbar.addWidget(self._btn_bookmarks)
        self._update_bookmark_count()

        # Bell with a live count of expiring/expired auths for active members.
        # Lives in the toolbar so it's visible whichever profile is open.
        self._btn_notif = QPushButton("🔔")
        self._btn_notif.setObjectName("btn_notifications")
        self._btn_notif.setToolTip("Authorizations expiring soon or expired")
        self._btn_notif.clicked.connect(self._open_notifications)
        toolbar.addWidget(self._btn_notif)

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
            decrypt_corpus_alt_ids(self._all_members, self._alt_id_key())
            try:
                self._terminated_ids = get_terminated_center_ids(db_path)
            except Exception as exc:
                # Members still render, just without terminated marks — log it
                # so the missing marks are diagnosable.
                import crash_log
                crash_log.log_warning(f"get_terminated_center_ids failed: {exc!r}")
                self._terminated_ids = set()
        except Exception as exc:
            from gui.errors import show_db_error
            show_db_error(self, exc, "Could Not Load Members")
        # A database is configured now — the pane's job is member selection.
        if self._all_members:
            self._placeholder.setText(
                "Select a member from the list to view their profile.\n"
                "Tip: press Ctrl+K to search from anywhere."
            )
        else:
            self._placeholder.setText(
                "This database has no members yet.\n"
                "Click  + Add New Member  to create the first one."
            )
        self._populate_list(self._all_members)
        self._update_member_counts()
        self._refresh_notifications()
        self._warn_missing_schema(db_path)

    def _warn_missing_schema(self, db_path: str):
        """One-time (per path) warning listing tables/columns this app needs but
        the selected database lacks, so features don't fail one by one later."""
        if db_path in getattr(self, "_schema_warned", set()):
            return
        try:
            from db.members import missing_schema
            missing = missing_schema(db_path)
        except Exception:
            return
        self._schema_warned = getattr(self, "_schema_warned", set())
        self._schema_warned.add(db_path)
        if missing:
            QMessageBox.warning(
                self, "Database Schema",
                "This database is missing some tables/columns the app uses.\n"
                "The affected features won't work until they are added:\n\n  • "
                + "\n  • ".join(missing))

    def _update_member_counts(self):
        """Refresh the sidebar's 'N members · M active' tally (active = not
        terminated), from the full member list regardless of any search filter."""
        from gui.theme import format_member_counts
        total = len(self._all_members)
        active = sum(1 for m in self._all_members
                     if m["center_id"] not in self._terminated_ids)
        self._member_counts.setText(format_member_counts(total, active))

    def _populate_list(self, members: list[dict], search_text: str = ""):
        self._member_list.clear()
        if not members and search_text.strip():
            # Zero-result search: say so instead of showing a silent void.
            item = QListWidgetItem(f"No members match\n“{search_text.strip()}”")
            item.setFlags(Qt.ItemFlag.NoItemFlags)   # not selectable
            self._member_list.addItem(item)
            return
        for m in active_first(members, self._terminated_ids):
            label = f"{m['last_name']}, {m['first_name']}\n{m['center_id']} · {m['health_plan']}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, m["center_id"])
            item.setData(TERMINATED_ROLE, m["center_id"] in self._terminated_ids)
            self._member_list.addItem(item)

    def _filter_members(self, text: str):
        filtered = [m for m in self._all_members if matches_search(m, text)]
        if text.strip():
            filtered.sort(key=lambda m: search_rank_key(m, text))
        self._populate_list(filtered, search_text=text)

    def eventFilter(self, obj, event):
        # ↑/↓ typed in the sidebar search box move the list highlight while
        # focus stays in the box; Enter (returnPressed) opens the highlight.
        if obj is getattr(self, "_search", None) and \
                event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Down:
                self._move_search_selection(1)
                return True
            if event.key() == Qt.Key.Key_Up:
                self._move_search_selection(-1)
                return True
        return super().eventFilter(obj, event)

    def _move_search_selection(self, delta: int):
        """Move the sidebar highlight without opening members along the way —
        selection signals are blocked, so only Enter commits (each open costs
        a database load)."""
        lst = self._member_list
        n = lst.count()
        if not n:
            return
        row = lst.currentRow()
        row = 0 if row < 0 else max(0, min(n - 1, row + delta))
        if lst.item(row).data(Qt.ItemDataRole.UserRole) is None:
            return                     # the "No members match" placeholder
        lst.blockSignals(True)
        lst.setCurrentRow(row)
        lst.blockSignals(False)

    def _open_from_search(self):
        """Enter in the search box: open the highlighted member, or the first
        result when nothing is highlighted yet."""
        item = self._member_list.currentItem()
        if item is None or item.data(Qt.ItemDataRole.UserRole) is None:
            item = next(
                (self._member_list.item(i)
                 for i in range(self._member_list.count())
                 if self._member_list.item(i).data(Qt.ItemDataRole.UserRole)
                 is not None),
                None)
        if item is None:
            return                     # no results to open
        self._jump_to_member(item.data(Qt.ItemDataRole.UserRole))

    def _ok_to_leave_current(self) -> bool:
        """True to proceed (no unsaved edits, or the user chose to discard)."""
        if self._detail_stack.count() > 1:
            current = self._detail_stack.widget(1)
            if hasattr(current, "is_dirty") and current.is_dirty():
                reply = QMessageBox.question(
                    self, "Unsaved Changes",
                    "You have unsaved changes. Discard them?",
                    QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                )
                return reply == QMessageBox.StandardButton.Discard
        return True

    def _on_member_selected(self, row: int):
        if row < 0:
            return
        import time
        self._click_t0 = time.perf_counter()
        self._select_timer.start()      # restarting coalesces click bursts

    def _load_selected_member(self):
        row = self._member_list.currentRow()
        if row < 0:
            return
        if not self._ok_to_leave_current():
            self._member_list.blockSignals(True)
            self._member_list.setCurrentRow(-1)
            self._member_list.blockSignals(False)
            return
        item = self._member_list.item(row)
        if item is None:
            return
        center_id = item.data(Qt.ItemDataRole.UserRole)
        self._show_member(center_id)

    def _open_quick_search(self):
        """Ctrl+K: a command-palette member search overlay.

        Shown non-modally so clicking the window behind it both closes the
        overlay and focuses that window; selection arrives via the `chosen`
        signal. A reference is kept so the dialog isn't garbage-collected."""
        if not self._all_members:
            return
        from gui.quick_search import QuickSearchDialog
        dlg = QuickSearchDialog(self._all_members, matches_search, self,
                                ranker=search_rank_key)
        dlg.chosen.connect(self._jump_to_member)
        self._quick_search_dlg = dlg
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()
        dlg._search.setFocus()

    def _jump_to_member(self, center_id):
        """Open a member by id (from quick search), honoring the unsaved guard
        and syncing the sidebar highlight when that member is visible."""
        if center_id is None:
            return
        if not self._ok_to_leave_current():
            return
        self._show_member(center_id)
        self._member_list.blockSignals(True)
        self._member_list.setCurrentRow(-1)
        for i in range(self._member_list.count()):
            if self._member_list.item(i).data(Qt.ItemDataRole.UserRole) == center_id:
                self._member_list.setCurrentRow(i)
                break
        self._member_list.blockSignals(False)

    def _show_member(self, center_id: int):
        import time
        # Set by _on_member_selected on a list click; other entry points
        # (quick search, back-from-events) start the clock here instead.
        t0 = getattr(self, "_click_t0", None) or time.perf_counter()
        self._click_t0 = None
        self._last_center_id = center_id
        from gui.member_tabs import MemberTabsWidget
        db_path = self._settings.get("db_path", "")
        events_path = self._settings.get("events_db_path", "")
        api_key = self._settings.get("google_api_key", "")
        show_row_ids = self._settings.get("show_row_ids", False)
        widget = MemberTabsWidget(center_id, db_path, events_path, api_key,
                                  show_row_ids,
                                  alt_id_key=self._alt_id_key(),
                                  settings=self._settings,
                                  settings_path=self._settings_path)
        widget.members_changed.connect(self._refresh_terminated_marks)
        widget.members_changed.connect(self._refresh_search_corpus)
        widget.bookmarks_changed.connect(self._update_bookmark_count)
        self._set_detail(widget)
        _FirstPaintLogger(widget, t0, center_id)

    def _refresh_terminated_marks(self):
        """Re-read which members are terminated and update the sidebar marks in
        place (e.g. after a member is re-enrolled or terminated), without
        rebuilding the list or disturbing the open member."""
        from db.members import get_terminated_center_ids
        db_path = self._settings.get("db_path", "")
        try:
            self._terminated_ids = get_terminated_center_ids(db_path)
        except Exception as exc:
            import crash_log
            crash_log.log_warning(f"refresh terminated marks failed: {exc!r}")
            return
        for i in range(self._member_list.count()):
            item = self._member_list.item(i)
            cid = item.data(Qt.ItemDataRole.UserRole)
            item.setData(TERMINATED_ROLE, cid in self._terminated_ids)
        self._member_list.viewport().update()
        self._update_member_counts()
        self._refresh_notifications()

    def _refresh_search_corpus(self):
        """Re-read the member list the search box matches against, so edits
        made in the open member (name, alt id) are searchable immediately —
        without restarting. Only re-renders the sidebar when a search filter
        is active, to leave the current selection undisturbed otherwise."""
        from db.members import get_all_members
        db_path = self._settings.get("db_path", "")
        if not db_path:
            return
        try:
            self._all_members = get_all_members(db_path)
        except Exception as exc:
            import crash_log
            crash_log.log_warning(f"refresh search corpus failed: {exc!r}")
            return
        decrypt_corpus_alt_ids(self._all_members, self._alt_id_key())
        text = self._search.text() if getattr(self, "_search", None) else ""
        if text.strip():
            self._filter_members(text)

    def _compute_notifications(self) -> dict:
        """Expiring/expired auth buckets for active members (35-day window)."""
        from datetime import date
        from db.members import get_member_auth_ends, classify_auth_notifications
        db_path = self._settings.get("db_path", "")
        empty = {"expiring": [], "expired": []}
        if not db_path or not self._all_members:
            return empty
        try:
            rows = get_member_auth_ends(db_path)
        except Exception as exc:
            import crash_log
            crash_log.log_warning(f"notification auth scan failed: {exc!r}")
            return empty
        active_ids = ({m["center_id"] for m in self._all_members}
                      - self._terminated_ids)
        return classify_auth_notifications(rows, active_ids, date.today())

    def _refresh_notifications(self):
        """Recompute the buckets and update the toolbar bell's count badge."""
        if not hasattr(self, "_btn_notif"):
            return
        self._notifications = self._compute_notifications()
        total = (len(self._notifications["expiring"])
                 + len(self._notifications["expired"]))
        self._btn_notif.setText(f"🔔  {total}" if total else "🔔")
        self._btn_notif.setProperty(
            "alert", bool(self._notifications["expired"]))
        self._btn_notif.style().unpolish(self._btn_notif)
        self._btn_notif.style().polish(self._btn_notif)

    def _open_notifications(self):
        from gui.notifications import NotificationsPanel
        self._refresh_notifications()          # fresh data on every open
        names = {m["center_id"]: f"{m['last_name']}, {m['first_name']}"
                 for m in self._all_members}
        panel = NotificationsPanel(
            self._notifications["expiring"], self._notifications["expired"],
            names, self)
        panel.member_chosen.connect(self._open_member_auths)
        self._notif_panel = panel              # keep a reference while shown
        panel.open_under(self._btn_notif)

    def _update_bookmark_count(self):
        """Refresh the toolbar Bookmarks button's saved-count suffix."""
        from bookmarks import load_bookmarks
        n = len(load_bookmarks())
        self._btn_bookmarks.setText(
            f"🔖  Bookmarks ({n})" if n else "🔖  Bookmarks")

    def _on_bookmarks_edited(self):
        """A bookmark was removed from the panel: refresh the toolbar count
        and, when that member's profile is open, its header 🔖 button — so the
        profile never keeps saying 'Bookmarked' after an ✕ in the list."""
        self._update_bookmark_count()
        current = (self._detail_stack.widget(1)
                   if self._detail_stack.count() > 1 else None)
        if current is not None and hasattr(current, "_sync_bookmark_button"):
            current._sync_bookmark_button()

    def _open_bookmarks(self):
        from bookmarks import load_bookmarks
        from gui.bookmarks_panel import BookmarksPanel
        panel = BookmarksPanel(load_bookmarks(), self)
        panel.member_chosen.connect(self._jump_to_member)
        panel.bookmarks_edited.connect(self._on_bookmarks_edited)
        self._bookmarks_panel = panel          # keep a reference while shown
        panel.open_under(self._btn_bookmarks)

    def _open_member_auths(self, center_id):
        """From a notification row: open the member on their Auths tab so the
        expiring/expired authorization can be resolved."""
        self._jump_to_member(center_id)
        if self._last_center_id != center_id:
            return                              # blocked by unsaved-changes guard
        current = (self._detail_stack.widget(1)
                   if self._detail_stack.count() > 1 else None)
        if current is not None and hasattr(current, "_tabs"):
            current._tabs.setCurrentIndex(2)    # Authorizations tab

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
        total = len(self._all_members)
        active = sum(1 for m in self._all_members
                     if m["center_id"] not in self._terminated_ids)
        widget = GlobalEventsWidget(
            events_path, on_back=self._back_from_events,
            member_count=total, active_count=active)
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

    def _open_birthday_report(self):
        """Monthly birthdays report: pick a month, save a record sheet of
        active members born in it."""
        if not self._all_members:
            QMessageBox.warning(self, "No Members",
                "Load a database first (see ⚙ Settings).")
            return
        from gui.birthday_report import BirthdayReportDialog
        BirthdayReportDialog(self._all_members, self._terminated_ids,
                             self).exec()

    def _open_expiring_report(self):
        """Monthly expiring-auths report: pick a month, save as a spreadsheet
        or print, grouped by health plan."""
        db_path = self._settings.get("db_path", "")
        if not db_path:
            QMessageBox.warning(self, "No Database",
                "Set a database path in Settings before running reports.")
            return
        from gui.expiring_report import ExpiringReportDialog
        ExpiringReportDialog(db_path, self._all_members,
                             self._terminated_ids, self).exec()

    def _open_absence_report(self):
        """Monthly absences report: pick a month and year, save a record
        sheet of every absence overlapping it."""
        db_path = self._settings.get("db_path", "")
        if not db_path:
            QMessageBox.warning(self, "No Database",
                "Set a database path in Settings before running reports.")
            return
        from gui.absence_report import AbsenceReportDialog
        AbsenceReportDialog(db_path, self._all_members,
                            self._terminated_ids, self).exec()

    def _export_members(self):
        """Save the full member roster (info + latest enrollment + today's
        active auth + first emergency contact) as an .xlsx spreadsheet."""
        from datetime import date
        from PyQt6.QtWidgets import QFileDialog
        db_path = self._settings.get("db_path", "")
        if not db_path:
            QMessageBox.warning(self, "No Database",
                "Set a database path in Settings before exporting.")
            return
        default = os.path.join(
            os.path.expanduser("~/Documents"),
            f"BSCA Members {date.today():%Y-%m-%d}.xlsx")
        out_path, _ = QFileDialog.getSaveFileName(
            self, "Export Members", default, "Excel Workbook (*.xlsx)")
        if not out_path:
            return
        from PyQt6.QtGui import QGuiApplication, QCursor
        QGuiApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        try:
            from db.export import export_members_xlsx
            count = export_members_xlsx(db_path, out_path)
        except PermissionError:
            QGuiApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Export Failed",
                "The file couldn't be written.\n\nIt may be open in Excel — "
                "close it there and try again.")
            return
        except Exception as exc:
            QGuiApplication.restoreOverrideCursor()
            from gui.errors import show_db_error
            show_db_error(self, exc, "Export Failed")
            return
        QGuiApplication.restoreOverrideCursor()
        done = QMessageBox(self)
        done.setWindowTitle("Export Complete")
        done.setIcon(QMessageBox.Icon.Information)
        done.setText(f"Exported {count} members to:\n{out_path}")
        open_btn = done.addButton("Open Spreadsheet",
                                  QMessageBox.ButtonRole.AcceptRole)
        done.addButton(QMessageBox.StandardButton.Close)
        done.exec()
        if done.clickedButton() is open_btn:
            os.startfile(out_path)

    def _alt_id_key(self):
        """Derived key for the session alt-id password (None when unset)."""
        from db.alt_id_crypto import cached_key
        return cached_key(self._alt_id_password)

    def _open_settings(self):
        dlg = SettingsDialog(self._settings, self,
                             alt_id_password=self._alt_id_password)
        if dlg.exec():
            self._settings.update(dlg.result_settings())
            save_settings(self._settings, self._settings_path)
            self._alt_id_password = dlg.result_alt_id_password()
            # First key derivation (PBKDF2) blocks ~0.15s — warm it here under
            # a wait cursor; every later use hits the cache.
            QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                self._alt_id_key()
            finally:
                QGuiApplication.restoreOverrideCursor()
            # Drop cached DB handles so the new path is used on next access.
            from db.members import close_connections
            close_connections()
            from gui.theme import apply_theme
            apply_theme(QApplication.instance(), self._settings["theme"])
            self._refresh_list_theme()
            self._update_db_indicator()
            self._load_members()
            # Apply the row-ID debug toggle and the alt-id key to the open
            # member live (no rebuild, so unsaved edits survive).
            from gui.member_tabs import MemberTabsWidget
            current = (self._detail_stack.widget(1)
                       if self._detail_stack.count() > 1 else None)
            if isinstance(current, MemberTabsWidget):
                current.set_show_row_ids(self._settings.get("show_row_ids", False))
                current.set_alt_id_key(self._alt_id_key())
