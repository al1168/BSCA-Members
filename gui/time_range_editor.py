"""Time-range editor: a two-handle range slider synced with manual h:mm fields.

Pure helpers (minutes <-> 'HH:mm', clamp, snap, 12-hour formatting) are unit
tested; the RangeSlider/TimeRangeEditor widgets are verified manually.
"""

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
