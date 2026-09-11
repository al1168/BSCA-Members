"""Time-range editor: a two-handle range slider synced with manual h:mm fields.

Pure helpers (minutes <-> 'HH:mm', clamp, snap, 12-hour formatting) are unit
tested; the RangeSlider/TimeRangeEditor widgets are verified manually.
"""

from PyQt6.QtWidgets import (
    QWidget, QSizePolicy, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QComboBox, QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, QRectF
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QFont, QFontMetrics

from gui.theme import px

MIN_MINUTES = 480   # 08:00
MAX_MINUTES = 960   # 16:00
SNAP_MINUTES = 15
MIN_WINDOW = 15


def hhmm_to_minutes(hhmm: str) -> int:
    """'08:00' -> 480. Raises ValueError on malformed input."""
    parts = hhmm.strip().split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid time: {hhmm!r}")
    return int(parts[0]) * 60 + int(parts[1])


def minutes_to_hhmm(m: int) -> str:
    """480 -> '08:00' (24-hour, zero-padded)."""
    return f"{m // 60:02d}:{m % 60:02d}"


def clamp_minutes(m: int) -> int:
    """Clamp to [MIN_MINUTES, MAX_MINUTES]."""
    return max(MIN_MINUTES, min(MAX_MINUTES, m))


def snap_minutes(m: int) -> int:
    """Round to the nearest SNAP_MINUTES, then clamp to bounds."""
    return clamp_minutes(round(m / SNAP_MINUTES) * SNAP_MINUTES)


def minutes_to_12h(m: int) -> tuple[str, str]:
    """480 -> ('8:00','AM'); 487 -> ('8:07','AM'); 720 -> ('12:00','PM')."""
    h24, mm = divmod(m, 60)
    period = "AM" if h24 < 12 else "PM"
    h12 = h24 % 12 or 12
    return f"{h12}:{mm:02d}", period


class RangeSlider(QWidget):
    """A horizontal two-handle range slider over MIN_MINUTES..MAX_MINUTES.

    Dragging a handle snaps to SNAP_MINUTES and cannot cross the other handle
    (min gap MIN_WINDOW). Emits windowChanged(start_min, end_min) while dragging.
    set_window() accepts any minute (no snap) so typed values render off-tick.
    """
    windowChanged = pyqtSignal(int, int)

    _MARGIN = 18      # px padding so handles aren't clipped
    _TRACK_Y = 22     # track top
    _TRACK_H = 8
    _HANDLE_R = 9

    def __init__(self, parent=None):
        super().__init__(parent)
        self._start = MIN_MINUTES
        self._end = MAX_MINUTES
        self._drag = None  # 'start' | 'end' | None
        # Painted geometry scales with the text size (class constants are the
        # Normal-scale values; px() must run at construction, not import).
        self._margin = px(self._MARGIN)      # keeps scaled handles unclipped at the ends
        self._track_y = px(self._TRACK_Y)
        self._track_h = px(self._TRACK_H)
        self._handle_r = px(self._HANDLE_R)
        # Ensure the tick labels below the track still fit inside the minimum
        # height at large scales.
        fm = QFontMetrics(QFont("Segoe UI", px(7)))
        needed = self._track_y + self._track_h + px(7) + fm.height() + px(4)
        self.setMinimumHeight(max(px(60), needed))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    # ── state ────────────────────────────────────────────────────────────
    def set_window(self, start_min: int, end_min: int) -> None:
        start = clamp_minutes(int(start_min))
        end = clamp_minutes(int(end_min))
        if end < start + MIN_WINDOW:
            end = clamp_minutes(start + MIN_WINDOW)
        self._start, self._end = start, end
        self.update()

    def window(self) -> tuple[int, int]:
        return self._start, self._end

    # ── geometry ─────────────────────────────────────────────────────────
    def _track_left_width(self):
        w = max(self.width() - 2 * self._margin, 1)
        return self._margin, w

    def _x_for(self, minutes: int) -> float:
        left, w = self._track_left_width()
        frac = (minutes - MIN_MINUTES) / (MAX_MINUTES - MIN_MINUTES)
        return left + frac * w

    def _minutes_for(self, x: float) -> int:
        left, w = self._track_left_width()
        frac = (x - left) / w
        return int(round(MIN_MINUTES + frac * (MAX_MINUTES - MIN_MINUTES)))

    # ── painting ─────────────────────────────────────────────────────────
    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        left, w = self._track_left_width()
        cy = self._track_y + self._track_h / 2

        # base track
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor("#2a2e3a")))
        p.drawRoundedRect(QRectF(left, self._track_y, w, self._track_h), 4, 4)

        # filled band
        xs, xe = self._x_for(self._start), self._x_for(self._end)
        p.setBrush(QBrush(QColor("#5b7cf4")))
        p.drawRoundedRect(QRectF(xs, self._track_y, max(xe - xs, 1), self._track_h), 4, 4)

        # hour ticks + labels (8a..4p)
        p.setFont(QFont("Segoe UI", px(7)))
        p.setPen(QPen(QColor("#757a98")))
        fm = p.fontMetrics()
        lw = fm.horizontalAdvance("12p") + px(6)
        for hour in range(8, 17):
            mx = self._x_for(hour * 60)
            p.drawLine(int(mx), self._track_y + self._track_h + px(2),
                       int(mx), self._track_y + self._track_h + px(6))
            label = f"{hour}a" if hour < 12 else ("12p" if hour == 12 else f"{hour - 12}p")
            p.drawText(QRectF(mx - lw / 2, self._track_y + self._track_h + px(7), lw, fm.height()),
                       Qt.AlignmentFlag.AlignHCenter, label)

        # handles
        p.setPen(QPen(QColor("#5b7cf4"), 2))
        p.setBrush(QBrush(QColor("#ffffff")))
        for mx in (xs, xe):
            p.drawEllipse(QRectF(mx - self._handle_r, cy - self._handle_r,
                                 self._handle_r * 2, self._handle_r * 2))
        p.end()

    # ── interaction ──────────────────────────────────────────────────────
    def mousePressEvent(self, ev):
        x = ev.position().x()
        self._drag = ("start" if abs(x - self._x_for(self._start))
                      <= abs(x - self._x_for(self._end)) else "end")
        self._drag_to(x)

    def mouseMoveEvent(self, ev):
        if self._drag:
            self._drag_to(ev.position().x())

    def mouseReleaseEvent(self, ev):
        self._drag = None

    def _drag_to(self, x: float) -> None:
        m = snap_minutes(self._minutes_for(x))
        if self._drag == "start":
            self._start = clamp_minutes(min(m, self._end - MIN_WINDOW))
        else:
            self._end = clamp_minutes(max(m, self._start + MIN_WINDOW))
        self.update()
        self.windowChanged.emit(self._start, self._end)

    def keyPressEvent(self, ev):
        step = SNAP_MINUTES
        if ev.key() == Qt.Key.Key_Left:
            self._end = clamp_minutes(max(self._end - step, self._start + MIN_WINDOW))
        elif ev.key() == Qt.Key.Key_Right:
            self._end = clamp_minutes(self._end + step)
        else:
            super().keyPressEvent(ev)
            return
        self.update()
        self.windowChanged.emit(self._start, self._end)


def _format_duration(minutes: int) -> str:
    h, m = divmod(minutes, 60)
    return f"{h}h {m}m"


class TimeRangeEditor(QWidget):
    """Range slider + manual Start/End (h:mm + AM/PM) kept in two-way sync.

    Drag snaps to 15 min; typing accepts any minute in 08:00-16:00 and clamps
    to bounds / enforces the 15-min minimum window. start_hhmm()/end_hhmm()
    return 24-hour 'HH:mm' for saving.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        from db.members import time_12h_to_24h  # reuse existing parser
        self._parse_12h = time_12h_to_24h
        self._start = MIN_MINUTES
        self._end = MAX_MINUTES

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._readout = QLabel()
        self._readout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._readout.setStyleSheet(f"font-size:{px(16)}px; font-weight:700;")
        layout.addWidget(self._readout)

        self._slider = RangeSlider()
        self._slider.windowChanged.connect(self._on_slider)
        layout.addWidget(self._slider)

        self._start_edit, self._start_period = self._time_field(layout, "Start")
        self._end_edit, self._end_period = self._time_field(layout, "End")

        self._refresh()

    def _time_field(self, layout, label):
        row = QHBoxLayout()
        row.addWidget(QLabel(f"{label}:"))
        edit = QLineEdit()
        edit.setPlaceholderText("h:mm")
        period = QComboBox()
        period.addItems(["AM", "PM"])
        row.addWidget(edit)
        row.addWidget(period)
        row.addStretch()
        layout.addLayout(row)
        commit = self._commit_start if label == "Start" else self._commit_end
        edit.editingFinished.connect(commit)
        period.currentIndexChanged.connect(commit)
        return edit, period

    # ── public API ───────────────────────────────────────────────────────
    def set_window(self, start_hhmm: str, end_hhmm: str) -> None:
        self._start = clamp_minutes(hhmm_to_minutes(start_hhmm))
        self._end = clamp_minutes(hhmm_to_minutes(end_hhmm))
        if self._end < self._start + MIN_WINDOW:
            self._end = clamp_minutes(self._start + MIN_WINDOW)
        self._refresh()

    def start_hhmm(self) -> str:
        return minutes_to_hhmm(self._start)

    def end_hhmm(self) -> str:
        return minutes_to_hhmm(self._end)

    # ── sync ─────────────────────────────────────────────────────────────
    def _on_slider(self, start_min: int, end_min: int) -> None:
        self._start, self._end = start_min, end_min
        self._refresh()

    def _commit_start(self) -> None:
        m = self._parse_field(self._start_edit, self._start_period)
        if m is None:
            return
        self._start = clamp_minutes(min(m, self._end - MIN_WINDOW))
        self._refresh()

    def _commit_end(self) -> None:
        m = self._parse_field(self._end_edit, self._end_period)
        if m is None:
            return
        self._end = clamp_minutes(max(m, self._start + MIN_WINDOW))
        self._refresh()

    def _parse_field(self, edit: QLineEdit, period: QComboBox):
        try:
            hhmm = self._parse_12h(edit.text(), period.currentText())
            return clamp_minutes(hhmm_to_minutes(hhmm))
        except ValueError:
            QMessageBox.warning(self, "Validation",
                "Enter times as h:mm with hour 1-12 and minute 00-59.")
            self._refresh()  # revert field to last valid value
            return None

    def _refresh(self) -> None:
        """Push current state to the slider, both fields, and the readout."""
        self._slider.set_window(self._start, self._end)
        st, sp = minutes_to_12h(self._start)
        et, ep = minutes_to_12h(self._end)
        for edit, period, text, per in (
            (self._start_edit, self._start_period, st, sp),
            (self._end_edit, self._end_period, et, ep),
        ):
            edit.blockSignals(True)
            period.blockSignals(True)
            edit.setText(text)
            period.setCurrentText(per)
            edit.blockSignals(False)
            period.blockSignals(False)
        self._readout.setText(
            f"{st} {sp}  –  {et} {ep}   ·   {_format_duration(self._end - self._start)}"
        )
