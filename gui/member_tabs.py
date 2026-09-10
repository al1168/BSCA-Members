from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel,
    QPushButton, QMessageBox, QTextEdit, QSizePolicy, QLineEdit,
)
from PyQt6.QtCore import Qt, pyqtSignal

from db.members import (
    get_member_context, format_phone, format_date_only, format_dob_display,
    age_from_dob,
    format_ssn, is_valid_ssn, format_medicaid, is_valid_medicaid,
    format_medicare, is_valid_medicare, is_valid_alt_id,
    format_ssn_live, format_medicaid_live, format_medicare_live,
)
from gui.address_autocomplete import (
    set_active_inline_editor, clear_active_inline_editor, make_phone_validator,
    PhoneLineEdit, set_widget_error, DateLineEdit,
)
from gui.errors import show_db_error


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
    "alt_id": "Alt ID", "group": "Group",
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


def set_table_empty_state(table, text: str) -> None:
    """When `table` has no data rows, show one muted, non-selectable row saying
    what belongs here and how to add it — never a bare void. Call after the
    table is fully built (so hidden debug columns are already applied)."""
    if table.rowCount() > 0:
        return
    from PyQt6.QtWidgets import QTableWidgetItem
    from PyQt6.QtGui import QColor
    from gui.theme import current_tokens
    first_visible = next(
        (c for c in range(table.columnCount()) if not table.isColumnHidden(c)), 0)
    table.setRowCount(1)
    if table.columnCount() - first_visible > 1:
        table.setSpan(0, first_visible, 1, table.columnCount() - first_visible)
    item = QTableWidgetItem(text)
    item.setFlags(Qt.ItemFlag.NoItemFlags)          # not selectable/editable
    item.setForeground(QColor(current_tokens()["text3"]))
    table.setItem(0, first_visible, item)


def _centered_cell(widget, vmargin: int = 4) -> QWidget:
    """Wrap a widget in a table cell that centers it horizontally, keeping it at
    its natural (compact) size rather than stretching it to fill the column.

    The widget is pinned to at least its own content size (width and height) so
    the centering stretches, a slightly narrow column, or a short row can never
    squeeze it and clip its text.

    Beware the space actually available: the view sizes a cell widget to the
    item's content rect, which the QSS 'QTableWidget::item' padding shrinks well
    below the row height (a 40px row leaves ~27px). A taller widget needs a
    smaller `vmargin` rather than more room — there is none.

    The wrapper is transparent (see #pill_cell in the theme) so the row's own
    background, including the Availability tab's authorized-day tint, shows
    through instead of being punched out by the table's inherited fill."""
    hint = widget.sizeHint()
    widget.setMinimumWidth(hint.width())
    widget.setMinimumHeight(hint.height())
    cell = QWidget()
    cell.setObjectName("pill_cell")
    box = QHBoxLayout(cell)
    box.setContentsMargins(_PILL_CELL_HMARGIN, vmargin, _PILL_CELL_HMARGIN, vmargin)
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


def authorized_weekdays(authorizations: list[dict], today=None) -> set[int]:
    """Day numbers (1=Mon … 7=Sun) the member is authorized for under the
    authorization in effect today; empty when no auth is currently in effect."""
    from db.members import current_authorization
    current = current_authorization(authorizations, today)
    if not current:
        return set()
    return decode_auth_days(current.get("auth_days") or "")


def weekdays_in_range(start, end) -> set[int]:
    """The set of ISO weekdays (1=Mon … 7=Sun) a [start, end] date range spans
    (capped at all 7). Empty for a missing/invalid range."""
    from datetime import timedelta
    start, end = _as_date(start), _as_date(end)
    if start is None or end is None or end < start:
        return set()
    days, d = set(), start
    while d <= end and len(days) < 7:
        days.add(d.isoweekday())
        d += timedelta(days=1)
    return days


def needs_unauthorized_warning(authorizations: list[dict], weekdays, today=None) -> bool:
    """Whether a change touching `weekdays` should be confirmed: True when none of
    those weekdays are authorized under the current authorization (i.e. the change
    is entirely on non-authorized days, or the member has no current auth)."""
    weekdays = set(weekdays)
    if not weekdays:
        return False
    return weekdays.isdisjoint(authorized_weekdays(authorizations, today))


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
    both so cosmetic-only differences are not reported as changes. Non-string
    values (e.g. alt_id ints) are stringified; None becomes ''.
    """
    s = "" if v is None else str(v)
    return s.replace("\r\n", "\n").replace("\r", "\n").strip()


def build_change_rows(old: dict, fields: dict) -> list[tuple[str, str, str]]:
    """(label, original, modified) for each field whose value changed, in
    `fields` order. Values are normalized (newlines unified, surrounding
    whitespace stripped) before comparison, so trailing spaces or CRLF/LF
    differences do not count as changes. Blanks stay '' here; the confirm
    dialog and the summary lines render them as '(empty)'."""
    rows = []
    for key, new_val in fields.items():
        old_norm = _normalize_value(old.get(key))
        new_norm = _normalize_value(new_val)
        if new_norm != old_norm:
            rows.append((FIELD_LABELS.get(key, key), old_norm, new_norm))
    return rows


def build_change_summary(old: dict, fields: dict) -> list[str]:
    """Friendly 'Label: old → new' lines for each changed field (the events
    log entry). Same change detection as build_change_rows."""
    return [f"{label}: {o or '(empty)'} → {n or '(empty)'}"
            for label, o, n in build_change_rows(old, fields)]


def missing_new_auth_fields(*, start_valid: bool, end_valid: bool,
                            has_day: bool, health_plan: str, plan_type: str,
                            member_id: str, auth_number: str) -> list[str]:
    """Labels of the required fields still missing when creating a NEW
    authorization (creation requires every field; editing is exempt —
    see _open_auth_dialog). Order matches the dialog's rows."""
    missing = []
    if not start_valid:
        missing.append("Auth Start")
    if not end_valid:
        missing.append("Auth End")
    if not has_day:
        missing.append("Days")
    if not health_plan.strip():
        missing.append("Health Plan")
    if not plan_type.strip():
        missing.append("Plan Type")
    if not member_id.strip():
        missing.append("Member ID")
    if not auth_number.strip():
        missing.append("Auth Number")
    return missing


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

# Accent used for clickable cross-references (e.g. the Linked Auth cell that
# jumps to the Authorizations tab); matches the app accent.
LINK_FG = "#5b7cf4"


def _as_date(value):
    """Normalize a temporal value to a datetime.date for comparison: a datetime
    becomes its date, a date stays a date, anything else (None, strings) becomes
    None. Prevents 'can't compare datetime to date' errors and silently-wrong
    status when an Access Date/Time field comes back as a datetime."""
    from datetime import date as _d, datetime as _dt
    if isinstance(value, _dt):
        return value.date()
    if isinstance(value, _d):
        return value
    return None


def is_auth_expired(auth: dict, today) -> bool:
    """True when an authorization's window has passed (auth_end < today).

    Mirrors auth_warning: today still counts as in-effect, and an open-ended
    authorization (no auth_end) is never expired.
    """
    end = _as_date(auth.get("auth_end"))
    today = _as_date(today)
    return end is not None and today is not None and end < today


def auth_status(auth: dict, today) -> str:
    """An authorization's state for the status pill:
    'expired' (ended before today), 'upcoming' (starts after today), or
    'active' (in effect today). Today's date counts as active at either edge.
    """
    today = _as_date(today)
    end = _as_date(auth.get("auth_end"))
    if end is not None and end < today:
        return "expired"
    start = _as_date(auth.get("auth_start"))
    if start is not None and start > today:
        return "upcoming"
    return "active"


def auth_overlap_map(auths: list[dict]) -> dict:
    """Map each auth id to the list of other auths whose [auth_start, auth_end]
    range overlaps it. Two ranges overlap when each starts on or before the
    other ends (a single shared day counts). Rows missing a start or end date
    are skipped (can't determine an overlap, so never flagged)."""
    dated = [(a, _as_date(a.get("auth_start")), _as_date(a.get("auth_end")))
             for a in auths]
    dated = [(a, s, e) for (a, s, e) in dated if s is not None and e is not None]
    overlaps = {a["id"]: [] for (a, _s, _e) in dated}
    for i in range(len(dated)):
        for j in range(i + 1, len(dated)):
            (a, sa, ea), (b, sb, eb) = dated[i], dated[j]
            if sa <= eb and sb <= ea:
                overlaps[a["id"]].append(b)
                overlaps[b["id"]].append(a)
    return overlaps


def auths_overlapping(auths: list[dict], start, end, exclude_id=None) -> list[dict]:
    """The existing auths whose range overlaps the candidate [start, end] window,
    ignoring the row identified by `exclude_id` (the one being edited)."""
    start, end = _as_date(start), _as_date(end)
    if not start or not end:
        return []
    hits = []
    for a in auths:
        if exclude_id is not None and a.get("id") == exclude_id:
            continue
        s, e = _as_date(a.get("auth_start")), _as_date(a.get("auth_end"))
        if s and e and s <= end and start <= e:
            hits.append(a)
    return hits


# ── Availability view helpers (Availability tab) ───────────────────────────
def is_avail_expired(avail: dict, today) -> bool:
    """True when an availability's effective window has passed
    (effective_end_date < today). Open-ended rows are never expired; today
    still counts as in-effect."""
    end = _as_date(avail.get("effective_end_date"))
    today = _as_date(today)
    return end is not None and today is not None and end < today


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


def avail_status(avail: dict, today) -> str:
    """'expired' (effective_end < today), 'upcoming' (effective_start > today),
    or 'active' (in effect today). Mirrors auth_status."""
    start = _as_date(avail.get("effective_start_date"))
    end = _as_date(avail.get("effective_end_date"))
    today = _as_date(today)
    if end is not None and today is not None and end < today:
        return "expired"
    if start is not None and today is not None and start > today:
        return "upcoming"
    return "active"


def current_schedule(avails: list[dict], today) -> dict:
    """Map day_of_week -> [(start, end)] for the row in effect today, one window
    per weekday. When several rows are in effect (e.g. a just-activated change
    that hasn't capped the old row), the latest effective_start wins, tie-break
    largest id — the same rule the scheduler uses in availability_for. Feeds the
    Current Schedule strip."""
    from datetime import date
    best: dict[int, tuple] = {}   # day -> ((eff_start, id), (start, end))
    for a in avails:
        if not avail_in_effect_on(a, today):
            continue
        d = a["day_of_week"]
        key = (_as_date(a.get("effective_start_date")) or date.min, a.get("id") or 0)
        win = (a.get("avail_start") or "", a.get("avail_end") or "")
        if d not in best or key > best[d][0]:
            best[d] = (key, win)
    return {d: [win] for d, (_k, win) in best.items()}


def pending_changes(avails: list[dict], today) -> list[dict]:
    """Future-effective availability rows (a queued change not yet in effect),
    soonest first then by weekday. Returns a new list."""
    from datetime import date
    today = _as_date(today)
    future = [a for a in avails
              if (_as_date(a.get("effective_start_date")) or date.min) > today]
    return sorted(future, key=lambda a: (
        _as_date(a.get("effective_start_date")) or date.min,
        a.get("day_of_week", 0)))


def avail_to_cap(avails: list[dict], day_of_week: int, new_start) -> dict | None:
    """The row a scheduled change supersedes: the same-weekday row in effect at
    `new_start` (effective_start before it, end open or on/after it). Its end
    should be capped to new_start - 1. None when nothing needs capping."""
    from datetime import date
    new_start = _as_date(new_start)
    cands = []
    for a in avails:
        if a.get("day_of_week") != day_of_week:
            continue
        s = _as_date(a.get("effective_start_date"))
        e = _as_date(a.get("effective_end_date"))
        if s is not None and s < new_start and (e is None or e >= new_start):
            cands.append((s, a.get("id") or 0, a))
    if not cands:
        return None
    return max(cands, key=lambda t: (t[0], t[1]))[2]


def avail_to_restore(avails: list[dict], day_of_week: int, removed_start) -> dict | None:
    """The predecessor that was capped when a change starting `removed_start`
    was added: the same-weekday row whose effective_end is the day before. Used
    to re-extend it when the change is deleted. None if not found."""
    from datetime import date, timedelta
    removed_start = _as_date(removed_start)
    target_end = removed_start - timedelta(days=1)
    cands = [a for a in avails
             if a.get("day_of_week") == day_of_week
             and _as_date(a.get("effective_end_date")) == target_end]
    if not cands:
        return None
    return max(cands, key=lambda a: (
        _as_date(a.get("effective_start_date")) or date.min, a.get("id") or 0))


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
    """A PHOTO_SIZE photo label that emits `clicked` when pressed (left button)."""

    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Click to change photo")

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(e)


class _AltIdLabel(QLabel):
    """The red header alt-id label; emits `clicked` (left button) so clicking
    it opens the edit dialog."""

    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Click to edit the alt id")

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(e)


_PENCIL_ICON = None


def _pencil_icon():
    """A small pencil glyph as a QIcon for the inline 'edit' affordance. Rendered
    once and reused (every editable Info field shares it)."""
    global _PENCIL_ICON
    if _PENCIL_ICON is None:
        from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor
        pm = QPixmap(16, 16)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setPen(QColor("#5b7cf4"))  # accent blue — clearly the edit affordance
        p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, "✎")
        p.end()
        _PENCIL_ICON = QIcon(pm)
    return _PENCIL_ICON


def apply_field_style(widget, cfg: dict) -> None:
    """Apply a layout field's styling (bold/size/highlight) to its widget via
    dynamic properties matched by theme QSS. Composite widgets (the address
    autocomplete) style their inner line edit."""
    from PyQt6.QtWidgets import QLineEdit
    target = widget if isinstance(widget, QLineEdit) \
        else widget.findChild(QLineEdit)
    if target is None:
        return
    target.setProperty("fbold", "true" if cfg.get("bold") else "false")
    target.setProperty("fsize", cfg.get("size", "normal"))
    target.setProperty("hl", cfg.get("color", "none"))
    style = target.style()
    style.unpolish(target)
    style.polish(target)


class _ViewEditLineEdit(QLineEdit):
    """A field that reads as flat, selectable text (highlight + copy) and only
    becomes editable when the user clicks its pencil (shown on hover).

    It stays a QLineEdit, so .text()/.setText()/textChanged work unchanged with
    the existing Save/Discard and dirty-tracking logic. ``editable=False`` makes
    a plain flat read-only field (no pencil) for values like Center ID.
    """

    def __init__(self, value: str = "", editable: bool = True, parent=None,
                 *, formatter=None, validator=None, live_formatter=None):
        # formatter(text)->text reformats on commit; live_formatter(text)->text
        # reformats on every keystroke (e.g. insert dashes / uppercase as you
        # type); validator(text)->bool flags an error outline when invalid (empty
        # is valid since these fields are optional).
        self._formatter = formatter
        self._validator = validator
        self._live_formatter = live_formatter
        value = formatter(value) if (formatter and value) else (value or "")
        super().__init__(value, parent)
        self._editable = editable
        self._baseline = value
        self._edit_start = value
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
            if validator is not None or live_formatter is not None:
                self.textEdited.connect(self._on_edited)
        self._refresh_state()

    def _on_edited(self):
        # Reformat as the user types (setText fires textChanged, not textEdited,
        # so no recursion), then validate live: a non-empty value that doesn't yet
        # match the field's format outlines red, clearing as soon as it's valid
        # (or empty, since these fields are optional).
        if self._live_formatter is not None:
            new = self._live_formatter(self.text())
            if new != self.text():
                self.setText(new)
                self.setCursorPosition(len(new))
        if self._validator is not None:
            text = self.text().strip()
            set_widget_error(self, bool(text) and not self._validator(text))

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

    def mouseDoubleClickEvent(self, e):
        # Double-click a flat field to start editing, same as the pencil. While
        # already editing, fall through to the normal word-select behavior.
        if self._editable and self.isReadOnly():
            self._begin_edit()
            return
        super().mouseDoubleClickEvent(e)

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
        if self._formatter:
            formatted = self._formatter(self.text())
            if formatted != self.text():
                self.setText(formatted)        # auto-format on commit (blur)
        self.setReadOnly(True)
        self.setProperty("editing", False)
        self._repolish()
        self._update_pencil()
        if self._validator is not None:
            set_widget_error(self, not self._validator(self.text()))
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

# Header photo edge length in px (square, shown in a circle).
PHOTO_SIZE = 108

# Decoded PHOTO_SIZE member photos, keyed by center_id: (QPixmap, has_photo).
# Reading and decoding the JPEG is the slowest part of opening a member after
# the DB read, so cache it across opens. Invalidated when a photo is changed
# in-app.
_PHOTO_CACHE: dict = {}
_PLACEHOLDER_PIX = None


def _placeholder_photo():
    """The generic PHOTO_SIZE avatar placeholder, drawn once and shared by all
    members (it's identical for everyone)."""
    global _PLACEHOLDER_PIX
    if _PLACEHOLDER_PIX is None:
        from PyQt6.QtGui import QPixmap, QPainter, QColor, QBrush
        s = PHOTO_SIZE
        pix = QPixmap(s, s)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QBrush(QColor("#3a3a3a")))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(0, 0, s, s)
        p.setBrush(QBrush(QColor("#888888")))
        # Head and torso, proportional to the old 80px art (28,12,24,24 /
        # 12,46,56,40).
        p.drawEllipse(int(s * .35), int(s * .15), int(s * .30), int(s * .30))
        p.drawEllipse(int(s * .15), int(s * .575), int(s * .70), int(s * .50))
        p.end()
        _PLACEHOLDER_PIX = pix
    return _PLACEHOLDER_PIX


class MemberTabsWidget(QWidget):
    # Emitted when this member's enrollments change (add/terminate/delete), so
    # the main window can refresh the sidebar's terminated marks.
    members_changed = pyqtSignal()
    # Emitted when this member is bookmarked/unbookmarked, so the main window
    # can refresh the toolbar Bookmarks count.
    bookmarks_changed = pyqtSignal()

    def __init__(self, center_id: int, db_path: str, events_path: str,
                 api_key: str = "", show_row_ids: bool = False, parent=None,
                 alt_id_key: bytes | None = None,
                 settings: dict | None = None, settings_path: str = ""):
        super().__init__(parent)
        self._center_id = center_id
        self._db_path = db_path
        self._events_path = events_path
        self._api_key = api_key or ""
        self._show_row_ids = show_row_ids
        # Session FPE key: alt_id is stored encrypted; with a key set, this
        # widget displays decrypted values and encrypts edits before saving.
        # self._member["alt_id"] always holds the stored (cipher) value.
        self._alt_id_key = alt_id_key
        # Customizable Info tab: the layout dict lives in the per-machine
        # settings JSON; without settings (tests, tools) the default is used.
        from gui.info_layout import normalize
        self._settings = settings
        self._settings_path = settings_path
        self._layout_cfg = normalize((settings or {}).get("info_tab_layout"))
        self._member = None
        from time import perf_counter
        t0 = perf_counter()
        self._load_data()
        t1 = perf_counter()
        self._build_ui()
        # Stage timings for the click-to-paint perf log (see MainWindow).
        self.perf_load_ms = (t1 - t0) * 1000
        self.perf_build_ms = (perf_counter() - t1) * 1000
        self._dirty = False
        self._setup_dirty_tracking()

    def _load_data(self):
        self._member = {}
        self._enrollments = []
        self._authorizations = []
        self._transport_auths = []
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
            show_db_error(self, exc, "Could Not Load Member")
        # Transport auths load independently and degrade to [] if the
        # [TransportAuthorization] table is missing, so they never block the
        # member from loading.
        from db.members import get_transport_authorizations
        self._transport_auths = get_transport_authorizations(
            self._center_id, self._db_path)
        self._overlay_current_auth()

    def _header_plan(self) -> str:
        """The plan for the pill next to the member's name: only the
        in-effect-today authorization's plan (falling back to Contacts when
        that auth row has no plan of its own). No active authorization — e.g.
        only an upcoming one — means no pill, so a stale or defaulted
        Contacts.[Health Plan] never shows as if it were active."""
        from db.members import current_authorization
        current = current_authorization(self._authorizations)
        if not current:
            return ""
        return ((current.get("health_plan") or "").strip()
                or (self._member.get("health_plan") or "").strip())

    def _refresh_header_plan(self):
        """Rebuild the header plan badge to match the member's current plan,
        so adding/editing an auth updates the header without reopening."""
        if not hasattr(self, "_header_top_row"):
            return
        if self._header_plan_badge is not None:
            self._header_top_row.removeWidget(self._header_plan_badge)
            self._header_plan_badge.deleteLater()
            self._header_plan_badge = None
        badge = make_plan_badge(self._header_plan())
        if badge is not None:
            self._header_top_row.insertWidget(   # right after the name label
                1, badge, alignment=Qt.AlignmentFlag.AlignVCenter)
            self._header_plan_badge = badge

    def _display_alt_id(self):
        """The alt id as shown to the user: decrypted when a session key is
        set, the raw stored value otherwise (including values the key can't
        decrypt). Read via __dict__ so it's safe on __new__-built test
        widgets."""
        from db.alt_id_crypto import decrypt_or_raw
        return decrypt_or_raw(self.__dict__.get("_alt_id_key"),
                              self._member.get("alt_id"))

    def _refresh_alt_id_label(self):
        """Show 'Alt ID n' in red under the Center ID when set; otherwise show
        the '+ alt id' affordance instead. Called at build time and after any
        alt-id save so the header updates without reopening the member."""
        # Read via __dict__ so it's safe on the __new__-built widgets used in
        # tests (a missing attr on an uninitialized QWidget raises, not False).
        label = self.__dict__.get("_alt_id_label")
        if label is None:
            return
        alt = self._display_alt_id()
        label.setText("" if alt is None else f"Alt ID {alt}")
        label.setVisible(alt is not None)
        btn = self.__dict__.get("_alt_id_add_btn")
        if btn is not None:
            btn.setVisible(alt is None)

    def _open_alt_id_dialog(self, existing: int | None = None):
        """Small dialog to enter a numeric alternative id. Returns
        (True, value) on save — value is None when the field was left blank
        to clear an existing id — or (False, None) if cancelled."""
        from PyQt6.QtWidgets import QDialog, QFormLayout, QDialogButtonBox

        dlg = QDialog(self)
        dlg.setWindowTitle("Edit Alt ID" if existing is not None
                           else "Add Alt ID")
        form = QFormLayout(dlg)
        edit = QLineEdit()
        edit.setPlaceholderText("e.g. 12345")
        if existing is not None:
            edit.setText(str(existing))
            edit.selectAll()
        form.addRow("Alt ID:", edit)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)

        def on_accept():
            t = edit.text().strip()
            # Blank clears an existing id; when adding, a value is required.
            if (not t and existing is None) or not is_valid_alt_id(t):
                QMessageBox.warning(dlg, "Validation",
                                    "Enter a numeric id (digits only).")
                return
            dlg.accept()
        btns.accepted.connect(on_accept)

        if not dlg.exec():
            return (False, None)
        t = edit.text().strip()
        return (True, int(t) if t else None)

    def _edit_alt_id(self):
        """Add/edit dialog for the alt id, from the header's '+ alt id'
        button or a click on the red alt-id label. The dialog works in
        display (decrypted) values; the DB write is the stored form —
        encrypted when a session key is set."""
        from db.members import set_member_alt_id
        from db.alt_id_crypto import encrypt_or_raw

        existing_stored = self._member.get("alt_id")
        saved, alt = self._open_alt_id_dialog(existing=self._display_alt_id())
        if not saved:
            return
        stored = encrypt_or_raw(self.__dict__.get("_alt_id_key"), alt)
        if stored == existing_stored:
            return
        try:
            set_member_alt_id(self._center_id, stored, self._db_path)
        except Exception as exc:
            show_db_error(self, exc)
            return
        self._member["alt_id"] = stored
        self._refresh_alt_id_label()
        # Keep the Info tab field in sync (if built) without marking the form
        # dirty — the value is already saved. The field shows display values.
        info_field = self.__dict__.get("_info_alt_id")
        if info_field is not None:
            was_dirty = self.__dict__.get("_dirty", False)
            info_field.setText("" if alt is None else str(alt))
            info_field.set_baseline()
            if not was_dirty:
                self._set_dirty(False)
        # Log the stored (cipher) value — the events log lives on disk, so
        # logging the plaintext would defeat encryption at rest.
        self._log_event("EDIT", "Alt ID cleared" if stored is None
                        else f"Alt ID set: {stored}")
        # The sidebar search matches over the main window's cached member
        # list — tell it to refresh so the new alt id is searchable now.
        self.members_changed.emit()

    def _refresh_terminated_badge(self):
        """Add or remove the header 'Terminated' badge to match the member's
        current enrollment state, so re-enrolling clears it without reopening."""
        if not hasattr(self, "_header_top_row"):
            return
        from db.members import is_terminated
        if self._term_badge is not None:
            self._header_top_row.removeWidget(self._term_badge)
            self._term_badge.deleteLater()
            self._term_badge = None
        if is_terminated(self._enrollments):
            badge = QLabel("⊘ Terminated")
            badge.setObjectName("terminated_badge")
            badge.setMaximumHeight(26)
            idx = 2 if self._header_plan_badge is not None else 1
            self._header_top_row.insertWidget(
                idx, badge, alignment=Qt.AlignmentFlag.AlignVCenter)
            self._term_badge = badge

    def _overlay_current_auth(self):
        """Show the *current* (in-effect-today) authorization's plan and member
        id on the header and Info tab. Contacts.[Health Plan]/[Member ID] are
        only re-synced on auth edits, so on open they can be stale (showing the
        latest-start auth); this overlays the in-effect values for display.
        Skips empty values so a current auth never blanks an existing one."""
        from db.members import current_authorization
        current = current_authorization(self._authorizations)
        if not current:
            return
        plan = (current.get("health_plan") or "").strip()
        if plan:
            self._member["health_plan"] = plan
        mid = (current.get("member_id") or "").strip()
        if mid:
            self._member["member_id"] = mid

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
        """Return a PHOTO_SIZE clickable label showing the member photo.
        Clicking it opens a file picker to set/replace the photo."""
        from db.members import get_member_photo
        self._photo_label = _PhotoLabel()
        self._photo_label.setFixedSize(PHOTO_SIZE, PHOTO_SIZE)
        self._photo_label.setStyleSheet(
            f"border-radius: {PHOTO_SIZE // 2}px; overflow: hidden;")
        self._photo_label.clicked.connect(self._change_photo)
        cached = _PHOTO_CACHE.get(self._center_id)
        if cached is not None:
            pix, self._has_photo = cached
            self._photo_label.setPixmap(pix)
        else:
            # Show the placeholder immediately (cheap) and load the real photo —
            # the slow part (a DAO read that can take 300 ms+ over the network)
            # — from paintEvent, AFTER the profile is on screen. A singleShot(0)
            # here fires before the first paint, so it would delay the whole
            # profile by the photo fetch.
            self._has_photo = False
            self._photo_label.setPixmap(_placeholder_photo())
            self._photo_pending = True
        return self._photo_label

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.__dict__.pop("_photo_pending", False):
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, self._load_photo_async)

    def _load_photo_async(self):
        from db.members import get_member_photo
        try:
            data = get_member_photo(self._center_id, self._db_path)
            self._set_photo_pixmap(data)
        except RuntimeError:
            pass        # the member view was closed before the photo arrived
        except Exception:
            pass

    def _set_photo_pixmap(self, photo_bytes):
        """Paint the member photo (or the placeholder) onto self._photo_label and
        record whether a photo exists; cache the result for fast reopen."""
        from PyQt6.QtGui import QPixmap
        from PyQt6.QtCore import Qt as QtCore
        self._has_photo = bool(photo_bytes)
        if photo_bytes:
            s = PHOTO_SIZE
            pix = QPixmap()
            pix.loadFromData(photo_bytes)
            pix = pix.scaled(s, s, QtCore.AspectRatioMode.KeepAspectRatioByExpanding,
                             QtCore.TransformationMode.SmoothTransformation)
            if pix.width() > s or pix.height() > s:
                x = (pix.width() - s) // 2
                y = (pix.height() - s) // 2
                pix = pix.copy(x, y, s, s)
        else:
            pix = _placeholder_photo()
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

    def _print_active_auth(self) -> dict | None:
        """The current active auth (auth_start <= today <= auth_end, same rule
        as the Auths tab's status pill; latest start wins) as pre-formatted
        strings for the printout, with the linked transport auth's number.
        None when nothing is active — the printout notes the lapse."""
        from datetime import date as _date
        today = _date.today()
        active = [a for a in self._authorizations
                  if auth_status(a, today) == "active"]
        if not active:
            return None
        a = max(active, key=lambda x: _as_date(x.get("auth_start")) or _date.min)

        def fmt(value):
            d = _as_date(value)
            return f"{d:%m/%d/%Y}" if d else ""

        from db.members import get_auth_edges
        linked = {e["transport_authorization_id"]
                  for e in get_auth_edges(self._db_path)
                  if e["authorization_id"] == a["id"]}
        trans_numbers = ", ".join(
            t.get("auth_number") or "" for t in self._transport_auths
            if t["id"] in linked and (t.get("auth_number") or ""))

        from db.export import format_auth_days_dotted
        return {
            "sadc": format_auth_days_dotted(a.get("auth_days")),
            "auth_start": fmt(a.get("auth_start")),
            "auth_end": fmt(a.get("auth_end")),
            "auth_number": a.get("auth_number") or "",
            "trans_auth": trans_numbers,
        }

    def _print_profile(self):
        """Open a print preview (print or Save-as-PDF) of this member's profile."""
        from gui.profile_print import open_profile_print_preview
        from db.members import get_member_photo

        photo = get_member_photo(self._center_id, self._db_path)
        open_profile_print_preview(
            self, self._member, self._emergency_contacts,
            self._enrollment_start(self._enrollments), photo_bytes=photo,
            active_auth=self._print_active_auth(),
        )

    # ── Bookmarks ──────────────────────────────────────────────────────────

    def _display_name(self) -> str:
        return (f"{self._member.get('last_name', '')}, "
                f"{self._member.get('first_name', '')}")

    def _sync_bookmark_button(self):
        """Match the header button's label/style to whether this member is
        currently bookmarked (the [marked] property drives the QSS state)."""
        from bookmarks import load_bookmarks, find_bookmark
        marked = find_bookmark(load_bookmarks(), self._center_id) is not None
        b = self._btn_bookmark
        b.setText("🔖 Bookmarked" if marked else "🔖 Bookmark")
        b.setToolTip("Edit this member's bookmark" if marked
                     else "Bookmark this member with an optional note")
        b.setProperty("marked", marked)
        b.style().unpolish(b)
        b.style().polish(b)

    def _open_bookmark_dialog(self):
        """Popup to save (or update/remove) this member's bookmark, with an
        optional note capped at NOTE_MAX_LEN so the list renders compactly."""
        from PyQt6.QtWidgets import QDialog, QPlainTextEdit
        from bookmarks import (
            NOTE_MAX_LEN, load_bookmarks, find_bookmark, upsert_bookmark,
            remove_bookmark, save_bookmarks,
        )
        from gui.theme import current_tokens

        t = current_tokens()
        existing = find_bookmark(load_bookmarks(), self._center_id)
        REMOVE = 2                      # third exit code besides accept/reject

        dlg = QDialog(self)
        dlg.setWindowTitle("Bookmark Member")
        dlg.setMinimumWidth(400)
        root = QVBoxLayout(dlg)
        root.setSpacing(8)

        who = QLabel(
            f"<span style='font-weight:700'>{self._display_name()}</span>"
            f"&nbsp;·&nbsp;<span style='font-weight:600; "
            f"color:{t['accent_text']}'>ID {self._center_id}</span>")
        who.setTextFormat(Qt.TextFormat.RichText)
        root.addWidget(who)

        note_label = QLabel("Note (optional)")
        note_label.setObjectName("field_label")
        root.addWidget(note_label)

        note_edit = QPlainTextEdit()
        note_edit.setPlaceholderText(
            "Why are you bookmarking this member? e.g. Follow up on auth renewal")
        note_edit.setFixedHeight(64)
        if existing:
            note_edit.setPlainText(existing.get("note", "") or "")
        root.addWidget(note_edit)

        counter = QLabel()
        counter.setAlignment(Qt.AlignmentFlag.AlignRight)
        root.addWidget(counter)

        def sync_counter():
            text = note_edit.toPlainText()
            if len(text) > NOTE_MAX_LEN:   # hard cap: trim and restore cursor
                pos = min(note_edit.textCursor().position(), NOTE_MAX_LEN)
                note_edit.blockSignals(True)
                note_edit.setPlainText(text[:NOTE_MAX_LEN])
                cur = note_edit.textCursor()
                cur.setPosition(pos)
                note_edit.setTextCursor(cur)
                note_edit.blockSignals(False)
                text = note_edit.toPlainText()
            at_limit = len(text) >= NOTE_MAX_LEN
            counter.setStyleSheet(
                f"font-size:11px; color:"
                f"{t['error_text'] if at_limit else t['text3']};")
            counter.setText(f"{len(text)} / {NOTE_MAX_LEN}")
        note_edit.textChanged.connect(sync_counter)
        sync_counter()

        btn_row = QHBoxLayout()
        if existing:
            btn_remove = QPushButton("Remove bookmark")
            btn_remove.setObjectName("btn_row_delete")
            btn_remove.clicked.connect(lambda: dlg.done(REMOVE))
            btn_row.addWidget(btn_remove)
        btn_row.addStretch()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(dlg.reject)
        btn_row.addWidget(btn_cancel)
        btn_save = QPushButton("Update bookmark" if existing else "🔖 Bookmark")
        btn_save.setObjectName("btn_row_add")
        btn_save.setDefault(True)
        btn_save.clicked.connect(dlg.accept)
        btn_row.addWidget(btn_save)
        root.addLayout(btn_row)

        code = dlg.exec()
        if code not in (QDialog.DialogCode.Accepted, REMOVE):
            return
        try:
            marks = load_bookmarks()
            if code == REMOVE:
                marks = remove_bookmark(marks, self._center_id)
            else:
                marks = upsert_bookmark(marks, self._center_id,
                                        self._display_name(),
                                        note_edit.toPlainText())
            save_bookmarks(marks)
        except OSError as exc:
            QMessageBox.warning(self, "Bookmarks",
                                f"Could not save bookmarks:\n{exc}")
            return
        self._sync_bookmark_button()
        self.bookmarks_changed.emit()

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
        photo_col = QVBoxLayout()
        photo_col.setSpacing(4)
        photo_col.addWidget(self._make_photo_label(),
                            alignment=Qt.AlignmentFlag.AlignHCenter)
        cid = str(self._center_id)
        id_label = QLabel(
            f"<span style='font-size:17px; font-weight:700; color:#5b7cf4'>"
            f"ID {cid}</span>")
        id_label.setTextFormat(Qt.TextFormat.RichText)
        # Let staff highlight + copy the ID.
        id_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        photo_col.addWidget(id_label, alignment=Qt.AlignmentFlag.AlignHCenter)
        self._alt_id_label = _AltIdLabel()
        self._alt_id_label.setObjectName("alt_id_label")
        self._alt_id_label.clicked.connect(self._edit_alt_id)
        photo_col.addWidget(self._alt_id_label,
                            alignment=Qt.AlignmentFlag.AlignHCenter)
        self._alt_id_add_btn = QPushButton("+ alt id")
        self._alt_id_add_btn.setObjectName("alt_id_add")
        self._alt_id_add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._alt_id_add_btn.clicked.connect(self._edit_alt_id)
        photo_col.addWidget(self._alt_id_add_btn,
                            alignment=Qt.AlignmentFlag.AlignHCenter)
        self._refresh_alt_id_label()
        header.addLayout(photo_col)
        # Top-align via setAlignment, NOT photo_col.addStretch(): an expanding
        # spacer makes the whole header layout report itself as vertically
        # expanding, so it steals half the window's height from the tabs below.
        header.setAlignment(photo_col, Qt.AlignmentFlag.AlignTop)

        right = QVBoxLayout()
        right.setSpacing(6)

        top_row = QHBoxLayout()
        name = f"{self._member.get('last_name', '')}, {self._member.get('first_name', '')}"
        name_label = QLabel(
            f"<span style='font-size:16px; font-weight:700'>{name}</span>")
        name_label.setTextFormat(Qt.TextFormat.RichText)
        # Let staff highlight + copy the name.
        name_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        top_row.addWidget(name_label, alignment=Qt.AlignmentFlag.AlignVCenter)
        # Kept as attributes so the badge can be refreshed in place when an auth
        # change moves which plan is currently in effect.
        self._header_top_row = top_row
        self._header_plan_badge = make_plan_badge(self._header_plan())
        if self._header_plan_badge is not None:
            top_row.addWidget(self._header_plan_badge,
                              alignment=Qt.AlignmentFlag.AlignVCenter)
        from db.members import is_terminated
        self._term_badge = None
        if is_terminated(self._enrollments):
            self._term_badge = QLabel("⊘ Terminated")
            self._term_badge.setObjectName("terminated_badge")
            self._term_badge.setMaximumHeight(26)
            top_row.addWidget(self._term_badge,
                              alignment=Qt.AlignmentFlag.AlignVCenter)
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
        self._btn_bookmark = QPushButton()
        self._btn_bookmark.setObjectName("btn_bookmark")
        self._btn_bookmark.setMaximumHeight(26)
        self._btn_bookmark.clicked.connect(self._open_bookmark_dialog)
        self._sync_bookmark_button()
        top_row.addWidget(self._btn_bookmark,
                          alignment=Qt.AlignmentFlag.AlignVCenter)
        btn_print = QPushButton("🖨 Print")
        btn_print.setObjectName("btn_print")
        btn_print.setToolTip("Print this member's profile")
        btn_print.setMaximumHeight(26)
        btn_print.clicked.connect(self._print_profile)
        top_row.addWidget(btn_print, alignment=Qt.AlignmentFlag.AlignVCenter)
        right.addLayout(top_row)

        notes_row = QHBoxLayout()
        self._notes_label = QLabel("Notes")
        self._notes_label.setObjectName("notes_label")
        notes_row.addWidget(self._notes_label, alignment=Qt.AlignmentFlag.AlignTop)
        self._info_notes = _NotesEdit()
        self._info_notes.setObjectName("notes_edit")
        self._info_notes.setPlainText(self._member.get("notes", "") or "")
        notes_row.addWidget(self._info_notes, 1)
        # A compact "+ Add note" button stands in for the editor until there's a
        # note (or the user clicks it), keeping the header uncluttered.
        self._btn_add_note = QPushButton("+ Add note")
        self._btn_add_note.setObjectName("btn_add_note")
        self._btn_add_note.setMaximumHeight(26)
        self._btn_add_note.clicked.connect(self._reveal_notes)
        notes_row.addWidget(self._btn_add_note, alignment=Qt.AlignmentFlag.AlignTop)
        notes_row.addStretch()
        right.addLayout(notes_row)

        header.addLayout(right, 1)
        layout.addLayout(header)
        # Only now do the notes widgets have this widget as parent (the layout
        # chain was just attached) — setVisible(True) before this point turns
        # them into parentless top-level windows that flash on screen.
        self._init_notes_visibility(
            bool((self._member.get("notes") or "").strip()))

        # Tabs. Only Info — the tab that actually appears — is built now;
        # the others are placeholders filled in on first view
        # (_ensure_tab_built), so opening a member costs one tab, not eight.
        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        self._tab_info = self._make_info_tab()
        self._tabs.addTab(self._tab_info, "Info")

        self._lazy_tabs = {}
        for title, attr, builder in (
            ("Enrollments", "_tab_enrollments", self._make_enrollments_tab),
            ("Auths ⚠" if warn else "Authorizations", "_tab_auths",
             self._make_auths_tab),
            ("Transportation", "_tab_transport", self._make_transport_tab),
            ("Time Slot Availability", "_tab_avail", self._make_avail_tab),
            ("Availability Override", "_tab_unavail",
             self._make_unavailable_tab),
            ("Absences", "_tab_absences", self._make_absences_tab),
            ("Events", "_tab_events", self._make_events_tab),
        ):
            index = self._tabs.addTab(QWidget(), title)
            self._lazy_tabs[index] = (attr, builder)

        # Guard leaving the Info tab with unsaved edits (see _on_tab_changed).
        # Connected last so building/adding the tabs above doesn't trigger it.
        self._info_tab_index = self._tabs.indexOf(self._tab_info)
        self._prev_tab_index = self._tabs.currentIndex()
        self._tabs.currentChanged.connect(self._on_tab_changed)

    def _init_notes_visibility(self, has_note: bool) -> None:
        """Header shows the Notes editor when a note exists, or the compact
        '+ Add note' button when it doesn't."""
        self._notes_label.setVisible(has_note)
        self._info_notes.setVisible(has_note)
        self._btn_add_note.setVisible(not has_note)

    def _reveal_notes(self) -> None:
        """Show the header Notes editor in place of the '+ Add note' button and
        focus it (the button only appears when the member has no note yet)."""
        self._btn_add_note.setVisible(False)
        self._notes_label.setVisible(True)
        self._info_notes.setVisible(True)
        self._info_notes.setFocus()

    def _on_tab_changed(self, index: int) -> None:
        """When the user leaves the Info tab with unsaved edits, confirm before
        moving on. On Cancel, snap back to the Info tab; on Discard, revert the
        Info fields. Only the Info tab has editable fields, so only leaving it is
        guarded."""
        prev = getattr(self, "_prev_tab_index", index)
        if (prev == getattr(self, "_info_tab_index", 0)
                and index != prev
                and getattr(self, "_dirty", False)):
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved changes on the Info tab. Discard them?",
                QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Discard:
                self._discard_info()
            else:
                # Cancel: return to the Info tab without re-triggering this guard.
                self._tabs.blockSignals(True)
                self._tabs.setCurrentIndex(prev)
                self._tabs.blockSignals(False)
                return
        self._ensure_tab_built(index)
        self._prev_tab_index = index

    def _ensure_tab_built(self, index: int) -> None:
        """Swap a lazy tab's placeholder for its real content on first view.

        Signals are blocked during the swap: _refresh_tab removes the current
        tab, which would otherwise re-enter _on_tab_changed and cascade-build
        the neighbouring tabs."""
        # __dict__.get, not hasattr: tests drive this on __new__-built widgets
        # where PyQt attribute lookup raises RuntimeError for missing attrs.
        lazy = self.__dict__.get("_lazy_tabs")
        entry = lazy.pop(index, None) if lazy else None
        if entry is None:
            return
        attr, builder = entry
        widget = builder()
        setattr(self, attr, widget)
        self._tabs.blockSignals(True)
        try:
            self._refresh_tab(index, widget)
        finally:
            self._tabs.blockSignals(False)

    def _make_events_tab(self) -> QWidget:
        from gui.events_view import EventsTableWidget
        return EventsTableWidget(
            self._events_path, center_id=self._center_id, show_header=False)

    # ── Info tab (Task 9) ──────────────────────────────────────────────────

    def _make_schedule_card(self, active_days, period_text) -> QWidget:
        """A compact, contained Schedule summary: authorized-day chips and the
        auth period on one spaced row (instead of stretched grid cells)."""
        card = QWidget()
        card.setObjectName("schedule_card")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        outer = QVBoxLayout(card)
        outer.setContentsMargins(16, 12, 16, 12)
        outer.setSpacing(8)

        caption = QLabel("Schedule")
        caption.setObjectName("strip_caption")
        outer.addWidget(caption)

        row = QHBoxLayout()
        row.setSpacing(10)
        days_lbl = QLabel("Authorized Days")
        days_lbl.setObjectName("field_label")
        row.addWidget(days_lbl)
        row.addWidget(WeekdayChips(active_days))
        # The same days in the paper-form notation staff use ("SADC 1.5"
        # for Mon+Fri), right next to the chips.
        sadc_lbl = QLabel("SADC")
        sadc_lbl.setObjectName("field_label")
        row.addSpacing(18)
        row.addWidget(sadc_lbl)
        sadc_val = QLabel(
            ".".join(str(d) for d in sorted(active_days)) or "—")
        sadc_val.setObjectName("schedule_value")
        sadc_val.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        row.addWidget(sadc_val)
        row.addSpacing(28)
        period_lbl = QLabel("Auth Period")
        period_lbl.setObjectName("field_label")
        row.addWidget(period_lbl)
        period_val = QLabel(period_text)
        period_val.setObjectName("schedule_value")
        period_val.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        row.addWidget(period_val)
        row.addStretch()
        outer.addLayout(row)
        return card

    def _build_schedule_card(self) -> QWidget:
        """A Schedule card reflecting the authorization in effect today: its
        authorized-day chips and auth period. 'None' when no auth is current.
        Factored out of _make_info_tab so it can be rebuilt after an auth
        change (see _refresh_schedule_card)."""
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
        return self._make_schedule_card(active_days, period_text)

    def _refresh_schedule_card(self) -> None:
        """Rebuild the Info tab's Schedule card in place so a newly added/edited/
        deleted authorization's days show the moment you return to the Info tab,
        without reopening the member. No-op if the Info tab wasn't built yet."""
        # __dict__ (not getattr) so it's safe on the __new__-built test widgets.
        if self.__dict__.get("_schedule_card") is None:
            return
        new_card = self._build_schedule_card()
        self._info_content_layout.replaceWidget(self._schedule_card, new_card)
        self._schedule_card.deleteLater()
        self._schedule_card = new_card

    def _open_layout_editor(self):
        """Open the layout editor; on save, persist and rebuild the tab."""
        from PyQt6.QtWidgets import QMessageBox
        if self.__dict__.get("_dirty"):
            QMessageBox.information(
                self, "Customize Layout",
                "Save or discard your field edits first — changing the "
                "layout rebuilds the tab.")
            return
        from PyQt6.QtWidgets import QDialog
        from gui.info_layout_editor import InfoLayoutEditor
        # The preview shows display values: alt_id decrypted, and the
        # computed Center ID / Enrollment Start the tab itself renders.
        preview_member = dict(self._member)
        alt = self._display_alt_id()
        preview_member["alt_id"] = "" if alt is None else str(alt)
        preview_member["center_id"] = str(self._center_id)
        start = self._enrollment_start(self._enrollments)
        preview_member["enrollment_start"] = str(start) if start else ""
        dlg = InfoLayoutEditor(self._layout_cfg, preview_member, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self._apply_layout(dlg.result_layout())

    def _apply_layout(self, layout_cfg: dict) -> None:
        """Adopt a new layout: save it to the settings JSON (when this widget
        has one) and rebuild the Info tab in place."""
        self._layout_cfg = layout_cfg
        settings = self.__dict__.get("_settings")
        path = self.__dict__.get("_settings_path")
        if settings is not None:
            settings["info_tab_layout"] = layout_cfg
            if path:
                from settings import save_settings
                try:
                    save_settings(settings, path)
                except OSError as exc:
                    from PyQt6.QtWidgets import QMessageBox
                    QMessageBox.warning(
                        self, "Customize Layout",
                        f"Could not save the layout:\n{exc}")
        self._rebuild_info_tab()

    def _rebuild_info_tab(self) -> None:
        """Swap a freshly built Info tab in at the same index. Field widgets
        are re-created, so dirty tracking is reset and re-armed."""
        idx = self._tabs.indexOf(self._tab_info)
        old = self._tab_info
        self._tabs.blockSignals(True)   # don't trip the unsaved-edits guard
        self._tabs.removeTab(idx)
        self._tab_info = self._make_info_tab()
        self._tabs.insertTab(idx, self._tab_info, "Info")
        self._tabs.setCurrentIndex(idx)
        self._tabs.blockSignals(False)
        self._info_tab_index = idx
        self._prev_tab_index = idx
        old.deleteLater()
        self._dirty = False
        self._setup_dirty_tracking()

    def _make_info_tab(self) -> QWidget:
        from PyQt6.QtWidgets import (
            QLineEdit, QScrollArea, QGridLayout,
        )
        from PyQt6.QtGui import QFont

        m = self._member

        def field(key: str) -> "_ViewEditLineEdit":
            # Flat, selectable text that becomes editable on the hover pencil.
            return _ViewEditLineEdit(m.get(key, "") or "")

        def phone_field(key: str) -> "_ViewEditLineEdit":
            # Shown formatted as (xxx)-xxx-xxxx; typing limited to phone chars.
            f = _ViewEditLineEdit(format_phone(m.get(key, "") or ""))
            f.setValidator(make_phone_validator(f))
            return f

        # ── Widgets (attribute names unchanged so save/discard/dirty work) ──
        self._info_first     = field("first_name")
        self._info_last      = field("last_name")
        self._info_chinese   = field("chinese_name")
        self._info_gender    = field("gender")
        self._info_dob       = _ViewEditLineEdit(
            format_dob_display(m.get("dob", "") or ""))
        self._info_cid       = _ViewEditLineEdit(str(self._center_id),
                                                 editable=False)
        # Member ID is assigned at member creation and shown read-only here.
        self._info_member_id = _ViewEditLineEdit(m.get("member_id", "") or "",
                                                 editable=False)

        from gui.address_autocomplete import AddressAutocomplete
        self._info_address = AddressAutocomplete(self._api_key, view_edit=True)
        self._info_address.set_address(m.get("address", "") or "")
        self._info_home_tell = phone_field("home_tell")
        self._info_cell      = phone_field("cell")
        self._info_emergency = field("emergency")

        self._info_plan = _ViewEditLineEdit(m.get("health_plan", "") or "",
                                            editable=False)
        # Validated fields that format as you type (empty allowed):
        self._info_medicaid = _ViewEditLineEdit(
            format_medicaid(m.get("medicaid", "") or ""),
            formatter=format_medicaid, validator=is_valid_medicaid,
            live_formatter=format_medicaid_live)
        self._info_medicare = _ViewEditLineEdit(
            format_medicare(m.get("medicare", "") or ""),
            formatter=format_medicare, validator=is_valid_medicare,
            live_formatter=format_medicare_live)
        self._info_ssn = _ViewEditLineEdit(
            format_ssn(m.get("ssn", "") or ""),
            formatter=format_ssn, validator=is_valid_ssn,
            live_formatter=format_ssn_live)
        self._info_pcp      = field("pcp")
        self._info_hospital = field("hospital")
        self._info_hha      = field("hha")
        self._info_language = field("language")
        alt = self._display_alt_id()
        self._info_alt_id = _ViewEditLineEdit(
            "" if alt is None else str(alt), validator=is_valid_alt_id)

        self._info_case_manager   = field("case_manager")
        # Group (Contacts.[Group]): the site/location code the meal sheet
        # prints as Location.
        self._info_group          = field("group")
        # Notes is built in the header (always-visible band), not here.

        enroll_start = self._enrollment_start(self._enrollments)
        enroll_lbl = _ViewEditLineEdit(str(enroll_start) if enroll_start else "—",
                                       editable=False)

        # ── Layout-driven sectioned grid (see gui/info_layout.py) ──────────
        from gui.info_layout import (
            normalize, placements, FIELD_LABELS_BY_KEY,
        )
        layout_cfg = normalize(self.__dict__.get("_layout_cfg"))
        self._layout_cfg = layout_cfg

        # Age readout beside the DOB: display-only, tracks the DOB field live.
        # Saving reads self._info_dob directly, so the age never enters the
        # stored value.
        self._info_age = QLabel()
        self._info_age.setObjectName("field_label")
        self._info_age.setProperty("lsize", layout_cfg.get("label_size", "normal"))

        def _refresh_age(text: str):
            years = age_from_dob(text.strip())
            self._info_age.setText("" if years is None else f"(Age {years})")
        self._info_dob.textChanged.connect(_refresh_age)
        _refresh_age(self._info_dob.text())

        self._info_dob_row = QWidget()
        dob_row = QHBoxLayout(self._info_dob_row)
        dob_row.setContentsMargins(0, 0, 0, 0)
        dob_row.setSpacing(6)
        dob_row.addWidget(self._info_dob, 1)
        dob_row.addWidget(self._info_age)

        widgets = {
            "first_name": self._info_first, "last_name": self._info_last,
            "chinese_name": self._info_chinese, "gender": self._info_gender,
            "dob": self._info_dob_row, "ssn": self._info_ssn,
            "center_id": self._info_cid, "enrollment_start": enroll_lbl,
            "language": self._info_language, "alt_id": self._info_alt_id,
            "address": self._info_address, "home_tell": self._info_home_tell,
            "cell": self._info_cell, "emergency": self._info_emergency,
            "health_plan": self._info_plan,
            "member_id": self._info_member_id,
            "medicaid": self._info_medicaid, "medicare": self._info_medicare,
            "hospital": self._info_hospital, "pcp": self._info_pcp,
            "hha": self._info_hha, "case_manager": self._info_case_manager,
            "group": self._info_group,
        }
        # Kept so hidden (unparented-from-grid) widgets are still reachable
        # for baseline resets after save — findChildren alone would miss them.
        self._info_widgets_by_key = widgets

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

        self._schedule_card = None
        placed_keys = set()
        for block in layout_cfg["blocks"]:
            if block["type"] == "schedule":
                if block.get("visible", True):
                    self._schedule_card = self._build_schedule_card()
                    grid.addWidget(self._schedule_card,
                                   state["row"], 0, 1, 6)
                    state["row"] += 1
            elif block["type"] == "emergency":
                # Box + fill always happen (the header badge and live
                # contact edits go through them); placing is optional.
                self._emergency_box = QWidget()
                ebox = QVBoxLayout(self._emergency_box)
                ebox.setContentsMargins(0, 0, 0, 0)
                if block.get("visible", True):
                    section("Emergency")
                    grid.addWidget(self._emergency_box,
                                   state["row"], 0, 1, 6)
                    state["row"] += 1
                else:
                    self._emergency_box.setVisible(False)
                self._fill_emergency_box()
            else:
                placed = placements(block["fields"])
                if not placed:
                    continue          # empty/all-hidden section: no header
                section(block["title"])
                base = state["row"]
                last_row = 0
                for cfg, row, slot, span in placed:
                    widget = widgets[cfg["key"]]
                    placed_keys.add(cfg["key"])
                    lab = QLabel(FIELD_LABELS_BY_KEY[cfg["key"]])
                    lab.setObjectName("field_label")
                    lab.setProperty(
                        "lsize", layout_cfg.get("label_size", "normal"))
                    grid.addWidget(
                        lab, base + row, slot * 2,
                        Qt.AlignmentFlag.AlignRight
                        | Qt.AlignmentFlag.AlignVCenter)
                    grid.addWidget(widget, base + row, slot * 2 + 1,
                                   1, span * 2 - 1)
                    apply_field_style(widget, cfg)
                    last_row = row
                state["row"] = base + last_row + 1

        # Hidden fields: widget exists and holds its value (saving reads every
        # widget) but is never placed.
        for key, widget in widgets.items():
            if key not in placed_keys:
                widget.setVisible(False)

        grid.setRowStretch(state["row"], 1)

        # ── Assemble (scroll area is a safety net; content fits unscrolled) ─
        content = QWidget()
        content.setLayout(grid)
        # Kept so the Schedule card can be rebuilt in place when an auth
        # changes (replaceWidget preserves the grid position).
        self._info_content_layout = grid

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
        btn_customize = QPushButton("✎ Customize Layout")
        btn_customize.clicked.connect(self._open_layout_editor)
        btn_row.addWidget(btn_customize)
        btn_row.addStretch()
        btn_discard = QPushButton("Discard Changes")
        btn_discard.setObjectName("btn_discard")
        btn_discard.clicked.connect(self._confirm_discard)
        btn_save = QPushButton("Save Changes")
        btn_save.setObjectName("btn_save")
        btn_save.clicked.connect(self._save_info)
        # Grayed/disabled until there are unsaved edits (see _set_dirty).
        btn_discard.setEnabled(False)
        btn_save.setEnabled(False)
        self._btn_discard = btn_discard
        self._btn_save = btn_save
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
            table.setItem(r, 1, QTableWidgetItem(format_phone(ec["phone"])))
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
        btn_add = QPushButton("+ Add Contact")
        btn_add.clicked.connect(self._add_emergency)
        btn_del = QPushButton("Delete Selected")
        btn_del.clicked.connect(lambda: self._delete_emergency(table))
        self._style_crud_buttons(table, btn_add, btn_del)
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
        # Same phone behavior as Add Member: type digits, auto-format on blur,
        # red outline when the entry isn't a valid 10-digit number.
        phone_edit = PhoneLineEdit()
        phone_edit.setText(format_phone(e.get("phone", "")))
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
            if phone_edit.text().strip() and not phone_edit.is_valid():
                set_widget_error(phone_edit, True)
                QMessageBox.warning(dlg, "Validation",
                                    "Phone number must be 10 digits.")
                return
            dlg.accept()

        btns.accepted.connect(on_accept)
        if not dlg.exec():
            return None
        return {
            "full_name": name_edit.text().strip(),
            "phone": format_phone(phone_edit.text().strip()),
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
            show_db_error(self, exc)

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
            show_db_error(self, exc)

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
                show_db_error(self, exc)

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

    def _populate_info_fields(self):
        """(Re)display every Info field from self._member, applying display
        formatting (phone -> (xxx)-xxx-xxxx, DOB -> date only). Used on discard
        and after a save so the shown values match what was stored."""
        m = self._member
        self._info_first.setText(m.get("first_name", "") or "")
        self._info_last.setText(m.get("last_name", "") or "")
        self._info_chinese.setText(m.get("chinese_name", "") or "")
        self._info_gender.setText(m.get("gender", "") or "")
        self._info_dob.setText(format_dob_display(m.get("dob", "") or ""))
        self._info_member_id.setText(m.get("member_id", "") or "")
        self._info_medicaid.setText(format_medicaid(m.get("medicaid", "") or ""))
        self._info_medicare.setText(format_medicare(m.get("medicare", "") or ""))
        self._info_ssn.setText(format_ssn(m.get("ssn", "") or ""))
        self._info_pcp.setText(m.get("pcp", "") or "")
        self._info_hospital.setText(m.get("hospital", "") or "")
        self._info_hha.setText(m.get("hha", "") or "")
        self._info_language.setText(m.get("language", "") or "")
        self._info_address.setText(m.get("address", "") or "")
        self._info_home_tell.setText(format_phone(m.get("home_tell", "") or ""))
        self._info_cell.setText(format_phone(m.get("cell", "") or ""))
        self._info_emergency.setText(m.get("emergency", "") or "")
        self._info_case_manager.setText(m.get("case_manager", "") or "")
        self._info_group.setText(m.get("group", "") or "")
        alt = self._display_alt_id()
        self._info_alt_id.setText("" if alt is None else str(alt))
        self._info_notes.setPlainText(m.get("notes", "") or "")

    def _discard_info(self):
        self._populate_info_fields()
        self._set_dirty(False)

    def _save_info(self):
        from db.members import update_contact

        # Block save on invalid (non-empty) SSN / Medicaid / Medicare, flagging
        # the offending field(s) — same idea as the Add Member phone validation.
        bad = []
        for w, valid_fn, label, hint in (
            (self._info_ssn, is_valid_ssn, "SSN", "xxx-xx-xxxx"),
            (self._info_medicaid, is_valid_medicaid, "Medicaid", "AA12345B"),
            (self._info_medicare, is_valid_medicare, "Medicare", "MBI format"),
            (self._info_alt_id, is_valid_alt_id, "Alt ID", "digits only"),
        ):
            if w.text().strip() and not valid_fn(w.text().strip()):
                set_widget_error(w, True)
                bad.append(f"{label} ({hint})")
        if bad:
            QMessageBox.warning(self, "Validation",
                                "Please fix these fields:\n  • " + "\n  • ".join(bad))
            return

        old = self._member
        fields = {
            "last_name":      self._info_last.text().strip(),
            "first_name":     self._info_first.text().strip(),
            "chinese_name":   self._info_chinese.text().strip(),
            "gender":         self._info_gender.text().strip(),
            "dob":            format_date_only(self._info_dob.text().strip()),
            "member_id":      self._info_member_id.text().strip(),
            "health_plan":    self._member.get("health_plan", "") or "",
            "medicaid":       format_medicaid(self._info_medicaid.text().strip()),
            "medicare":       format_medicare(self._info_medicare.text().strip()),
            "ssn":            format_ssn(self._info_ssn.text().strip()),
            "language":       self._info_language.text().strip(),
            "case_manager":   self._info_case_manager.text().strip(),
            "home_tell":      format_phone(self._info_home_tell.text().strip()),
            "cell":           format_phone(self._info_cell.text().strip()),
            "address":        self._info_address.text().strip(),
            "emergency":      self._info_emergency.text().strip(),
            "pcp":            self._info_pcp.text().strip(),
            "hospital":       self._info_hospital.text().strip(),
            "hha":            self._info_hha.text().strip(),
            "group":          self._info_group.text().strip(),
            # Admission Date is no longer shown/edited here; preserve the stored
            # value so saving the form never blanks it.
            "admission_date": old.get("admission_date", "") or "",
            "notes":          self._info_notes.toPlainText().strip(),
            # Canonical int | None (validation above guarantees digits).
            "alt_id":         (int(self._info_alt_id.text().strip())
                               if self._info_alt_id.text().strip() else None),
        }

        # The field holds the display (decrypted) value; the DB stores the
        # encrypted form when a session key is set. FPE is deterministic, so
        # an untouched value re-encrypts to the identical stored value and is
        # correctly reported as "no change".
        from db.alt_id_crypto import encrypt_or_raw
        alt_plain = fields["alt_id"]
        fields["alt_id"] = encrypt_or_raw(
            self.__dict__.get("_alt_id_key"), alt_plain)

        # Compare/summarize in display values so the confirm dialog never
        # shows ciphertext (bijectivity keeps change detection equivalent).
        shown_old = {**old, "alt_id": self._display_alt_id()}
        shown_new = {**fields, "alt_id": alt_plain}
        rows = build_change_rows(shown_old, shown_new)
        summary = build_change_summary(shown_old, shown_new)
        if not rows:
            self._set_dirty(False)
            return

        name = f"{old.get('last_name', '')}, {old.get('first_name', '')}"
        from PyQt6.QtWidgets import QDialog
        from gui.confirm_changes import ConfirmChangesDialog
        confirm = ConfirmChangesDialog(name, rows, self)
        if confirm.exec() != QDialog.DialogCode.Accepted:
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
                alt_id=fields["alt_id"],
                group=fields["group"],
            )
            self._member.update(fields)
            # Refresh the shown values from what was saved so formatting (phone,
            # DOB) appears immediately, without revisiting the profile.
            self._populate_info_fields()
            self._refresh_alt_id_label()
            # findChildren alone misses hidden fields (never parented into the
            # grid), so also sweep the layout's widget map for those — looking
            # inside composite entries (the DOB row) for their line edits.
            baseline_widgets = set(self.findChildren(_ViewEditLineEdit))
            for entry in getattr(self, "_info_widgets_by_key", {}).values():
                if isinstance(entry, _ViewEditLineEdit):
                    baseline_widgets.add(entry)
                else:
                    baseline_widgets.update(entry.findChildren(_ViewEditLineEdit))
            for w in baseline_widgets:
                w.set_baseline()                 # saved values -> clear highlight
            self._set_dirty(False)
            new_long_lat = self._info_address.long_lat()
            if new_long_lat:
                from db.members import set_member_long_lat
                set_member_long_lat(self._center_id, new_long_lat, self._db_path)
            self._log_event("EDIT", "; ".join(summary))
            # Names / alt id feed the sidebar search — refresh its cached list.
            self.members_changed.emit()
        except Exception as exc:
            show_db_error(self, exc, "Could Not Save Changes")

    # ── Dirty tracking ─────────────────────────────────────────────────────

    def _set_dirty(self, dirty: bool):
        """Track unsaved edits and reflect them on the action buttons: grayed and
        disabled when clean, enabled and colored (Save green, Discard red) when
        there are edits."""
        self._dirty = dirty
        if hasattr(self, "_btn_save"):
            self._btn_save.setEnabled(dirty)
        if hasattr(self, "_btn_discard"):
            self._btn_discard.setEnabled(dirty)

    def _setup_dirty_tracking(self):
        self._set_dirty(False)
        line_edits = (
            self._info_first, self._info_last, self._info_chinese,
            self._info_gender, self._info_dob,
            self._info_medicaid, self._info_medicare, self._info_ssn,
            self._info_language, self._info_case_manager,
            self._info_home_tell, self._info_cell, self._info_address,
            self._info_emergency, self._info_pcp, self._info_hospital,
            self._info_hha, self._info_alt_id, self._info_group,
        )
        for w in line_edits:
            w.textChanged.connect(lambda: self._set_dirty(True))
        # __dict__.get, not attribute access: _info_notes lives on the header
        # (built once in _build_ui, not _make_info_tab), so a __new__-built
        # test widget that only ever calls _make_info_tab() never has it. A
        # rebuilt Info tab re-runs this method against the same surviving
        # header widget, so the connection is armed only once — otherwise
        # repeated layout applies would stack another lambda onto it forever.
        notes = self.__dict__.get("_info_notes")
        if notes is not None and not self.__dict__.get("_notes_dirty_armed"):
            notes.textChanged.connect(lambda: self._set_dirty(True))
            self._notes_dirty_armed = True

    def is_dirty(self) -> bool:
        return self._dirty

    # ── Row-ID column visibility (debug setting) ────────────────────────────

    # Bookkeeping columns the debug 'show row IDs' setting governs: the row ID
    # plus the auto-stamped 'Created' timestamp, both noise for everyday use.
    _DEBUG_COLUMNS = ("ID", "Created")

    def _apply_id_column(self, table) -> None:
        """Hide the bookkeeping columns ('ID', 'Created') unless the debug
        'show row IDs' setting is on. The columns' cells still populate, so
        row-id lookups (delete, edit, select-by-id) keep working — they are only
        hidden from view. Called by every table builder so refreshed tabs stay
        consistent. Tables without these columns (Info emergency, Events) are
        left untouched."""
        # Read via __dict__ so it's safe on the __new__-built widgets used in
        # tests (a missing attr would otherwise raise, not default).
        show = self.__dict__.get("_show_row_ids", False)
        for c in range(table.columnCount()):
            header = table.horizontalHeaderItem(c)
            if header is not None and header.text() in self._DEBUG_COLUMNS:
                table.setColumnHidden(c, not show)

    # Tables (one per tab) whose 'ID' column the debug toggle governs.
    _ID_TABLE_ATTRS = ("_enroll_table", "_auth_table", "_transport_table",
                       "_avail_table", "_unavail_table", "_abs_table")

    def set_show_row_ids(self, show: bool) -> None:
        """Toggle the debug row-ID columns live across every already-built table,
        without rebuilding the tabs (so unsaved edits aren't lost)."""
        self._show_row_ids = show
        for name in self._ID_TABLE_ATTRS:
            table = self.__dict__.get(name)
            if table is not None:
                self._apply_id_column(table)

    def set_alt_id_key(self, key: bytes | None) -> None:
        """Apply a changed session alt-id password live: the header label and
        Info field re-render with the new key's display values, without
        rebuilding the tabs (so unsaved edits elsewhere survive)."""
        self._alt_id_key = key
        self._refresh_alt_id_label()
        info_field = self.__dict__.get("_info_alt_id")
        if info_field is not None:
            was_dirty = self.__dict__.get("_dirty", False)
            alt = self._display_alt_id()
            info_field.setText("" if alt is None else str(alt))
            info_field.set_baseline()
            if not was_dirty:
                self._set_dirty(False)

    # ── Table tab helper ───────────────────────────────────────────────────

    def _make_table_tab(self, columns, rows, on_add, on_delete,
                        empty_text: str = "Nothing here yet — click + Add."):
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

        btn_add = QPushButton("+ Add")
        btn_add.clicked.connect(on_add)
        btn_del = QPushButton("Delete Selected")
        btn_del.clicked.connect(lambda: on_delete(table))
        self._style_crud_buttons(table, btn_add, btn_del)

        layout.addLayout(self._add_bar(btn_add))   # Add at top-right
        layout.addWidget(table)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(btn_del)
        layout.addLayout(btn_row)
        self._apply_id_column(table)
        set_table_empty_state(table, empty_text)
        return w, table

    def _refresh_tab(self, index: int, new_widget: QWidget):
        old = self._tabs.widget(index)
        label = self._tabs.tabText(index)
        self._tabs.removeTab(index)
        self._tabs.insertTab(index, new_widget, label)
        self._tabs.setCurrentIndex(index)
        if old:
            old.deleteLater()

    @staticmethod
    def _bind_delete_button(table, btn_del):
        """Style the Delete button red and keep it grayed/disabled until a row is
        selected (it acts on the selection)."""
        btn_del.setObjectName("btn_row_delete")

        def _sync():
            btn_del.setEnabled(len(table.selectionModel().selectedRows()) > 0)
        table.itemSelectionChanged.connect(_sync)
        _sync()

    @staticmethod
    def _style_crud_buttons(table, btn_add, btn_del):
        """Color-code the row Add (green) / Delete (red) buttons, and keep Delete
        grayed/disabled until a row is selected (it acts on the selection)."""
        btn_add.setObjectName("btn_row_add")
        MemberTabsWidget._bind_delete_button(table, btn_del)

    @staticmethod
    def _add_bar(btn_add):
        """A right-aligned top bar that places the primary '+ Add' action at the
        top-right of a tab (instead of the bottom-left)."""
        bar = QHBoxLayout()
        bar.setContentsMargins(0, 0, 0, 6)
        bar.addStretch()
        bar.addWidget(btn_add)
        return bar

    def _confirm_unauthorized_day(self, weekdays, action: str) -> bool:
        """If a scheduling change touches weekday(s) the member isn't currently
        authorized for, ask the user to confirm. Returns True to proceed."""
        from datetime import date
        today = date.today()
        if not needs_unauthorized_warning(self._authorizations, weekdays, today):
            return True
        if authorized_weekdays(self._authorizations, today):
            names = ", ".join(WEEKDAY_NAMES.get(d, str(d))
                              for d in sorted(set(weekdays)))
            text = (f"The member isn't currently authorized for {names}.\n\n"
                    f"{action} anyway?")
        else:
            text = f"The member has no current authorization.\n\n{action} anyway?"
        return QMessageBox.question(self, "Day not authorized", text) \
            == QMessageBox.StandardButton.Yes

    # ── Enrollments tab ────────────────────────────────────────────────────

    def _make_enrollments_tab(self) -> QWidget:
        from PyQt6.QtWidgets import (
            QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView,
        )
        from datetime import date

        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 12, 0, 0)

        columns = ["ID", "Start Date", "End Date", "Status", "Action"]
        table = QTableWidget(len(self._enrollments), len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        # Columns hug their content (dates stay compact, like the Auths tab);
        # leftover width stays plain table background. Action is fixed below to
        # fit the widest Edit/Terminate row (ResizeToContents mis-measures
        # widget-only columns and clips the buttons).
        hdr = table.horizontalHeader()
        hdr.setStretchLastSection(False)
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(40)  # room for action buttons

        from db.members import enrollment_active, sort_enrollments_active_first

        today = date.today()
        action_wraps = []
        # Active (in-effect) enrollments on top, ended ones below; each by start
        # date, most recent first.
        for r, e in enumerate(sort_enrollments_active_first(self._enrollments, today)):
            end = e["end_date"]
            active = enrollment_active(e, today)
            table.setItem(r, 0, QTableWidgetItem(str(e["id"])))
            table.setItem(r, 1, QTableWidgetItem(str(e["start_date"])))
            table.setItem(r, 2, QTableWidgetItem(str(end) if end else "ongoing"))
            table.setItem(r, 3, QTableWidgetItem("Active" if active else "Ended"))
            edit_btn = QPushButton("Edit")
            edit_btn.setObjectName("btn_edit")
            edit_btn.clicked.connect(
                lambda _=False, entry=e: self._edit_enrollment(entry)
            )
            # Wrap so the buttons hug their text instead of stretching into
            # full-width bars across the Action column.
            wrap = QWidget()
            hl = QHBoxLayout(wrap)
            hl.setContentsMargins(6, 2, 6, 2)
            hl.addWidget(edit_btn)
            if active:
                btn = QPushButton("Terminate…")
                btn.setObjectName("btn_terminate")
                btn.clicked.connect(
                    lambda _=False, rid=e["id"]: self._terminate_enrollment(rid)
                )
                hl.addWidget(btn)
            hl.addStretch()
            table.setCellWidget(r, 4, wrap)
            action_wraps.append(wrap)

        # Fix Action to the widest row's real size hint (plus slack) so the
        # buttons never clip; the empty-table floor keeps the header readable.
        widest = max((w_.sizeHint().width() for w_ in action_wraps), default=0)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(4, max(widest + 36, 140))

        self._apply_id_column(table)
        set_table_empty_state(
            table, "No enrollments yet — click + Add to record one.")
        self._enroll_table = table
        btn_add = QPushButton("+ Add")
        btn_add.clicked.connect(self._add_enrollment)
        btn_del = QPushButton("Delete Selected")
        btn_del.clicked.connect(lambda: self._delete_enrollment(table))
        self._style_crud_buttons(table, btn_add, btn_del)

        layout.addLayout(self._add_bar(btn_add))   # Add at top-right
        layout.addWidget(table)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(btn_del)
        layout.addLayout(btn_row)
        return w

    def _add_enrollment(self):
        from PyQt6.QtWidgets import QDialog, QFormLayout, QDateEdit, QDialogButtonBox
        from PyQt6.QtCore import QDate
        from datetime import date
        from db.members import (
            insert_enrollment, enrollment_active, has_active_enrollment,
        )
        from monthly_schedule.db import get_enrollments

        dlg = QDialog(self)
        dlg.setWindowTitle("Add Enrollment")
        form = QFormLayout(dlg)
        start = DateLineEdit()
        start.set_pydate(date.today())
        end = DateLineEdit()        # blank = ongoing
        form.addRow("Start Date:", start)
        form.addRow("End Date (blank = ongoing):", end)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)

        def on_accept():
            ok = start.flag_validity(required=True)
            ok = end.flag_validity() and ok
            if not ok:
                QMessageBox.warning(dlg, "Validation",
                    "Enter a valid Start Date (MM/DD/YYYY); leave End blank for "
                    "ongoing.")
                return
            dlg.accept()
        btns.accepted.connect(on_accept)

        if dlg.exec():
            s = start.to_pydate()
            e = end.to_pydate()         # None when blank (ongoing)
            # A member can have only one active enrollment at a time. Block adding
            # a second in-effect enrollment; the existing one must be terminated
            # first.
            today = date.today()
            new_active = enrollment_active({"end_date": e}, today)
            if new_active and has_active_enrollment(self._enrollments, today):
                QMessageBox.warning(
                    self, "Active enrollment exists",
                    "This member already has an active enrollment. Terminate it "
                    "before adding a new one.")
                return
            try:
                insert_enrollment(self._center_id, s, e, self._db_path)
                self._enrollments = get_enrollments(self._center_id, self._db_path)
                self._refresh_tab(1, self._make_enrollments_tab())
                self._refresh_terminated_badge()
                self.members_changed.emit()
                self._log_event("ENROLL", f"Enrollment added: {s} – {e or 'ongoing'}")
            except Exception as exc:
                show_db_error(self, exc)

    def _edit_enrollment(self, entry: dict):
        from PyQt6.QtWidgets import QDialog, QFormLayout, QDialogButtonBox
        from datetime import date
        from db.members import (
            update_enrollment, enrollment_active, has_active_enrollment,
        )
        from monthly_schedule.db import get_enrollments

        dlg = QDialog(self)
        dlg.setWindowTitle("Edit Enrollment")
        form = QFormLayout(dlg)
        start = DateLineEdit()
        old_start = _as_date(entry.get("start_date"))
        if old_start:
            start.set_pydate(old_start)
        end = DateLineEdit()        # blank = ongoing
        old_end = _as_date(entry.get("end_date"))
        if old_end:
            end.set_pydate(old_end)
        form.addRow("Start Date:", start)
        form.addRow("End Date (blank = ongoing):", end)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)

        def on_accept():
            ok = start.flag_validity(required=True)
            ok = end.flag_validity() and ok
            if not ok:
                QMessageBox.warning(dlg, "Validation",
                    "Enter a valid Start Date (MM/DD/YYYY); leave End blank for "
                    "ongoing.")
                return
            e = end.to_pydate()
            if e and e < start.to_pydate():
                QMessageBox.warning(dlg, "Validation",
                    "End Date can't be before the Start Date.")
                return
            dlg.accept()
        btns.accepted.connect(on_accept)

        if not dlg.exec():
            return
        s = start.to_pydate()
        e = end.to_pydate()         # None when blank (ongoing)
        # A member can have only one active enrollment at a time. Block an edit
        # that would make this one active alongside another in-effect enrollment.
        today = date.today()
        others = [x for x in self._enrollments if x["id"] != entry["id"]]
        if enrollment_active({"end_date": e}, today) \
                and has_active_enrollment(others, today):
            QMessageBox.warning(
                self, "Active enrollment exists",
                "This member already has another active enrollment. Terminate "
                "it before making this one active.")
            return
        try:
            update_enrollment(entry["id"], s, e, self._db_path)
            self._enrollments = get_enrollments(self._center_id, self._db_path)
            self._refresh_tab(1, self._make_enrollments_tab())
            self._refresh_terminated_badge()
            self.members_changed.emit()
            self._log_event(
                "ENROLL",
                f"Enrollment edited: {entry['start_date']} – "
                f"{entry['end_date'] or 'ongoing'} → {s} – {e or 'ongoing'}")
        except Exception as exc:
            show_db_error(self, exc)

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
                self._refresh_terminated_badge()
                self.members_changed.emit()
                if entry:
                    self._log_event(
                        "ENROLL",
                        f"Enrollment deleted: {entry['start_date']} – "
                        f"{entry['end_date'] or 'ongoing'}")
            except Exception as exc:
                show_db_error(self, exc)

    def _terminate_enrollment(self, record_id: int):
        from PyQt6.QtWidgets import QDialog, QFormLayout, QLabel, QDialogButtonBox
        from datetime import date
        from db.members import terminate_enrollment
        from monthly_schedule.db import get_enrollments

        entry = next((e for e in self._enrollments if e["id"] == record_id), None)
        start = _as_date(entry.get("start_date")) if entry else None

        dlg = QDialog(self)
        dlg.setWindowTitle("Terminate Enrollment")
        form = QFormLayout(dlg)
        form.addRow(QLabel("Terminate this enrollment? This can't be undone."))
        end = DateLineEdit()
        end.set_pydate(date.today())
        form.addRow("Termination Date:", end)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)

        def on_accept():
            if not end.flag_validity(required=True):
                QMessageBox.warning(dlg, "Validation",
                    "Enter a valid Termination Date (MM/DD/YYYY).")
                return
            if start and end.to_pydate() < start:
                QMessageBox.warning(dlg, "Validation",
                    f"Termination Date can't be before the enrollment start "
                    f"({start.isoformat()}).")
                return
            dlg.accept()
        btns.accepted.connect(on_accept)

        if not dlg.exec():
            return
        end_date = end.to_pydate()
        try:
            terminate_enrollment(record_id, self._db_path, end_date)
            self._enrollments = get_enrollments(self._center_id, self._db_path)
            self._refresh_tab(1, self._make_enrollments_tab())
            self._refresh_terminated_badge()
            self.members_changed.emit()
            self._log_event("ENROLL",
                            f"Enrollment terminated: end set to {end_date.isoformat()}")
        except Exception as exc:
            show_db_error(self, exc)

    # ── Authorizations tab ─────────────────────────────────────────────────

    def _make_auths_tab(self) -> QWidget:
        from datetime import date
        from PyQt6.QtWidgets import (
            QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView,
            QGraphicsOpacityEffect,
        )
        from PyQt6.QtGui import QColor

        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 12, 0, 0)

        columns = ["ID", "Auth Start", "Auth End", "Days", "Health Plan",
                   "Plan Type", "Member ID", "Auth Number", "Created", "Status",
                   "Transport", "Document", "Action"]
        ci = {name: i for i, name in enumerate(columns)}
        table = QTableWidget(len(self._authorizations), len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.horizontalHeaderItem(ci["Days"]).setToolTip(
            "1=Mon  2=Tue  3=Wed  4=Thu  5=Fri")
        table.horizontalHeaderItem(ci["Transport"]).setToolTip(
            "Linked transportation authorizations")
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        hdr = table.horizontalHeader()
        # Columns hug their content; leftover width stays plain table background
        # (no trailing grayed strip).
        hdr.setStretchLastSection(False)
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(40)  # roomier rows; pills uncramped

        from db.members import get_auth_ids_with_documents, get_auth_edges
        doc_ids = get_auth_ids_with_documents(self._center_id, self._db_path)

        # Linked transport auths per care auth (via the [AuthEdge] junction).
        t_by_id = {t["id"]: t for t in self._transport_auths}
        transports_by_care: dict = {}
        for e in get_auth_edges(self._db_path):
            tr = t_by_id.get(e["transport_authorization_id"])
            if tr is not None:
                transports_by_care.setdefault(e["authorization_id"], []).append(tr)

        today = date.today()
        overlaps = auth_overlap_map(self._authorizations)
        plan_badges, status_chips = [], []
        for r, a in enumerate(sort_auths_latest_first(self._authorizations)):
            status = auth_status(a, today)

            start_item = QTableWidgetItem(str(a["auth_start"]))
            end_item = QTableWidgetItem(str(a["auth_end"]))
            table.setItem(r, ci["ID"], QTableWidgetItem(str(a["id"])))
            table.setItem(r, ci["Auth Start"], start_item)
            table.setItem(r, ci["Auth End"], end_item)

            # Conflict: this auth's date range overlaps another's. Tint the date
            # cells red and explain which auth(s) it collides with.
            conflicts = overlaps.get(a["id"]) or []
            if conflicts:
                tip = "⚠ Overlaps " + ", ".join(
                    f"#{o['id']} ({o['auth_start']} – {o['auth_end']})"
                    for o in conflicts)
                for it in (start_item, end_item):
                    it.setBackground(QColor(208, 85, 85, 70))
                    it.setToolTip(tip)

            chips = WeekdayChips(decode_auth_days(a["auth_days"] or ""), compact=True)
            table.setCellWidget(r, ci["Days"], chips)

            # Health plan as the same colored pill used everywhere else, a
            # compact pill centered in its column.
            badge = make_plan_badge(a.get("health_plan", "") or "")
            plan_cell = None
            if badge is not None:
                plan_cell = _centered_cell(badge)
                plan_badges.append(badge)
                table.setCellWidget(r, ci["Health Plan"], plan_cell)
            else:
                table.setItem(r, ci["Health Plan"], QTableWidgetItem(""))

            # Plan type (MAP/MLTC); blank for rows that predate the column.
            table.setItem(r, ci["Plan Type"], QTableWidgetItem(a.get("plan_type") or ""))

            # Member ID (per-authorization); blank when unset.
            table.setItem(r, ci["Member ID"], QTableWidgetItem(a.get("member_id") or ""))

            # Authorization number; blank when unset / predating the column.
            table.setItem(r, ci["Auth Number"], QTableWidgetItem(a.get("auth_number") or ""))

            # When the row was created (auto-stamped on insert); blank for rows
            # that predate the column.
            table.setItem(r, ci["Created"],
                          QTableWidgetItem(format_created_at(a.get("created_at"))))

            # Linked transportation auths: a button that opens a picker of the
            # transport auths tied to this care auth; "—" when there are none.
            linked = transports_by_care.get(a["id"], [])
            if linked:
                t_btn = QPushButton(f"View ({len(linked)})")
                t_btn.setObjectName("btn_edit")
                t_btn.clicked.connect(
                    lambda _=False, items=linked:
                    self._open_linked_transports_popup(items))
                table.setCellWidget(r, ci["Transport"], t_btn)
            else:
                dash = QTableWidgetItem("—")
                dash.setForeground(QColor(EXPIRED_FG))
                dash.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(r, ci["Transport"], dash)

            has_doc = a["id"] in doc_ids
            doc_btn = QPushButton("Open" if has_doc else "Attach")
            doc_btn.setObjectName("btn_edit")
            if has_doc:
                doc_btn.clicked.connect(
                    lambda _=False, auth=a: self._open_auth_document_menu(auth))
            else:
                doc_btn.clicked.connect(
                    lambda _=False, auth=a: self._attach_auth_document(auth))
            table.setCellWidget(r, ci["Document"], doc_btn)

            # Every authorization is editable (older ones included).
            btn = QPushButton("Edit")
            btn.setObjectName("btn_edit")
            btn.clicked.connect(lambda _=False, auth=a: self._edit_auth(auth))
            table.setCellWidget(r, ci["Action"], btn)

            # Status pill: green Active / amber Upcoming / red Expired, centered.
            _label = {"active": "Active", "upcoming": "Upcoming",
                      "expired": "Expired"}[status]
            _chip_obj = {"active": "active_chip", "upcoming": "upcoming_chip",
                         "expired": "expired_chip"}[status]
            chip = QLabel(_label)
            chip.setObjectName(_chip_obj)
            status_chips.append(chip)
            table.setCellWidget(r, ci["Status"], _centered_cell(chip))

            if status != "expired":
                continue

            # Expired rows are dimmed so the in-effect ones stand out.
            for name in ("ID", "Auth Start", "Auth End", "Plan Type",
                         "Member ID", "Auth Number", "Created"):
                item = table.item(r, ci[name])
                if item is not None:
                    item.setForeground(QColor(EXPIRED_FG))
            for widget in (chips, plan_cell):
                if widget is not None:
                    eff = QGraphicsOpacityEffect(widget)
                    eff.setOpacity(0.45)
                    widget.setGraphicsEffect(eff)

        # Size the pill columns to fit their widest pill so nothing clips.
        _fit_pill_column(table, ci["Health Plan"], plan_badges, floor=96)
        _fit_pill_column(table, ci["Status"], status_chips, floor=96)

        self._apply_id_column(table)
        set_table_empty_state(
            table, "No authorizations yet — click + Add to record one.")
        self._auth_table = table
        btn_add = QPushButton("+ Add")
        btn_add.clicked.connect(self._add_auth)
        btn_del = QPushButton("Delete Selected")
        btn_del.clicked.connect(lambda: self._delete_auth(table))
        self._style_crud_buttons(table, btn_add, btn_del)

        layout.addLayout(self._add_bar(btn_add))   # Add at top-right
        layout.addWidget(table)

        btn_row = QHBoxLayout()
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
        from db.members import (
            get_authorizations, sync_health_plan_from_current_auth,
            sync_member_id_from_current_auth,
        )

        sync_health_plan_from_current_auth(self._center_id, self._db_path)
        sync_member_id_from_current_auth(self._center_id, self._db_path)
        self._authorizations = get_authorizations(self._center_id, self._db_path)

        # Refresh the profile so it reflects the change: re-derive the current
        # auth's plan/member id, then update the header badge and Info fields.
        self._overlay_current_auth()
        if hasattr(self, "_info_plan"):
            self._info_plan.setText(self._member.get("health_plan", "") or "")
        if hasattr(self, "_info_member_id"):
            self._info_member_id.setText(self._member.get("member_id", "") or "")
        self._refresh_header_plan()
        # Rebuild the Info tab's Schedule card so its authorized-day chips reflect
        # the change immediately (not only after reopening the member).
        self._refresh_schedule_card()

        self._refresh_tab(2, self._make_auths_tab())
        if description:
            self._log_event("AUTH", description)
        # Auth dates changed: let the main window refresh the notification
        # bell (expiring/expired counts) without reopening the member.
        self.members_changed.emit()

    def _open_auth_dialog(self, existing: dict | None = None) -> dict | None:
        """Build the Add/Edit Authorization dialog. Returns a dict with
        auth_start, auth_end, days, health_plan, plan_type, member_id,
        auth_number — or None if cancelled. Pre-fills from `existing` when
        editing."""
        from PyQt6.QtWidgets import (
            QDialog, QFormLayout, QDateEdit, QCheckBox, QComboBox,
            QHBoxLayout, QDialogButtonBox, QWidget, QLineEdit,
        )
        from PyQt6.QtCore import QDate
        from db.members import HEALTH_PLANS, PLAN_TYPES

        dlg = QDialog(self)
        dlg.setWindowTitle("Edit Authorization" if existing else "Add Authorization")
        form = QFormLayout(dlg)

        # Creating: dates start empty and must be typed — a new authorization
        # is an explicit act, nothing is pre-dated.
        auth_start = DateLineEdit()
        auth_end = DateLineEdit()
        if existing:
            auth_start.set_pydate(existing["auth_start"])
            auth_end.set_pydate(existing["auth_end"])

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
        if existing:
            plan_combo.addItems(HEALTH_PLANS)
            idx = plan_combo.findText(existing.get("health_plan", ""))
            if idx >= 0:
                plan_combo.setCurrentIndex(idx)
        else:
            # Creating: start on a blank entry so the plan is a choice, not
            # whatever happened to be first in the list.
            plan_combo.addItems(("",) + HEALTH_PLANS)

        # Plan type (MAP/MLTC); the blank entry covers rows that predate the
        # column so editing one doesn't force a value onto it.
        plan_type_combo = QComboBox()
        plan_type_combo.addItems(PLAN_TYPES)
        if existing:
            idx = plan_type_combo.findText(existing.get("plan_type", "") or "")
            if idx >= 0:
                plan_type_combo.setCurrentIndex(idx)

        # Member ID per authorization; defaults to the member's current Member ID
        # for a new auth, or the auth's own value when editing.
        member_id_edit = QLineEdit(
            (existing.get("member_id") if existing else self._member.get("member_id"))
            or "")
        member_id_edit.setPlaceholderText("Health plan member / insurance ID")

        auth_number_edit = QLineEdit(
            (existing.get("auth_number") if existing else "") or "")
        auth_number_edit.setPlaceholderText("Authorization number")

        if not existing:
            # A failed OK outlines missing fields red; editing one clears it.
            for combo in (plan_combo, plan_type_combo):
                combo.currentIndexChanged.connect(
                    lambda _i, c=combo: set_widget_error(c, False))
            for edit in (member_id_edit, auth_number_edit):
                edit.textEdited.connect(
                    lambda _t, e=edit: set_widget_error(e, False))

        form.addRow("Auth Start:", auth_start)
        form.addRow("Auth End:", auth_end)
        form.addRow("Days:", days_widget)
        form.addRow("Health Plan:", plan_combo)
        form.addRow("Plan Type:", plan_type_combo)
        form.addRow("Member ID:", member_id_edit)
        form.addRow("Auth Number:", auth_number_edit)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)

        def on_accept():
            # Paint the date outlines in both modes.
            dates_ok = auth_start.flag_validity(required=True)
            dates_ok = auth_end.flag_validity(required=True) and dates_ok
            if existing:
                # Editing keeps the original rules (dates + days) so legacy
                # rows with blank plan type / auth number stay editable.
                if not dates_ok:
                    QMessageBox.warning(dlg, "Validation",
                        "Enter valid Auth Start and Auth End dates "
                        "(MM/DD/YYYY).")
                    return
                if not any(cb.isChecked() for cb in day_checks.values()):
                    QMessageBox.warning(dlg, "Validation",
                                        "Select at least one day.")
                    return
                dlg.accept()
                return
            # flag_validity above already painted the outlines; is_valid
            # re-reads them.
            missing = missing_new_auth_fields(
                start_valid=auth_start.is_valid(required=True),
                end_valid=auth_end.is_valid(required=True),
                has_day=any(cb.isChecked() for cb in day_checks.values()),
                health_plan=plan_combo.currentText(),
                plan_type=plan_type_combo.currentText(),
                member_id=member_id_edit.text(),
                auth_number=auth_number_edit.text(),
            )
            set_widget_error(plan_combo, "Health Plan" in missing)
            set_widget_error(plan_type_combo, "Plan Type" in missing)
            set_widget_error(member_id_edit, "Member ID" in missing)
            set_widget_error(auth_number_edit, "Auth Number" in missing)
            if missing:
                QMessageBox.warning(
                    dlg, "Validation",
                    "All fields are required for a new authorization. "
                    "Missing:\n  •  " + "\n  •  ".join(missing))
                return
            dlg.accept()
        btns.accepted.connect(on_accept)

        if not dlg.exec():
            return None
        return {
            "auth_start": auth_start.to_pydate(),
            "auth_end": auth_end.to_pydate(),
            "days": {n for n, cb in day_checks.items() if cb.isChecked()},
            "health_plan": plan_combo.currentText(),
            "plan_type": plan_type_combo.currentText(),
            "member_id": member_id_edit.text().strip(),
            "auth_number": auth_number_edit.text().strip(),
        }

    def _confirm_overlap(self, start, end, exclude_id=None) -> bool:
        """If the candidate [start, end] overlaps existing auths, warn that it
        would leave two authorizations active at once and ask to proceed.
        Returns True to continue, False to abort."""
        conflicts = auths_overlapping(self._authorizations, start, end, exclude_id)
        if not conflicts:
            return True
        listing = "\n".join(
            f"  •  #{a['id']}: {a['auth_start']} – {a['auth_end']}"
            for a in conflicts)
        return QMessageBox.question(
            self, "Overlapping authorization",
            "These dates overlap an existing authorization, which would leave "
            "two authorizations active at the same time:\n\n"
            f"{listing}\n\nSave it anyway?",
        ) == QMessageBox.StandardButton.Yes

    def _add_auth(self):
        from db.members import insert_authorization, encode_auth_days

        result = self._open_auth_dialog()
        if not result:
            return
        if not self._confirm_overlap(result["auth_start"], result["auth_end"]):
            return
        try:
            insert_authorization(
                self._center_id, result["auth_start"], result["auth_end"],
                result["days"], None, None, result["health_plan"], self._db_path,
                member_id=result["member_id"],
                auth_number=result["auth_number"],
                plan_type=result["plan_type"],
            )
            self._after_auth_change(
                f"Auth added: {result['auth_start']} – {result['auth_end']} · "
                f"{encode_auth_days(result['days'])} · {result['health_plan']}"
            )
        except Exception as exc:
            show_db_error(self, exc)

    def _edit_auth(self, auth: dict):
        from db.members import update_authorization, encode_auth_days

        result = self._open_auth_dialog(existing=auth)
        if not result:
            return
        if not self._confirm_overlap(result["auth_start"], result["auth_end"],
                                     exclude_id=auth["id"]):
            return
        try:
            update_authorization(
                auth["id"], result["auth_start"], result["auth_end"],
                result["days"], result["health_plan"], self._db_path,
                member_id=result["member_id"],
                auth_number=result["auth_number"],
                plan_type=result["plan_type"],
            )
            self._after_auth_change(
                f"Auth edited: {result['auth_start']} – {result['auth_end']} · "
                f"{encode_auth_days(result['days'])} · {result['health_plan']}"
            )
        except Exception as exc:
            show_db_error(self, exc)

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
                show_db_error(self, exc)

    # ── Transportation tab ─────────────────────────────────────────────────

    def _make_transport_tab(self) -> QWidget:
        """Transportation authorizations: a separate [TransportAuthorization]
        table shown like the Authorizations tab, with a 'Linked Auth' column
        derived from the [AuthEdge] junction. The Document column appears only
        when [TransportAuthorization] has a [Document] attachment field."""
        from datetime import date
        from PyQt6.QtWidgets import (
            QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView,
            QGraphicsOpacityEffect,
        )
        from PyQt6.QtGui import QColor
        from db.members import (
            get_transport_ids_with_documents, get_auth_edges,
            transport_has_document_column,
        )

        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 12, 0, 0)

        has_doc = transport_has_document_column(self._db_path)
        columns = ["ID", "Auth Start", "Auth End", "Days", "Health Plan",
                   "Member ID", "Auth Number", "Linked Auth", "Created", "Status"]
        if has_doc:
            columns.append("Document")
        columns.append("Action")
        ci = {name: i for i, name in enumerate(columns)}

        table = QTableWidget(len(self._transport_auths), len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.horizontalHeaderItem(ci["Days"]).setToolTip(
            "1=Mon  2=Tue  3=Wed  4=Thu  5=Fri")
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        hdr = table.horizontalHeader()
        hdr.setStretchLastSection(False)
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(40)

        doc_ids = get_transport_ids_with_documents(self._center_id, self._db_path)

        # care<->transport link: transport id -> care auth id -> care auth number.
        link_map = {e["transport_authorization_id"]: e["authorization_id"]
                    for e in get_auth_edges(self._db_path)}
        auth_by_id = {a["id"]: a for a in self._authorizations}

        today = date.today()
        plan_badges, status_chips = [], []
        for r, t in enumerate(sort_auths_latest_first(self._transport_auths)):
            status = auth_status(t, today)

            table.setItem(r, ci["ID"], QTableWidgetItem(str(t["id"])))
            table.setItem(r, ci["Auth Start"], QTableWidgetItem(str(t["auth_start"])))
            table.setItem(r, ci["Auth End"], QTableWidgetItem(str(t["auth_end"])))

            chips = WeekdayChips(decode_auth_days(t["auth_days"] or ""), compact=True)
            table.setCellWidget(r, ci["Days"], chips)

            badge = make_plan_badge(t.get("health_plan", "") or "")
            plan_cell = None
            if badge is not None:
                plan_cell = _centered_cell(badge)
                plan_badges.append(badge)
                table.setCellWidget(r, ci["Health Plan"], plan_cell)
            else:
                table.setItem(r, ci["Health Plan"], QTableWidgetItem(""))

            table.setItem(r, ci["Member ID"], QTableWidgetItem(t.get("member_id") or ""))
            table.setItem(r, ci["Auth Number"], QTableWidgetItem(t.get("auth_number") or ""))

            # Linked care auth: show its auth number (blank when unlinked). When
            # linked, the cell is a clickable link that jumps to that care auth
            # on the Authorizations tab (care id stashed in UserRole).
            care_id = link_map.get(t["id"])
            care = auth_by_id.get(care_id)
            linked_item = QTableWidgetItem((care.get("auth_number") if care else "") or "")
            if care:
                linked_item.setData(Qt.ItemDataRole.UserRole, care_id)
                linked_item.setToolTip(
                    f"Click to open the linked care authorization #{care_id} "
                    f"({care.get('auth_start')} – {care.get('auth_end')})")
                linked_item.setForeground(QColor(LINK_FG))
                lf = linked_item.font()
                lf.setUnderline(True)
                linked_item.setFont(lf)
            table.setItem(r, ci["Linked Auth"], linked_item)

            table.setItem(r, ci["Created"],
                          QTableWidgetItem(format_created_at(t.get("created_at"))))

            if has_doc:
                has_d = t["id"] in doc_ids
                doc_btn = QPushButton("Open" if has_d else "Attach")
                doc_btn.setObjectName("btn_edit")
                if has_d:
                    doc_btn.clicked.connect(
                        lambda _=False, tr=t: self._open_transport_document_menu(tr))
                else:
                    doc_btn.clicked.connect(
                        lambda _=False, tr=t: self._attach_transport_document(tr))
                table.setCellWidget(r, ci["Document"], doc_btn)

            btn = QPushButton("Edit")
            btn.setObjectName("btn_edit")
            btn.clicked.connect(
                lambda _=False, tr=t, link=care_id: self._edit_transport(tr, link))
            table.setCellWidget(r, ci["Action"], btn)

            _label = {"active": "Active", "upcoming": "Upcoming",
                      "expired": "Expired"}[status]
            _chip_obj = {"active": "active_chip", "upcoming": "upcoming_chip",
                         "expired": "expired_chip"}[status]
            chip = QLabel(_label)
            chip.setObjectName(_chip_obj)
            status_chips.append(chip)
            table.setCellWidget(r, ci["Status"], _centered_cell(chip))

            if status != "expired":
                continue

            for name in ("ID", "Auth Start", "Auth End", "Member ID",
                         "Auth Number", "Linked Auth", "Created"):
                item = table.item(r, ci[name])
                if item is not None:
                    item.setForeground(QColor(EXPIRED_FG))
            for widget in (chips, plan_cell):
                if widget is not None:
                    eff = QGraphicsOpacityEffect(widget)
                    eff.setOpacity(0.45)
                    widget.setGraphicsEffect(eff)

        _fit_pill_column(table, ci["Health Plan"], plan_badges, floor=96)
        _fit_pill_column(table, ci["Status"], status_chips, floor=96)

        self._apply_id_column(table)
        set_table_empty_state(
            table,
            "No transportation authorizations yet — click + Add to record one.")
        self._transport_table = table
        self._transport_linked_col = ci["Linked Auth"]
        table.cellClicked.connect(self._on_transport_linked_clicked)
        btn_add = QPushButton("+ Add")
        btn_add.clicked.connect(self._add_transport)
        btn_del = QPushButton("Delete Selected")
        btn_del.clicked.connect(lambda: self._delete_transport(table))
        self._style_crud_buttons(table, btn_add, btn_del)

        layout.addLayout(self._add_bar(btn_add))   # Add at top-right
        layout.addWidget(table)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(btn_del)
        layout.addLayout(btn_row)
        return w

    def _open_transport_dialog(self, existing: dict | None = None,
                               current_link=None) -> dict | None:
        """Add/Edit Transportation Auth dialog. Mirrors the Authorization dialog
        plus a 'Linked Care Auth' combo; on a fresh add, picking a care auth
        prefills dates/days/plan from it (transport usually mirrors the care
        auth, but may differ). Returns the auth dict + care_auth_id, or None."""
        from PyQt6.QtWidgets import (
            QDialog, QFormLayout, QCheckBox, QComboBox,
            QHBoxLayout, QDialogButtonBox, QWidget, QLineEdit,
        )
        from db.members import (
            HEALTH_PLANS, current_authorization, latest_authorization,
        )
        from datetime import date as _date

        dlg = QDialog(self)
        dlg.setWindowTitle(
            "Edit Transportation Auth" if existing else "Add Transportation Auth")
        form = QFormLayout(dlg)

        auth_start = DateLineEdit()
        auth_end = DateLineEdit()
        if existing:
            auth_start.set_pydate(existing["auth_start"])
            auth_end.set_pydate(existing["auth_end"])
        else:
            today = _date.today()
            auth_start.set_pydate(today)
            auth_end.set_pydate(today.replace(year=today.year + 1))

        existing_days = (
            self.decode_auth_days_static(existing["auth_days"]) if existing else set()
        )
        day_checks = {}
        days_widget = QWidget()
        days_hl = QHBoxLayout(days_widget)
        days_hl.setContentsMargins(0, 0, 0, 0)
        for num, label in [(1, "Mon"), (2, "Tue"), (3, "Wed"), (4, "Thu"),
                           (5, "Fri"), (6, "Sat"), (7, "Sun")]:
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

        member_id_edit = QLineEdit(
            (existing.get("member_id") if existing else self._member.get("member_id"))
            or "")
        member_id_edit.setPlaceholderText("Health plan member / insurance ID")

        auth_number_edit = QLineEdit(
            (existing.get("auth_number") if existing else "") or "")
        auth_number_edit.setPlaceholderText("Transportation authorization number")

        # Linked care auth (optional). Selecting one on a fresh add prefills the
        # dates/days/plan/member-id from it.
        auth_by_id = {a["id"]: a for a in self._authorizations}
        link_combo = QComboBox()
        link_combo.addItem("— none —", None)
        for a in sort_auths_latest_first(self._authorizations):
            num = a.get("auth_number") or "(no #)"
            link_combo.addItem(
                f"{num}  ({a.get('auth_start')} – {a.get('auth_end')})", a["id"])

        def apply_prefill():
            if existing is not None:
                return
            src = auth_by_id.get(link_combo.currentData())
            if not src:
                return
            if src.get("auth_start"):
                auth_start.set_pydate(src["auth_start"])
            if src.get("auth_end"):
                auth_end.set_pydate(src["auth_end"])
            src_days = self.decode_auth_days_static(src.get("auth_days") or "")
            for n, cb in day_checks.items():
                cb.setChecked(n in src_days)
            pidx = plan_combo.findText(src.get("health_plan", "") or "")
            if pidx >= 0:
                plan_combo.setCurrentIndex(pidx)
            if not member_id_edit.text().strip():
                member_id_edit.setText(src.get("member_id") or "")

        link_combo.currentIndexChanged.connect(lambda _=0: apply_prefill())

        preselect_id = current_link if existing else (
            (current_authorization(self._authorizations)
             or latest_authorization(self._authorizations) or {}).get("id"))
        if preselect_id is not None:
            pos = link_combo.findData(preselect_id)
            if pos >= 0:
                link_combo.setCurrentIndex(pos)

        form.addRow("Linked Care Auth:", link_combo)
        form.addRow("Auth Start:", auth_start)
        form.addRow("Auth End:", auth_end)
        form.addRow("Days:", days_widget)
        form.addRow("Health Plan:", plan_combo)
        form.addRow("Member ID:", member_id_edit)
        form.addRow("Auth Number:", auth_number_edit)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)

        def on_accept():
            ok = auth_start.flag_validity(required=True)
            ok = auth_end.flag_validity(required=True) and ok
            if not ok:
                QMessageBox.warning(dlg, "Validation",
                    "Enter valid Auth Start and Auth End dates (MM/DD/YYYY).")
                return
            if not any(cb.isChecked() for cb in day_checks.values()):
                QMessageBox.warning(dlg, "Validation", "Select at least one day.")
                return
            dlg.accept()
        btns.accepted.connect(on_accept)

        if not dlg.exec():
            return None
        return {
            "auth_start": auth_start.to_pydate(),
            "auth_end": auth_end.to_pydate(),
            "days": {n for n, cb in day_checks.items() if cb.isChecked()},
            "health_plan": plan_combo.currentText(),
            "member_id": member_id_edit.text().strip(),
            "auth_number": auth_number_edit.text().strip(),
            "care_auth_id": link_combo.currentData(),
        }

    def _add_transport(self):
        from db.members import (
            insert_transport_authorization, set_transport_link, encode_auth_days,
        )
        result = self._open_transport_dialog()
        if not result:
            return
        try:
            new_id = insert_transport_authorization(
                self._center_id, result["auth_start"], result["auth_end"],
                result["days"], result["health_plan"], self._db_path,
                member_id=result["member_id"], auth_number=result["auth_number"],
            )
            set_transport_link(new_id, result["care_auth_id"], self._db_path)
            self._after_transport_change(
                f"Transport auth added: {result['auth_start']} – "
                f"{result['auth_end']} · {encode_auth_days(result['days'])} · "
                f"{result['auth_number']}")
        except Exception as exc:
            show_db_error(self, exc)

    def _edit_transport(self, transport: dict, current_link=None):
        from db.members import (
            update_transport_authorization, set_transport_link, encode_auth_days,
        )
        result = self._open_transport_dialog(existing=transport,
                                             current_link=current_link)
        if not result:
            return
        try:
            update_transport_authorization(
                transport["id"], result["auth_start"], result["auth_end"],
                result["days"], result["health_plan"], self._db_path,
                member_id=result["member_id"], auth_number=result["auth_number"],
            )
            set_transport_link(transport["id"], result["care_auth_id"], self._db_path)
            self._after_transport_change(
                f"Transport auth edited: {result['auth_start']} – "
                f"{result['auth_end']} · {encode_auth_days(result['days'])} · "
                f"{result['auth_number']}")
        except Exception as exc:
            show_db_error(self, exc)

    def _delete_transport(self, table):
        row = table.currentRow()
        if row < 0:
            return
        record_id = int(table.item(row, 0).text())
        if QMessageBox.question(
                self, "Confirm", "Delete this transportation authorization?") \
                == QMessageBox.StandardButton.Yes:
            from db.members import delete_transport_authorization
            entry = next((t for t in self._transport_auths
                          if t["id"] == record_id), None)
            try:
                delete_transport_authorization(record_id, self._db_path)
                self._after_transport_change(None)
                if entry:
                    self._log_event(
                        "TRANSPORT",
                        f"Transport auth deleted: {entry['auth_start']} – "
                        f"{entry['auth_end']} · {entry.get('auth_number', '')}")
            except Exception as exc:
                show_db_error(self, exc)

    def _attach_transport_document(self, transport: dict, replace: bool = False):
        from PyQt6.QtWidgets import QFileDialog
        from db.members import set_transport_document
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
            set_transport_document(transport["id"], path, self._db_path)
            verb = "replaced" if replace else "attached"
            self._after_transport_change(
                f"Transport document {verb}: "
                f"{transport['auth_start']} – {transport['auth_end']}")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Could not attach document:\n{exc}")

    def _open_transport_document_menu(self, transport: dict):
        box = QMessageBox(self)
        box.setWindowTitle("Transportation Document")
        box.setText(
            f"Document for transportation authorization "
            f"{transport['auth_start']} – {transport['auth_end']}.")
        open_btn = box.addButton("Open", QMessageBox.ButtonRole.AcceptRole)
        replace_btn = box.addButton("Replace", QMessageBox.ButtonRole.ActionRole)
        box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked is open_btn:
            self._do_open_transport_document(transport)
        elif clicked is replace_btn:
            self._attach_transport_document(transport, replace=True)

    def _do_open_transport_document(self, transport: dict):
        from db.members import save_transport_document
        import os
        import tempfile

        tmp_dir = tempfile.mkdtemp(prefix="transportdoc_")
        try:
            path = save_transport_document(transport["id"], tmp_dir, self._db_path)
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

    def _after_transport_change(self, description: str | None):
        """Reload transport auths, refresh the Transportation tab, and (optionally)
        log a TRANSPORT event. No Contacts plan/member sync (transport must not
        drive the member's health plan)."""
        from db.members import get_transport_authorizations
        self._transport_auths = get_transport_authorizations(
            self._center_id, self._db_path)
        self._refresh_tab(3, self._make_transport_tab())
        if description:
            self._log_event("TRANSPORT", description)

    # ── Cross-tab navigation (Authorizations <-> Transportation) ───────────

    def _select_row_by_id(self, table, record_id) -> None:
        """Select and scroll to the row whose first column equals record_id."""
        if table is None:
            return
        for r in range(table.rowCount()):
            it = table.item(r, 0)
            if it is not None and it.text() == str(record_id):
                table.selectRow(r)
                table.scrollToItem(it)
                table.setFocus()
                return

    def _goto_auth(self, auth_id) -> None:
        """Switch to the Authorizations tab and select that care auth."""
        self._tabs.setCurrentIndex(2)
        self._select_row_by_id(getattr(self, "_auth_table", None), auth_id)

    def _goto_transport(self, transport_id) -> None:
        """Switch to the Transportation tab and select that transport auth."""
        self._tabs.setCurrentIndex(3)
        self._select_row_by_id(getattr(self, "_transport_table", None), transport_id)

    def _on_transport_linked_clicked(self, row, col) -> None:
        """Clicking the Linked Auth cell jumps to its care auth on the Auth tab."""
        if col != getattr(self, "_transport_linked_col", -1):
            return
        item = self._transport_table.item(row, col)
        if item is None:
            return
        care_id = item.data(Qt.ItemDataRole.UserRole)
        if care_id is not None:
            self._goto_auth(care_id)

    def _open_linked_transports_popup(self, transports: list) -> None:
        """A small picker (Ctrl-K-like) of the transport auths linked to a care
        auth; single-click navigates to that transport on the Transportation tab."""
        from PyQt6.QtWidgets import (
            QDialog, QVBoxLayout, QLabel, QListWidget, QListWidgetItem,
        )
        dlg = QDialog(self)
        dlg.setWindowTitle("Linked Transportation Authorizations")
        dlg.resize(480, 320)
        v = QVBoxLayout(dlg)
        v.addWidget(QLabel("Select a transportation authorization to open it:"))
        lst = QListWidget()
        for t in sort_auths_latest_first(transports):
            num = t.get("auth_number") or "(no #)"
            days = format_auth_days(t.get("auth_days", "") or "")
            label = (f"{num}      {t.get('auth_start')} – {t.get('auth_end')}"
                     f"      [{days}]")
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, t["id"])
            lst.addItem(item)
        if lst.count():
            lst.setCurrentRow(0)
        v.addWidget(lst)

        def choose(item):
            tid = item.data(Qt.ItemDataRole.UserRole)
            dlg.accept()
            self._goto_transport(tid)

        lst.itemClicked.connect(choose)
        dlg.exec()

    # ── Availability tab ───────────────────────────────────────────────────

    def _make_current_schedule_strip(self, today) -> QWidget:
        """A read-only 'what's in effect today' strip: Mon–Fri always (dash for a
        day with no current window), plus any weekend day that has a window or is
        authorized. Authorized days are flagged with a green check."""
        box = QWidget()
        outer = QVBoxLayout(box)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)

        # Caption + a small legend: a light-green swatch marks authorized days.
        cap_row = QHBoxLayout()
        cap_row.setSpacing(8)
        caption = QLabel("Current Schedule")
        caption.setObjectName("strip_caption")
        cap_row.addWidget(caption)
        swatch = QLabel()
        swatch.setObjectName("avail_legend_swatch")
        swatch.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        swatch.setFixedSize(12, 12)
        cap_row.addWidget(swatch)
        legend = QLabel("authorized day")
        legend.setObjectName("avail_legend")
        cap_row.addWidget(legend)
        cap_row.addStretch()
        outer.addLayout(cap_row)

        sched = current_schedule(self._availability, today)
        auth_days = authorized_weekdays(self._authorizations, today)
        days = [1, 2, 3, 4, 5] + [d for d in (6, 7) if d in sched or d in auth_days]

        row = QHBoxLayout()
        row.setSpacing(8)
        for d in days:
            windows = sched.get(d)
            authorized = d in auth_days
            cell = QWidget()
            cell.setObjectName("avail_day" if windows else "avail_day_empty")
            cell.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            # Authorized days are tinted light green (the time stays legible),
            # driven by this dynamic property in the QSS.
            cell.setProperty("authorized", bool(authorized))
            cell.setMinimumWidth(104)
            cv = QVBoxLayout(cell)
            cv.setContentsMargins(10, 7, 10, 7)
            cv.setSpacing(2)

            # Day name (centered); authorization is conveyed by the cell tint.
            name_row = QHBoxLayout()
            name_row.setContentsMargins(0, 0, 0, 0)
            name_row.setSpacing(4)
            name_row.addStretch()
            day_lbl = QLabel(WEEKDAY_NAMES[d])
            day_lbl.setObjectName("avail_day_name")
            name_row.addWidget(day_lbl)
            name_row.addStretch()
            cv.addLayout(name_row)
            cell.setToolTip("Authorized day" if authorized
                            else "Not authorized under the current authorization")
            for s, e in (windows or [(None, None)]):
                t_lbl = QLabel(format_avail_window(s, e) if windows else "—")
                t_lbl.setObjectName("avail_day_time" if windows else "avail_day_dash")
                t_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                cv.addWidget(t_lbl)
            row.addWidget(cell)
        row.addStretch()
        outer.addLayout(row)
        return box

    def _make_hha_note_card(self):
        """Info card beside the availability table showing Contacts.[HHA], so
        schedule edits can be made against the HHA constraints without leaving
        the tab. None when the member has no HHA text."""
        from PyQt6.QtWidgets import QFrame
        from gui.theme import current_tokens
        member = self.__dict__.get("_member") or {}
        text = (member.get("hha") or "").strip()
        if not text:
            return None
        t = current_tokens()
        card = QFrame()
        card.setObjectName("hha_note_card")
        card.setStyleSheet(
            f"#hha_note_card {{ background: {t['accent_bg']}; "
            f"border: 1px solid {t['accent']}; border-radius: 7px; }}")
        card.setMinimumWidth(260)
        card.setMaximumWidth(400)
        row = QHBoxLayout(card)
        row.setContentsMargins(16, 14, 16, 14)
        row.setSpacing(11)
        icon = QLabel("i")
        icon.setFixedSize(18, 18)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(
            f"background: {t['accent']}; color: white; border-radius: 9px; "
            f"font-size: 12px; font-weight: 700;")
        row.addWidget(icon, alignment=Qt.AlignmentFlag.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(5)
        title = QLabel("HHA Note")
        title.setStyleSheet(
            f"color: {t['accent_text']}; font-size: 13px; font-weight: 700; "
            f"background: transparent; border: none;")
        col.addWidget(title)
        body = QLabel(text)
        body.setWordWrap(True)
        body.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        body.setStyleSheet(
            f"color: {t['accent_text']}; font-size: 13px; "
            f"background: transparent; border: none;")
        col.addWidget(body)
        row.addLayout(col, 1)
        return card

    def _make_avail_tab(self) -> QWidget:
        from datetime import date
        from PyQt6.QtWidgets import (
            QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView,
            QSizePolicy,
        )
        from PyQt6.QtGui import QColor
        from gui.theme import current_tokens
        day_names = WEEKDAY_NAMES
        today = date.today()

        # Same set the Current Schedule strip tints, so the strip and the rows
        # below it can never disagree about which days are authorized. Empty
        # when no auth is in effect, which simply leaves every row untinted.
        auth_days = authorized_weekdays(self._authorizations, today)
        auth_tint = QColor(current_tokens()["success_bg"])

        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(12)

        layout.addWidget(self._make_current_schedule_strip(today))

        # Expired rows (e.g. a window capped when a scheduled change took
        # effect) stay in the database as history but are hidden here: the
        # table shows only what's in effect now or queued for later.
        visible = [a for a in sort_avail_for_table(self._availability, today)
                   if avail_status(a, today) != "expired"]

        # Trailing "" spacer column soaks up the leftover width as a grayed strip.
        columns = ["ID", "Day", "Start", "End", "Effective From", "Effective To",
                   "Status", "Action", ""]
        SPACER_COL = len(columns) - 1
        table = QTableWidget(len(visible), len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        hdr = table.horizontalHeader()
        hdr.setStretchLastSection(False)
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(SPACER_COL, QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)
        ROW_H = 40                    # roomier rows; pills uncramped
        table.verticalHeader().setDefaultSectionSize(ROW_H)

        status_chips = []
        edit_btns = []
        row_statuses = []
        for r, a in enumerate(visible):
            status = avail_status(a, today)
            row_statuses.append(status)
            eff_end = a.get("effective_end_date")

            table.setItem(r, 0, QTableWidgetItem(str(a["id"])))
            table.setItem(r, 1, QTableWidgetItem(
                day_names.get(a["day_of_week"], str(a["day_of_week"]))))
            table.setItem(r, 2, QTableWidgetItem(a["avail_start"] or "—"))
            table.setItem(r, 3, QTableWidgetItem(a["avail_end"] or "—"))
            table.setItem(r, 4, QTableWidgetItem(str(a["effective_start_date"])))
            table.setItem(r, 5, QTableWidgetItem(str(eff_end) if eff_end else "—"))

            # Status column: Active is plain text (a pill on every row drew the
            # eye too much); Upcoming (a scheduled change) keeps its amber pill
            # so the exception stands out. Expired rows are filtered out above.
            if status == "active":
                active_item = QTableWidgetItem("Active")
                active_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(r, 6, active_item)
            else:
                chip = QLabel("Upcoming")
                chip.setObjectName("upcoming_chip")
                status_chips.append(chip)
                table.setCellWidget(r, 6, _centered_cell(chip))

            btn = QPushButton("Edit")
            btn.setObjectName("btn_edit")
            btn.clicked.connect(lambda _=False, av=a: self._edit_avail(av))
            edit_btns.append(btn)
            # Centered at its natural width (like the Upcoming chip) rather than
            # filling the cell, so the authorized-day tint shows around it. A
            # button's height hint is taller than a pill's and the cell is only
            # ~27px, so it needs the tighter inset to fit without being clipped.
            table.setCellWidget(r, 7, _centered_cell(btn, vmargin=2))

            spacer = QTableWidgetItem("")
            spacer.setFlags(Qt.ItemFlag.NoItemFlags)
            spacer.setBackground(QColor(120, 124, 140, 18))
            table.setItem(r, SPACER_COL, spacer)

            # Authorized days get a light-green band across the whole row (the
            # tint the strip's legend swatch advertises). Status and Action hold
            # cell widgets, not items, so they need an empty backing item to
            # paint under — widgets are transparent and draw on top of it. The
            # trailing spacer keeps its own gray. Selection still wins: the QSS
            # gives QTableWidget::item:selected its own background.
            if a["day_of_week"] in auth_days:
                for c in range(SPACER_COL):
                    it = table.item(r, c)
                    if it is None:
                        it = QTableWidgetItem("")
                        it.setFlags(Qt.ItemFlag.NoItemFlags)
                        table.setItem(r, c, it)
                    it.setBackground(auth_tint)
                table.item(r, 1).setToolTip("Authorized day")

        _fit_pill_column(table, 6, status_chips, floor=96)
        # Action gets a bit more air than ResizeToContents' tight hug around
        # the Edit buttons.
        edit_w = max((b.sizeHint().width() for b in edit_btns), default=0)
        hdr.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(7, max(edit_w + 2 * _PILL_CELL_HMARGIN + 24, 116))

        self._apply_id_column(table)
        set_table_empty_state(
            table,
            "No weekly availability yet — use Scheduled Changes to set it up.")
        self._avail_table = table

        # This tab uses scheduled changes instead of a raw "+ Add": the Scheduled
        # Changes button is the primary (green) action, top-right in the Add slot.
        n_pending = len(pending_changes(self._availability, today))
        btn_sched = QPushButton(
            f"Scheduled Changes ({n_pending})" if n_pending else "Scheduled Changes")
        btn_sched.setObjectName("btn_row_add")
        btn_sched.setToolTip(
            "Review and manage availability changes queued to take effect later")
        btn_sched.clicked.connect(self._open_scheduled_changes)
        btn_del = QPushButton("Delete Selected")
        btn_del.clicked.connect(lambda: self._delete_avail(table))
        # Only Upcoming rows (queued changes) may be deleted: active and expired
        # rows are the schedule history the calendar depends on.
        btn_del.setObjectName("btn_row_delete")
        btn_del.setToolTip("Only Upcoming (not-yet-effective) rows can be deleted")

        def _sync_delete():
            rows = [ix.row() for ix in table.selectionModel().selectedRows()]
            btn_del.setEnabled(bool(rows) and all(
                r < len(row_statuses) and row_statuses[r] == "upcoming"
                for r in rows))
        table.itemSelectionChanged.connect(_sync_delete)
        _sync_delete()

        layout.addLayout(self._add_bar(btn_sched))   # primary action at top-right
        # Table on the left; the HHA note card (when present) sits beside it so
        # times can be edited against the constraints written in Contacts.[HHA].
        body_row = QHBoxLayout()
        body_row.setSpacing(16)
        body_row.addWidget(table, 1)
        note_card = self._make_hha_note_card()
        if note_card is not None:
            body_row.addWidget(note_card, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addLayout(body_row)

        btn_row = QHBoxLayout()
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
        eff_start = DateLineEdit()
        eff_start.set_pydate(start_d)
        form.addRow("Effective From:", eff_start)

        end_row = QWidget()
        end_hl = QHBoxLayout(end_row)
        end_hl.setContentsMargins(0, 0, 0, 0)
        eff_end = DateLineEdit()
        ongoing = QCheckBox("Ongoing (no end date)")
        end_d = avail.get("effective_end_date")
        if end_d:
            eff_end.set_pydate(end_d)
        else:
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
            if not eff_start.flag_validity(required=True):
                QMessageBox.warning(dlg, "Validation",
                    "Enter a valid Effective From date (MM/DD/YYYY).")
                return
            es = eff_start.to_pydate()
            if not ongoing.isChecked() and not eff_end.flag_validity(required=True):
                QMessageBox.warning(dlg, "Validation",
                    "Enter a valid Effective To date, or check Ongoing.")
                return
            ee = None if ongoing.isChecked() else eff_end.to_pydate()
            if ee is not None and ee < es:
                QMessageBox.warning(dlg, "Validation",
                    "Effective To must be on or after Effective From.")
                return
            dlg.accept()
        btns.accepted.connect(on_accept)
        v.addWidget(btns)

        if not dlg.exec():
            return
        if not self._confirm_unauthorized_day({avail["day_of_week"]},
                                              "Save this availability"):
            return
        ts, te = editor.start_hhmm(), editor.end_hhmm()
        es = eff_start.to_pydate()
        ee = None if ongoing.isChecked() else eff_end.to_pydate()
        try:
            update_availability(avail["id"], ts, te, es, ee, self._db_path)
            self._availability = get_availability(self._center_id, self._db_path)
            self._refresh_tab(4, self._make_avail_tab())
            end_txt = ee.isoformat() if ee else "ongoing"
            self._log_event(
                "AVAIL",
                f"Availability edited: {day_name} {ts}–{te} "
                f"(eff {es.isoformat()} → {end_txt})")
        except Exception as exc:
            show_db_error(self, exc)

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

        from datetime import date
        start_row, start_edit, start_period = time_row("8:00", "AM")
        end_row, end_edit, end_period = time_row("4:00", "PM")
        eff_start = DateLineEdit()
        eff_start.set_pydate(date.today())

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
            if not eff_start.flag_validity(required=True):
                QMessageBox.warning(dlg, "Validation",
                    "Enter a valid Effective From date (MM/DD/YYYY).")
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
                    eff_start.to_pydate(), None, self._db_path,
                )
                self._availability = get_availability(self._center_id, self._db_path)
                self._refresh_tab(4, self._make_avail_tab())
                self._log_event("AVAIL", f"Availability added: {day_name} {ts}–{te}")
            except Exception as exc:
                show_db_error(self, exc)

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
                self._refresh_tab(4, self._make_avail_tab())
                if entry:
                    day = WEEKDAY_NAMES.get(entry["day_of_week"],
                                            str(entry["day_of_week"]))
                    self._log_event(
                        "AVAIL",
                        f"Availability deleted: {day} "
                        f"{entry['avail_start']}–{entry['avail_end']}")
            except Exception as exc:
                show_db_error(self, exc)

    # ── Scheduled availability changes (future-effective rows) ───────────────

    def _open_scheduled_changes(self):
        """A popup listing availability changes queued to take effect later, with
        add / edit / delete. Each is just a future-effective Availability row."""
        from datetime import date
        from PyQt6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
            QAbstractItemView, QHeaderView, QPushButton, QLabel, QWidget,
        )
        dlg = QDialog(self)
        dlg.setWindowTitle("Scheduled Availability Changes")
        dlg.resize(580, 380)
        v = QVBoxLayout(dlg)

        cap = QLabel("Changes queued to take effect on a future date. Each one "
                     "replaces that weekday's current window when its date arrives.")
        cap.setWordWrap(True)
        cap.setObjectName("field_label")
        v.addWidget(cap)

        table = QTableWidget(0, 4)
        table.setHorizontalHeaderLabels(
            ["Day", "New Window", "Effective From", "Action"])
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(36)
        hdr = table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        v.addWidget(table)

        empty = QLabel("No scheduled changes yet. Use “+ Schedule a change”.")
        empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty.setObjectName("field_label")
        v.addWidget(empty)

        def repopulate():
            rows = pending_changes(self._availability, date.today())
            table.setRowCount(len(rows))
            for r, a in enumerate(rows):
                day = WEEKDAY_NAMES.get(a["day_of_week"], str(a["day_of_week"]))
                table.setItem(r, 0, QTableWidgetItem(day))
                table.setItem(r, 1, QTableWidgetItem(format_avail_window(
                    a.get("avail_start") or "", a.get("avail_end") or "")))
                table.setItem(r, 2, QTableWidgetItem(str(a["effective_start_date"])))
                cellw = QWidget()
                hl = QHBoxLayout(cellw)
                hl.setContentsMargins(0, 0, 0, 0)
                hl.setSpacing(4)
                edit = QPushButton("✎")
                edit.setObjectName("btn_icon_edit")
                edit.setFixedWidth(28)
                edit.setToolTip("Edit this scheduled change")
                edit.clicked.connect(
                    lambda _=False, av=a: (self._edit_scheduled_change(av),
                                           repopulate()))
                dele = QPushButton("✕")
                dele.setObjectName("btn_icon_delete")
                dele.setFixedWidth(28)
                dele.setToolTip("Delete this scheduled change")
                dele.clicked.connect(
                    lambda _=False, av=a: (self._delete_scheduled_change(av),
                                           repopulate()))
                hl.addWidget(edit)
                hl.addWidget(dele)
                table.setCellWidget(r, 3, cellw)
            table.setVisible(bool(rows))
            empty.setVisible(not rows)

        repopulate()

        btns = QHBoxLayout()
        add = QPushButton("+ Schedule a change")
        add.setObjectName("btn_primary")
        add.clicked.connect(lambda: (self._add_scheduled_change(), repopulate()))
        close = QPushButton("Close")
        close.clicked.connect(dlg.accept)
        btns.addWidget(add)
        btns.addStretch()
        btns.addWidget(close)
        v.addLayout(btns)
        dlg.exec()

    def _schedule_change_form(self, existing: dict | None = None) -> dict | None:
        """Dedicated 'schedule a change' form: weekday, new window, future
        effective date. Returns {day, ts, te, eff} or None. When editing, the
        weekday is fixed (matching how a row's day is immutable elsewhere)."""
        from datetime import date, timedelta
        from PyQt6.QtWidgets import (
            QDialog, QFormLayout, QComboBox, QDialogButtonBox, QLabel,
        )
        from gui.time_range_editor import TimeRangeEditor

        dlg = QDialog(self)
        dlg.setWindowTitle("Edit Scheduled Change" if existing
                           else "Schedule a Change")
        form = QFormLayout(dlg)

        day_combo = QComboBox()
        for num, name in [(1, "Mon"), (2, "Tue"), (3, "Wed"), (4, "Thu"),
                          (5, "Fri"), (6, "Sat"), (7, "Sun")]:
            day_combo.addItem(name, num)
        editor = TimeRangeEditor()
        tomorrow = date.today() + timedelta(days=1)
        eff = DateLineEdit(minimum=tomorrow)

        if existing:
            idx = day_combo.findData(existing["day_of_week"])
            if idx >= 0:
                day_combo.setCurrentIndex(idx)
            day_combo.setEnabled(False)   # weekday is fixed when editing
            editor.set_window(existing.get("avail_start") or "08:00",
                              existing.get("avail_end") or "16:00")
            eff.set_pydate(existing["effective_start_date"])
        else:
            editor.set_window("08:00", "16:00")
            eff.set_pydate(tomorrow)

        form.addRow("Weekday:", day_combo)
        form.addRow("New Window:", editor)
        form.addRow("Effective From:", eff)
        hint = QLabel("Takes effect on this date and replaces the current window "
                      "for that weekday.")
        hint.setWordWrap(True)
        hint.setObjectName("field_label")
        form.addRow(hint)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.rejected.connect(dlg.reject)

        def on_accept():
            if not eff.flag_validity(required=True) or eff.to_pydate() <= date.today():
                set_widget_error(eff, True)
                QMessageBox.warning(dlg, "Validation",
                    "Enter a valid future Effective From date (MM/DD/YYYY).")
                return
            dlg.accept()
        btns.accepted.connect(on_accept)
        form.addRow(btns)

        if not dlg.exec():
            return None
        return {"day": day_combo.currentData(),
                "ts": editor.start_hhmm(), "te": editor.end_hhmm(),
                "eff": eff.to_pydate()}

    def _add_scheduled_change(self):
        from datetime import timedelta
        from db.members import insert_availability, update_availability
        from monthly_schedule.db import get_availability

        result = self._schedule_change_form()
        if not result:
            return
        day, ts, te, eff = result["day"], result["ts"], result["te"], result["eff"]
        if not self._confirm_unauthorized_day({day}, "Schedule this change"):
            return
        try:
            # Cap the current window for that weekday so it ends the day before
            # the change starts (the change becomes the new ongoing window).
            pred = avail_to_cap(self._availability, day, eff)
            if pred is not None:
                update_availability(
                    pred["id"], pred["avail_start"], pred["avail_end"],
                    pred["effective_start_date"], eff - timedelta(days=1),
                    self._db_path)
            insert_availability(self._center_id, day, ts, te, eff, None,
                                self._db_path)
            self._availability = get_availability(self._center_id, self._db_path)
            self._refresh_tab(4, self._make_avail_tab())
            day_name = WEEKDAY_NAMES.get(day, str(day))
            self._log_event("AVAIL", f"Scheduled change: {day_name} → {ts}–{te} "
                            f"effective {eff.isoformat()}")
        except Exception as exc:
            show_db_error(self, exc)

    def _edit_scheduled_change(self, entry: dict):
        from datetime import timedelta
        from db.members import update_availability
        from monthly_schedule.db import get_availability

        result = self._schedule_change_form(existing=entry)
        if not result:
            return
        day, ts, te, eff = result["day"], result["ts"], result["te"], result["eff"]
        if not self._confirm_unauthorized_day({day}, "Save this change"):
            return
        try:
            # Re-extend the predecessor capped for the old date, then re-cap for
            # the new date — so moving the change date keeps the hand-off clean.
            pred_old = avail_to_restore(self._availability, entry["day_of_week"],
                                        entry["effective_start_date"])
            if pred_old is not None:
                update_availability(
                    pred_old["id"], pred_old["avail_start"], pred_old["avail_end"],
                    pred_old["effective_start_date"], entry.get("effective_end_date"),
                    self._db_path)
            update_availability(entry["id"], ts, te, eff, None, self._db_path)
            self._availability = get_availability(self._center_id, self._db_path)
            pred_new = avail_to_cap(self._availability, day, eff)
            if pred_new is not None and pred_new["id"] != entry["id"]:
                update_availability(
                    pred_new["id"], pred_new["avail_start"], pred_new["avail_end"],
                    pred_new["effective_start_date"], eff - timedelta(days=1),
                    self._db_path)
            self._availability = get_availability(self._center_id, self._db_path)
            self._refresh_tab(4, self._make_avail_tab())
            day_name = WEEKDAY_NAMES.get(day, str(day))
            self._log_event("AVAIL", f"Scheduled change updated: {day_name} → "
                            f"{ts}–{te} effective {eff.isoformat()}")
        except Exception as exc:
            show_db_error(self, exc)

    def _delete_scheduled_change(self, entry: dict):
        from db.members import delete_availability, update_availability
        from monthly_schedule.db import get_availability

        day_name = WEEKDAY_NAMES.get(entry["day_of_week"], str(entry["day_of_week"]))
        if QMessageBox.question(
                self, "Confirm",
                f"Cancel the scheduled change for {day_name} effective "
                f"{entry['effective_start_date']}?") \
                != QMessageBox.StandardButton.Yes:
            return
        try:
            # Re-extend the capped predecessor over the gap the change leaves.
            pred = avail_to_restore(self._availability, entry["day_of_week"],
                                    entry["effective_start_date"])
            if pred is not None:
                update_availability(
                    pred["id"], pred["avail_start"], pred["avail_end"],
                    pred["effective_start_date"], entry.get("effective_end_date"),
                    self._db_path)
            delete_availability(entry["id"], self._db_path)
            self._availability = get_availability(self._center_id, self._db_path)
            self._refresh_tab(4, self._make_avail_tab())
            self._log_event("AVAIL", f"Scheduled change canceled: {day_name} "
                            f"effective {entry['effective_start_date']}")
        except Exception as exc:
            show_db_error(self, exc)

    # ── Unavailable Times tab (one-off) ──────────────────────────────────────

    def _make_unavailable_tab(self) -> QWidget:
        from PyQt6.QtWidgets import (
            QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView,
        )
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 12, 0, 0)

        caption = QLabel(
            "Date-specific availability overrides (times the member is unavailable).")
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

        self._apply_id_column(table)
        set_table_empty_state(
            table,
            "No overrides yet — click + Add to record a date-specific change.")
        self._unavail_table = table
        btn_add = QPushButton("+ Add")
        btn_add.clicked.connect(self._add_unavailable)
        btn_del = QPushButton("Delete Selected")
        btn_del.clicked.connect(lambda: self._delete_unavailable(table))
        self._style_crud_buttons(table, btn_add, btn_del)

        layout.addLayout(self._add_bar(btn_add))   # Add at top-right
        layout.addWidget(table)

        btn_row = QHBoxLayout()
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
        dlg.setWindowTitle("Edit Availability Override" if existing
                           else "Add Availability Override")
        form = QFormLayout(dlg)

        from datetime import date as _date
        date_edit = DateLineEdit()
        editor = TimeRangeEditor()
        notes_edit = QPlainTextEdit()
        notes_edit.setFixedHeight(60)

        if existing:
            date_edit.set_pydate(existing.get("date") or _date.today())
            editor.set_window(existing.get("avail_start") or "09:00",
                              existing.get("avail_end") or "12:00")
            notes_edit.setPlainText(existing.get("notes", "") or "")
        else:
            date_edit.set_pydate(_date.today())
            editor.set_window("09:00", "12:00")

        form.addRow("Date:", date_edit)
        form.addRow("Time:", editor)
        form.addRow("Notes:", notes_edit)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)

        def on_accept():
            if not date_edit.flag_validity(required=True):
                QMessageBox.warning(dlg, "Validation",
                    "Enter a valid Date (MM/DD/YYYY).")
                return
            dlg.accept()
        btns.accepted.connect(on_accept)

        if not dlg.exec():
            return None
        return {
            "date": date_edit.to_pydate(),
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
        if not self._confirm_unauthorized_day(
                {result["date"].isoweekday()}, "Add this override"):
            return
        try:
            insert_one_off_availability(
                self._center_id, result["date"], result["avail_start"],
                result["avail_end"], result["notes"], self._db_path,
            )
            self._one_off = get_one_off_availability(self._center_id, self._db_path)
            self._refresh_tab(5, self._make_unavailable_tab())
            self._log_event(
                "AVAIL",
                f"Availability override added: {result['date']} "
                f"{result['avail_start']}–{result['avail_end']}")
        except Exception as exc:
            show_db_error(self, exc)

    def _edit_unavailable(self, entry: dict):
        from db.members import (
            update_one_off_availability, get_one_off_availability,
        )
        result = self._open_one_off_dialog(existing=entry)
        if not result:
            return
        if not self._confirm_unauthorized_day(
                {result["date"].isoweekday()}, "Save this override"):
            return
        try:
            update_one_off_availability(
                entry["id"], result["date"], result["avail_start"],
                result["avail_end"], result["notes"], self._db_path,
            )
            self._one_off = get_one_off_availability(self._center_id, self._db_path)
            self._refresh_tab(5, self._make_unavailable_tab())
            self._log_event(
                "AVAIL",
                f"Availability override edited: {result['date']} "
                f"{result['avail_start']}–{result['avail_end']}")
        except Exception as exc:
            show_db_error(self, exc)

    def _delete_unavailable(self, table):
        row = table.currentRow()
        if row < 0:
            return
        record_id = int(table.item(row, 0).text())
        if QMessageBox.question(self, "Confirm", "Delete this availability override?") \
                == QMessageBox.StandardButton.Yes:
            from db.members import (
                delete_one_off_availability, get_one_off_availability,
            )
            entry = next((a for a in self._one_off if a["id"] == record_id), None)
            try:
                delete_one_off_availability(record_id, self._db_path)
                self._one_off = get_one_off_availability(
                    self._center_id, self._db_path)
                self._refresh_tab(5, self._make_unavailable_tab())
                if entry:
                    self._log_event(
                        "AVAIL",
                        f"Availability override deleted: {entry['date']} "
                        f"{entry['avail_start']}–{entry['avail_end']}")
            except Exception as exc:
                show_db_error(self, exc)

    # ── Absences tab ───────────────────────────────────────────────────────

    def _make_absences_tab(self) -> QWidget:
        from PyQt6.QtWidgets import (
            QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView,
        )
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 12, 0, 0)

        columns = ["ID", "Leave Type", "Start", "End", "Notes", "Action"]
        table = QTableWidget(len(self._absences), len(columns))
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

        for r, a in enumerate(self._absences):
            table.setItem(r, 0, QTableWidgetItem(str(a["id"])))
            table.setItem(r, 1, QTableWidgetItem(a["leave_type"] or ""))
            table.setItem(r, 2, QTableWidgetItem(str(a["start_date"])))
            table.setItem(r, 3, QTableWidgetItem(str(a["end_date"])))
            table.setItem(r, 4, QTableWidgetItem(a.get("notes", "") or ""))
            btn = QPushButton("Edit")
            btn.setObjectName("btn_edit")
            btn.clicked.connect(lambda _=False, ab=a: self._edit_absence(ab))
            table.setCellWidget(r, 5, btn)

        self._apply_id_column(table)
        set_table_empty_state(table, "Nothing here yet — click + Add.")
        self._abs_table = table

        btn_add = QPushButton("+ Add")
        btn_add.clicked.connect(self._add_absence)
        btn_del = QPushButton("Delete Selected")
        btn_del.clicked.connect(lambda: self._delete_absence(table))
        self._style_crud_buttons(table, btn_add, btn_del)

        layout.addLayout(self._add_bar(btn_add))   # Add at top-right
        layout.addWidget(table)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(btn_del)
        layout.addLayout(btn_row)
        return w

    def _open_absence_dialog(self, existing: dict | None = None):
        """Add/Edit dialog: leave type + date range + notes. Returns a dict
        with leave_type, start, end, notes — or None if cancelled."""
        from PyQt6.QtWidgets import (
            QDialog, QFormLayout, QComboBox, QPlainTextEdit, QDialogButtonBox,
        )
        from datetime import date
        from db.members import LEAVE_TYPES

        dlg = QDialog(self)
        dlg.setWindowTitle("Edit Absence" if existing else "Add Absence")
        form = QFormLayout(dlg)

        leave_combo = QComboBox()
        leave_combo.addItems(LEAVE_TYPES)
        start = DateLineEdit()
        end = DateLineEdit()
        notes_edit = QPlainTextEdit()
        notes_edit.setFixedHeight(60)
        if existing:
            idx = leave_combo.findText(existing.get("leave_type") or "")
            if idx >= 0:
                leave_combo.setCurrentIndex(idx)
            start.set_pydate(existing.get("start_date") or date.today())
            end.set_pydate(existing.get("end_date") or date.today())
            notes_edit.setPlainText(existing.get("notes", "") or "")
        else:
            start.set_pydate(date.today())
            end.set_pydate(date.today())

        form.addRow("Leave Type:", leave_combo)
        form.addRow("Start Date:", start)
        form.addRow("End Date:", end)
        form.addRow("Notes:", notes_edit)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)

        def on_accept():
            ok = start.flag_validity(required=True)
            ok = end.flag_validity(required=True) and ok
            if not ok:
                QMessageBox.warning(dlg, "Validation",
                    "Enter valid Start and End dates (MM/DD/YYYY).")
                return
            if end.to_pydate() < start.to_pydate():
                QMessageBox.warning(dlg, "Validation",
                    "End Date must be on or after Start Date.")
                return
            dlg.accept()
        btns.accepted.connect(on_accept)

        if not dlg.exec():
            return None
        return {
            "leave_type": leave_combo.currentText(),
            "start": start.to_pydate(),
            "end": end.to_pydate(),
            "notes": notes_edit.toPlainText().strip(),
        }

    def _add_absence(self):
        from db.members import insert_absence, get_absences

        result = self._open_absence_dialog()
        if not result:
            return
        lt, s, e = result["leave_type"], result["start"], result["end"]
        if not self._confirm_unauthorized_day(
                weekdays_in_range(s, e), "Add this absence"):
            return
        try:
            insert_absence(self._center_id, lt, s, e, result["notes"],
                           self._db_path)
            self._absences = get_absences(self._center_id, self._db_path)
            self._refresh_tab(6, self._make_absences_tab())
            self._log_event("ABS", f"Absence added: {lt} · {s} – {e}")
        except Exception as exc:
            show_db_error(self, exc)

    def _edit_absence(self, entry: dict):
        from db.members import update_absence, get_absences

        result = self._open_absence_dialog(existing=entry)
        if not result:
            return
        lt, s, e = result["leave_type"], result["start"], result["end"]
        if not self._confirm_unauthorized_day(
                weekdays_in_range(s, e), "Save this absence"):
            return
        try:
            update_absence(entry["id"], lt, s, e, result["notes"],
                           self._db_path)
            self._absences = get_absences(self._center_id, self._db_path)
            self._refresh_tab(6, self._make_absences_tab())
            self._log_event("ABS", f"Absence edited: {lt} · {s} – {e}")
        except Exception as exc:
            show_db_error(self, exc)

    def _delete_absence(self, table):
        row = table.currentRow()
        if row < 0:
            return
        record_id = int(table.item(row, 0).text())
        if QMessageBox.question(self, "Confirm", "Delete this absence?") \
                == QMessageBox.StandardButton.Yes:
            from db.members import delete_absence, get_absences
            entry = next((a for a in self._absences if a["id"] == record_id), None)
            try:
                delete_absence(record_id, self._db_path)
                self._absences = get_absences(self._center_id, self._db_path)
                self._refresh_tab(6, self._make_absences_tab())
                if entry:
                    self._log_event(
                        "ABS",
                        f"Absence deleted: {entry['leave_type']} "
                        f"{entry['start_date']} – {entry['end_date']}")
            except Exception as exc:
                show_db_error(self, exc)
