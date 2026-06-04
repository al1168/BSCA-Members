"""Time-range editor: a two-handle range slider synced with manual h:mm fields.

Pure helpers (minutes <-> 'HH:mm', clamp, snap, 12-hour formatting) are unit
tested; the RangeSlider/TimeRangeEditor widgets are verified manually.
"""

from PyQt6.QtWidgets import QWidget, QSizePolicy
from PyQt6.QtCore import Qt, pyqtSignal, QRectF
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QFont

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
        self.setMinimumHeight(60)
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
        w = max(self.width() - 2 * self._MARGIN, 1)
        return self._MARGIN, w

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
        cy = self._TRACK_Y + self._TRACK_H / 2

        # base track
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor("#2a2e3a")))
        p.drawRoundedRect(QRectF(left, self._TRACK_Y, w, self._TRACK_H), 4, 4)

        # filled band
        xs, xe = self._x_for(self._start), self._x_for(self._end)
        p.setBrush(QBrush(QColor("#5b7cf4")))
        p.drawRoundedRect(QRectF(xs, self._TRACK_Y, max(xe - xs, 1), self._TRACK_H), 4, 4)

        # hour ticks + labels (8a..4p)
        p.setFont(QFont("Segoe UI", 7))
        p.setPen(QPen(QColor("#757a98")))
        for hour in range(8, 17):
            mx = self._x_for(hour * 60)
            p.drawLine(int(mx), self._TRACK_Y + self._TRACK_H + 2,
                       int(mx), self._TRACK_Y + self._TRACK_H + 6)
            label = f"{hour}a" if hour < 12 else ("12p" if hour == 12 else f"{hour - 12}p")
            p.drawText(QRectF(mx - 12, self._TRACK_Y + self._TRACK_H + 7, 24, 12),
                       Qt.AlignmentFlag.AlignHCenter, label)

        # handles
        p.setPen(QPen(QColor("#5b7cf4"), 2))
        p.setBrush(QBrush(QColor("#ffffff")))
        for mx in (xs, xe):
            p.drawEllipse(QRectF(mx - self._HANDLE_R, cy - self._HANDLE_R,
                                 self._HANDLE_R * 2, self._HANDLE_R * 2))
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
