"""Placement for toolbar popups (Bookmarks, Notifications)."""
from PyQt6.QtWidgets import QApplication

# Gap between the anchor's bottom edge and the popup (logical px; not scaled —
# it holds no text).
_GAP = 6


def place_popup_under(popup, anchor) -> None:
    """Move an already-sized `popup` under `anchor`, right-aligned, and keep
    it on screen.

    At Large / Extra Large text the toolbar buttons overflow into the "…"
    menu; an overflowed button is hidden and reports no on-screen position
    (its geometry is the default 640x480 at the origin), so the popup would
    land off-screen. Such a button is anchored under its toolbar instead. The
    result is then clamped into the work area of the screen it lands on, so a
    tall popup never runs past the bottom edge."""
    ref = anchor
    if not anchor.isVisible() and anchor.parentWidget() is not None:
        ref = anchor.parentWidget()
    corner = ref.mapToGlobal(ref.rect().bottomRight())
    x = corner.x() - popup.width()
    y = corner.y() + _GAP
    screen = QApplication.screenAt(corner) or QApplication.primaryScreen()
    if screen is not None:
        avail = screen.availableGeometry()
        x = max(avail.left(), min(x, avail.right() - popup.width() + 1))
        y = max(avail.top(), min(y, avail.bottom() - popup.height() + 1))
    popup.move(x, y)
