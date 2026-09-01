# gui/info_layout_editor.py
"""WYSIWYG editor for the customizable member Info tab.

Left: a live schematic preview of the layout (click a field or a section
header to select it). Right: a properties panel for the selection. All
edits go through the pure helpers in gui.info_layout on a deep copy; the
caller reads result_layout() only after the dialog is accepted.
"""
import copy
import html

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout,
    QScrollArea, QPushButton, QFrame, QComboBox, QCheckBox, QLineEdit,
    QMessageBox,
)

from gui.info_layout import (
    normalize, default_layout, placements, FIELD_LABELS_BY_KEY, COLORS,
    find_field, set_field_prop, move_field, move_field_to_section,
    move_block, rename_section, add_section, delete_section,
    SIZES, LABEL_SIZES,
)
from gui.theme import current_tokens

# Preview-only pixel mapping; must track the theme QSS rules.
VALUE_PX = {"small": 11, "normal": 13, "large": 16, "xlarge": 20}
LABEL_PX = {"small": 9, "normal": 11, "large": 13}
SIZE_NAMES = {"small": "Small", "normal": "Normal", "large": "Large",
              "xlarge": "X-Large"}


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
        lbl_row = QHBoxLayout()
        lbl_row.addWidget(QLabel("Label size (all fields)"))
        self._label_size_combo = QComboBox()
        for s in LABEL_SIZES:
            self._label_size_combo.addItem(SIZE_NAMES[s], s)
        self._label_size_combo.setCurrentIndex(
            LABEL_SIZES.index(self._layout.get("label_size", "normal")))
        self._label_size_combo.currentIndexChanged.connect(
            self._on_label_size_changed)
        lbl_row.addWidget(self._label_size_combo)
        lbl_row.addStretch()
        right.addLayout(lbl_row)
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
        self._label_size_combo.blockSignals(True)
        self._label_size_combo.setCurrentIndex(
            LABEL_SIZES.index(self._layout["label_size"]))
        self._label_size_combo.blockSignals(False)
        self._rebuild_preview()
        self._rebuild_props()

    def _changed(self):
        """Re-render after any model mutation (wired up by the properties panel)."""
        self._rebuild_preview()

    def _on_label_size_changed(self, _i):
        self._layout["label_size"] = self._label_size_combo.currentData()
        self._changed()

    # ── preview ────────────────────────────────────────────────────────────

    def _cell_css(self, cfg, selected):
        t = current_tokens()
        color = cfg.get("color", "none")
        bg = t.get("hl_" + color, "transparent") if color != "none" \
            else t["raised"]
        border = t["accent"] if selected else t["border"]
        weight = 800 if cfg.get("bold") else 600
        dim_css = "" if cfg.get("visible", True) else \
            f"color: {t['text4']};"
        return (f"background-color: {bg}; border: 2px solid {border}; "
                f"border-radius: 6px; padding: 6px; "
                f"font-weight: {weight}; {dim_css}")

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
                label_px = LABEL_PX[self._layout.get("label_size", "normal")]
                value_px = VALUE_PX[cfg.get("size", "normal")]
                cell = _ClickLabel(
                    f"<span style='font-size:{label_px}px'>"
                    f"{html.escape(text)}</span><br>"
                    f"<span style='font-size:{value_px}px'>"
                    f"{html.escape(self._preview_value(key))}</span>")
                cell.setTextFormat(Qt.TextFormat.RichText)
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

    # ── model mutation handlers (thin wrappers over gui.info_layout) ───────

    def _set_prop(self, prop, value):
        if not self._selection or self._selection[0] != "field":
            return
        set_field_prop(self._layout, self._selection[1], prop, value)
        self._changed()

    def _move_selected_field(self, delta):
        if not self._selection or self._selection[0] != "field":
            return
        move_field(self._layout, self._selection[1], delta)
        self._changed()

    def _move_to_section(self, block_index):
        if not self._selection or self._selection[0] != "field":
            return
        move_field_to_section(self._layout, self._selection[1], block_index)
        self._changed()

    def _move_selected_block(self, delta):
        if not self._selection or self._selection[0] != "block":
            return
        index = self._selection[1]
        move_block(self._layout, index, delta)
        j = index + delta
        if 0 <= j < len(self._layout["blocks"]):
            self._selection = ("block", j)
        self._changed()
        self._rebuild_props()

    def _set_block_visible(self, visible):
        if not self._selection or self._selection[0] != "block":
            return
        block = self._layout["blocks"][self._selection[1]]
        if block["type"] in ("schedule", "emergency"):
            block["visible"] = bool(visible)
        self._changed()

    def _rename(self, title):
        if not self._selection or self._selection[0] != "block":
            return
        rename_section(self._layout, self._selection[1], title)
        self._changed()
        # A rejected (blank) title must not linger in the name box.
        if not title.strip():
            self._rebuild_props()

    def _add_section(self):
        if not self._selection or self._selection[0] != "block":
            return
        add_section(self._layout, self._selection[1])
        self._changed()

    def _delete_section(self):
        if not self._selection or self._selection[0] != "block":
            return
        index = self._selection[1]
        block = self._layout["blocks"][index]
        if block.get("type") != "section":
            return
        # The last remaining section can't be deleted (the pure helper
        # refuses) — don't show a confirm for a no-op.
        if sum(1 for b in self._layout["blocks"]
               if b["type"] == "section") <= 1:
            return
        if block["fields"] and self.isVisible():
            keep = QMessageBox.question(
                self, "Delete Section",
                f"Delete \"{block['title']}\"? Its fields move to the "
                "neighboring section.",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No)
            if keep != QMessageBox.StandardButton.Yes:
                return
        delete_section(self._layout, index)
        self._selection = None
        self._changed()
        self._rebuild_props()

    # ── properties panel ───────────────────────────────────────────────────

    def _clear_props(self):
        box = self._props_host.layout()
        while box.count():
            item = box.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
            elif item.layout() is not None:
                sub = item.layout()
                while sub.count():
                    sw = sub.takeAt(0).widget()
                    if sw is not None:
                        sw.setParent(None)
                        sw.deleteLater()

    def _rebuild_props(self):
        self._clear_props()
        box = self._props_host.layout()
        if self._selection is None:
            hint = QLabel("Click a field or a section header in the\n"
                          "preview to edit it.")
            hint.setObjectName("empty_state")
            box.addWidget(hint)
            return
        kind, ref = self._selection
        if kind == "field":
            self._build_field_props(box, ref)
        else:
            self._build_block_props(box, ref)

    def _build_field_props(self, box, key):
        pos = find_field(self._layout, key)
        if pos is None:
            return
        cfg = self._layout["blocks"][pos[0]]["fields"][pos[1]]
        title = QLabel(FIELD_LABELS_BY_KEY[key])
        title.setStyleSheet("font-weight: 700; font-size: 14px;")
        box.addWidget(title)

        section_combo = QComboBox()
        for bi, block in enumerate(self._layout["blocks"]):
            if block["type"] == "section":
                section_combo.addItem(block["title"], bi)
                if bi == pos[0]:
                    section_combo.setCurrentIndex(section_combo.count() - 1)
        section_combo.currentIndexChanged.connect(
            lambda _i: self._move_to_section(section_combo.currentData()))
        box.addWidget(QLabel("Section"))
        box.addWidget(section_combo)

        move_row = QHBoxLayout()
        up = QPushButton("▲ Move up")
        up.clicked.connect(lambda: self._move_selected_field(-1))
        down = QPushButton("▼ Move down")
        down.clicked.connect(lambda: self._move_selected_field(1))
        move_row.addWidget(up)
        move_row.addWidget(down)
        box.addLayout(move_row)

        span_combo = QComboBox()
        for s in (1, 2, 3):
            span_combo.addItem(f"{s} column{'s' if s > 1 else ''}", s)
        span_combo.setCurrentIndex(cfg["span"] - 1)
        span_combo.currentIndexChanged.connect(
            lambda _i: self._set_prop("span", span_combo.currentData()))
        box.addWidget(QLabel("Width"))
        box.addWidget(span_combo)

        bold = QCheckBox("Bold")
        bold.setChecked(cfg["bold"])
        bold.toggled.connect(lambda v: self._set_prop("bold", v))
        box.addWidget(bold)
        size_combo = QComboBox()
        for s in SIZES:
            size_combo.addItem(SIZE_NAMES[s], s)
        size_combo.setCurrentIndex(SIZES.index(cfg["size"]))
        size_combo.currentIndexChanged.connect(
            lambda _i: self._set_prop("size", size_combo.currentData()))
        box.addWidget(QLabel("Text size"))
        box.addWidget(size_combo)

        color_combo = QComboBox()
        for c in COLORS:
            color_combo.addItem(c.title(), c)
        color_combo.setCurrentIndex(COLORS.index(cfg["color"]))
        color_combo.currentIndexChanged.connect(
            lambda _i: self._set_prop("color", color_combo.currentData()))
        box.addWidget(QLabel("Highlight"))
        box.addWidget(color_combo)

        visible = QCheckBox("Visible")
        visible.setChecked(cfg["visible"])
        visible.toggled.connect(lambda v: self._set_prop("visible", v))
        box.addWidget(visible)

    def _build_block_props(self, box, index):
        block = self._layout["blocks"][index]
        if block["type"] == "section":
            title = QLabel("Section")
        else:
            title = QLabel("Schedule card" if block["type"] == "schedule"
                           else "Emergency contacts")
        title.setStyleSheet("font-weight: 700; font-size: 14px;")
        box.addWidget(title)

        move_row = QHBoxLayout()
        up = QPushButton("▲ Move up")
        up.clicked.connect(lambda: self._move_selected_block(-1))
        down = QPushButton("▼ Move down")
        down.clicked.connect(lambda: self._move_selected_block(1))
        move_row.addWidget(up)
        move_row.addWidget(down)
        box.addLayout(move_row)

        if block["type"] == "section":
            name = QLineEdit(block["title"])
            name.editingFinished.connect(
                lambda: self._rename(name.text()))
            box.addWidget(QLabel("Name"))
            box.addWidget(name)
            btn_add = QPushButton("+ Add section after")
            btn_add.clicked.connect(self._add_section)
            box.addWidget(btn_add)
            btn_del = QPushButton("Delete section")
            btn_del.setObjectName("btn_row_delete")
            btn_del.clicked.connect(self._delete_section)
            box.addWidget(btn_del)
        else:
            visible = QCheckBox("Visible")
            visible.setChecked(block.get("visible", True))
            visible.toggled.connect(self._set_block_visible)
            box.addWidget(visible)
