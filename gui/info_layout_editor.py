# gui/info_layout_editor.py
"""WYSIWYG editor for the customizable member Info tab.

Left: a live schematic preview of the layout (click a field or a section
header to select it). Right: a properties panel for the selection. All
edits go through the pure helpers in gui.info_layout on a deep copy; the
caller reads result_layout() only after the dialog is accepted.
"""
import copy

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout,
    QScrollArea, QPushButton, QFrame,
)

from gui.info_layout import (
    normalize, default_layout, placements, FIELD_LABELS_BY_KEY,
)
from gui.theme import current_tokens


class _ClickLabel(QLabel):
    """A label that emits clicked() on left press (preview cells/headers)."""

    clicked = pyqtSignal()

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(e)


class InfoLayoutEditor(QDialog):
    def __init__(self, layout_cfg, member, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Customize Info Tab")
        self.resize(980, 640)
        self._layout = normalize(copy.deepcopy(layout_cfg))
        self._member = member or {}
        self._selection = None          # ("field", key) | ("block", index)
        self._preview_cells = {}        # field key -> _ClickLabel

        root = QVBoxLayout(self)
        body = QHBoxLayout()
        root.addLayout(body, 1)

        self._preview_scroll = QScrollArea()
        self._preview_scroll.setWidgetResizable(True)
        body.addWidget(self._preview_scroll, 2)

        right = QVBoxLayout()
        self._props_host = QWidget()
        self._props_host.setMinimumWidth(280)
        QVBoxLayout(self._props_host)
        right.addWidget(self._props_host)
        right.addStretch()
        body.addLayout(right, 1)

        btn_row = QHBoxLayout()
        btn_reset = QPushButton("Reset to Default")
        btn_reset.clicked.connect(self._reset)
        btn_row.addWidget(btn_reset)
        btn_row.addStretch()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        btn_save = QPushButton("Save")
        btn_save.setObjectName("btn_save")
        btn_save.setDefault(True)
        btn_save.clicked.connect(self.accept)
        btn_row.addWidget(btn_save)
        root.addLayout(btn_row)

        self._rebuild_preview()
        self._rebuild_props()

    # ── API ────────────────────────────────────────────────────────────────

    def result_layout(self) -> dict:
        return normalize(self._layout)

    # ── state ──────────────────────────────────────────────────────────────

    def _select(self, selection):
        self._selection = selection
        self._rebuild_preview()
        self._rebuild_props()

    def _reset(self):
        self._layout = default_layout()
        self._selection = None
        self._rebuild_preview()
        self._rebuild_props()

    def _changed(self):
        """Re-render after any model mutation (wired up by the properties panel)."""
        self._rebuild_preview()

    # ── preview ────────────────────────────────────────────────────────────

    def _cell_css(self, cfg, selected):
        t = current_tokens()
        color = cfg.get("color", "none")
        bg = t.get("hl_" + color, "transparent") if color != "none" \
            else t["raised"]
        border = t["accent"] if selected else t["border"]
        weight = 800 if cfg.get("bold") else 600
        size = 15 if cfg.get("size") == "large" else 12
        opacity = "" if cfg.get("visible", True) else \
            f"color: {t['text4']};"
        return (f"background-color: {bg}; border: 2px solid {border}; "
                f"border-radius: 6px; padding: 6px; font-size: {size}px; "
                f"font-weight: {weight}; {opacity}")

    def _preview_value(self, key):
        v = self._member.get(key)
        s = str(v) if v not in (None, "") else "—"
        return s[:24]

    def _rebuild_preview(self):
        t = current_tokens()
        self._preview_cells = {}
        content = QWidget()
        grid = QGridLayout(content)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)
        for col in range(3):
            grid.setColumnStretch(col, 1)
        row = 0
        for bi, block in enumerate(self._layout["blocks"]):
            if block["type"] in ("schedule", "emergency"):
                name = ("Schedule card" if block["type"] == "schedule"
                        else "Emergency contacts")
                if not block.get("visible", True):
                    name += "  (hidden)"
                cell = _ClickLabel("▦  " + name)
                selected = self._selection == ("block", bi)
                border = t["accent"] if selected else t["border"]
                dim = "" if block.get("visible", True) \
                    else f"color: {t['text4']};"
                cell.setStyleSheet(
                    f"background-color: {t['surface']}; border: 2px "
                    f"dashed {border}; border-radius: 6px; padding: 10px; "
                    f"font-weight: 600; {dim}")
                cell.clicked.connect(
                    lambda b=bi: self._select(("block", b)))
                grid.addWidget(cell, row, 0, 1, 3)
                row += 1
                continue
            header = _ClickLabel(block["title"].upper())
            hsel = self._selection == ("block", bi)
            header.setStyleSheet(
                f"color: {t['accent_text']}; font-size: 11px; "
                f"font-weight: 700; padding: 6px 2px 2px 2px; "
                f"border: none; border-bottom: 2px solid "
                f"{t['accent'] if hsel else t['border_mid']};")
            header.clicked.connect(lambda b=bi: self._select(("block", b)))
            grid.addWidget(header, row, 0, 1, 3)
            row += 1
            base = row
            last = -1
            for cfg, frow, slot, span in placements(
                    block["fields"], include_hidden=True):
                key = cfg["key"]
                text = FIELD_LABELS_BY_KEY[key]
                if not cfg.get("visible", True):
                    text += "  (hidden)"
                cell = _ClickLabel(f"{text}\n{self._preview_value(key)}")
                cell.setStyleSheet(self._cell_css(
                    cfg, self._selection == ("field", key)))
                cell.clicked.connect(
                    lambda k=key: self._select(("field", k)))
                grid.addWidget(cell, base + frow, slot, 1, span)
                self._preview_cells[key] = cell
                last = frow
            row = base + last + 1
        grid.setRowStretch(row, 1)
        # setWidget() deletes the previous preview synchronously — but a
        # rebuild can be triggered from inside a preview cell's own
        # mousePressEvent. Detach the old widget and let deleteLater free it
        # once the event stack unwinds.
        old = self._preview_scroll.takeWidget()
        if old is not None:
            old.deleteLater()
        self._preview_scroll.setWidget(content)

    # ── properties panel (built in Task 7) ─────────────────────────────────

    def _rebuild_props(self):
        pass
