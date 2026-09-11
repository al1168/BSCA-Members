"""The "Confirm Changes" dialog shown before an Info-tab save.

Changes are laid out side by side — Field | ORIGINAL → MODIFIED — instead of
one "Label: old → new" line per field, so a long value (Notes especially)
widens the row rather than stacking the dialog taller than the screen. The
table scrolls inside a capped height, so the Save and Cancel buttons are
always visible. The two value columns are tinted (original red, modified
green) and captioned so it is obvious at a glance which side is which.
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QScrollArea,
    QWidget, QPushButton, QFrame,
)
from gui.theme import px

_ORIGINAL_CAPTION = "ORIGINAL"
_MODIFIED_CAPTION = "MODIFIED"
_EMPTY = "(empty)"


def _value_label(text: str, bg: str, fg: str) -> QLabel:
    lbl = QLabel(text or _EMPTY)
    lbl.setWordWrap(True)
    lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
    lbl.setStyleSheet(
        f"background-color:{bg}; color:{fg}; border-radius:6px; "
        f"padding:6px 8px; font-size:{px(13)}px;")
    if not text:
        lbl.setProperty("empty", True)
    return lbl


class ConfirmChangesDialog(QDialog):
    """rows: (field label, original value, modified value) — display-ready
    strings, blanks shown as '(empty)'. exec() returns Accepted on Save."""

    def __init__(self, member_name: str, rows: list[tuple[str, str, str]],
                 parent=None):
        super().__init__(parent)
        from gui.theme import current_tokens
        t = current_tokens()
        self.setWindowTitle("Confirm Changes")
        self.setMinimumWidth(760)
        self._rows = list(rows)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        heading = QLabel(f"Confirm changes for {member_name}?")
        heading.setStyleSheet(f"font-size:{px(15)}px; font-weight:600;")
        layout.addWidget(heading)

        # ── column captions ─────────────────────────────────────────────
        captions = QGridLayout()
        captions.setHorizontalSpacing(8)
        self._orig_caption = QLabel(_ORIGINAL_CAPTION)
        self._orig_caption.setObjectName("confirm_original_caption")
        self._orig_caption.setStyleSheet(
            f"color:{t['error_text']}; font-weight:700; letter-spacing:1px;")
        self._mod_caption = QLabel(_MODIFIED_CAPTION)
        self._mod_caption.setObjectName("confirm_modified_caption")
        self._mod_caption.setStyleSheet(
            f"color:{t['success']}; font-weight:700; letter-spacing:1px;")
        field_caption = QLabel("Field")
        field_caption.setStyleSheet(f"color:{t['text2']}; font-weight:600;")
        captions.addWidget(field_caption, 0, 0)
        captions.addWidget(self._orig_caption, 0, 1)
        captions.addWidget(QLabel(""), 0, 2)
        captions.addWidget(self._mod_caption, 0, 3)
        self._set_column_stretch(captions)
        layout.addLayout(captions)

        rule = QFrame()
        rule.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(rule)

        # ── one row per changed field, inside a capped-height scroller ──
        body = QWidget()
        grid = QGridLayout(body)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)
        grid.setContentsMargins(0, 0, 0, 0)
        self._value_labels: list[tuple[QLabel, QLabel]] = []
        for i, (label, old, new) in enumerate(self._rows):
            name = QLabel(label)
            name.setStyleSheet("font-weight:600;")
            name.setAlignment(Qt.AlignmentFlag.AlignLeft
                              | Qt.AlignmentFlag.AlignTop)
            orig = _value_label(old, t["error_bg"], t["error_text"])
            arrow = QLabel("→")
            arrow.setStyleSheet(f"color:{t['text2']}; font-size:{px(18)}px;")
            arrow.setAlignment(Qt.AlignmentFlag.AlignHCenter
                               | Qt.AlignmentFlag.AlignTop)
            mod = _value_label(new, t["success_bg"], t["success"])
            grid.addWidget(name, i, 0)
            grid.addWidget(orig, i, 1)
            grid.addWidget(arrow, i, 2)
            grid.addWidget(mod, i, 3)
            self._value_labels.append((orig, mod))
        grid.setRowStretch(len(self._rows), 1)
        self._set_column_stretch(grid)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setWidget(body)
        layout.addWidget(self._scroll, 1)

        # ── buttons, always visible under the scroller ──────────────────
        buttons = QHBoxLayout()
        buttons.addStretch()
        self._btn_cancel = QPushButton("Cancel")
        self._btn_cancel.clicked.connect(self.reject)
        self._btn_save = QPushButton("Save")
        self._btn_save.setObjectName("btn_row_add")
        self._btn_save.setDefault(True)
        self._btn_save.clicked.connect(self.accept)
        buttons.addWidget(self._btn_cancel)
        buttons.addWidget(self._btn_save)
        layout.addLayout(buttons)

        self._cap_height()
        # Open tall enough to show everything up to the cap; beyond that the
        # table scrolls.
        wanted = body.sizeHint().height() + 150
        self.resize(self.minimumWidth(), min(wanted, self.maximumHeight()))

    @staticmethod
    def _set_column_stretch(grid: QGridLayout) -> None:
        grid.setColumnStretch(0, 0)
        grid.setColumnMinimumWidth(0, 120)
        grid.setColumnStretch(1, 1)
        grid.setColumnMinimumWidth(2, 24)
        grid.setColumnStretch(3, 1)

    def _cap_height(self) -> None:
        """Never taller than ~70% of the screen: long Notes scroll inside the
        table instead of pushing the buttons off-screen."""
        from PyQt6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            self.setMaximumHeight(int(screen.availableGeometry().height() * 0.7))
