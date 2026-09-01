# Info Tab Layout Font Sizes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Per-field value text size (Small/Normal/Large/X-Large) and one global label size (Small/Normal/Large) for the customizable Info tab, chosen in the layout editor and persisted in the saved layout.

**Architecture:** The layout model widens `SIZES` and gains a top-level `label_size` key (clamped by `normalize()`); theme QSS gains `fsize="small"/"xlarge"` and `QLabel#field_label[lsize=…]` rules; the renderer stamps the `lsize` property onto every field label; the editor swaps the "Large text" checkbox for a size dropdown, adds a global label-size dropdown, and renders its preview cells as rich text so both sizes are visible.

**Tech Stack:** Python 3.11, PyQt6, pytest offscreen (`QT_QPA_PLATFORM=offscreen`).

**Spec:** `docs/superpowers/specs/2026-09-01-layout-font-sizes-design.md`

**Working notes for the implementer:**
- Run tests from repo root: `python -m pytest <file> -v`. Full suite is currently 669 passing.
- Pixel mapping (fixed, theme-independent): value Small/Normal/Large/X-Large = 11/13/16/20px ("normal" = the un-ruled base 13px); label Small/Normal/Large = 9/11/13px ("normal" = the un-ruled base 11px).
- Anchor on quoted code, not line numbers.
- Every commit message ends with:
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`

---

### Task 1: Model — widened SIZES, LABEL_SIZES, `label_size` in default/normalize

**Files:**
- Modify: `gui/info_layout.py`
- Test: `tests/test_info_layout.py` (append)

- [ ] **Step 1: Append the failing tests** to `tests/test_info_layout.py`:

```python
# ── font sizes: widened value sizes + global label size ────────────────────

def test_size_constants():
    from gui.info_layout import SIZES, LABEL_SIZES
    assert SIZES == ("small", "normal", "large", "xlarge")
    assert LABEL_SIZES == ("small", "normal", "large")


def test_default_layout_has_normal_label_size():
    from gui.info_layout import default_layout
    assert default_layout()["label_size"] == "normal"


def test_normalize_keeps_new_size_values():
    from gui.info_layout import normalize
    lay = normalize({"version": 1, "blocks": [
        {"type": "section", "title": "A", "fields": [
            {"key": "dob", "size": "xlarge"},
            {"key": "ssn", "size": "small"},
            {"key": "cell", "size": "huge"},          # junk -> normal
        ]},
    ]})
    by_key = {f["key"]: f for b in lay["blocks"] if b["type"] == "section"
              for f in b["fields"]}
    assert by_key["dob"]["size"] == "xlarge"
    assert by_key["ssn"]["size"] == "small"
    assert by_key["cell"]["size"] == "normal"


def test_normalize_clamps_label_size():
    from gui.info_layout import normalize, default_layout
    base = {"version": 1, "blocks": default_layout()["blocks"]}
    assert normalize(base)["label_size"] == "normal"          # absent
    assert normalize({**base, "label_size": "large"})["label_size"] == "large"
    assert normalize({**base, "label_size": "giant"})["label_size"] == "normal"
    assert normalize({**base, "label_size": 7})["label_size"] == "normal"


def test_label_size_roundtrips():
    import json
    from gui.info_layout import normalize, default_layout
    lay = default_layout()
    lay["label_size"] = "small"
    assert normalize(json.loads(json.dumps(lay)))["label_size"] == "small"
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_info_layout.py -v`
Expected: the 5 new tests FAIL (`LABEL_SIZES` ImportError / KeyError `'label_size'` / `xlarge` clamped away); the existing 22 pass.

- [ ] **Step 3: Implement** in `gui/info_layout.py`:

3a. Replace the constants line

```python
SIZES = ("normal", "large")
```

with:

```python
# Value text sizes -> 11/13/16/20px ("normal" is the un-ruled 13px base).
SIZES = ("small", "normal", "large", "xlarge")
# Global field-label sizes -> 9/11/13px ("normal" is the un-ruled 11px base).
LABEL_SIZES = ("small", "normal", "large")
```

3b. In `default_layout()`, change the opening of the returned dict from

```python
    return {"version": 1, "blocks": [
```

to:

```python
    return {"version": 1, "label_size": "normal", "blocks": [
```

3c. In `normalize()`, replace the final return

```python
    return {"version": 1, "blocks": blocks}
```

with:

```python
    label_size = layout.get("label_size")
    if label_size not in LABEL_SIZES:
        label_size = "normal"
    return {"version": 1, "label_size": label_size, "blocks": blocks}
```

(The garbage path already returns `default_layout()`, which now carries the key. `_clean_field` needs no change — it clamps `size` against the widened `SIZES`.)

3d. Extend `normalize()`'s docstring first line list of guarantees: after "values are clamped," add "and the global `label_size` is clamped to LABEL_SIZES." — keep the rest.

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_info_layout.py -v`
Expected: 27 passed (the existing round-trip test compares against `default_layout()`, which gained the key on both sides — still green)

- [ ] **Step 5: Commit**

```bash
git add gui/info_layout.py tests/test_info_layout.py
git commit -m "feat: layout model — value size steps and global label size"
```

---

### Task 2: Theme — QSS rules for the new sizes

**Files:**
- Modify: `gui/theme.py` — `build_qss`
- Test: `tests/test_info_tab_render.py` (append)

- [ ] **Step 1: Append the failing tests** to `tests/test_info_tab_render.py`:

```python
# ── font-size steps: value fsize small/xlarge + label lsize rules ──────────

def test_qss_has_size_step_rules_both_themes():
    from gui.theme import build_qss, DARK, LIGHT
    for tokens in (DARK, LIGHT):
        qss = build_qss(tokens)
        assert 'QLineEdit#info_field[fsize="small"]' in qss
        assert 'QLineEdit#info_field[fsize="xlarge"]' in qss
        assert 'QLineEdit[fsize="small"]' in qss
        assert 'QLineEdit[fsize="xlarge"]' in qss
        assert 'QLabel#field_label[lsize="small"]' in qss
        assert 'QLabel#field_label[lsize="large"]' in qss


def test_xlarge_value_and_large_label_render(qapp):
    from PyQt6.QtWidgets import QLabel
    from gui.theme import build_qss, DARK
    w = _styled_line_edit("info_field", {"fsize": "xlarge"})
    assert w.font().pixelSize() == 20
    lab = QLabel("DOB")
    lab.setObjectName("field_label")
    lab.setProperty("lsize", "large")
    lab.setStyleSheet(build_qss(DARK))
    lab.style().unpolish(lab)
    lab.style().polish(lab)
    assert lab.font().pixelSize() == 13
```

(`_styled_line_edit` already exists earlier in this file.)

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_info_tab_render.py -v`
Expected: 2 new FAIL; the existing 13 pass.

- [ ] **Step 3: Implement** in `gui/theme.py`, inside `build_qss`'s f-string:

3a. In the ID-qualified block, replace

```python
QLineEdit#info_field[fsize="large"] {{ font-size: 16px; }}
```

with:

```python
QLineEdit#info_field[fsize="small"] {{ font-size: 11px; }}
QLineEdit#info_field[fsize="large"] {{ font-size: 16px; }}
QLineEdit#info_field[fsize="xlarge"] {{ font-size: 20px; }}
```

3b. In the generic fallback block, replace

```python
QLineEdit[fsize="large"] {{ font-size: 16px; }}
```

with:

```python
QLineEdit[fsize="small"] {{ font-size: 11px; }}
QLineEdit[fsize="large"] {{ font-size: 16px; }}
QLineEdit[fsize="xlarge"] {{ font-size: 20px; }}
```

3c. Directly after the closing `}}` of the base `QLabel#field_label` rule, insert:

```python
/* Global label size from the customizable layout ("normal" = the 11px base
   above; the lsize property is stamped by _make_info_tab). */
QLabel#field_label[lsize="small"] {{ font-size: 9px; }}
QLabel#field_label[lsize="large"] {{ font-size: 13px; }}
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_info_tab_render.py tests/test_settings.py -q`
Expected: 15 + 13 passed

- [ ] **Step 5: Commit**

```bash
git add gui/theme.py tests/test_info_tab_render.py
git commit -m "feat: theme rules for value size steps and label sizes"
```

---

### Task 3: Renderer — stamp `lsize` on field labels

**Files:**
- Modify: `gui/member_tabs.py` — `_make_info_tab` placement loop
- Test: `tests/test_info_tab_render.py` (append)

- [ ] **Step 1: Append the failing tests** to `tests/test_info_tab_render.py`:

```python
def test_labels_carry_global_label_size(qapp):
    from gui.info_layout import default_layout
    lay = default_layout()
    lay["label_size"] = "large"
    _w, tab = _make_tab(qapp, layout_cfg=lay)
    from PyQt6.QtWidgets import QLabel
    labels = [l for l in tab.findChildren(QLabel)
              if l.objectName() == "field_label"]
    assert labels
    assert all(l.property("lsize") == "large" for l in labels)


def test_field_small_size_sets_fsize_property(qapp):
    from gui.info_layout import default_layout
    lay = default_layout()
    for f in lay["blocks"][1]["fields"]:
        if f["key"] == "dob":
            f["size"] = "small"
    w, _tab = _make_tab(qapp, layout_cfg=lay)
    assert w._info_dob.property("fsize") == "small"
```

(`_make_tab` already exists earlier in this file.)

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_info_tab_render.py -v`
Expected: `test_labels_carry_global_label_size` FAILS (property is None); `test_field_small_size_sets_fsize_property` PASSES already (apply_field_style forwards any size value) — that's expected, note it and continue.

- [ ] **Step 3: Implement** in `gui/member_tabs.py`, in `_make_info_tab`'s placement loop, replace

```python
                    lab = QLabel(FIELD_LABELS_BY_KEY[cfg["key"]])
                    lab.setObjectName("field_label")
```

with:

```python
                    lab = QLabel(FIELD_LABELS_BY_KEY[cfg["key"]])
                    lab.setObjectName("field_label")
                    lab.setProperty(
                        "lsize", layout_cfg.get("label_size", "normal"))
```

- [ ] **Step 4: Run to verify pass, plus neighbors**

Run: `python -m pytest tests/test_info_tab_render.py -q`
Expected: 19 passed

- [ ] **Step 5: Commit**

```bash
git add gui/member_tabs.py tests/test_info_tab_render.py
git commit -m "feat: Info tab labels take the layout's global label size"
```

---

### Task 4: Editor — size dropdown, global label-size dropdown, rich-text preview

**Files:**
- Modify: `gui/info_layout_editor.py`
- Test: `tests/test_info_layout_editor.py` (append)

- [ ] **Step 1: Append the failing tests** to `tests/test_info_layout_editor.py`:

```python
# ── font sizes in the editor ───────────────────────────────────────────────

def test_text_size_dropdown_sets_field_size(qapp):
    from gui.info_layout import find_field
    dlg = _dlg(qapp)
    dlg._select(("field", "dob"))
    dlg._set_prop("size", "xlarge")
    bi, fi = find_field(dlg._layout, "dob")
    assert dlg._layout["blocks"][bi]["fields"][fi]["size"] == "xlarge"
    # The props panel offers a Text size dropdown with all four steps.
    from PyQt6.QtWidgets import QComboBox
    combos = dlg._props_host.findChildren(QComboBox)
    size_combos = [c for c in combos
                   if [c.itemData(i) for i in range(c.count())]
                   == ["small", "normal", "large", "xlarge"]]
    assert len(size_combos) == 1
    assert size_combos[0].currentData() == "xlarge"


def test_global_label_size_dropdown(qapp):
    dlg = _dlg(qapp)
    assert dlg._layout["label_size"] == "normal"
    dlg._label_size_combo.setCurrentIndex(2)          # "large"
    assert dlg._layout["label_size"] == "large"
    # Survives selection changes and preview rebuilds.
    dlg._select(("field", "dob"))
    assert dlg._label_size_combo.currentData() == "large"
    assert dlg._layout["label_size"] == "large"
    assert dlg.result_layout()["label_size"] == "large"


def test_reset_resyncs_label_size_combo(qapp):
    dlg = _dlg(qapp)
    dlg._label_size_combo.setCurrentIndex(0)          # "small"
    dlg._reset()
    assert dlg._layout["label_size"] == "normal"
    assert dlg._label_size_combo.currentData() == "normal"


def test_preview_cells_render_both_sizes_as_rich_text(qapp):
    from gui.info_layout import find_field
    dlg = _dlg(qapp)
    dlg._layout["label_size"] = "large"               # 13px labels
    bi, fi = find_field(dlg._layout, "dob")
    dlg._layout["blocks"][bi]["fields"][fi]["size"] = "xlarge"   # 20px value
    dlg._rebuild_preview()
    cell_text = dlg._preview_cells["dob"].text()
    assert "font-size:13px" in cell_text
    assert "font-size:20px" in cell_text
    # A normal field uses the base value size.
    assert "font-size:13px" in dlg._preview_cells["first_name"].text()
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_info_layout_editor.py -v`
Expected: the 4 new tests FAIL (`_label_size_combo` missing, no size dropdown, plain-text preview); the existing 12 pass.

- [ ] **Step 3: Implement** in `gui/info_layout_editor.py`:

3a. Extend the model import to include the size constants:

```python
from gui.info_layout import (
    normalize, default_layout, placements, FIELD_LABELS_BY_KEY, COLORS,
    SIZES, LABEL_SIZES,
    find_field, set_field_prop, move_field, move_field_to_section,
    move_block, rename_section, add_section, delete_section,
)
```

Also add `import html` next to `import copy`, and module-level pixel maps
after the imports:

```python
# Preview-only pixel mapping; must track the theme QSS rules.
VALUE_PX = {"small": 11, "normal": 13, "large": 16, "xlarge": 20}
LABEL_PX = {"small": 9, "normal": 11, "large": 13}
SIZE_NAMES = {"small": "Small", "normal": "Normal", "large": "Large",
              "xlarge": "X-Large"}
```

3b. In `__init__`, directly after `right = QVBoxLayout()` and before the `self._props_host` lines, add the always-visible global dropdown:

```python
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
```

(`QComboBox` may need adding to the QtWidgets import at the top if the
constructor section doesn't already see it — it's already imported for the
props panel; verify.)

3c. Add the handler next to `_reset`:

```python
    def _on_label_size_changed(self, _i):
        self._layout["label_size"] = self._label_size_combo.currentData()
        self._changed()
```

3d. In `_reset`, after `self._layout = default_layout()`, resync the combo
without re-triggering the handler:

```python
        self._label_size_combo.blockSignals(True)
        self._label_size_combo.setCurrentIndex(
            LABEL_SIZES.index(self._layout["label_size"]))
        self._label_size_combo.blockSignals(False)
```

3e. Rich-text preview. In `_cell_css`, delete the `size = 15 if ...` line and remove `font-size: {size}px; ` from the returned string (font weight, background, border, padding, dim stay). In `_rebuild_preview`'s field loop, replace

```python
                cell = _ClickLabel(f"{text}\n{self._preview_value(key)}")
```

with:

```python
                label_px = LABEL_PX[self._layout.get("label_size", "normal")]
                value_px = VALUE_PX.get(cfg.get("size", "normal"), 13)
                cell = _ClickLabel(
                    f"<span style='font-size:{label_px}px'>"
                    f"{html.escape(text)}</span><br>"
                    f"<span style='font-size:{value_px}px'>"
                    f"{html.escape(self._preview_value(key))}</span>")
                cell.setTextFormat(Qt.TextFormat.RichText)
```

3f. In `_build_field_props`, replace the "Large text" checkbox block

```python
        large = QCheckBox("Large text")
        large.setChecked(cfg["size"] == "large")
        large.toggled.connect(
            lambda v: self._set_prop("size", "large" if v else "normal"))
        box.addWidget(large)
```

with:

```python
        size_combo = QComboBox()
        for s in SIZES:
            size_combo.addItem(SIZE_NAMES[s], s)
        size_combo.setCurrentIndex(SIZES.index(cfg["size"]))
        size_combo.currentIndexChanged.connect(
            lambda _i: self._set_prop("size", size_combo.currentData()))
        box.addWidget(QLabel("Text size"))
        box.addWidget(size_combo)
```

(If `QCheckBox` is then still used by the Bold/Visible checkboxes, keep its
import.)

- [ ] **Step 4: Run to verify pass, then the full suite**

Run: `python -m pytest tests/test_info_layout_editor.py -v`
Expected: 16 passed
Run: `python -m pytest -q`
Expected: 678 passed (669 + 9 new across the four test files)

- [ ] **Step 5: Commit**

```bash
git add gui/info_layout_editor.py tests/test_info_layout_editor.py
git commit -m "feat: editor size dropdowns and true-to-size rich-text preview"
```

---

### Task 5: Full verification

- [ ] **Step 1:** `python -m pytest -q` → 678 passed.
- [ ] **Step 2:** Manual smoke test: open a member → Customize Layout. Set a field's Text size to X-Large and another to Small → Save → the values render at visibly different sizes; set Label size to Large → all field labels grow; Reset to Default restores everything; restart the app → sizes persist; switch light/dark theme → sizes unchanged and legible. Also confirm an old saved layout (from before this feature) still loads with normal sizes.
- [ ] **Step 3:** Use the superpowers:finishing-a-development-branch skill.

---

## Self-Review (done at plan time)

- **Spec coverage:** widened `SIZES` + `LABEL_SIZES` + `label_size` default/clamp (Task 1), theme rules incl. generic fallback (Task 2), renderer `lsize` stamping (Task 3), editor dropdowns + rich-text preview + reset resync (Task 4), compatibility covered by Task 1's clamp tests and Task 5's smoke step. Out-of-scope items untouched.
- **Placeholder scan:** none.
- **Type consistency:** `label_size` read via `.get(..., "normal")` everywhere; `VALUE_PX`/`LABEL_PX` match the QSS pixel values (11/13/16/20 and 9/11/13); `SIZE_NAMES` covers all members of both tuples; `_set_prop("size", …)` reuses the existing handler.
