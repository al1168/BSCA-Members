# App-wide Text Size Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Settings "Text size" choice (Normal 13px / Large 25px / Extra Large 30px) that enlarges every piece of on-screen text and the dimensions that hold it, plus 25px/30px per-field steps in the Info layout editor.

**Architecture:** One scale factor lives in `gui/theme.py` (`text_scale_for`, `set_text_size`, `current_text_scale`, `px`). `build_qss(t, scale)` writes every font-size through it; widget files call `px(n)` for inline font sizes and text-holding fixed dimensions at construction time. A text-size change closes the main window with a reopen request; `member_manager.run(app)` loops, re-applies the theme at the new scale and rebuilds the window on the same member.

**Tech Stack:** Python 3.11, PyQt6, Qt stylesheets (QSS), pytest + pytest-qt (offscreen platform). Run tests with `python -m pytest <path> -q` from the repo root.

**Spec:** `docs/superpowers/specs/2026-09-11-text-size-mode-design.md`

**Conventions used throughout:**
- Every GUI test module starts with the same offscreen preamble used across `tests/` (shown in Task 2). Reuse it verbatim in each new test file.
- Rounding rule everywhere: `int(n * scale + 0.5)`. Factors: large = 25/13 ≈ 1.923, xlarge = 30/13 ≈ 2.308. Handy values: 9→17/21, 10→19/23, 11→21/25, 12→23/28, 13→25/30, 14→27/32, 15→29/35, 16→31/37, 17→33/39, 18→35/42, 20→38/46, 26→50/60, 28→54/65, 34→65/78, 40→77/92, 220→423/508.
- Where a computed column width is `max(measured + slack, floor)`, only the `floor` goes through `px()`; measured terms already reflect the larger font and slack is padding.
- The wizard step dot is a circle drawn with `border-radius:14px` on a 28px square; the radius scales with the dot (`px(14)`) so it stays round. This is the one radius that scales.

---

## File map

| File | Change |
|---|---|
| `settings.py` | `text_size` default |
| `gui/theme.py` | scale model (`TEXT_SIZES`, `BASE_PX`, `text_scale_for`, `set_text_size`, `current_text_scale`, `px`), `build_qss(t, scale)`, new `fsize`/`lsize` rules, `apply_theme(app, theme, text_size)` |
| `gui/info_layout.py` | widen `SIZES`, `LABEL_SIZES` |
| `gui/info_layout_editor.py` | `VALUE_PX`/`LABEL_PX`/`SIZE_NAMES` entries; preview and titles via `px` |
| `gui/settings_dialog.py` | "Text size:" radio row; `result_settings()["text_size"]` |
| `gui/main_window.py` | `px` for sidebar/geometry/counts label; reopen logic in `_open_settings`; public `jump_to_member` |
| `member_manager.py` | `run(app)` loop; `main()` calls it |
| `gui/member_tabs.py` | inline font sizes and text-holding dimensions via `px` |
| `gui/bookmarks_panel.py`, `gui/notifications.py`, `gui/confirm_changes.py`, `gui/events_view.py`, `gui/expiring_report.py`, `gui/address_autocomplete.py`, `gui/time_range_editor.py`, `gui/company_calendar.py`, `gui/profile_print.py` | same, smaller files |
| `gui/wizard/wizard.py`, `step_auths.py`, `step_contact.py`, `step_enrollment.py`, `step_review.py` | same |
| `tests/test_text_size.py` (new) | scale model, QSS scaling, rendered sizes, no-literal-font-size guard, settings dialog, main window reopen, `member_manager.run` |
| `tests/test_settings.py`, `tests/test_info_layout.py`, `tests/test_info_layout_editor.py`, `tests/test_info_tab_render.py` | extend existing tests |

---

### Task 1: Branch and `text_size` setting default

**Files:**
- Modify: `settings.py`
- Test: `tests/test_settings.py`

- [ ] **Step 1: Create the feature branch**

```bash
git checkout -b feature/text-size-mode
```

- [ ] **Step 2: Write the failing test**

Append to `tests/test_settings.py`:

```python
def test_text_size_defaults_to_normal(tmp_path):
    assert DEFAULT_SETTINGS["text_size"] == "normal"
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"theme": "light"}))   # pre-feature file: no key
    assert load_settings(str(path))["text_size"] == "normal"
```

- [ ] **Step 3: Run it to verify it fails**

Run: `python -m pytest tests/test_settings.py::test_text_size_defaults_to_normal -q`
Expected: FAIL with `KeyError: 'text_size'`

- [ ] **Step 4: Add the default**

In `settings.py`, extend `DEFAULT_SETTINGS`:

```python
DEFAULT_SETTINGS = {
    "db_path": "",
    "theme": "dark",
    "events_db_path": "",
    "google_api_key": "",
    # Debug: show the internal row "ID" column in the member tables. Off by
    # default so day-to-day users don't see database ids like 442.
    "show_row_ids": False,
    # App-wide text size: "normal" (13px base) | "large" (25px) | "xlarge" (30px).
    "text_size": "normal",
}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `python -m pytest tests/test_settings.py -q`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add settings.py tests/test_settings.py
git commit -m "feat(settings): text_size default (normal)"
```

---

### Task 2: Scale model in `gui/theme.py`

> **Post-review adjustments (applied in a follow-up commit, supersede the text below where they differ):** `apply_theme(app, theme_name, text_size=None)` keeps the current scale when `text_size` is omitted; `px` and `build_qss`'s `p` both call a private `_scaled(n, scale)`; `TEXT_SIZES["normal"]` is `BASE_PX`; the scale is pinned to Normal before and after every test by an autouse fixture in `tests/conftest.py`, so no test needs a `normal_scale` fixture.

**Files:**
- Modify: `gui/theme.py` (state block near line 890 and `apply_theme` at the end)
- Create: `tests/test_text_size.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_text_size.py`:

```python
"""App-wide text size mode: one scale factor drives every on-screen font size
and the fixed dimensions that hold text."""
import os
import re

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def normal_scale():
    """Any test that changes the module-level scale must leave it at Normal."""
    from gui import theme
    yield
    theme.set_text_size("normal")


# ── scale model ────────────────────────────────────────────────────────────

def test_text_sizes_and_factors():
    from gui.theme import TEXT_SIZES, BASE_PX, text_scale_for
    assert TEXT_SIZES == {"normal": 13, "large": 25, "xlarge": 30}
    assert BASE_PX == 13
    assert text_scale_for("normal") == 1.0
    assert text_scale_for("large") == pytest.approx(25 / 13)
    assert text_scale_for("xlarge") == pytest.approx(30 / 13)
    assert text_scale_for("bogus") == 1.0


def test_px_rounds_to_nearest_pixel(normal_scale):
    from gui.theme import set_text_size, px, current_text_scale
    assert current_text_scale() == 1.0
    assert px(13) == 13 and px(9) == 9
    set_text_size("large")
    assert [px(n) for n in (9, 10, 12, 13, 20)] == [17, 19, 23, 25, 38]
    set_text_size("xlarge")
    assert [px(n) for n in (9, 10, 12, 13, 20)] == [21, 23, 28, 30, 46]
    set_text_size("normal")
    assert px(220) == 220


def test_set_text_size_returns_scale_and_ignores_unknown(normal_scale):
    from gui.theme import set_text_size, current_text_scale
    assert set_text_size("xlarge") == pytest.approx(30 / 13)
    assert set_text_size("nonsense") == 1.0
    assert current_text_scale() == 1.0
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/test_text_size.py -q`
Expected: FAIL with `ImportError: cannot import name 'TEXT_SIZES'`

- [ ] **Step 3: Add the scale model**

In `gui/theme.py`, replace the state block

```python
# The active theme, kept current by apply_theme so widgets built later (event
# badges, count labels) can color themselves without threading the settings
# dict everywhere.
_current_name = "dark"
```

with

```python
# The active theme, kept current by apply_theme so widgets built later (event
# badges, count labels) can color themselves without threading the settings
# dict everywhere.
_current_name = "dark"

# App-wide text size. Every on-screen font size in build_qss and every inline
# size / text-holding dimension in the widget files is multiplied by the
# current factor (base ÷ 13). Widgets read it at construction; a change
# rebuilds the main window (see MainWindow._open_settings).
BASE_PX = 13
TEXT_SIZES = {"normal": 13, "large": 25, "xlarge": 30}
_current_scale = 1.0


def text_scale_for(name: str) -> float:
    """Scale factor for a text-size name; unknown names mean Normal (1.0)."""
    return TEXT_SIZES.get(name, BASE_PX) / BASE_PX


def set_text_size(name: str) -> float:
    """Make `name` the active text size and return its factor."""
    global _current_scale
    _current_scale = text_scale_for(name)
    return _current_scale


def current_text_scale() -> float:
    return _current_scale


def px(n) -> int:
    """`n` logical pixels at Normal size, scaled to the active text size and
    rounded to the nearest whole pixel."""
    return int(n * _current_scale + 0.5)
```

Then change `apply_theme` at the bottom of the file to:

```python
def apply_theme(app, theme_name: str, text_size: str = "normal") -> None:
    """Apply 'dark' or 'light' QSS at the given text size to the whole app."""
    global _current_name
    _current_name = "dark" if theme_name == "dark" else "light"
    tokens = DARK if theme_name == "dark" else LIGHT
    scale = set_text_size(text_size)
    app.setStyleSheet(build_qss(tokens, scale))
    # Re-polish everything: some chrome (toolbars, property-selector styles)
    # keeps the old palette after a runtime stylesheet swap otherwise.
    style = app.style()
    for w in app.allWidgets():
        style.unpolish(w)
        style.polish(w)
        w.update()
```

Also update the module docstring's second paragraph to:

```python
Colors are pre-converted from OKLCH to sRGB hex. Call apply_theme(app, "dark")
or apply_theme(app, "light") to swap at runtime; pass text_size="large" or
"xlarge" to enlarge every on-screen font (see TEXT_SIZES / px()).
```

`build_qss` does not accept `scale` yet — Task 3 adds it. Until then give it the parameter with a default so this task runs:

```python
def build_qss(t: dict, scale: float = 1.0) -> str:
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_text_size.py tests/test_info_tab_render.py -q`
Expected: all PASS (the render tests confirm the `build_qss` signature change is harmless)

- [ ] **Step 5: Commit**

```bash
git add gui/theme.py tests/test_text_size.py
git commit -m "feat(theme): text size scale model (TEXT_SIZES, set_text_size, px)"
```

---

### Task 3: `build_qss` writes every font size through the scale

**Files:**
- Modify: `gui/theme.py` (`build_qss`, all 48 `font-size` rules)
- Test: `tests/test_text_size.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_text_size.py`:

```python
# ── build_qss scaling ──────────────────────────────────────────────────────

def test_qss_default_scale_is_unchanged_and_has_no_literal_sizes_left():
    from gui.theme import build_qss, DARK, LIGHT
    for tokens in (DARK, LIGHT):
        qss = build_qss(tokens)
        assert qss == build_qss(tokens, 1.0)
        assert "font-size: 13px;" in qss           # base rule intact at Normal
        assert 'QLineEdit#info_field[fsize="xlarge"] { font-size: 20px; }' in qss
        assert 'QLabel#field_label[lsize="large"] { font-size: 13px; }' in qss


def test_qss_scales_every_font_size():
    from gui.theme import build_qss, DARK, text_scale_for
    normal = build_qss(DARK)
    large = build_qss(DARK, text_scale_for("large"))
    xlarge = build_qss(DARK, text_scale_for("xlarge"))
    # Same number of font-size rules in each; none left at Normal pixels.
    sizes = lambda q: re.findall(r"font-size: (\d+)px", q)
    assert len(sizes(normal)) == len(sizes(large)) == len(sizes(xlarge)) >= 48
    assert "font-size: 25px;" in large and "font-size: 23px;" in large
    assert "font-size: 30px;" in xlarge and "font-size: 28px;" in xlarge
    assert 'QLineEdit#info_field[fsize="xlarge"] { font-size: 46px; }' in xlarge
    assert 'QLabel#field_label[lsize="large"] { font-size: 30px; }' in xlarge
    # Paddings and radii are not scaled.
    assert "padding: 7px 16px;" in xlarge and "border-radius: 7px;" in xlarge


def test_rendered_label_reports_scaled_pixel_size(qapp):
    from PyQt6.QtWidgets import QLabel
    from gui.theme import build_qss, DARK, text_scale_for
    lab = QLabel("Members")
    lab.setStyleSheet(build_qss(DARK, text_scale_for("xlarge")))
    lab.style().unpolish(lab)
    lab.style().polish(lab)
    assert lab.font().pixelSize() == 30
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/test_text_size.py -q`
Expected: `test_qss_scales_every_font_size` and `test_rendered_label_reports_scaled_pixel_size` FAIL (sizes unchanged at scale ≠ 1)

- [ ] **Step 3: Convert the rules**

All 48 `font-size: Npx` occurrences in `gui/theme.py` sit inside the `build_qss` f-string. Rewrite them mechanically:

```bash
sed -i -E 's/font-size: ([0-9]+)px/font-size: {p(\1)}px/g' gui/theme.py
grep -c "font-size: {p(" gui/theme.py     # expect 48
grep -c "font-size: [0-9]" gui/theme.py    # expect 0
```

Then define `p` at the top of `build_qss`:

```python
def build_qss(t: dict, scale: float = 1.0) -> str:
    def p(n: int) -> int:
        """Font pixels at Normal size → pixels at `scale`; shares the rounding
        rule with px() so QSS and inline sizes can never drift apart."""
        return _scaled(n, scale)

    plan_rules = "\n".join(
        f'QLabel#plan_badge[plan="{code}"] {{ background-color: {color}; '
        f'color: {_readable_text(color)}; border: 1px solid {color}; }}'
        for code, color in PLAN_COLORS.items()
    )
    return f"""
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_text_size.py tests/test_info_tab_render.py tests/test_plan_badge_colors.py -q`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add gui/theme.py tests/test_text_size.py
git commit -m "feat(theme): build_qss scales every font-size by the text size factor"
```

---

### Task 4: Info layout — new size steps in model, QSS and editor

**Files:**
- Modify: `gui/info_layout.py:54-57`
- Modify: `gui/theme.py` (`fsize`/`lsize` rule blocks)
- Modify: `gui/info_layout_editor.py:28-31`, preview cell (≈line 203-208), header/title styles
- Test: `tests/test_info_layout.py`, `tests/test_info_layout_editor.py`, `tests/test_info_tab_render.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_info_layout.py`:

```python
def test_new_size_steps_accepted_and_unknown_clamped():
    from gui.info_layout import normalize, default_layout, SIZES, LABEL_SIZES, find_field
    assert SIZES == ("small", "normal", "large", "xlarge", "xxlarge", "xxxlarge")
    assert LABEL_SIZES == ("small", "normal", "large", "xlarge", "xxlarge", "xxxlarge")
    lay = default_layout()
    bi, fi = find_field(lay, "dob")
    lay["blocks"][bi]["fields"][fi]["size"] = "xxxlarge"
    lay["label_size"] = "xxlarge"
    out = normalize(lay)
    assert out["blocks"][bi]["fields"][fi]["size"] == "xxxlarge"
    assert out["label_size"] == "xxlarge"
    lay["blocks"][bi]["fields"][fi]["size"] = "gigantic"
    lay["label_size"] = "gigantic"
    out = normalize(lay)
    assert out["blocks"][bi]["fields"][fi]["size"] == "normal"
    assert out["label_size"] == "normal"
```

In `tests/test_info_layout_editor.py::test_text_size_dropdown_sets_field_size` change the expected item list and comment:

```python
    # The props panel offers a Text size dropdown with all six steps.
    from PyQt6.QtWidgets import QComboBox
    dlg._rebuild_props()
    combos = dlg._props_host.findChildren(QComboBox)
    size_combos = [c for c in combos
                   if [c.itemData(i) for i in range(c.count())]
                   == ["small", "normal", "large", "xlarge", "xxlarge", "xxxlarge"]]
```

and append:

```python
def test_label_size_dropdown_offers_six_steps_with_display_names(qapp):
    dlg = _dlg(qapp)
    combo = dlg._label_size_combo
    assert [combo.itemData(i) for i in range(combo.count())] == [
        "small", "normal", "large", "xlarge", "xxlarge", "xxxlarge"]
    assert [combo.itemText(i) for i in range(combo.count())] == [
        "Small", "Normal", "Large", "X-Large", "2X-Large", "3X-Large"]
    combo.setCurrentIndex(5)
    assert dlg._layout["label_size"] == "xxxlarge"


def test_preview_uses_scaled_pixels(qapp):
    from gui import theme
    dlg = _dlg(qapp)
    dlg._select(("field", "dob"))
    dlg._set_prop("size", "xxxlarge")
    theme.set_text_size("xlarge")          # conftest resets to Normal afterwards
    dlg._rebuild_preview()
    from PyQt6.QtWidgets import QLabel
    texts = [w.text() for w in dlg._preview_scroll.widget().findChildren(QLabel)]
    assert any("font-size:69px" in t for t in texts)      # value 30 × 30/13
    assert any("font-size:25px" in t for t in texts)      # label 11 × 30/13
```

In `tests/test_info_tab_render.py::test_qss_pixel_values_match_editor_maps` widen the loops:

```python
    for s in ("small", "large", "xlarge", "xxlarge", "xxxlarge"):
        assert f'[fsize="{s}"] {{ font-size: {VALUE_PX[s]}px' in qss
    for s in ("small", "large", "xlarge", "xxlarge", "xxxlarge"):
        assert f'QLabel#field_label[lsize="{s}"] {{ font-size: {LABEL_PX[s]}px' in qss
```

(Keep whatever the second loop's existing assertion line looks like; only the tuple changes.)

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/test_info_layout.py tests/test_info_layout_editor.py tests/test_info_tab_render.py -q`
Expected: the new/changed tests FAIL (tuples and maps lack the new names)

- [ ] **Step 3: Widen the model**

In `gui/info_layout.py` replace lines 54-57 with:

```python
# Value text sizes -> 11/13/16/20/25/30px at Normal app text size ("normal" is
# the un-ruled 13px base). All multiply with the app-wide text size factor.
SIZES = ("small", "normal", "large", "xlarge", "xxlarge", "xxxlarge")
# Global field-label sizes -> 9/11/13/20/25/30px ("normal" is the un-ruled base).
LABEL_SIZES = ("small", "normal", "large", "xlarge", "xxlarge", "xxxlarge")
```

- [ ] **Step 4: Add the QSS rules**

In `gui/theme.py`, after each existing `xlarge` value rule (both blocks) add:

```python
QLineEdit#info_field[fsize="xxlarge"] {{ font-size: {p(25)}px; }}
QLineEdit#info_field[fsize="xxxlarge"] {{ font-size: {p(30)}px; }}
```

and in the generic block:

```python
QLineEdit[fsize="xxlarge"] {{ font-size: {p(25)}px; }}
QLineEdit[fsize="xxxlarge"] {{ font-size: {p(30)}px; }}
```

After `QLabel#field_label[lsize="large"] {{ font-size: {p(13)}px; }}` add:

```python
QLabel#field_label[lsize="xlarge"] {{ font-size: {p(20)}px; }}
QLabel#field_label[lsize="xxlarge"] {{ font-size: {p(25)}px; }}
QLabel#field_label[lsize="xxxlarge"] {{ font-size: {p(30)}px; }}
```

- [ ] **Step 5: Update the editor maps, names and preview**

In `gui/info_layout_editor.py` replace lines 25-31 with:

```python
from gui.theme import current_tokens, px

# Preview-only pixel mapping at Normal app text size; must track the theme
# QSS rules. The preview multiplies these through px() so it matches the
# live tab in every text-size mode.
VALUE_PX = {"small": 11, "normal": 13, "large": 16, "xlarge": 20,
            "xxlarge": 25, "xxxlarge": 30}
LABEL_PX = {"small": 9, "normal": 11, "large": 13, "xlarge": 20,
            "xxlarge": 25, "xxxlarge": 30}
SIZE_NAMES = {"small": "Small", "normal": "Normal", "large": "Large",
              "xlarge": "X-Large", "xxlarge": "2X-Large", "xxxlarge": "3X-Large"}
```

In the preview loop (≈lines 203-204) scale the pixels:

```python
                label_px = px(LABEL_PX[self._layout.get("label_size", "normal")])
                value_px = px(VALUE_PX[cfg.get("size", "normal")])
```

Section header style (≈line 188): `f"color: {t['accent_text']}; font-size: {px(11)}px; "`.
Both props titles (≈lines 348 and 414): `title.setStyleSheet(f"font-weight: 700; font-size: {px(14)}px;")`.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python -m pytest tests/test_info_layout.py tests/test_info_layout_editor.py tests/test_info_tab_render.py tests/test_text_size.py -q`
Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add gui/info_layout.py gui/theme.py gui/info_layout_editor.py tests/test_info_layout.py tests/test_info_layout_editor.py tests/test_info_tab_render.py
git commit -m "feat(info-layout): 2X-Large/3X-Large value and label sizes; preview follows text size"
```

---

### Task 5: Settings dialog "Text size" row

**Files:**
- Modify: `gui/settings_dialog.py` (after the Theme row, ≈line 95; `result_settings`)
- Test: `tests/test_text_size.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_text_size.py`:

```python
# ── settings dialog ────────────────────────────────────────────────────────

_BASE_SETTINGS = {"db_path": "", "events_db_path": "", "theme": "dark",
                  "google_api_key": "", "show_row_ids": False}


@pytest.mark.parametrize("name", ["normal", "large", "xlarge"])
def test_settings_dialog_roundtrips_text_size(qapp, name):
    from gui.settings_dialog import SettingsDialog
    dlg = SettingsDialog({**_BASE_SETTINGS, "text_size": name})
    assert dlg.result_settings()["text_size"] == name


def test_settings_dialog_text_size_defaults_to_normal_when_missing(qapp):
    from gui.settings_dialog import SettingsDialog
    dlg = SettingsDialog(dict(_BASE_SETTINGS))
    assert dlg._radio_size_normal.isChecked()
    assert dlg.result_settings()["text_size"] == "normal"
    dlg._radio_size_xlarge.setChecked(True)
    assert dlg.result_settings()["text_size"] == "xlarge"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_text_size.py -k settings_dialog -q`
Expected: FAIL with `KeyError: 'text_size'`

- [ ] **Step 3: Add the row**

In `gui/settings_dialog.py`, directly after `form.addRow("Theme:", theme_row)` insert:

```python
        # App-wide text size. Large/Extra Large enlarge every on-screen font
        # (and the rows/panels that hold text); the main window reopens to
        # apply it. Printouts are unaffected.
        size_row = QWidget()
        size_hl = QHBoxLayout(size_row)
        size_hl.setContentsMargins(0, 0, 0, 0)
        self._radio_size_normal = QRadioButton("Normal")
        self._radio_size_large = QRadioButton("Large")
        self._radio_size_xlarge = QRadioButton("Extra Large")
        self._text_size_group = QButtonGroup()
        for b in (self._radio_size_normal, self._radio_size_large,
                  self._radio_size_xlarge):
            self._text_size_group.addButton(b)
            size_hl.addWidget(b)
        current = self._settings.get("text_size", "normal")
        {"large": self._radio_size_large,
         "xlarge": self._radio_size_xlarge}.get(
            current, self._radio_size_normal).setChecked(True)
        size_row.setToolTip(
            "Make all text in the program larger. The window reopens to apply "
            "the new size; printed reports keep their normal size.")
        form.addRow("Text size:", size_row)
```

In `result_settings()` add the key:

```python
            "show_row_ids": self._show_row_ids.isChecked(),
            "text_size": ("xlarge" if self._radio_size_xlarge.isChecked()
                          else "large" if self._radio_size_large.isChecked()
                          else "normal"),
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_text_size.py tests/test_settings.py tests/test_row_id_column.py -q`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add gui/settings_dialog.py tests/test_text_size.py
git commit -m "feat(settings): Text size row (Normal / Large / Extra Large)"
```

---

### Task 6: Main window — scaled sidebar and geometry, reopen on text-size change

**Files:**
- Modify: `gui/main_window.py` (imports, `__init__`, `_apply_default_geometry`, sidebar ≈line 260, counts label ≈line 306, `_jump_to_member`, `_open_settings`)
- Test: `tests/test_text_size.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_text_size.py`:

```python
# ── main window ────────────────────────────────────────────────────────────

def _main_window(tmp_path, **settings):
    from gui.main_window import MainWindow
    return MainWindow({"db_path": "", "theme": "dark", **settings},
                      str(tmp_path / "settings.json"))


def test_sidebar_and_startup_size_follow_text_scale(qapp, tmp_path):
    from gui import theme
    theme.set_text_size("xlarge")
    w = _main_window(tmp_path, text_size="xlarge")
    from PyQt6.QtWidgets import QWidget
    sidebar = w.findChild(QWidget, "sidebar")
    # setFixedWidth pins min == max; width() is unreliable before show().
    assert sidebar.minimumWidth() == sidebar.maximumWidth() == theme.px(220) == 508
    assert w._member_counts.styleSheet() == f"font-size:{theme.px(12)}px;"


class _FakeSettingsDialog:
    """Stands in for SettingsDialog: accepted immediately with a fixed result."""
    result = {}

    def __init__(self, settings, parent=None, alt_id_password=""):
        self._settings = dict(settings)

    def exec(self):
        return True

    def result_settings(self):
        return {**self._settings, **self.result}

    def result_alt_id_password(self):
        return ""


def _saved(tmp_path):
    import json
    return json.loads((tmp_path / "settings.json").read_text())


def test_text_size_change_requests_reopen_on_current_member(qapp, tmp_path, monkeypatch):
    import gui.main_window as mw
    w = _main_window(tmp_path)
    w._last_center_id = 4242
    _FakeSettingsDialog.result = {"text_size": "large"}
    monkeypatch.setattr(mw, "SettingsDialog", _FakeSettingsDialog)
    monkeypatch.setattr(w, "_ok_to_leave_current", lambda: True)
    w._open_settings()
    assert w.reopen_requested is True
    assert w.reopen_member_id == 4242
    assert _saved(tmp_path)["text_size"] == "large"


def test_cancelling_discard_reverts_text_size_but_saves_the_rest(qapp, tmp_path, monkeypatch):
    import gui.main_window as mw
    w = _main_window(tmp_path)
    _FakeSettingsDialog.result = {"text_size": "xlarge", "show_row_ids": True}
    monkeypatch.setattr(mw, "SettingsDialog", _FakeSettingsDialog)
    monkeypatch.setattr(w, "_ok_to_leave_current", lambda: False)
    w._open_settings()
    assert w.reopen_requested is False
    saved = _saved(tmp_path)
    assert saved["text_size"] == "normal"
    assert saved["show_row_ids"] is True


def test_theme_only_change_does_not_reopen(qapp, tmp_path, monkeypatch):
    import gui.main_window as mw
    w = _main_window(tmp_path)
    _FakeSettingsDialog.result = {"theme": "light"}
    monkeypatch.setattr(mw, "SettingsDialog", _FakeSettingsDialog)
    w._open_settings()
    assert w.reopen_requested is False
    assert _saved(tmp_path)["theme"] == "light"
    from gui.theme import apply_theme
    apply_theme(qapp, "dark")          # leave the shared app on the default


def test_jump_to_member_is_public(qapp, tmp_path):
    w = _main_window(tmp_path)
    assert callable(w.jump_to_member)
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/test_text_size.py -k "main_window or sidebar or reopen or revert or jump or theme_only" -q`
Expected: FAIL (`AttributeError: 'MainWindow' object has no attribute 'reopen_requested'`, sidebar width 220, no `jump_to_member`)

- [ ] **Step 3: Import `px` and add the reopen state**

At the top of `gui/main_window.py` change the imports:

```python
from settings import save_settings
from gui.settings_dialog import SettingsDialog
from gui.theme import px
```

In `__init__`, after `self._alt_id_password = ""` add:

```python
        # Set by _open_settings when the text size changes: the window closes
        # and member_manager.run() rebuilds it at the new scale, reopening the
        # same member (row heights and panel widths are fixed at construction).
        self.reopen_requested = False
        self.reopen_member_id = None
```

- [ ] **Step 4: Scale geometry, sidebar and counts label**

In `_apply_default_geometry` change `desired = QSize(1800, 920)` to:

```python
        desired = QSize(px(1800), px(920))
```

and the docstring's first line to `"""Open at 1800x920 at Normal text size (scaled with the text size; wide ...`.

Sidebar (≈line 260): `sidebar.setFixedWidth(px(220))`.

Counts label (≈line 306): `self._member_counts.setStyleSheet(f"font-size:{px(12)}px;")`.

- [ ] **Step 5: Public `jump_to_member`**

Directly above `def _jump_to_member(self, center_id):` add:

```python
    def jump_to_member(self, center_id) -> None:
        """Open a member by id — used by member_manager.run() to restore the
        open member after a text-size rebuild."""
        self._jump_to_member(center_id)
```

- [ ] **Step 6: Rewrite `_open_settings`**

Replace the whole method with:

```python
    def _open_settings(self):
        dlg = SettingsDialog(self._settings, self,
                             alt_id_password=self._alt_id_password)
        if not dlg.exec():
            return
        result = dlg.result_settings()
        old_size = self._settings.get("text_size", "normal")
        size_changed = result.get("text_size", "normal") != old_size
        # A text-size change rebuilds the window, which drops unsaved edits —
        # run the same guard as switching members. On Cancel the size reverts
        # (nothing half-applied) while every other setting still saves.
        if size_changed and not self._ok_to_leave_current():
            result["text_size"] = old_size
            size_changed = False
        self._settings.update(result)
        save_settings(self._settings, self._settings_path)
        self._alt_id_password = dlg.result_alt_id_password()
        # First key derivation (PBKDF2) blocks ~0.15s — warm it here under
        # a wait cursor; every later use hits the cache.
        QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self._alt_id_key()
        finally:
            QGuiApplication.restoreOverrideCursor()
        # Drop cached DB handles so the new path is used on next access.
        from db.members import close_connections
        close_connections()
        if size_changed:
            # member_manager.run() sees the flag once exec() returns and
            # rebuilds the window at the new scale on the same member.
            self.reopen_requested = True
            self.reopen_member_id = self._last_center_id
            self.close()
            return
        from gui.theme import apply_theme
        apply_theme(QApplication.instance(), self._settings["theme"],
                    self._settings.get("text_size", "normal"))
        self._refresh_list_theme()
        self._update_db_indicator()
        self._load_members()
        # Apply the row-ID debug toggle and the alt-id key to the open
        # member live (no rebuild, so unsaved edits survive).
        from gui.member_tabs import MemberTabsWidget
        current = (self._detail_stack.widget(1)
                   if self._detail_stack.count() > 1 else None)
        if isinstance(current, MemberTabsWidget):
            current.set_show_row_ids(self._settings.get("show_row_ids", False))
            current.set_alt_id_key(self._alt_id_key())
```

(`_open_settings` is the last method in the file and ends at `current.set_alt_id_key(...)`; the replacement covers it entirely.)

- [ ] **Step 7: Run the tests to verify they pass**

Run: `python -m pytest tests/test_text_size.py tests/test_startup_geometry.py tests/test_bookmark_button.py tests/test_sidebar_counts.py -q`
Expected: all PASS

- [ ] **Step 8: Commit**

```bash
git add gui/main_window.py tests/test_text_size.py
git commit -m "feat(gui): main window scales sidebar/geometry and reopens on text-size change"
```

---

### Task 7: `member_manager.run(app)` rebuild loop

**Files:**
- Modify: `member_manager.py:59-71`
- Test: `tests/test_text_size.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_text_size.py`:

```python
# ── entry point loop ───────────────────────────────────────────────────────

def test_run_rebuilds_window_once_when_requested(monkeypatch, tmp_path):
    import member_manager as mm

    created = []

    class StubWindow:
        def __init__(self, settings, path):
            self.settings = settings
            self.jumped = None
            self.password = None
            # First window asks to reopen on member 7; the second does not.
            self.reopen_requested = len(created) == 0
            self.reopen_member_id = 7 if self.reopen_requested else None
            self.reopen_alt_id_password = "hunter2" if self.reopen_requested else ""
            created.append(self)

        def show(self):
            pass

        def set_alt_id_password(self, pw):
            self.password = pw

        def jump_to_member(self, cid):
            self.jumped = cid

    class StubApp:
        execs = 0

        def exec(self):
            StubApp.execs += 1
            return 0

    applied = []
    sizes = iter(["xlarge", "xlarge"])
    monkeypatch.setattr(mm, "MainWindow", StubWindow)
    monkeypatch.setattr(mm, "apply_theme",
                        lambda app, theme, text_size="normal": applied.append((theme, text_size)))
    monkeypatch.setattr(mm, "load_settings",
                        lambda path: {"theme": "light", "text_size": next(sizes),
                                      "events_db_path": "x"})
    monkeypatch.setattr(mm, "SETTINGS_PATH", str(tmp_path / "s.json"))

    code = mm.run(StubApp())

    assert code == 0
    assert StubApp.execs == 2
    assert len(created) == 2
    assert created[0].jumped is None
    assert created[1].jumped == 7
    assert created[0].password == "" and created[1].password == "hunter2"
    assert applied == [("light", "xlarge"), ("light", "xlarge")]
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_text_size.py::test_run_rebuilds_window_once_when_requested -q`
Expected: FAIL with `AttributeError: module 'member_manager' has no attribute 'run'`

- [ ] **Step 3: Extract the loop**

In `member_manager.py` replace `main()` with:

```python
def run(app) -> int:
    """Build the main window and run the event loop; rebuild the window when
    it asks to be reopened (a text-size change) and exit otherwise.

    Settings are re-read on every pass so the rebuilt window and the freshly
    applied theme see the size the user just saved."""
    reopen_id = None
    reopen_password = ""
    while True:
        settings = load_settings(SETTINGS_PATH)
        if ensure_events_path(settings):
            save_settings(settings, SETTINGS_PATH)   # persist the appdata default
        apply_theme(app, settings.get("theme", "dark"),
                    settings.get("text_size", "normal"))
        window = MainWindow(settings, SETTINGS_PATH)
        # Session-only alt-id password survives the rebuild (it is never
        # written to disk, so it has to be carried in memory).
        window.set_alt_id_password(reopen_password)
        window.show()
        if reopen_id is not None:
            window.jump_to_member(reopen_id)
        code = app.exec()
        if not getattr(window, "reopen_requested", False):
            return code
        reopen_id = window.reopen_member_id
        reopen_password = window.reopen_alt_id_password


def main():
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(_resource_path("bowery-emblem.ico")))
    crash_log.install()
    sys.exit(run(app))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_text_size.py tests/test_events_path.py -q`
Expected: all PASS

- [ ] **Step 5: Smoke-run the app**

Run: `python main.py` — the app opens as before. Open Settings, pick Extra Large, OK: the window closes and reopens with big text in the sidebar and toolbar (member tabs are scaled in Tasks 8–10). Set it back to Normal and quit.

- [ ] **Step 6: Commit**

```bash
git add member_manager.py tests/test_text_size.py
git commit -m "feat(app): run() loop rebuilds the main window after a text-size change"
```

---

### Task 8: `gui/member_tabs.py` — inline sizes and text-holding dimensions

**Files:**
- Modify: `gui/member_tabs.py`
- Test: `tests/test_text_size.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_text_size.py`:

```python
# ── no literal font sizes left in widget code ──────────────────────────────

# Files converted so far; Tasks 9 and 10 extend this list until it covers
# every widget module. theme.py (the QSS) and profile_print.py (printouts,
# deliberately unscaled) are excluded by design.
_CONVERTED = [
    "gui/member_tabs.py",
    "gui/main_window.py",
    "gui/info_layout_editor.py",
]

_LITERAL_FONT_SIZE = re.compile(r"font-size:\s*\d+px")
_LITERAL_ROW_HEIGHT = re.compile(r"setDefaultSectionSize\(\s*\d+\s*\)")


@pytest.mark.parametrize("rel", _CONVERTED)
def test_no_literal_font_sizes_or_row_heights(rel):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = open(os.path.join(root, rel), encoding="utf-8").read()
    assert not _LITERAL_FONT_SIZE.findall(src), rel
    assert not _LITERAL_ROW_HEIGHT.findall(src), rel


def test_member_table_row_height_follows_scale(qapp):
    """Same bare-widget setup as tests/test_emergency_table.py::_info_tab_with:
    _make_info_tab builds the emergency-contacts table without a database."""
    from PyQt6.QtWidgets import QLabel
    from gui import theme
    import gui.member_tabs as mt
    theme.set_text_size("large")
    w = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)
    w._member = {"first_name": "A", "last_name": "B"}
    w._center_id = 1
    w._db_path = ""
    w._api_key = ""
    w._enrollments = []
    w._authorizations = []
    w._emergency_contacts = [{"id": 1, "full_name": "Andy Lau",
                              "phone": "(917) 628-0459", "relationship": "Son"}]
    w._emergency_badge = QLabel()
    w._test_outer = w._make_info_tab()   # keep a ref so children aren't GC'd
    assert w._emergency_table.verticalHeader().defaultSectionSize() == theme.px(34) == 65
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python -m pytest tests/test_text_size.py -k "literal or row_height" -q`
Expected: the `main_window.py` and `info_layout_editor.py` cases already PASS (Tasks 4 and 6); the `member_tabs.py` case and `test_member_table_row_height_follows_scale` FAIL

- [ ] **Step 3: Import `px`**

At the top of `gui/member_tabs.py` after `from PyQt6.QtCore import Qt, pyqtSignal` add:

```python
from gui.theme import px
```

- [ ] **Step 4: Convert each site**

Make these exact edits (line numbers approximate; search for the text):

```python
# _NotesEdit._fit (≈line 50)
        self.setFixedHeight(max(px(self._MIN_H), min(h, px(self._MAX_H))))

# make_plan_badge (≈line 82)
    badge.setMaximumHeight(px(max_height))

# _fit_pill_column (≈line 146)
    width = max(widest + 2 * _PILL_CELL_HMARGIN + 4, px(floor))

# terminated badge in header refresh (≈line 1012)
            badge.setMaximumHeight(px(26))

# bookmark note editor (≈line 1283)
        note_edit.setFixedHeight(px(64))

# bookmark note counter (≈line 1305)
                f"font-size:{px(11)}px; color:"

# header ID label (≈line 1364)
            f"<span style='font-size:{px(17)}px; font-weight:700; color:#5b7cf4'>"

# header name label (≈line 1395)
            f"<span style='font-size:{px(16)}px; font-weight:700'>{name}</span>")

# header badges/buttons (≈lines 1413, 1422, 1429, 1435, 1443, 1460) — all six
            ....setMaximumHeight(px(26))

# emergency contacts table (≈line 1963)
        table.verticalHeader().setDefaultSectionSize(px(34))

# tables (≈lines 2399, 2501, 2794, 3304, 4262, 4505, 4685)
        table.verticalHeader().setDefaultSectionSize(px(34))   # 34 → px(34)
        table.verticalHeader().setDefaultSectionSize(px(40))   # 40 → px(40)
        table.verticalHeader().setDefaultSectionSize(px(36))   # 36 → px(36)

# Enrollments action column (≈line 2542)
        table.setColumnWidth(4, max(widest + 36, px(140)))

# HHA note card (≈lines 3854-3878)
        card.setMinimumWidth(px(260))
        card.setMaximumWidth(px(400))
        ...
            f"font-size: {px(12)}px; font-weight: 700;")
        ...
            f"color: {t['accent_text']}; font-size: {px(13)}px; font-weight: 700; "
        ...
            f"color: {t['accent_text']}; font-size: {px(13)}px; "

# Authorizations table (≈lines 3927-3928)
        ROW_H = px(40)                # roomier rows; pills uncramped
        table.verticalHeader().setDefaultSectionSize(ROW_H)

# Authorizations edit column (≈line 3995)
        table.setColumnWidth(7, max(edit_w + 2 * _PILL_CELL_HMARGIN + 24, px(116)))

# scheduled-change icon buttons (≈lines 4288, 4295)
                edit.setFixedWidth(px(28))
                dele.setFixedWidth(px(28))

# notes editors in absence dialogs (≈lines 4556, 4735)
        notes_edit.setFixedHeight(px(60))
```

Verify nothing was missed:

```bash
grep -nE "font-size:\s*[0-9]+px|setDefaultSectionSize\([0-9]|setMaximumHeight\(26\)|setFixedWidth\(2[68]\)|setFixedHeight\(6[04]\)" gui/member_tabs.py
```

Expected: no output.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/test_text_size.py tests/test_info_tab_render.py tests/test_header_layout.py tests/test_hha_note_card.py tests/test_schedule_card.py tests/test_emergency_table.py -q`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add gui/member_tabs.py tests/test_text_size.py
git commit -m "feat(member-tabs): inline font sizes and text-holding dimensions follow the text size"
```

---

### Task 9: Smaller widget files — inline sizes and dimensions

**Files:**
- Modify: `gui/bookmarks_panel.py`, `gui/notifications.py`, `gui/confirm_changes.py`, `gui/events_view.py`, `gui/expiring_report.py`, `gui/address_autocomplete.py`, `gui/time_range_editor.py`, `gui/company_calendar.py`, `gui/profile_print.py`
- Test: `tests/test_text_size.py`

- [ ] **Step 1: Extend the guard list (failing)**

In `tests/test_text_size.py` extend `_CONVERTED`:

```python
_CONVERTED = [
    "gui/member_tabs.py",
    "gui/main_window.py",
    "gui/info_layout_editor.py",
    "gui/bookmarks_panel.py",
    "gui/notifications.py",
    "gui/confirm_changes.py",
    "gui/events_view.py",
    "gui/expiring_report.py",
    "gui/address_autocomplete.py",
    "gui/time_range_editor.py",
]
```

(The two point-size fonts are guarded by the `_LITERAL_POINT_SIZE` regex the
Task 8 review added to the same test — `QFont(..., 10)` fails it, `QFont(..., px(10))` passes — so no separate source-substring test is needed.)

- [ ] **Step 2: Run to verify the new entries fail**

Run: `python -m pytest tests/test_text_size.py -k "literal" -q`
Expected: the seven new files FAIL (events_view and time_range_editor on the point-size guard as well)

- [ ] **Step 3: Convert each file**

`gui/bookmarks_panel.py` — change the import and four sites:

```python
from gui.theme import current_tokens, px
...
            note_lbl.setStyleSheet(f"color:{t['text']}; font-size:{px(11)}px;")
...
        date_lbl.setStyleSheet(f"color:{t['text3']}; font-size:{px(10)}px;")
...
        btn.setFixedWidth(px(26))
...
        self.setFixedWidth(px(380))
...
        self._scroll.setFixedHeight(px(260))
```

`gui/notifications.py`:

```python
from gui.theme import current_tokens, px
...
        sub.setStyleSheet(f"color:{sub_color}; font-size:{px(11)}px;")
...
        self.setFixedWidth(px(360))
...
        self._scroll.setFixedHeight(px(220))
```

`gui/confirm_changes.py` — add a top-level import after the PyQt imports and change three sites:

```python
from gui.theme import px
...
        f"padding:6px 8px; font-size:{px(13)}px;")
...
        heading.setStyleSheet(f"font-size:{px(15)}px; font-weight:600;")
...
            arrow.setStyleSheet(f"color:{t['text2']}; font-size:{px(18)}px;")
```

`gui/events_view.py`:

```python
from gui.theme import event_badge_colors, format_member_counts, current_tokens, px
...
            title.setStyleSheet(f"font-size:{px(15)}px; font-weight:600;")
            ttl_lbl = QLabel("Auto-deletes after 30 days")
            ttl_lbl.setStyleSheet(f"font-size:{px(10)}px; color: gray;")
...
                counts.setStyleSheet(f"font-size:{px(12)}px;")
...
        mono_font = QFont("Cascadia Mono, Consolas", px(10))
```

`gui/expiring_report.py` — add `from gui.theme import px` after the PyQt imports and:

```python
            b.setStyleSheet(f"font-size:{px(11)}px; padding:1px 8px;")
```

`gui/address_autocomplete.py` — add `from gui.theme import px` after the QtNetwork import and:

```python
        self._status.setStyleSheet(f"color:#3d9e6e; font-size:{px(10)}px;")
...
        self._status.setStyleSheet(f"color:{color}; font-size:{px(10)}px;")
```

`gui/time_range_editor.py` — add `from gui.theme import px` after the QtGui import and:

```python
        self.setMinimumHeight(px(60))
...
        p.setFont(QFont("Segoe UI", px(7)))
...
        self._readout.setStyleSheet(f"font-size:{px(16)}px; font-weight:700;")
```

`gui/company_calendar.py` — add `from gui.theme import px` after the PyQt imports and:

```python
        self.edit.setFixedWidth(px(64))
...
        self._date_edit.setFixedWidth(px(110))
```

`gui/profile_print.py` — only the on-screen printer picker changes (the printed HTML keeps its point scale). Add `from gui.theme import px` next to the other `gui`/`db` imports and:

```python
    combo.setMaximumWidth(px(240))
```

Verify:

```bash
grep -nE "font-size:\s*[0-9]+px" gui/bookmarks_panel.py gui/notifications.py gui/confirm_changes.py gui/events_view.py gui/expiring_report.py gui/address_autocomplete.py gui/time_range_editor.py
```

Expected: no output.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_text_size.py tests/test_bookmarks.py tests/test_notifications.py tests/test_confirm_changes.py tests/test_expiring_report.py tests/test_address_autocomplete.py tests/test_company_calendar_dialog.py tests/test_time_range_editor.py -q`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add gui/bookmarks_panel.py gui/notifications.py gui/confirm_changes.py gui/events_view.py gui/expiring_report.py gui/address_autocomplete.py gui/time_range_editor.py gui/company_calendar.py gui/profile_print.py tests/test_text_size.py
git commit -m "feat(gui): panels, dialogs and reports follow the text size"
```

---

### Task 10: Wizard files

**Files:**
- Modify: `gui/wizard/wizard.py`, `gui/wizard/step_auths.py`, `gui/wizard/step_contact.py`, `gui/wizard/step_enrollment.py`, `gui/wizard/step_review.py`
- Test: `tests/test_text_size.py`

- [ ] **Step 1: Extend the guard list (failing)**

Append to `_CONVERTED` in `tests/test_text_size.py`:

```python
    "gui/wizard/wizard.py",
    "gui/wizard/step_auths.py",
    "gui/wizard/step_contact.py",
    "gui/wizard/step_enrollment.py",
    "gui/wizard/step_review.py",
```

and add:

```python
def test_wizard_dots_scale_and_stay_round(qapp):
    from gui import theme
    theme.set_text_size("xlarge")
    from gui.wizard.wizard import AddMemberWizard
    wiz = AddMemberWizard("", "")
    dot = wiz._dots[0]
    assert dot.width() == dot.height() == theme.px(28) == 65
    assert f"border-radius:{theme.px(14)}px" in dot.styleSheet()
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_text_size.py -k "literal or wizard" -q`
Expected: the five wizard files FAIL; `wizard_dots` FAILS (28 ≠ 65)

- [ ] **Step 3: Convert the files**

`gui/wizard/wizard.py` — add `from gui.theme import px` after `from PyQt6.QtCore import Qt` and:

```python
            dot.setFixedSize(px(28), px(28))
...
                line.setFixedWidth(px(64))
...
            lbl.setFixedWidth(px(84))
...
            lbl.setStyleSheet(f"font-size:{px(10)}px; color:#31354a;")
```

and `_dot_style`:

```python
    def _dot_style(self, dot_index: int, current: int) -> str:
        r, fs = px(14), px(11)     # radius = half the dot so it stays a circle
        if dot_index < current:
            return (f"background:#3d9e6e; color:white; border-radius:{r}px;"
                    f"font-weight:700; font-size:{fs}px;")
        if dot_index == current:
            return (f"background:#5b7cf4; color:white; border-radius:{r}px;"
                    f"font-weight:700; font-size:{fs}px; border:3px solid #1c2040;")
        return (f"background:#1e2128; color:#31354a; border-radius:{r}px;"
                f"border:1px solid #282c38; font-size:{fs}px;")
```

`gui/wizard/step_auths.py` — add `from gui.theme import px` after the `db.members` import and:

```python
        self.setFixedWidth(px(64))
...
        title_auth.setStyleSheet(f"font-weight:600; font-size:{px(11)}px;")
...
        title_transport.setStyleSheet(f"font-weight:600; font-size:{px(11)}px;")
...
        title_avail.setStyleSheet(f"font-weight:600; font-size:{px(11)}px;")
...
        btn_add_day.setStyleSheet(f"color: #5b7cf4; font-size:{px(10)}px; text-align:left;")
```

`gui/wizard/step_contact.py` — add `from gui.theme import px` after the `gui.address_autocomplete` import and:

```python
        self._error_label.setStyleSheet(f"color: #d05555; font-size: {px(11)}px;")
...
        phone_hint.setStyleSheet(f"color: #7a7f93; font-size: {px(10)}px;")
```

`gui/wizard/step_enrollment.py` — add `from gui.theme import px` after the `DateLineEdit` import and:

```python
        note.setStyleSheet(f"color: gray; font-size: {px(11)}px;")
```

`gui/wizard/step_review.py` — add `from gui.theme import px` after `from PyQt6.QtCore import Qt` and:

```python
        title.setStyleSheet(f"font-size:{px(12)}px; color:gray;")
```

Verify:

```bash
grep -rnE "font-size:\s*[0-9]+px" gui/wizard/
```

Expected: no output.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_text_size.py tests/test_step_contact.py tests/test_step_enrollment.py tests/test_step_review.py tests/test_step_auths_time.py tests/test_step_auths_transport.py tests/test_step_auth_number.py -q`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add gui/wizard/ tests/test_text_size.py
git commit -m "feat(wizard): step indicator and hints follow the text size"
```

---

### Task 11: Full verification, manual check, docs

**Files:**
- Modify: `PRODUCT.md` (Key Surfaces / Tech Stack note), `docs/superpowers/specs/2026-09-11-text-size-mode-design.md` (status)

- [ ] **Step 1: Run the whole suite**

Run: `python -m pytest tests -q`
Expected: all PASS (integration tests that need the Access DB self-skip)

- [ ] **Step 2: Manual check in the real app**

Run: `python main.py`

1. Settings → Text size → **Extra Large** → OK. The window closes and reopens; sidebar, toolbar, tabs, tables, badges and the header are all large; no clipped rows or buttons.
2. Open a member with a bookmark note and an Authorizations table; check row heights and the Edit column fit.
2b. Availability tab at Extra Large for a member with Saturday availability: the current-schedule strip (`_make_current_schedule_strip`) needs ~1430px for six day cells on a 1920 screen, which is wider than the detail pane. If the rightmost day clips, wrap the strip in a `QScrollArea` with vertical scrolling off and horizontal on demand.
3. Add New Member: the step dots are round and readable.
4. Edit a field, then Settings → **Normal** → OK → the Unsaved Changes prompt appears → **Cancel**: window stays at Extra Large, text size still Extra Large in Settings on reopening the dialog.
5. Discard or save the edit, switch to **Normal**: window reopens at the original size on the same member.
6. Print preview of a profile still uses the compact scale.

Fix anything that clips by routing that dimension through `px()` in the owning file, add it to the plan's file list in the commit message, and rerun the suite.

- [ ] **Step 3: Record the surface**

In `PRODUCT.md` under "Key Surfaces" add:

```markdown
- Settings → Text size (Normal / Large / Extra Large): app-wide on-screen font scaling; printouts unaffected
```

In the spec header change `**Status:** Approved` to `**Status:** Implemented`.

- [ ] **Step 4: Commit**

```bash
git add PRODUCT.md docs/superpowers/specs/2026-09-11-text-size-mode-design.md
git commit -m "docs: record the Text size setting; mark spec implemented"
```

- [ ] **Step 5: Finish the branch**

Use the `superpowers:finishing-a-development-branch` skill to merge `feature/text-size-mode` into `main` (or open a PR), per the user's choice.
