from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel,
    QPushButton, QMessageBox, QTextEdit, QSizePolicy, QLineEdit,
)
from PyQt6.QtCore import Qt, pyqtSignal

from db.members import get_member_context
from gui.address_autocomplete import (
    set_active_inline_editor, clear_active_inline_editor,
)


class _NotesEdit(QTextEdit):
    """A QTextEdit that grows and shrinks its height to fit its content.

    Short notes stay compact; longer notes expand up to a cap (then scroll).
    """
    _MIN_H = 36
    _MAX_H = 150

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Fixed vertical policy: without this, QTextEdit's default Expanding
        # policy makes the whole header greedy for height and spreads its rows.
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.textChanged.connect(self._fit)

    def setPlainText(self, text: str) -> None:
        super().setPlainText(text)
        self._fit()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit()

    def _fit(self) -> None:
        doc = self.document()
        doc.setTextWidth(self.viewport().width())
        h = int(doc.size().height()) + 2 * self.frameWidth() + 4
        self.setFixedHeight(max(self._MIN_H, min(h, self._MAX_H)))


FIELD_LABELS = {
    "first_name": "First Name", "last_name": "Last Name",
    "chinese_name": "Chinese Name", "gender": "Gender", "dob": "DOB",
    "member_id": "Member ID", "medicaid": "Medicaid", "medicare": "Medicare",
    "ssn": "SSN", "language": "Language Spoken", "case_manager": "Case Manager",
    "home_tell": "Home Phone", "cell": "Cell", "address": "Address",
    "emergency": "Emergency", "pcp": "PCP", "hospital": "Hospital",
    "hha": "HHA", "admission_date": "Admission Date", "notes": "Notes",
}

WEEKDAY_NAMES = {
    1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat", 7: "Sun",
}


def make_plan_badge(plan: str | None, *, max_height: int = 26):
    """The colored health-plan pill, or None when there is no plan.

    Reused by the member header and the Authorizations table so the plan
    renders identically everywhere (per-plan color comes from PLAN_COLORS /
    the #plan_badge rules in theme.py).
    """
    if not plan:
        return None
    badge = QLabel(plan)
    badge.setObjectName("plan_badge")
    badge.setProperty("plan", plan)
    badge.setToolTip("Health Plan")
    badge.setMaximumHeight(max_height)
    return badge


_PILL_CELL_HMARGIN = 6   # left+right inset inside a centered pill cell


def _centered_cell(widget) -> QWidget:
    """Wrap a widget in a table cell that centers it horizontally, keeping it at
    its natural (compact) size rather than stretching it to fill the column.

    The widget is pinned to at least its own content width so the centering
    stretches (or a slightly narrow column) can never squeeze it and clip its
    text."""
    widget.setMinimumWidth(widget.sizeHint().width())
    cell = QWidget()
    box = QHBoxLayout(cell)
    box.setContentsMargins(_PILL_CELL_HMARGIN, 4, _PILL_CELL_HMARGIN, 4)
    box.setSpacing(0)
    box.addStretch()
    box.addWidget(widget)
    box.addStretch()
    return cell


def _fit_pill_column(table, col: int, pills: list, floor: int) -> None:
    """Fix `col` to a width that always fits the widest pill (plus the cell
    insets) or `floor`, whichever is larger. Avoids relying on ResizeToContents,
    which mis-measures widget-only columns and let the pills clip across DPI."""
    from PyQt6.QtWidgets import QHeaderView
    widest = max((p.sizeHint().width() for p in pills), default=0)
    width = max(widest + 2 * _PILL_CELL_HMARGIN + 4, floor)
    table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
    table.setColumnWidth(col, width)


def format_created_at(value) -> str:
    """Render an authorization's created_at for the table.

    datetime -> 'mm/dd/yyyy h:mm AM/PM' (minutes padded, hour not); a plain
    date -> 'mm/dd/yyyy'; missing/legacy rows -> '' (blank, not 'None').
    """
    from datetime import datetime, date
    if not value:
        return ""
    if isinstance(value, datetime):
        return f"{value:%m/%d/%Y} " + value.strftime("%I:%M %p").lstrip("0")
    if isinstance(value, date):
        return f"{value:%m/%d/%Y}"
    return str(value)


def decode_auth_days(auth_days: str) -> set[int]:
    """'1,3,5' -> {1, 3, 5}. Blank, whitespace-only, and non-numeric tokens are
    ignored so malformed data never raises."""
    days = set()
    for tok in (auth_days or "").split(","):
        tok = tok.strip()
        if tok.isdigit():
            days.add(int(tok))
    return days


def format_auth_days(auth_days: str) -> str:
    """'1,3,6' -> 'Mon Wed Sat'. Unknown day numbers fall back to their digit."""
    days = sorted(decode_auth_days(auth_days))
    return " ".join(WEEKDAY_NAMES.get(d, str(d)) for d in days)


def auth_warning(authorizations: list, today) -> str | None:
    """Warning label for a member's authorization state, or None.

    - "Missing: Authorizations" when there are no authorizations.
    - "Authorization Expired" when there are authorizations but none is
      currently valid (the latest end date is before today).
    - None when a currently-valid authorization exists.

    An end date equal to today is still valid; null end dates are open-ended
    and never count as expired.
    """
    if not authorizations:
        return "Missing: Authorizations"
    ends = [a["auth_end"] for a in authorizations if a.get("auth_end")]
    if ends and max(ends) < today:
        return "Authorization Expired"
    return None


def emergency_contact_warning(emergency_contacts: list) -> str | None:
    """'Missing: Emergency Contact' when the member has no emergency contacts
    on file, else None."""
    if not emergency_contacts:
        return "Missing: Emergency Contact"
    return None


def _normalize_value(v) -> str:
    """Normalize a field value for change comparison/display.

    Stored values may carry trailing whitespace (Access) and CRLF line
    endings (memo fields), while widget read-back is stripped with LF. Unify
    both so cosmetic-only differences are not reported as changes.
    """
    return (v or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def build_change_summary(old: dict, fields: dict) -> list[str]:
    """Friendly 'Label: old → new' lines for each field whose value changed.

    Values are normalized (newlines unified, surrounding whitespace stripped)
    before comparison, so trailing spaces or CRLF/LF differences do not count
    as changes. Blank values render as '(empty)'. Order follows `fields`.
    """
    lines = []
    for key, new_val in fields.items():
        old_norm = _normalize_value(old.get(key))
        new_norm = _normalize_value(new_val)
        if new_norm != old_norm:
            label = FIELD_LABELS.get(key, key)
            lines.append(f"{label}: {old_norm or '(empty)'} → {new_norm or '(empty)'}")
    return lines


def to_jpeg_bytes(src_path: str) -> bytes:
    """Load an image file and return JPEG-encoded bytes. Raises ValueError if the
    file can't be read as an image."""
    from PyQt6.QtGui import QImage
    from PyQt6.QtCore import QBuffer, QByteArray
    img = QImage(src_path)
    if img.isNull():
        raise ValueError("Could not read the selected image.")
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QBuffer.OpenModeFlag.WriteOnly)
    img.save(buf, "JPEG", 90)
    buf.close()
    return bytes(ba)


def sort_auths_latest_first(auths: list[dict]) -> list[dict]:
    """Authorizations ordered by end date, latest first. Missing end dates sort
    last. Returns a new list (does not mutate the input)."""
    from datetime import date
    return sorted(auths, key=lambda a: a.get("auth_end") or date.min, reverse=True)


# Muted foreground for expired authorization rows. Neutral slate that reads as
# clearly dimmed against both the dark and light backgrounds.
EXPIRED_FG = "#7d8198"


def is_auth_expired(auth: dict, today) -> bool:
    """True when an authorization's window has passed (auth_end < today).

    Mirrors auth_warning: today still counts as in-effect, and an open-ended
    authorization (no auth_end) is never expired.
    """
    end = auth.get("auth_end")
    return bool(end) and end < today


# ── Availability view helpers (Availability tab) ───────────────────────────
def is_avail_expired(avail: dict, today) -> bool:
    """True when an availability's effective window has passed
    (effective_end_date < today). Open-ended rows are never expired; today
    still counts as in-effect."""
    end = avail.get("effective_end_date")
    return bool(end) and end < today


def avail_in_effect_on(avail: dict, today) -> bool:
    """True when `today` falls inside the availability's effective window:
    effective_start_date <= today <= effective_end_date (end open = no upper
    bound; missing start = already begun)."""
    start = avail.get("effective_start_date")
    end = avail.get("effective_end_date")
    if start is not None and start > today:
        return False
    if end is not None and end < today:
        return False
    return True


def format_avail_window(start: str, end: str) -> str:
    """'08:00'/'16:00' -> '08:00–16:00'; blank/blank -> '—'."""
    if not start and not end:
        return "—"
    return f"{start or '—'}–{end or '—'}"


def current_schedule(avails: list[dict], today) -> dict:
    """Map day_of_week -> [(start, end), ...] for the rows in effect today,
    each day's windows ordered by start time. Feeds the Current Schedule strip."""
    sched: dict[int, list] = {}
    for a in avails:
        if avail_in_effect_on(a, today):
            sched.setdefault(a["day_of_week"], []).append(
                (a.get("avail_start") or "", a.get("avail_end") or ""))
    for windows in sched.values():
        windows.sort()
    return sched


def sort_avail_for_table(avails: list[dict], today) -> list[dict]:
    """Active rows first then expired, each group ordered by weekday (Mon→Sun)
    then by effective-from date. Returns a new list (input is not mutated)."""
    from datetime import date
    return sorted(
        avails,
        key=lambda a: (
            is_avail_expired(a, today),
            a.get("day_of_week", 0),
            a.get("effective_start_date") or date.min,
        ),
    )


class WeekdayChips(QWidget):
    """A row of seven weekday chips, Mon→Sun. Authorized days are filled with the
    accent color (object name 'day_chip_on'); the rest are dimmed
    ('day_chip_off'). `compact=True` uses single-letter labels for table cells.
    Purely presentational — callers decode the encoded auth_days string with
    `decode_auth_days` and pass the resulting set in."""

    def __init__(self, days, compact: bool = False, parent=None):
        super().__init__(parent)
        self._days = set(days)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(3 if compact else 4)
        row.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._chips = []
        for num in range(1, 8):
            name = WEEKDAY_NAMES[num]
            chip = QLabel(name[0] if compact else name.upper())
            chip.setObjectName("day_chip_on" if num in self._days else "day_chip_off")
            chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chip.setMinimumWidth(22 if compact else 34)  # uniform, grid-like track
            self._chips.append(chip)
            row.addWidget(chip)
        row.addStretch()


class _PhotoLabel(QLabel):
    """An 80x80 photo label that emits `clicked` when pressed (left button)."""

    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Click to change photo")

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(e)


def _pencil_icon():
    """A small pencil glyph as a QIcon for the inline 'edit' affordance."""
    from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor
    pm = QPixmap(16, 16)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setPen(QColor("#5b7cf4"))  # accent blue — clearly the edit affordance
    p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, "✎")
    p.end()
    return QIcon(pm)


class _ViewEditLineEdit(QLineEdit):
    """A field that reads as flat, selectable text (highlight + copy) and only
    becomes editable when the user clicks its pencil (shown on hover).

    It stays a QLineEdit, so .text()/.setText()/textChanged work unchanged with
    the existing Save/Discard and dirty-tracking logic. ``editable=False`` makes
    a plain flat read-only field (no pencil) for values like Center ID.
    """

    def __init__(self, value: str = "", editable: bool = True, parent=None):
        super().__init__(value or "", parent)
        self._editable = editable
        self._baseline = value or ""
        self._edit_start = value or ""
        self._hover = False
        self.setObjectName("info_field")
        self.setReadOnly(True)
        self.setCursorPosition(0)
        self._pencil = None
        if editable:
            self._pencil = self.addAction(
                _pencil_icon(), QLineEdit.ActionPosition.TrailingPosition)
            self._pencil.setToolTip("Edit")
            self._pencil.triggered.connect(self._begin_edit)
            self._pencil.setVisible(False)
            self.editingFinished.connect(self._finish_edit)
            self.textChanged.connect(self._refresh_state)
        self._refresh_state()

    def _repolish(self):
        self.style().unpolish(self)
        self.style().polish(self)

    def _is_empty(self) -> bool:
        return self._editable and self.text() == ""

    def _update_pencil(self):
        # Pencil shows on hover for filled fields, and always for empty editable
        # fields (so an empty field is obviously there and fillable).
        if self._pencil is not None:
            self._pencil.setVisible(
                self.isReadOnly() and (self._is_empty() or self._hover))

    def enterEvent(self, e):
        self._hover = True
        self._update_pencil()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False
        self._update_pencil()
        super().leaveEvent(e)

    def _begin_edit(self):
        if not self._editable or not self.isReadOnly():
            return
        set_active_inline_editor(self)        # finish any other open field
        self._edit_start = self.text()
        self.setReadOnly(False)
        if self._pencil is not None:
            self._pencil.setVisible(False)
        self.setProperty("editing", True)
        self._repolish()
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        self.selectAll()

    def _finish_edit(self):
        if self.isReadOnly():
            return
        self.setReadOnly(True)
        self.setProperty("editing", False)
        self._repolish()
        self._update_pencil()
        clear_active_inline_editor(self)

    def keyPressEvent(self, e):
        if not self.isReadOnly() and e.key() == Qt.Key.Key_Escape:
            self.setText(self._edit_start)     # revert the in-progress edit
            self._finish_edit()
            return
        super().keyPressEvent(e)

    def _refresh_state(self):
        # Empty editable fields read as a visible (dashed) box; filled fields are
        # flat text. A value differing from the saved baseline gets a highlight.
        self.setProperty("empty", self._is_empty())
        self.setProperty("changed", self.text() != self._baseline)
        self._repolish()
        self._update_pencil()

    def set_baseline(self):
        """Treat the current text as the saved value (clears the changed mark)."""
        self._baseline = self.text()
        self._refresh_state()


# Warn before attaching a document larger than this (native Access attachments
# live inside the .accdb, which has a 2 GB ceiling).
MAX_DOC_WARN_MB = 10

# Decoded 80x80 member photos, keyed by center_id: (QPixmap, has_photo). Reading
# and decoding the JPEG is the slowest part of opening a member after the DB
# read, so cache it across opens. Invalidated when a photo is changed in-app.
_PHOTO_CACHE: dict = {}


class MemberTabsWidget(QWidget):
    def __init__(self, center_id: int, db_path: str, events_path: str,
                 api_key: str = "", parent=None):
        super().__init__(parent)
        self._center_id = center_id
        self._db_path = db_path
        self._events_path = events_path
        self._api_key = api_key or ""
        self._member = None
        self._load_data()
        self._build_ui()
        self._dirty = False
        self._setup_dirty_tracking()

    def _load_data(self):
        self._member = {}
        self._enrollments = []
        self._authorizations = []
        self._availability = []
        self._absences = []
        self._one_off = []
        self._emergency_contacts = []
        try:
            # get_member_context reads the live DB: the cached read connection
            # reopens automatically when the file changed (mtime), so external
            # edits (e.g. in Microsoft Access) are picked up without paying a
            # reconnect on every member click.
            ctx = get_member_context(self._center_id, self._db_path)
            self._member = ctx["member"]
            self._enrollments = ctx["enrollments"]
            self._authorizations = ctx["authorizations"]
            self._availability = ctx["availability"]
            self._absences = ctx["absences"]
            self._one_off = ctx.get("one_off_availability", [])
            self._emergency_contacts = ctx.get("emergency_contacts", [])
        except Exception as exc:
            QMessageBox.critical(self, "Load Error", str(exc))

    def _log_event(self, event_type: str, description: str) -> None:
        """Record an event for this member (when an events log is configured)
        and refresh the member's Events tab."""
        if self._events_path:
            from db.events import open_db, insert_event
            m = self._member
            conn = open_db(self._events_path)
            try:
                insert_event(
                    conn, event_type, self._center_id,
                    f"{m.get('last_name', '')}, {m.get('first_name', '')}",
                    description,
                )
            finally:
                conn.close()
        if hasattr(self, "_tab_events"):
            self._tab_events.refresh()

    def _make_photo_label(self) -> QLabel:
        """Return an 80×80 clickable label showing the member photo. Clicking it
        opens a file picker to set/replace the photo."""
        from db.members import get_member_photo
        self._photo_label = _PhotoLabel()
        self._photo_label.setFixedSize(80, 80)
        self._photo_label.setStyleSheet("border-radius: 40px; overflow: hidden;")
        self._photo_label.clicked.connect(self._change_photo)
        cached = _PHOTO_CACHE.get(self._center_id)
        if cached is not None:
            pix, self._has_photo = cached
            self._photo_label.setPixmap(pix)
        else:
            self._set_photo_pixmap(get_member_photo(self._center_id, self._db_path))
        return self._photo_label

    def _set_photo_pixmap(self, photo_bytes):
        """Paint the member photo (or the placeholder) onto self._photo_label and
        record whether a photo exists."""
        from PyQt6.QtGui import QPixmap, QPainter, QColor, QBrush
        from PyQt6.QtCore import Qt as QtCore
        self._has_photo = bool(photo_bytes)
        if photo_bytes:
            pix = QPixmap()
            pix.loadFromData(photo_bytes)
            pix = pix.scaled(80, 80, QtCore.AspectRatioMode.KeepAspectRatioByExpanding,
                             QtCore.TransformationMode.SmoothTransformation)
            if pix.width() > 80 or pix.height() > 80:
                x = (pix.width() - 80) // 2
                y = (pix.height() - 80) // 2
                pix = pix.copy(x, y, 80, 80)
            self._photo_label.setPixmap(pix)
        else:
            pix = QPixmap(80, 80)
            pix.fill(QtCore.GlobalColor.transparent)
            painter = QPainter(pix)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QBrush(QColor("#3a3a3a")))
            painter.setPen(QtCore.PenStyle.NoPen)
            painter.drawEllipse(0, 0, 80, 80)
            painter.setBrush(QBrush(QColor("#888888")))
            painter.drawEllipse(28, 12, 24, 24)
            painter.drawEllipse(12, 46, 56, 40)
            painter.end()
            self._photo_label.setPixmap(pix)
        _PHOTO_CACHE[self._center_id] = (pix, self._has_photo)

    def _change_photo(self):
        from PyQt6.QtWidgets import QFileDialog
        from db.members import set_member_photo, get_member_photo
        import os
        import tempfile

        if self._has_photo:
            if QMessageBox.question(
                self, "Replace photo",
                "Replace this member's existing photo?",
            ) != QMessageBox.StandardButton.Yes:
                return

        path, _ = QFileDialog.getOpenFileName(
            self, "Choose photo", "",
            "Images (*.jpg *.jpeg *.png *.bmp *.webp)",
        )
        if not path:
            return

        try:
            data = to_jpeg_bytes(path)
        except ValueError as exc:
            QMessageBox.critical(self, "Invalid Image", str(exc))
            return

        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        try:
            tmp.write(data)
            tmp.close()
            set_member_photo(self._center_id, tmp.name, self._db_path)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Could not save photo:\n{exc}")
            return
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

        _PHOTO_CACHE.pop(self._center_id, None)  # photo changed -> refresh cache
        self._set_photo_pixmap(get_member_photo(self._center_id, self._db_path))
        self._log_event("EDIT", "Photo updated")

    @staticmethod
    def decode_auth_days_static(value: str) -> set[int]:
        if not value:
            return set()
        return {int(x) for x in value.split(",") if x.strip()}

    @staticmethod
    def _active_authorization(authorizations: list[dict]) -> dict | None:
        """Return the auth row covering today, preferring latest start. None if none."""
        from datetime import date
        today = date.today()
        candidates = [
            a for a in authorizations
            if a.get("effective_start") and a.get("effective_end")
            and a["effective_start"] <= today <= a["effective_end"]
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda a: a["effective_start"])

    @staticmethod
    def _enrollment_start(enrollments: list[dict]):
        """Return the earliest enrollment start_date, or None."""
        dates = [e["start_date"] for e in enrollments if e.get("start_date")]
        return min(dates) if dates else None

    def _print_profile(self):
        """Open a print preview (print or Save-as-PDF) of this member's profile."""
        from gui.profile_print import open_profile_print_preview
        from db.members import get_member_photo

        photo = get_member_photo(self._center_id, self._db_path)
        open_profile_print_preview(
            self, self._member, self._emergency_contacts,
            self._enrollment_start(self._enrollments), photo_bytes=photo,
        )

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 10, 20, 8)
        layout.setSpacing(8)

        # Header: photo on the left; a right column with the name + missing
        # badge on top, and the Notes editor (auto-sizing) filling the rest of
        # the otherwise-empty band. Notes is created here (before the tabs) so
        # the Info tab's save/discard/dirty tracking can reference it.
        header = QHBoxLayout()
        header.setSpacing(14)
        header.addWidget(self._make_photo_label(),
                         alignment=Qt.AlignmentFlag.AlignTop)

        right = QVBoxLayout()
        right.setSpacing(6)

        top_row = QHBoxLayout()
        name = f"{self._member.get('last_name', '')}, {self._member.get('first_name', '')}"
        cid = str(self._center_id)
        name_label = QLabel(f"<b style='font-size:15px'>{name}</b>"
                            f"<span style='color:gray;font-size:12px'> &nbsp;ID {cid}</span>")
        name_label.setTextFormat(Qt.TextFormat.RichText)
        top_row.addWidget(name_label)
        plan_badge = make_plan_badge(self._member.get("health_plan", ""))
        if plan_badge is not None:
            top_row.addWidget(plan_badge, alignment=Qt.AlignmentFlag.AlignVCenter)
        from db.members import is_terminated
        if is_terminated(self._enrollments):
            term_badge = QLabel("⊘ Terminated")
            term_badge.setObjectName("terminated_badge")
            term_badge.setMaximumHeight(26)
            top_row.addWidget(term_badge, alignment=Qt.AlignmentFlag.AlignVCenter)
        top_row.addStretch()
        from datetime import date
        warn = auth_warning(self._authorizations, date.today())
        if warn:
            badge = QLabel("⚠ " + warn)
            badge.setObjectName("warning_badge")
            badge.setMaximumHeight(26)
            top_row.addWidget(badge, alignment=Qt.AlignmentFlag.AlignVCenter)
        # Emergency-contact badge: created here (hidden) so it can toggle live
        # when contacts are added/removed in the Info tab. _fill_emergency_box
        # sets its initial state.
        self._emergency_badge = QLabel()
        self._emergency_badge.setObjectName("warning_badge")
        self._emergency_badge.setMaximumHeight(26)
        self._emergency_badge.setVisible(False)
        top_row.addWidget(self._emergency_badge,
                          alignment=Qt.AlignmentFlag.AlignVCenter)
        btn_print = QPushButton("🖨 Print")
        btn_print.setObjectName("btn_print")
        btn_print.setToolTip("Print this member's profile")
        btn_print.setMaximumHeight(26)
        btn_print.clicked.connect(self._print_profile)
        top_row.addWidget(btn_print, alignment=Qt.AlignmentFlag.AlignVCenter)
        right.addLayout(top_row)

        notes_row = QHBoxLayout()
        notes_lbl = QLabel("Notes")
        notes_lbl.setObjectName("notes_label")
        notes_row.addWidget(notes_lbl, alignment=Qt.AlignmentFlag.AlignTop)
        self._info_notes = _NotesEdit()
        self._info_notes.setObjectName("notes_edit")
        self._info_notes.setPlainText(self._member.get("notes", "") or "")
        notes_row.addWidget(self._info_notes, 1)
        right.addLayout(notes_row)

        header.addLayout(right, 1)
        layout.addLayout(header)

        # Tabs
        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        self._tab_info = self._make_info_tab()
        self._tab_enrollments = self._make_enrollments_tab()
        self._tab_auths = self._make_auths_tab()
        self._tab_avail = self._make_avail_tab()
        self._tab_unavail = self._make_unavailable_tab()
        self._tab_absences = self._make_absences_tab()

        self._tabs.addTab(self._tab_info, "Info")
        self._tabs.addTab(self._tab_enrollments, "Enrollments")
        self._tabs.addTab(self._tab_auths,
            "Auths ⚠" if warn else "Authorizations")
        self._tabs.addTab(self._tab_avail, "Time Slot Availability")
        self._tabs.addTab(self._tab_unavail, "Unavailable Times")
        self._tabs.addTab(self._tab_absences, "Absences")

        # Events tab added after (Task 11 wires it in)
        from gui.events_view import EventsTableWidget
        self._tab_events = EventsTableWidget(
            self._events_path, center_id=self._center_id, show_header=False
        )
        self._tabs.addTab(self._tab_events, "Events")

    # ── Info tab (Task 9) ──────────────────────────────────────────────────

    def _make_info_tab(self) -> QWidget:
        from PyQt6.QtWidgets import (
            QLineEdit, QScrollArea, QGridLayout,
        )
        from PyQt6.QtGui import QFont

        m = self._member

        def field(key: str) -> "_ViewEditLineEdit":
            # Flat, selectable text that becomes editable on the hover pencil.
            return _ViewEditLineEdit(m.get(key, "") or "")

        # ── Widgets (attribute names unchanged so save/discard/dirty work) ──
        self._info_first     = field("first_name")
        self._info_last      = field("last_name")
        self._info_chinese   = field("chinese_name")
        self._info_gender    = field("gender")
        self._info_dob       = field("dob")
        self._info_cid       = _ViewEditLineEdit(str(self._center_id),
                                                 editable=False)
        # Member ID is assigned at member creation and shown read-only here.
        self._info_member_id = _ViewEditLineEdit(m.get("member_id", "") or "",
                                                 editable=False)

        from gui.address_autocomplete import AddressAutocomplete
        self._info_address = AddressAutocomplete(self._api_key, view_edit=True)
        self._info_address.set_address(m.get("address", "") or "")
        self._info_home_tell = field("home_tell")
        self._info_cell      = field("cell")
        self._info_emergency = field("emergency")

        self._info_plan = _ViewEditLineEdit(m.get("health_plan", "") or "",
                                            editable=False)
        self._info_medicaid = field("medicaid")
        self._info_medicare = field("medicare")
        self._info_ssn      = field("ssn")
        self._info_pcp      = field("pcp")
        self._info_hospital = field("hospital")
        self._info_hha      = field("hha")
        self._info_language = field("language")

        self._info_case_manager   = field("case_manager")
        self._info_admission_date = field("admission_date")
        # Notes is built in the header (always-visible band), not here.

        enroll_start = self._enrollment_start(self._enrollments)
        enroll_lbl = _ViewEditLineEdit(str(enroll_start) if enroll_start else "—",
                                       editable=False)
        active_auth = self._active_authorization(self._authorizations)
        if active_auth:
            active_days = decode_auth_days(active_auth.get("auth_days", ""))
            plan = active_auth.get("health_plan", "")
            period_text = (f"{active_auth['effective_start']} – "
                           f"{active_auth['effective_end']}"
                           + (f"  ·  {plan}" if plan else ""))
        else:
            active_days = set()
            period_text = "None"
        auth_period_lbl = _ViewEditLineEdit(period_text, editable=False)

        # ── Dense sectioned grid: 3 field columns, no card chrome ──────────
        grid = QGridLayout()
        grid.setContentsMargins(4, 4, 8, 4)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(5)
        for wcol in (1, 3, 5):            # the three widget columns stretch
            grid.setColumnStretch(wcol, 1)
        state = {"row": 0}

        def section(title: str):
            h = QLabel(title.upper())
            h.setObjectName("section_header")
            f = h.font()
            f.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 108)
            h.setFont(f)
            grid.addWidget(h, state["row"], 0, 1, 6)
            state["row"] += 1

        def cell(slot: int, label_text: str, widget, wspan: int = 1):
            lab = QLabel(label_text)
            lab.setObjectName("field_label")
            grid.addWidget(lab, state["row"], slot * 2,
                           Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(widget, state["row"], slot * 2 + 1, 1, wspan * 2 - 1)

        section("Schedule")
        cell(0, "Authorized Days", WeekdayChips(active_days), wspan=3)
        state["row"] += 1
        cell(0, "Auth Period", auth_period_lbl, wspan=2)
        state["row"] += 1

        section("Identity")
        cell(0, "First Name", self._info_first)
        cell(1, "Last Name", self._info_last)
        cell(2, "Chinese Name", self._info_chinese)
        state["row"] += 1
        cell(0, "Gender", self._info_gender)
        cell(1, "DOB", self._info_dob)
        cell(2, "SSN", self._info_ssn)
        state["row"] += 1
        cell(0, "Center ID", self._info_cid)
        cell(1, "Enrollment Start", enroll_lbl)
        cell(2, "Language Spoken", self._info_language)
        state["row"] += 1

        section("Contact")
        cell(0, "Address", self._info_address, wspan=3)
        state["row"] += 1
        cell(0, "Home Phone", self._info_home_tell)
        cell(1, "Cell", self._info_cell)
        state["row"] += 1

        section("Medical")
        cell(0, "Health Plan", self._info_plan)
        cell(1, "Member ID", self._info_member_id)
        cell(2, "Medicaid", self._info_medicaid)
        state["row"] += 1
        cell(0, "Medicare", self._info_medicare)
        cell(1, "Hospital", self._info_hospital)
        state["row"] += 1
        # PCP and HHA can hold long, address-like values — give each the full
        # row width so the text is visible instead of truncated in a column.
        cell(0, "PCP", self._info_pcp, wspan=3)
        state["row"] += 1
        cell(0, "HHA", self._info_hha, wspan=3)
        state["row"] += 1

        section("Care")
        cell(0, "Case Manager", self._info_case_manager)
        cell(1, "Admission Date", self._info_admission_date)
        state["row"] += 1

        section("Emergency")
        self._emergency_box = QWidget()
        ebox = QVBoxLayout(self._emergency_box)
        ebox.setContentsMargins(0, 0, 0, 0)
        grid.addWidget(self._emergency_box, state["row"], 0, 1, 6)
        state["row"] += 1
        self._fill_emergency_box()

        # ── Assemble (scroll area is a safety net; content fits unscrolled) ─
        content = QWidget()
        cvbox = QVBoxLayout(content)
        cvbox.setContentsMargins(0, 4, 0, 4)
        cvbox.addLayout(grid)
        cvbox.addStretch()

        scroll = QScrollArea()
        scroll.setWidget(content)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        outer = QWidget()
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(0, 8, 0, 0)
        outer_layout.setSpacing(8)
        outer_layout.addWidget(scroll)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_discard = QPushButton("Discard Changes")
        btn_discard.clicked.connect(self._confirm_discard)
        btn_save = QPushButton("Save Changes")
        btn_save.setObjectName("btn_save")
        btn_save.clicked.connect(self._save_info)
        btn_row.addWidget(btn_discard)
        btn_row.addWidget(btn_save)
        outer_layout.addLayout(btn_row)

        return outer

    def _fill_emergency_box(self):
        """(Re)build the embedded emergency-contacts table + buttons in place."""
        from PyQt6.QtWidgets import (
            QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView,
        )
        box = self._emergency_box.layout()
        while box.count():
            item = box.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
            elif item.layout() is not None:
                sub = item.layout()
                while sub.count():
                    sw = sub.takeAt(0).widget()
                    if sw is not None:
                        sw.deleteLater()

        columns = ["Full Name", "Phone", "Relationship", "Action"]
        table = QTableWidget(len(self._emergency_contacts), len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        hdr = table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(34)

        for r, ec in enumerate(self._emergency_contacts):
            name_item = QTableWidgetItem(ec["full_name"])
            name_item.setData(Qt.ItemDataRole.UserRole, ec["id"])
            table.setItem(r, 0, name_item)
            table.setItem(r, 1, QTableWidgetItem(ec["phone"]))
            table.setItem(r, 2, QTableWidgetItem(ec["relationship"]))
            btn = QPushButton("Edit")
            btn.setObjectName("btn_edit")
            btn.clicked.connect(lambda _=False, e=ec: self._edit_emergency(e))
            table.setCellWidget(r, 3, btn)

        # Fix the table's height to fit its rows so it can't be vertically
        # squeezed/collapsed inside the Info scroll area (an Expanding table let
        # the scroll area hide contacts until the window was enlarged). The outer
        # scroll bar handles overflow instead.
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        header_h = table.horizontalHeader().sizeHint().height()
        rows_h = table.verticalHeader().defaultSectionSize() * table.rowCount()
        table.setFixedHeight(header_h + rows_h + 2 * table.frameWidth() + 2)

        self._emergency_table = table
        box.addWidget(table)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("+ Add")
        btn_add.clicked.connect(self._add_emergency)
        btn_del = QPushButton("Delete Selected")
        btn_del.clicked.connect(lambda: self._delete_emergency(table))
        btn_row.addWidget(btn_add)
        btn_row.addStretch()
        btn_row.addWidget(btn_del)
        box.addLayout(btn_row)

        self._update_emergency_badge()

    def _update_emergency_badge(self):
        """Show/hide the header 'Missing: Emergency Contact' badge to match the
        current contact list. Called on initial render and after every
        add/edit/delete (all of which funnel through _fill_emergency_box)."""
        badge = getattr(self, "_emergency_badge", None)
        if badge is None:
            return
        warn = emergency_contact_warning(self._emergency_contacts)
        if warn:
            badge.setText("⚠ " + warn)
            badge.setVisible(True)
        else:
            badge.setVisible(False)

    def _open_emergency_dialog(self, existing: dict | None = None):
        from PyQt6.QtWidgets import (
            QDialog, QFormLayout, QLineEdit, QDialogButtonBox,
        )
        e = existing or {}
        dlg = QDialog(self)
        dlg.setWindowTitle("Edit Emergency Contact" if existing
                           else "Add Emergency Contact")
        form = QFormLayout(dlg)
        name_edit = QLineEdit(e.get("full_name", ""))
        phone_edit = QLineEdit(e.get("phone", ""))
        rel_edit = QLineEdit(e.get("relationship", ""))
        form.addRow("Full Name:", name_edit)
        form.addRow("Phone Number:", phone_edit)
        form.addRow("Relationship:", rel_edit)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)

        def on_accept():
            if not name_edit.text().strip():
                QMessageBox.warning(dlg, "Validation", "Full Name is required.")
                return
            dlg.accept()

        btns.accepted.connect(on_accept)
        if not dlg.exec():
            return None
        return {
            "full_name": name_edit.text().strip(),
            "phone": phone_edit.text().strip(),
            "relationship": rel_edit.text().strip(),
        }

    def _add_emergency(self):
        from db.members import insert_emergency_contact, get_emergency_contacts
        result = self._open_emergency_dialog()
        if not result:
            return
        try:
            insert_emergency_contact(
                self._center_id, result["full_name"], result["phone"],
                result["relationship"], self._db_path,
            )
            self._emergency_contacts = get_emergency_contacts(
                self._center_id, self._db_path)
            self._fill_emergency_box()
            self._log_event("EDIT",
                            f"Emergency contact added: {result['full_name']}")
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _edit_emergency(self, entry: dict):
        from db.members import update_emergency_contact, get_emergency_contacts
        result = self._open_emergency_dialog(existing=entry)
        if not result:
            return
        try:
            update_emergency_contact(
                entry["id"], result["full_name"], result["phone"],
                result["relationship"], self._db_path,
            )
            self._emergency_contacts = get_emergency_contacts(
                self._center_id, self._db_path)
            self._fill_emergency_box()
            self._log_event("EDIT",
                            f"Emergency contact edited: {result['full_name']}")
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _delete_emergency(self, table):
        row = table.currentRow()
        if row < 0:
            return
        item = table.item(row, 0)
        record_id = item.data(Qt.ItemDataRole.UserRole) if item else None
        if record_id is None:
            return
        if QMessageBox.question(self, "Confirm", "Delete this emergency contact?") \
                == QMessageBox.StandardButton.Yes:
            from db.members import delete_emergency_contact, get_emergency_contacts
            entry = next((e for e in self._emergency_contacts
                          if e["id"] == record_id), None)
            try:
                delete_emergency_contact(record_id, self._db_path)
                self._emergency_contacts = get_emergency_contacts(
                    self._center_id, self._db_path)
                self._fill_emergency_box()
                if entry:
                    self._log_event(
                        "EDIT",
                        f"Emergency contact deleted: {entry['full_name']}")
            except Exception as exc:
                QMessageBox.critical(self, "Error", str(exc))

    def _confirm_discard(self):
        """Confirm before reverting unsaved edits. No-op when nothing changed."""
        if not self._dirty:
            return
        reply = QMessageBox.question(
            self, "Discard changes?",
            "Discard all unsaved changes to this member?",
            QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Discard:
            self._discard_info()

    def _discard_info(self):
        m = self._member
        self._info_first.setText(m.get("first_name", "") or "")
        self._info_last.setText(m.get("last_name", "") or "")
        self._info_chinese.setText(m.get("chinese_name", "") or "")
        self._info_gender.setText(m.get("gender", "") or "")
        self._info_dob.setText(m.get("dob", "") or "")
        self._info_member_id.setText(m.get("member_id", "") or "")
        self._info_medicaid.setText(m.get("medicaid", "") or "")
        self._info_medicare.setText(m.get("medicare", "") or "")
        self._info_ssn.setText(m.get("ssn", "") or "")
        self._info_pcp.setText(m.get("pcp", "") or "")
        self._info_hospital.setText(m.get("hospital", "") or "")
        self._info_hha.setText(m.get("hha", "") or "")
        self._info_language.setText(m.get("language", "") or "")
        self._info_address.setText(m.get("address", "") or "")
        self._info_home_tell.setText(m.get("home_tell", "") or "")
        self._info_cell.setText(m.get("cell", "") or "")
        self._info_emergency.setText(m.get("emergency", "") or "")
        self._info_case_manager.setText(m.get("case_manager", "") or "")
        self._info_admission_date.setText(m.get("admission_date", "") or "")
        self._info_notes.setPlainText(m.get("notes", "") or "")
        self._dirty = False

    def _save_info(self):
        from db.members import update_contact

        old = self._member
        fields = {
            "last_name":      self._info_last.text().strip(),
            "first_name":     self._info_first.text().strip(),
            "chinese_name":   self._info_chinese.text().strip(),
            "gender":         self._info_gender.text().strip(),
            "dob":            self._info_dob.text().strip(),
            "member_id":      self._info_member_id.text().strip(),
            "health_plan":    self._member.get("health_plan", "") or "",
            "medicaid":       self._info_medicaid.text().strip(),
            "medicare":       self._info_medicare.text().strip(),
            "ssn":            self._info_ssn.text().strip(),
            "language":       self._info_language.text().strip(),
            "case_manager":   self._info_case_manager.text().strip(),
            "home_tell":      self._info_home_tell.text().strip(),
            "cell":           self._info_cell.text().strip(),
            "address":        self._info_address.text().strip(),
            "emergency":      self._info_emergency.text().strip(),
            "pcp":            self._info_pcp.text().strip(),
            "hospital":       self._info_hospital.text().strip(),
            "hha":            self._info_hha.text().strip(),
            "admission_date": self._info_admission_date.text().strip(),
            "notes":          self._info_notes.toPlainText().strip(),
        }

        summary = build_change_summary(old, fields)
        if not summary:
            self._dirty = False
            return

        name = f"{old.get('last_name', '')}, {old.get('first_name', '')}"
        confirm = QMessageBox(self)
        confirm.setWindowTitle("Confirm Changes")
        confirm.setIcon(QMessageBox.Icon.Question)
        confirm.setText(f"Confirm changes for {name}?")
        confirm.setInformativeText("\n".join(summary))
        confirm.setStandardButtons(
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Cancel
        )
        confirm.setDefaultButton(QMessageBox.StandardButton.Save)
        if confirm.exec() != QMessageBox.StandardButton.Save:
            return  # user cancelled — keep edits, stay dirty

        try:
            update_contact(
                center_id=self._center_id,
                last_name=fields["last_name"],
                first_name=fields["first_name"],
                chinese_name=fields["chinese_name"],
                gender=fields["gender"],
                dob=fields["dob"],
                member_id=fields["member_id"],
                health_plan=fields["health_plan"],
                medicaid=fields["medicaid"],
                medicare=fields["medicare"],
                ssn=fields["ssn"],
                language=fields["language"],
                case_manager=fields["case_manager"],
                home_tell=fields["home_tell"],
                cell=fields["cell"],
                address=fields["address"],
                emergency=fields["emergency"],
                pcp=fields["pcp"],
                hospital=fields["hospital"],
                hha=fields["hha"],
                admission_date=fields["admission_date"],
                notes=fields["notes"],
                db_path=self._db_path,
            )
            self._member.update(fields)
            self._dirty = False
            for w in self.findChildren(_ViewEditLineEdit):
                w.set_baseline()                 # saved values -> clear highlight
            new_long_lat = self._info_address.long_lat()
            if new_long_lat:
                from db.members import set_member_long_lat
                set_member_long_lat(self._center_id, new_long_lat, self._db_path)
            self._log_event("EDIT", "; ".join(summary))
        except Exception as exc:
            QMessageBox.critical(self, "Save Error", str(exc))

    # ── Dirty tracking ─────────────────────────────────────────────────────

    def _setup_dirty_tracking(self):
        self._dirty = False
        line_edits = (
            self._info_first, self._info_last, self._info_chinese,
            self._info_gender, self._info_dob,
            self._info_medicaid, self._info_medicare, self._info_ssn,
            self._info_language, self._info_case_manager,
            self._info_home_tell, self._info_cell, self._info_address,
            self._info_emergency, self._info_pcp, self._info_hospital,
            self._info_hha, self._info_admission_date,
        )
        for w in line_edits:
            w.textChanged.connect(lambda: setattr(self, '_dirty', True))
        self._info_notes.textChanged.connect(lambda: setattr(self, '_dirty', True))

    def is_dirty(self) -> bool:
        return self._dirty

    # ── Table tab helper ───────────────────────────────────────────────────

    def _make_table_tab(self, columns, rows, on_add, on_delete):
        from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QAbstractItemView
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 12, 0, 0)

        table = QTableWidget(len(rows), len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(34)  # room for action buttons

        for r, row_data in enumerate(rows):
            for c, val in enumerate(row_data):
                table.setItem(r, c, QTableWidgetItem(str(val) if val is not None else ""))

        layout.addWidget(table)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("+ Add")
        btn_add.clicked.connect(on_add)
        btn_del = QPushButton("Delete Selected")
        btn_del.clicked.connect(lambda: on_delete(table))
        btn_row.addWidget(btn_add)
        btn_row.addStretch()
        btn_row.addWidget(btn_del)
        layout.addLayout(btn_row)
        return w, table

    def _refresh_tab(self, index: int, new_widget: QWidget):
        old = self._tabs.widget(index)
        label = self._tabs.tabText(index)
        self._tabs.removeTab(index)
        self._tabs.insertTab(index, new_widget, label)
        self._tabs.setCurrentIndex(index)
        if old:
            old.deleteLater()

    # ── Enrollments tab ────────────────────────────────────────────────────

    def _make_enrollments_tab(self) -> QWidget:
        from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QAbstractItemView
        from datetime import date

        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 12, 0, 0)

        columns = ["ID", "Start Date", "End Date", "Status"]
        table = QTableWidget(len(self._enrollments), len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(34)  # room for action buttons

        today = date.today()
        for r, e in enumerate(self._enrollments):
            end = e["end_date"]
            table.setItem(r, 0, QTableWidgetItem(str(e["id"])))
            table.setItem(r, 1, QTableWidgetItem(str(e["start_date"])))
            table.setItem(r, 2, QTableWidgetItem(str(end) if end else "ongoing"))
            if end is None or end > today:
                btn = QPushButton("Terminate")
                btn.setObjectName("btn_terminate")
                btn.clicked.connect(
                    lambda _=False, rid=e["id"]: self._terminate_enrollment(rid)
                )
                table.setCellWidget(r, 3, btn)
            else:
                table.setItem(r, 3, QTableWidgetItem("Ended"))

        self._enroll_table = table
        layout.addWidget(table)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("+ Add")
        btn_add.clicked.connect(self._add_enrollment)
        btn_del = QPushButton("Delete Selected")
        btn_del.clicked.connect(lambda: self._delete_enrollment(table))
        btn_row.addWidget(btn_add)
        btn_row.addStretch()
        btn_row.addWidget(btn_del)
        layout.addLayout(btn_row)
        return w

    def _add_enrollment(self):
        from PyQt6.QtWidgets import QDialog, QFormLayout, QDateEdit, QDialogButtonBox
        from PyQt6.QtCore import QDate
        from db.members import insert_enrollment
        from monthly_schedule.db import get_enrollments

        dlg = QDialog(self)
        dlg.setWindowTitle("Add Enrollment")
        form = QFormLayout(dlg)
        start = QDateEdit(QDate.currentDate())
        start.setCalendarPopup(True)
        end = QDateEdit()
        end.setCalendarPopup(True)
        end.setMinimumDate(QDate(2000, 1, 1))
        end.setSpecialValueText("Ongoing")
        end.setDate(QDate(2000, 1, 1))
        form.addRow("Start Date:", start)
        form.addRow("End Date (optional):", end)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)
        if dlg.exec():
            s = start.date().toPyDate()
            e = end.date().toPyDate() if end.date() != QDate(2000, 1, 1) else None
            try:
                insert_enrollment(self._center_id, s, e, self._db_path)
                self._enrollments = get_enrollments(self._center_id, self._db_path)
                self._refresh_tab(1, self._make_enrollments_tab())
                self._log_event("ENROLL", f"Enrollment added: {s} – {e or 'ongoing'}")
            except Exception as exc:
                QMessageBox.critical(self, "Error", str(exc))

    def _delete_enrollment(self, table):
        row = table.currentRow()
        if row < 0:
            return
        record_id = int(table.item(row, 0).text())
        if QMessageBox.question(self, "Confirm", "Delete this enrollment record?") \
                == QMessageBox.StandardButton.Yes:
            from db.members import delete_enrollment
            from monthly_schedule.db import get_enrollments
            entry = next((e for e in self._enrollments if e["id"] == record_id), None)
            try:
                delete_enrollment(record_id, self._db_path)
                self._enrollments = get_enrollments(self._center_id, self._db_path)
                self._refresh_tab(1, self._make_enrollments_tab())
                if entry:
                    self._log_event(
                        "ENROLL",
                        f"Enrollment deleted: {entry['start_date']} – "
                        f"{entry['end_date'] or 'ongoing'}")
            except Exception as exc:
                QMessageBox.critical(self, "Error", str(exc))

    def _terminate_enrollment(self, record_id: int):
        from datetime import date
        from db.members import terminate_enrollment
        from monthly_schedule.db import get_enrollments

        today = date.today()
        reply = QMessageBox.question(
            self, "Terminate Enrollment",
            f"Terminate this enrollment? The end date will be set to today "
            f"({today.isoformat()}). This can't be undone.",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            terminate_enrollment(record_id, self._db_path)
            self._enrollments = get_enrollments(self._center_id, self._db_path)
            self._refresh_tab(1, self._make_enrollments_tab())
            self._log_event("ENROLL",
                            f"Enrollment terminated: end set to {today.isoformat()}")
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    # ── Authorizations tab ─────────────────────────────────────────────────

    def _make_auths_tab(self) -> QWidget:
        from datetime import date
        from PyQt6.QtWidgets import (
            QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView,
            QGraphicsOpacityEffect,
        )
        from PyQt6.QtGui import QColor
        from db.members import latest_authorization

        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 12, 0, 0)

        # A trailing spacer column (index SPACER_COL) soaks up the leftover width
        # as a single grayed strip, instead of leaving a bare gap past the last
        # real column.
        columns = ["ID", "Auth Start", "Auth End", "Days", "Health Plan",
                   "Created", "Status", "Document", "Action", ""]
        SPACER_COL = len(columns) - 1
        table = QTableWidget(len(self._authorizations), len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.horizontalHeaderItem(3).setToolTip("1=Mon  2=Tue  3=Wed  4=Thu  5=Fri")
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        hdr = table.horizontalHeader()
        hdr.setStretchLastSection(False)
        # Real columns hug their content; the spacer alone stretches to fill the
        # rest of the row.
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(SPACER_COL, QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(34)  # room for action buttons

        from db.members import get_auth_ids_with_documents
        doc_ids = get_auth_ids_with_documents(self._center_id, self._db_path)

        latest = latest_authorization(self._authorizations)
        latest_id = latest["id"] if latest else None
        today = date.today()
        plan_badges, status_chips = [], []
        for r, a in enumerate(sort_auths_latest_first(self._authorizations)):
            expired = is_auth_expired(a, today)

            table.setItem(r, 0, QTableWidgetItem(str(a["id"])))
            table.setItem(r, 1, QTableWidgetItem(str(a["auth_start"])))
            table.setItem(r, 2, QTableWidgetItem(str(a["auth_end"])))

            chips = WeekdayChips(decode_auth_days(a["auth_days"] or ""), compact=True)
            table.setCellWidget(r, 3, chips)

            # Health plan as the same colored pill used everywhere else, a
            # compact pill centered in its column.
            badge = make_plan_badge(a.get("health_plan", "") or "")
            plan_cell = None
            if badge is not None:
                plan_cell = _centered_cell(badge)
                plan_badges.append(badge)
                table.setCellWidget(r, 4, plan_cell)
            else:
                table.setItem(r, 4, QTableWidgetItem(""))

            # When the row was created (auto-stamped on insert); blank for rows
            # that predate the column.
            table.setItem(r, 5, QTableWidgetItem(format_created_at(a.get("created_at"))))

            has_doc = a["id"] in doc_ids
            doc_btn = QPushButton("Open" if has_doc else "Attach")
            doc_btn.setObjectName("btn_edit")
            if has_doc:
                doc_btn.clicked.connect(
                    lambda _=False, auth=a: self._open_auth_document_menu(auth))
            else:
                doc_btn.clicked.connect(
                    lambda _=False, auth=a: self._attach_auth_document(auth))
            table.setCellWidget(r, 7, doc_btn)

            # Every row gets an Edit button so the Action column reads as
            # intentional, but only the most recent authorization is editable.
            btn = QPushButton("Edit")
            btn.setObjectName("btn_edit")
            if a["id"] == latest_id:
                btn.clicked.connect(lambda _=False, auth=a: self._edit_auth(auth))
            else:
                btn.setEnabled(False)
                btn.setToolTip("Only the most recent authorization can be edited.")
            table.setCellWidget(r, 8, btn)

            # Status pill in its own column: a compact green "Active" or red
            # "Expired" tag, centered.
            chip = QLabel("Expired" if expired else "Active")
            chip.setObjectName("expired_chip" if expired else "active_chip")
            status_chips.append(chip)
            table.setCellWidget(r, 6, _centered_cell(chip))

            # Grayed filler so the leftover width past the row reads as inert.
            spacer = QTableWidgetItem("")
            spacer.setFlags(Qt.ItemFlag.NoItemFlags)
            spacer.setBackground(QColor(120, 124, 140, 18))
            table.setItem(r, SPACER_COL, spacer)

            if not expired:
                continue

            # Expired rows are dimmed so the in-effect ones stand out.
            for col in (0, 1, 2, 4, 5):
                item = table.item(r, col)
                if item is not None:
                    item.setForeground(QColor(EXPIRED_FG))
            for widget in (chips, plan_cell):
                if widget is not None:
                    eff = QGraphicsOpacityEffect(widget)
                    eff.setOpacity(0.45)
                    widget.setGraphicsEffect(eff)

        # Size the pill columns to fit their widest pill so nothing clips.
        _fit_pill_column(table, 4, plan_badges, floor=96)
        _fit_pill_column(table, 6, status_chips, floor=96)

        self._auth_table = table
        layout.addWidget(table)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("+ Add")
        btn_add.clicked.connect(self._add_auth)
        btn_del = QPushButton("Delete Selected")
        btn_del.clicked.connect(lambda: self._delete_auth(table))
        btn_row.addWidget(btn_add)
        btn_row.addStretch()
        btn_row.addWidget(btn_del)
        layout.addLayout(btn_row)
        return w

    def _attach_auth_document(self, auth: dict, replace: bool = False):
        from PyQt6.QtWidgets import QFileDialog
        from db.members import set_auth_document
        import os

        path, _ = QFileDialog.getOpenFileName(
            self, "Choose document", "",
            "Documents (*.pdf *.jpg *.jpeg *.png *.tif *.tiff *.doc *.docx)",
        )
        if not path:
            return
        try:
            size_mb = os.path.getsize(path) / (1024 * 1024)
        except OSError:
            size_mb = 0
        if size_mb > MAX_DOC_WARN_MB:
            if QMessageBox.question(
                self, "Large file",
                f"This file is {size_mb:.1f} MB. Large attachments grow the database "
                f"quickly (Access has a 2 GB limit). Attach it anyway?",
            ) != QMessageBox.StandardButton.Yes:
                return
        try:
            set_auth_document(auth["id"], path, self._db_path)
            verb = "replaced" if replace else "attached"
            self._after_auth_change(
                f"Auth document {verb}: {auth['auth_start']} – {auth['auth_end']}")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Could not attach document:\n{exc}")

    def _open_auth_document_menu(self, auth: dict):
        box = QMessageBox(self)
        box.setWindowTitle("Authorization Document")
        box.setText(
            f"Document for authorization {auth['auth_start']} – {auth['auth_end']}.")
        open_btn = box.addButton("Open", QMessageBox.ButtonRole.AcceptRole)
        replace_btn = box.addButton("Replace", QMessageBox.ButtonRole.ActionRole)
        box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked is open_btn:
            self._do_open_auth_document(auth)
        elif clicked is replace_btn:
            self._attach_auth_document(auth, replace=True)

    def _do_open_auth_document(self, auth: dict):
        from db.members import save_auth_document
        import os
        import tempfile

        tmp_dir = tempfile.mkdtemp(prefix="authdoc_")
        try:
            path = save_auth_document(auth["id"], tmp_dir, self._db_path)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Could not open document:\n{exc}")
            return
        if not path:
            QMessageBox.information(self, "No document", "No document is attached.")
            return
        try:
            os.startfile(path)  # Windows: open in the default application
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Could not open the file:\n{exc}")

    def _after_auth_change(self, description: str | None):
        """Re-sync the plan, reload auths, refresh the tab, and (optionally)
        log an AUTH event. Called after add/edit/delete of an authorization."""
        from db.members import get_authorizations, sync_health_plan_from_latest_auth

        synced = sync_health_plan_from_latest_auth(self._center_id, self._db_path)
        if synced:
            self._member["health_plan"] = synced
            if hasattr(self, "_info_plan"):
                self._info_plan.setText(synced)
        self._authorizations = get_authorizations(self._center_id, self._db_path)
        self._refresh_tab(2, self._make_auths_tab())
        if description:
            self._log_event("AUTH", description)

    def _open_auth_dialog(self, existing: dict | None = None) -> dict | None:
        """Build the Add/Edit Authorization dialog. Returns a dict with
        auth_start, auth_end, days, health_plan — or None if cancelled.
        Pre-fills from `existing` when editing."""
        from PyQt6.QtWidgets import (
            QDialog, QFormLayout, QDateEdit, QCheckBox, QComboBox,
            QHBoxLayout, QDialogButtonBox, QWidget,
        )
        from PyQt6.QtCore import QDate
        from db.members import HEALTH_PLANS

        dlg = QDialog(self)
        dlg.setWindowTitle("Edit Authorization" if existing else "Add Authorization")
        form = QFormLayout(dlg)

        auth_start = QDateEdit()
        auth_start.setCalendarPopup(True)
        auth_end = QDateEdit()
        auth_end.setCalendarPopup(True)
        if existing:
            s, e = existing["auth_start"], existing["auth_end"]
            auth_start.setDate(QDate(s.year, s.month, s.day))
            auth_end.setDate(QDate(e.year, e.month, e.day))
        else:
            auth_start.setDate(QDate.currentDate())
            auth_end.setDate(QDate.currentDate().addYears(1))

        existing_days = (
            self.decode_auth_days_static(existing["auth_days"]) if existing else set()
        )
        day_checks = {}
        days_widget = QWidget()
        days_hl = QHBoxLayout(days_widget)
        days_hl.setContentsMargins(0, 0, 0, 0)
        for num, label in [(1, "Mon"), (2, "Tue"), (3, "Wed"), (4, "Thu"), (5, "Fri"),
                          (6, "Sat"), (7, "Sun")]:
            cb = QCheckBox(label)
            cb.setChecked(num in existing_days)
            day_checks[num] = cb
            days_hl.addWidget(cb)

        plan_combo = QComboBox()
        plan_combo.addItems(HEALTH_PLANS)
        if existing:
            idx = plan_combo.findText(existing.get("health_plan", ""))
            if idx >= 0:
                plan_combo.setCurrentIndex(idx)

        form.addRow("Auth Start:", auth_start)
        form.addRow("Auth End:", auth_end)
        form.addRow("Days:", days_widget)
        form.addRow("Health Plan:", plan_combo)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)
        btns.accepted.connect(
            lambda: dlg.accept() if any(cb.isChecked() for cb in day_checks.values())
            else QMessageBox.warning(dlg, "Validation", "Select at least one day.")
        )

        if not dlg.exec():
            return None
        return {
            "auth_start": auth_start.date().toPyDate(),
            "auth_end": auth_end.date().toPyDate(),
            "days": {n for n, cb in day_checks.items() if cb.isChecked()},
            "health_plan": plan_combo.currentText(),
        }

    def _add_auth(self):
        from db.members import insert_authorization, encode_auth_days

        result = self._open_auth_dialog()
        if not result:
            return
        try:
            insert_authorization(
                self._center_id, result["auth_start"], result["auth_end"],
                result["days"], None, None, result["health_plan"], self._db_path,
            )
            self._after_auth_change(
                f"Auth added: {result['auth_start']} – {result['auth_end']} · "
                f"{encode_auth_days(result['days'])} · {result['health_plan']}"
            )
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _edit_auth(self, auth: dict):
        from db.members import update_authorization, encode_auth_days

        result = self._open_auth_dialog(existing=auth)
        if not result:
            return
        try:
            update_authorization(
                auth["id"], result["auth_start"], result["auth_end"],
                result["days"], result["health_plan"], self._db_path,
            )
            self._after_auth_change(
                f"Auth edited: {result['auth_start']} – {result['auth_end']} · "
                f"{encode_auth_days(result['days'])} · {result['health_plan']}"
            )
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _delete_auth(self, table):
        row = table.currentRow()
        if row < 0:
            return
        record_id = int(table.item(row, 0).text())
        if QMessageBox.question(self, "Confirm", "Delete this authorization?") \
                == QMessageBox.StandardButton.Yes:
            from db.members import delete_authorization
            entry = next((a for a in self._authorizations if a["id"] == record_id), None)
            try:
                delete_authorization(record_id, self._db_path)
                self._after_auth_change(None)
                if entry:
                    self._log_event(
                        "AUTH",
                        f"Authorization deleted: {entry['auth_start']} – "
                        f"{entry['auth_end']} "
                        f"[{format_auth_days(entry.get('auth_days', '') or '')}] · "
                        f"{entry.get('health_plan', '')}")
            except Exception as exc:
                QMessageBox.critical(self, "Error", str(exc))

    # ── Availability tab ───────────────────────────────────────────────────

    def _make_current_schedule_strip(self, today) -> QWidget:
        """A read-only 'what's in effect today' strip: Mon–Fri always (dash for a
        day with no current window), plus any weekend day that has one."""
        box = QWidget()
        outer = QVBoxLayout(box)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)
        caption = QLabel("Current Schedule")
        caption.setObjectName("strip_caption")
        outer.addWidget(caption)

        sched = current_schedule(self._availability, today)
        days = [1, 2, 3, 4, 5] + [d for d in (6, 7) if d in sched]

        row = QHBoxLayout()
        row.setSpacing(8)
        for d in days:
            windows = sched.get(d)
            cell = QWidget()
            cell.setObjectName("avail_day" if windows else "avail_day_empty")
            cell.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            cell.setMinimumWidth(104)
            cv = QVBoxLayout(cell)
            cv.setContentsMargins(10, 7, 10, 7)
            cv.setSpacing(2)
            day_lbl = QLabel(WEEKDAY_NAMES[d])
            day_lbl.setObjectName("avail_day_name")
            day_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cv.addWidget(day_lbl)
            for s, e in (windows or [(None, None)]):
                t_lbl = QLabel(format_avail_window(s, e) if windows else "—")
                t_lbl.setObjectName("avail_day_time" if windows else "avail_day_dash")
                t_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                cv.addWidget(t_lbl)
            row.addWidget(cell)
        row.addStretch()
        outer.addLayout(row)
        return box

    def _make_avail_tab(self) -> QWidget:
        from datetime import date
        from PyQt6.QtWidgets import (
            QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView,
            QSizePolicy,
        )
        from PyQt6.QtGui import QColor
        day_names = WEEKDAY_NAMES
        today = date.today()

        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(12)

        layout.addWidget(self._make_current_schedule_strip(today))

        # Trailing "" spacer column soaks up the leftover width as a grayed strip.
        columns = ["ID", "Day", "Start", "End", "Effective From", "Effective To",
                   "Status", "Action", ""]
        SPACER_COL = len(columns) - 1
        table = QTableWidget(len(self._availability), len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        hdr = table.horizontalHeader()
        hdr.setStretchLastSection(False)
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(SPACER_COL, QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(34)  # room for action buttons

        status_chips = []
        for r, a in enumerate(sort_avail_for_table(self._availability, today)):
            expired = is_avail_expired(a, today)
            eff_end = a.get("effective_end_date")

            table.setItem(r, 0, QTableWidgetItem(str(a["id"])))
            table.setItem(r, 1, QTableWidgetItem(
                day_names.get(a["day_of_week"], str(a["day_of_week"]))))
            table.setItem(r, 2, QTableWidgetItem(a["avail_start"] or "—"))
            table.setItem(r, 3, QTableWidgetItem(a["avail_end"] or "—"))
            table.setItem(r, 4, QTableWidgetItem(str(a["effective_start_date"])))
            table.setItem(r, 5, QTableWidgetItem(str(eff_end) if eff_end else "—"))

            # Compact status pill centered in its column, like the Auth tab.
            chip = QLabel("Expired" if expired else "Active")
            chip.setObjectName("expired_chip" if expired else "active_chip")
            status_chips.append(chip)
            table.setCellWidget(r, 6, _centered_cell(chip))

            btn = QPushButton("Edit")
            btn.setObjectName("btn_edit")
            btn.clicked.connect(lambda _=False, av=a: self._edit_avail(av))
            table.setCellWidget(r, 7, btn)

            spacer = QTableWidgetItem("")
            spacer.setFlags(Qt.ItemFlag.NoItemFlags)
            spacer.setBackground(QColor(120, 124, 140, 18))
            table.setItem(r, SPACER_COL, spacer)

            if expired:
                for col in (0, 1, 2, 3, 4, 5):
                    table.item(r, col).setForeground(QColor(EXPIRED_FG))

        _fit_pill_column(table, 6, status_chips, floor=96)

        self._avail_table = table
        layout.addWidget(table)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("+ Add")
        btn_add.clicked.connect(self._add_avail)
        btn_del = QPushButton("Delete Selected")
        btn_del.clicked.connect(lambda: self._delete_avail(table))
        btn_row.addWidget(btn_add)
        btn_row.addStretch()
        btn_row.addWidget(btn_del)
        layout.addLayout(btn_row)
        return w

    def _edit_avail(self, avail: dict):
        from datetime import date as _date
        from PyQt6.QtWidgets import (
            QDialog, QVBoxLayout, QFormLayout, QLabel, QDialogButtonBox,
            QDateEdit, QCheckBox, QWidget, QHBoxLayout,
        )
        from PyQt6.QtCore import QDate
        from gui.time_range_editor import TimeRangeEditor
        from db.members import update_availability
        from monthly_schedule.db import get_availability

        day_names = WEEKDAY_NAMES
        day_name = day_names.get(avail["day_of_week"], str(avail["day_of_week"]))

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Edit Availability — {day_name}")
        v = QVBoxLayout(dlg)
        v.addWidget(QLabel(f"Day: {day_name}"))

        editor = TimeRangeEditor()
        editor.set_window(avail["avail_start"] or "08:00", avail["avail_end"] or "16:00")
        v.addWidget(editor)

        form = QFormLayout()
        start_d = avail.get("effective_start_date") or _date.today()
        eff_start = QDateEdit()
        eff_start.setCalendarPopup(True)
        eff_start.setDate(QDate(start_d.year, start_d.month, start_d.day))
        form.addRow("Effective From:", eff_start)

        end_row = QWidget()
        end_hl = QHBoxLayout(end_row)
        end_hl.setContentsMargins(0, 0, 0, 0)
        eff_end = QDateEdit()
        eff_end.setCalendarPopup(True)
        ongoing = QCheckBox("Ongoing (no end date)")
        end_d = avail.get("effective_end_date")
        if end_d:
            eff_end.setDate(QDate(end_d.year, end_d.month, end_d.day))
        else:
            eff_end.setDate(QDate(start_d.year, start_d.month, start_d.day))
            ongoing.setChecked(True)
        eff_end.setEnabled(not ongoing.isChecked())
        ongoing.toggled.connect(lambda on: eff_end.setEnabled(not on))
        end_hl.addWidget(eff_end)
        end_hl.addWidget(ongoing)
        form.addRow("Effective To:", end_row)
        v.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.rejected.connect(dlg.reject)

        def on_accept():
            es = eff_start.date().toPyDate()
            ee = None if ongoing.isChecked() else eff_end.date().toPyDate()
            if ee is not None and ee < es:
                QMessageBox.warning(dlg, "Validation",
                    "Effective To must be on or after Effective From.")
                return
            dlg.accept()
        btns.accepted.connect(on_accept)
        v.addWidget(btns)

        if not dlg.exec():
            return
        ts, te = editor.start_hhmm(), editor.end_hhmm()
        es = eff_start.date().toPyDate()
        ee = None if ongoing.isChecked() else eff_end.date().toPyDate()
        try:
            update_availability(avail["id"], ts, te, es, ee, self._db_path)
            self._availability = get_availability(self._center_id, self._db_path)
            self._refresh_tab(3, self._make_avail_tab())
            end_txt = ee.isoformat() if ee else "ongoing"
            self._log_event(
                "AVAIL",
                f"Availability edited: {day_name} {ts}–{te} "
                f"(eff {es.isoformat()} → {end_txt})")
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _add_avail(self):
        from PyQt6.QtWidgets import (
            QDialog, QFormLayout, QComboBox, QLineEdit, QDateEdit,
            QDialogButtonBox, QWidget, QHBoxLayout,
        )
        from PyQt6.QtCore import QDate
        from db.members import insert_availability, time_12h_to_24h
        from monthly_schedule.db import get_availability

        dlg = QDialog(self)
        dlg.setWindowTitle("Add Availability")
        form = QFormLayout(dlg)

        day_combo = QComboBox()
        for num, name in [(1, "Mon"), (2, "Tue"), (3, "Wed"), (4, "Thu"), (5, "Fri"),
                          (6, "Sat"), (7, "Sun")]:
            day_combo.addItem(name, num)

        def time_row(default_text: str, default_period: str):
            container = QWidget()
            hl = QHBoxLayout(container)
            hl.setContentsMargins(0, 0, 0, 0)
            edit = QLineEdit(default_text)
            edit.setPlaceholderText("h:mm")
            period = QComboBox()
            period.addItems(["AM", "PM"])
            period.setCurrentText(default_period)
            hl.addWidget(edit)
            hl.addWidget(period)
            return container, edit, period

        start_row, start_edit, start_period = time_row("8:00", "AM")
        end_row, end_edit, end_period = time_row("4:00", "PM")
        eff_start = QDateEdit(QDate.currentDate())
        eff_start.setCalendarPopup(True)

        form.addRow("Day:", day_combo)
        form.addRow("Start Time:", start_row)
        form.addRow("End Time:", end_row)
        form.addRow("Effective From:", eff_start)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)

        def on_accept():
            try:
                time_12h_to_24h(start_edit.text(), start_period.currentText())
                time_12h_to_24h(end_edit.text(), end_period.currentText())
            except ValueError:
                QMessageBox.warning(dlg, "Validation",
                    "Enter times as h:mm with hour 1-12 and minute 00-59.")
                return
            dlg.accept()

        btns.accepted.connect(on_accept)

        if dlg.exec():
            day = day_combo.currentData()
            day_name = day_combo.currentText()
            ts = time_12h_to_24h(start_edit.text(), start_period.currentText())
            te = time_12h_to_24h(end_edit.text(), end_period.currentText())
            try:
                insert_availability(
                    self._center_id, day, ts, te,
                    eff_start.date().toPyDate(), None, self._db_path,
                )
                self._availability = get_availability(self._center_id, self._db_path)
                self._refresh_tab(3, self._make_avail_tab())
                self._log_event("AVAIL", f"Availability added: {day_name} {ts}–{te}")
            except Exception as exc:
                QMessageBox.critical(self, "Error", str(exc))

    def _delete_avail(self, table):
        row = table.currentRow()
        if row < 0:
            return
        record_id = int(table.item(row, 0).text())
        if QMessageBox.question(self, "Confirm", "Delete this availability row?") \
                == QMessageBox.StandardButton.Yes:
            from db.members import delete_availability
            from monthly_schedule.db import get_availability
            entry = next((a for a in self._availability if a["id"] == record_id), None)
            try:
                delete_availability(record_id, self._db_path)
                self._availability = get_availability(self._center_id, self._db_path)
                self._refresh_tab(3, self._make_avail_tab())
                if entry:
                    day = WEEKDAY_NAMES.get(entry["day_of_week"],
                                            str(entry["day_of_week"]))
                    self._log_event(
                        "AVAIL",
                        f"Availability deleted: {day} "
                        f"{entry['avail_start']}–{entry['avail_end']}")
            except Exception as exc:
                QMessageBox.critical(self, "Error", str(exc))

    # ── Unavailable Times tab (one-off) ──────────────────────────────────────

    def _make_unavailable_tab(self) -> QWidget:
        from PyQt6.QtWidgets import (
            QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView,
        )
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 12, 0, 0)

        caption = QLabel("Times the member is unavailable on a specific date.")
        caption.setObjectName("field_label")
        layout.addWidget(caption)

        columns = ["ID", "Date", "Start", "End", "Notes", "Action"]
        table = QTableWidget(len(self._one_off), len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        hdr = table.horizontalHeader()
        hdr.setStretchLastSection(False)
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(34)

        for r, a in enumerate(self._one_off):
            table.setItem(r, 0, QTableWidgetItem(str(a["id"])))
            table.setItem(r, 1, QTableWidgetItem(str(a["date"]) if a["date"] else ""))
            table.setItem(r, 2, QTableWidgetItem(a["avail_start"] or ""))
            table.setItem(r, 3, QTableWidgetItem(a["avail_end"] or ""))
            table.setItem(r, 4, QTableWidgetItem(a.get("notes", "") or ""))
            btn = QPushButton("Edit")
            btn.setObjectName("btn_edit")
            btn.clicked.connect(lambda _=False, uv=a: self._edit_unavailable(uv))
            table.setCellWidget(r, 5, btn)

        self._unavail_table = table
        layout.addWidget(table)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("+ Add")
        btn_add.clicked.connect(self._add_unavailable)
        btn_del = QPushButton("Delete Selected")
        btn_del.clicked.connect(lambda: self._delete_unavailable(table))
        btn_row.addWidget(btn_add)
        btn_row.addStretch()
        btn_row.addWidget(btn_del)
        layout.addLayout(btn_row)
        return w

    def _open_one_off_dialog(self, existing: dict | None = None):
        """Add/Edit dialog: date + time window + notes. Returns a dict with
        date, avail_start, avail_end, notes — or None if cancelled."""
        from PyQt6.QtWidgets import (
            QDialog, QFormLayout, QDateEdit, QPlainTextEdit, QDialogButtonBox,
        )
        from PyQt6.QtCore import QDate
        from gui.time_range_editor import TimeRangeEditor

        dlg = QDialog(self)
        dlg.setWindowTitle("Edit Unavailable Time" if existing
                           else "Add Unavailable Time")
        form = QFormLayout(dlg)

        date_edit = QDateEdit()
        date_edit.setCalendarPopup(True)
        editor = TimeRangeEditor()
        notes_edit = QPlainTextEdit()
        notes_edit.setFixedHeight(60)

        if existing:
            d = existing.get("date")
            date_edit.setDate(QDate(d.year, d.month, d.day) if d
                              else QDate.currentDate())
            editor.set_window(existing.get("avail_start") or "09:00",
                              existing.get("avail_end") or "12:00")
            notes_edit.setPlainText(existing.get("notes", "") or "")
        else:
            date_edit.setDate(QDate.currentDate())
            editor.set_window("09:00", "12:00")

        form.addRow("Date:", date_edit)
        form.addRow("Time:", editor)
        form.addRow("Notes:", notes_edit)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)

        if not dlg.exec():
            return None
        return {
            "date": date_edit.date().toPyDate(),
            "avail_start": editor.start_hhmm(),
            "avail_end": editor.end_hhmm(),
            "notes": notes_edit.toPlainText().strip(),
        }

    def _add_unavailable(self):
        from db.members import (
            insert_one_off_availability, get_one_off_availability,
        )
        result = self._open_one_off_dialog()
        if not result:
            return
        try:
            insert_one_off_availability(
                self._center_id, result["date"], result["avail_start"],
                result["avail_end"], result["notes"], self._db_path,
            )
            self._one_off = get_one_off_availability(self._center_id, self._db_path)
            self._refresh_tab(4, self._make_unavailable_tab())
            self._log_event(
                "AVAIL",
                f"One-off unavailable added: {result['date']} "
                f"{result['avail_start']}–{result['avail_end']}")
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _edit_unavailable(self, entry: dict):
        from db.members import (
            update_one_off_availability, get_one_off_availability,
        )
        result = self._open_one_off_dialog(existing=entry)
        if not result:
            return
        try:
            update_one_off_availability(
                entry["id"], result["date"], result["avail_start"],
                result["avail_end"], result["notes"], self._db_path,
            )
            self._one_off = get_one_off_availability(self._center_id, self._db_path)
            self._refresh_tab(4, self._make_unavailable_tab())
            self._log_event(
                "AVAIL",
                f"One-off unavailable edited: {result['date']} "
                f"{result['avail_start']}–{result['avail_end']}")
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _delete_unavailable(self, table):
        row = table.currentRow()
        if row < 0:
            return
        record_id = int(table.item(row, 0).text())
        if QMessageBox.question(self, "Confirm", "Delete this unavailable time?") \
                == QMessageBox.StandardButton.Yes:
            from db.members import (
                delete_one_off_availability, get_one_off_availability,
            )
            entry = next((a for a in self._one_off if a["id"] == record_id), None)
            try:
                delete_one_off_availability(record_id, self._db_path)
                self._one_off = get_one_off_availability(
                    self._center_id, self._db_path)
                self._refresh_tab(4, self._make_unavailable_tab())
                if entry:
                    self._log_event(
                        "AVAIL",
                        f"One-off unavailable deleted: {entry['date']} "
                        f"{entry['avail_start']}–{entry['avail_end']}")
            except Exception as exc:
                QMessageBox.critical(self, "Error", str(exc))

    # ── Absences tab ───────────────────────────────────────────────────────

    def _make_absences_tab(self) -> QWidget:
        rows = [
            [a["id"], a["leave_type"], str(a["start_date"]), str(a["end_date"])]
            for a in self._absences
        ]
        w, self._abs_table = self._make_table_tab(
            ["ID", "Leave Type", "Start", "End"],
            rows, self._add_absence, self._delete_absence,
        )
        return w

    def _add_absence(self):
        from PyQt6.QtWidgets import (
            QDialog, QFormLayout, QComboBox, QDateEdit, QDialogButtonBox,
        )
        from PyQt6.QtCore import QDate
        from db.members import insert_absence, LEAVE_TYPES
        from monthly_schedule.db import get_absences

        dlg = QDialog(self)
        dlg.setWindowTitle("Add Absence")
        form = QFormLayout(dlg)

        leave_combo = QComboBox()
        leave_combo.addItems(LEAVE_TYPES)
        start = QDateEdit(QDate.currentDate())
        start.setCalendarPopup(True)
        end = QDateEdit(QDate.currentDate())
        end.setCalendarPopup(True)

        form.addRow("Leave Type:", leave_combo)
        form.addRow("Start Date:", start)
        form.addRow("End Date:", end)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)

        if dlg.exec():
            lt = leave_combo.currentText()
            s = start.date().toPyDate()
            e = end.date().toPyDate()
            try:
                insert_absence(self._center_id, lt, s, e, self._db_path)
                self._absences = get_absences(self._center_id, self._db_path)
                self._refresh_tab(5, self._make_absences_tab())
                self._log_event("ABS", f"Absence added: {lt} · {s} – {e}")
            except Exception as exc:
                QMessageBox.critical(self, "Error", str(exc))

    def _delete_absence(self, table):
        row = table.currentRow()
        if row < 0:
            return
        record_id = int(table.item(row, 0).text())
        if QMessageBox.question(self, "Confirm", "Delete this absence?") \
                == QMessageBox.StandardButton.Yes:
            from db.members import delete_absence
            from monthly_schedule.db import get_absences
            entry = next((a for a in self._absences if a["id"] == record_id), None)
            try:
                delete_absence(record_id, self._db_path)
                self._absences = get_absences(self._center_id, self._db_path)
                self._refresh_tab(5, self._make_absences_tab())
                if entry:
                    self._log_event(
                        "ABS",
                        f"Absence deleted: {entry['leave_type']} "
                        f"{entry['start_date']} – {entry['end_date']}")
            except Exception as exc:
                QMessageBox.critical(self, "Error", str(exc))
