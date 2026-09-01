# Customizable Info Tab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user rearrange the member Info tab (custom sections, field order, visibility) and style fields (span, bold, size, highlight) through a WYSIWYG editor dialog, persisted per-machine in the settings JSON.

**Architecture:** A pure-Python layout model (`gui/info_layout.py`: registry, default layout, normalize, flow placement, mutation helpers) drives both the Info tab renderer (`MemberTabsWidget._make_info_tab` walks the layout instead of hardcoding the grid) and a new preview+properties editor dialog (`gui/info_layout_editor.py`). Styling is applied via dynamic Qt properties matched by new theme QSS rules.

**Tech Stack:** Python 3, PyQt6, pytest (offscreen Qt tests via `QT_QPA_PLATFORM=offscreen`), JSON settings file (`settings.py`).

**Spec:** `docs/superpowers/specs/2026-09-01-customizable-info-tab-design.md`

**Working notes for the implementer:**
- Run tests with `python -m pytest <file> -v` from the repo root.
- Qt test files must start with `import os` / `os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")` *before* any PyQt import, and use the module-scoped `qapp` fixture shown in `tests/test_alt_id_header.py`.
- `gui/member_tabs.py` is large; the Info tab code is `_make_info_tab` (~line 1593) and `_build_ui` (~line 1293). `MemberTabsWidget.__init__` is ~line 760.
- Commit after every task with the exact message given. All commit messages end with:
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`

---

### Task 1: Layout model — registry, default layout, flow placement

**Files:**
- Create: `gui/info_layout.py`
- Test: `tests/test_info_layout.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_info_layout.py
"""Pure-model tests for the customizable Info tab layout (no Qt)."""


def test_default_layout_shape():
    from gui.info_layout import default_layout
    lay = default_layout()
    assert lay["version"] == 1
    types = [b["type"] for b in lay["blocks"]]
    assert types[0] == "schedule"
    assert types[-1] == "emergency"
    titles = [b["title"] for b in lay["blocks"] if b["type"] == "section"]
    assert titles == ["Identity", "Contact", "Medical", "Care"]


def test_default_layout_covers_registry_exactly_once():
    from gui.info_layout import default_layout, FIELD_REGISTRY
    lay = default_layout()
    keys = [f["key"] for b in lay["blocks"] if b["type"] == "section"
            for f in b["fields"]]
    assert sorted(keys) == sorted(k for k, _ in FIELD_REGISTRY)
    assert len(keys) == len(set(keys))


def test_default_layout_spans_and_legacy_hidden():
    from gui.info_layout import default_layout
    lay = default_layout()
    by_key = {f["key"]: f for b in lay["blocks"] if b["type"] == "section"
              for f in b["fields"]}
    assert by_key["address"]["span"] == 3
    assert by_key["pcp"]["span"] == 3
    assert by_key["hha"]["span"] == 3
    assert by_key["first_name"]["span"] == 1
    # The legacy Contacts.[Emergency] text field exists but is hidden by
    # default (it is not placed on today's tab either).
    assert by_key["emergency"]["visible"] is False
    assert by_key["first_name"]["visible"] is True


def test_placements_flow_and_wrap():
    from gui.info_layout import placements
    fields = [
        {"key": "a", "span": 1, "visible": True},
        {"key": "b", "span": 1, "visible": True},
        {"key": "c", "span": 1, "visible": True},
        {"key": "d", "span": 2, "visible": True},   # row 1, slots 0-1
        {"key": "e", "span": 1, "visible": True},   # row 1, slot 2
        {"key": "f", "span": 3, "visible": True},   # wraps to row 2
    ]
    out = [(f["key"], row, slot, span)
           for f, row, slot, span in placements(fields)]
    assert out == [("a", 0, 0, 1), ("b", 0, 1, 1), ("c", 0, 2, 1),
                   ("d", 1, 0, 2), ("e", 1, 2, 1), ("f", 2, 0, 3)]


def test_placements_skips_hidden_by_default():
    from gui.info_layout import placements
    fields = [
        {"key": "a", "span": 1, "visible": True},
        {"key": "h", "span": 1, "visible": False},
        {"key": "b", "span": 1, "visible": True},
    ]
    assert [f["key"] for f, *_ in placements(fields)] == ["a", "b"]
    assert [f["key"] for f, *_ in placements(fields, include_hidden=True)] \
        == ["a", "h", "b"]


def test_placements_wide_span_wraps_when_row_partial():
    from gui.info_layout import placements
    fields = [
        {"key": "a", "span": 2, "visible": True},   # row 0, slots 0-1
        {"key": "b", "span": 2, "visible": True},   # doesn't fit -> row 1
    ]
    out = [(f["key"], row, slot) for f, row, slot, _ in placements(fields)]
    assert out == [("a", 0, 0), ("b", 1, 0)]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_info_layout.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'gui.info_layout'`

- [ ] **Step 3: Write the implementation**

```python
# gui/info_layout.py
"""Layout model for the customizable member Info tab.

Pure Python (no Qt): the field registry, the default layout matching the
classic tab, saved-layout normalization, the 3-column flow placement used by
both the tab renderer and the editor preview, and the mutation helpers the
editor dialog calls. The layout dict is stored per-machine under the
``info_tab_layout`` settings key.

Layout schema (version 1)::

    {"version": 1, "blocks": [
        {"type": "schedule", "visible": true},
        {"type": "section", "title": "Identity", "fields": [
            {"key": "first_name", "span": 1, "bold": false,
             "size": "normal", "color": "none", "visible": true},
            ...]},
        {"type": "emergency", "visible": true},
    ]}
"""

# Canonical customizable fields, in default display order. Keys match the
# member-dict keys _make_info_tab already uses. "emergency" is the legacy
# Contacts.[Emergency] text column: its widget must keep existing (saving
# reads it) but it is hidden by default, exactly like today.
FIELD_REGISTRY = (
    ("first_name", "First Name"),
    ("last_name", "Last Name"),
    ("chinese_name", "Chinese Name"),
    ("gender", "Gender"),
    ("dob", "DOB"),
    ("ssn", "SSN"),
    ("center_id", "Center ID"),
    ("enrollment_start", "Enrollment Start"),
    ("language", "Language Spoken"),
    ("alt_id", "Alt ID"),
    ("address", "Address"),
    ("home_tell", "Home Phone"),
    ("cell", "Cell"),
    ("emergency", "Emergency (legacy)"),
    ("health_plan", "Health Plan"),
    ("member_id", "Member ID"),
    ("medicaid", "Medicaid"),
    ("medicare", "Medicare"),
    ("hospital", "Hospital"),
    ("pcp", "PCP"),
    ("hha", "HHA"),
    ("case_manager", "Case Manager"),
)
FIELD_LABELS_BY_KEY = dict(FIELD_REGISTRY)

NCOLS = 3
SIZES = ("normal", "large")
COLORS = ("none", "amber", "blue", "green", "red")


def _field(key, span=1, visible=True):
    return {"key": key, "span": span, "bold": False, "size": "normal",
            "color": "none", "visible": visible}


def default_layout() -> dict:
    """The classic Info tab, expressed as a layout dict."""
    return {"version": 1, "blocks": [
        {"type": "schedule", "visible": True},
        {"type": "section", "title": "Identity", "fields": [
            _field("first_name"), _field("last_name"), _field("chinese_name"),
            _field("gender"), _field("dob"), _field("ssn"),
            _field("center_id"), _field("enrollment_start"),
            _field("language"), _field("alt_id"),
        ]},
        {"type": "section", "title": "Contact", "fields": [
            _field("address", span=3), _field("home_tell"), _field("cell"),
            _field("emergency", visible=False),
        ]},
        {"type": "section", "title": "Medical", "fields": [
            _field("health_plan"), _field("member_id"), _field("medicaid"),
            _field("medicare"), _field("hospital"),
            _field("pcp", span=3), _field("hha", span=3),
        ]},
        {"type": "section", "title": "Care", "fields": [
            _field("case_manager"),
        ]},
        {"type": "emergency", "visible": True},
    ]}


def placements(fields, include_hidden=False):
    """Flow a section's fields into the 3-column grid: left to right, a field
    that doesn't fit the remaining slots wraps to the next row. Returns
    [(field_dict, row, slot, span), ...]. Hidden fields are skipped unless
    include_hidden (the editor preview shows them dimmed in place)."""
    out = []
    row, slot = 0, 0
    for f in fields:
        if not f.get("visible", True) and not include_hidden:
            continue
        span = max(1, min(NCOLS, int(f.get("span", 1))))
        if slot + span > NCOLS:
            row += 1
            slot = 0
        out.append((f, row, slot, span))
        slot += span
        if slot >= NCOLS:
            row += 1
            slot = 0
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_info_layout.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add gui/info_layout.py tests/test_info_layout.py
git commit -m "feat: Info tab layout model — registry, default layout, flow placement"
```

---

### Task 2: Layout model — normalize()

**Files:**
- Modify: `gui/info_layout.py`
- Test: `tests/test_info_layout.py`

- [ ] **Step 1: Write the failing tests** (append to `tests/test_info_layout.py`)

```python
# ── normalize ──────────────────────────────────────────────────────────────

def test_normalize_garbage_returns_default():
    from gui.info_layout import normalize, default_layout
    assert normalize(None) == default_layout()
    assert normalize("nonsense") == default_layout()
    assert normalize({"version": 1}) == default_layout()
    assert normalize({"version": 1, "blocks": "oops"}) == default_layout()


def test_normalize_valid_layout_roundtrips():
    import json
    from gui.info_layout import normalize, default_layout
    lay = default_layout()
    assert normalize(json.loads(json.dumps(lay))) == lay


def test_normalize_drops_unknown_keys_and_duplicates():
    from gui.info_layout import normalize
    lay = normalize({"version": 1, "blocks": [
        {"type": "section", "title": "Stuff", "fields": [
            {"key": "dob"}, {"key": "no_such_field"}, {"key": "dob"},
        ]},
    ]})
    stuff = [b for b in lay["blocks"] if b["type"] == "section"
             and b["title"] == "Stuff"][0]
    assert [f["key"] for f in stuff["fields"]].count("dob") == 1
    all_keys = [f["key"] for b in lay["blocks"] if b["type"] == "section"
                for f in b["fields"]]
    assert "no_such_field" not in all_keys


def test_normalize_appends_missing_fields_to_default_home_section():
    from gui.info_layout import normalize
    # A saved layout that only mentions two fields, in sections named like
    # the defaults: missing fields land in their default-named section.
    lay = normalize({"version": 1, "blocks": [
        {"type": "section", "title": "Identity", "fields": [{"key": "dob"}]},
        {"type": "section", "title": "Contact", "fields": [{"key": "cell"}]},
    ]})
    identity = [b for b in lay["blocks"] if b.get("title") == "Identity"][0]
    contact = [b for b in lay["blocks"] if b.get("title") == "Contact"][0]
    assert "first_name" in [f["key"] for f in identity["fields"]]
    assert "address" in [f["key"] for f in contact["fields"]]
    # Medical-default fields have no "Medical" section here -> last section.
    assert "medicaid" in [f["key"] for f in contact["fields"]]
    # Every registry key ends up somewhere, exactly once.
    all_keys = [f["key"] for b in lay["blocks"] if b["type"] == "section"
                for f in b["fields"]]
    from gui.info_layout import FIELD_REGISTRY
    assert sorted(all_keys) == sorted(k for k, _ in FIELD_REGISTRY)


def test_normalize_ensures_special_blocks_once():
    from gui.info_layout import normalize
    lay = normalize({"version": 1, "blocks": [
        {"type": "schedule", "visible": False},
        {"type": "section", "title": "A", "fields": [{"key": "dob"}]},
        {"type": "schedule"},              # duplicate -> dropped
    ]})
    types = [b["type"] for b in lay["blocks"]]
    assert types.count("schedule") == 1
    assert types.count("emergency") == 1   # missing -> appended at end
    assert types[-1] == "emergency"
    sched = [b for b in lay["blocks"] if b["type"] == "schedule"][0]
    assert sched["visible"] is False       # first occurrence wins


def test_normalize_clamps_bad_values():
    from gui.info_layout import normalize
    lay = normalize({"version": 1, "blocks": [
        {"type": "section", "title": "A", "fields": [
            {"key": "dob", "span": 99, "size": "huge", "color": "pink",
             "bold": 1, "visible": 0},
        ]},
    ]})
    dob = [f for b in lay["blocks"] if b["type"] == "section"
           for f in b["fields"] if f["key"] == "dob"][0]
    assert dob["span"] == 3
    assert dob["size"] == "normal"
    assert dob["color"] == "none"
    assert dob["bold"] is True
    assert dob["visible"] is False


def test_normalize_no_sections_creates_other():
    from gui.info_layout import normalize
    lay = normalize({"version": 1, "blocks": [{"type": "schedule"}]})
    sections = [b for b in lay["blocks"] if b["type"] == "section"]
    assert len(sections) == 1 and sections[0]["title"] == "Other"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_info_layout.py -v`
Expected: the 7 new tests FAIL with `ImportError: cannot import name 'normalize'`; the Task 1 tests still pass.

- [ ] **Step 3: Write the implementation** (append to `gui/info_layout.py`)

```python
def _clean_field(raw, defaults):
    """One saved field entry -> a complete, clamped field dict."""
    d = dict(defaults)
    if isinstance(raw, dict):
        try:
            span = int(raw.get("span", d["span"]))
        except (TypeError, ValueError):
            span = d["span"]
        d["span"] = max(1, min(NCOLS, span))
        d["bold"] = bool(raw.get("bold", d["bold"]))
        if raw.get("size") in SIZES:
            d["size"] = raw["size"]
        if raw.get("color") in COLORS:
            d["color"] = raw["color"]
        d["visible"] = bool(raw.get("visible", d["visible"]))
    return d


def normalize(layout) -> dict:
    """A saved layout -> a complete, valid layout. Unknown/duplicate field
    keys are dropped, registry fields the layout lacks are appended to their
    default-titled section (fallback: last section, or a new 'Other'),
    schedule/emergency blocks appear exactly once, values are clamped.
    Unusable input degrades to default_layout(); never raises."""
    default = default_layout()
    if not isinstance(layout, dict) or not isinstance(layout.get("blocks"), list):
        return default
    defaults_by_key, default_section_of = {}, {}
    for block in default["blocks"]:
        if block["type"] == "section":
            for f in block["fields"]:
                defaults_by_key[f["key"]] = f
                default_section_of[f["key"]] = block["title"]

    blocks, seen_keys, seen_special = [], set(), set()
    for raw in layout["blocks"]:
        if not isinstance(raw, dict):
            continue
        btype = raw.get("type")
        if btype in ("schedule", "emergency"):
            if btype not in seen_special:
                seen_special.add(btype)
                blocks.append({"type": btype,
                               "visible": bool(raw.get("visible", True))})
        elif btype == "section":
            fields = []
            for rf in raw.get("fields") or []:
                key = rf.get("key") if isinstance(rf, dict) else None
                if key in defaults_by_key and key not in seen_keys:
                    seen_keys.add(key)
                    f = _clean_field(rf, defaults_by_key[key])
                    f["key"] = key
                    fields.append(f)
            title = raw.get("title")
            blocks.append({
                "type": "section",
                "title": title.strip() if isinstance(title, str)
                and title.strip() else "Section",
                "fields": fields,
            })

    sections_by_title = {}
    for b in blocks:
        if b["type"] == "section" and b["title"] not in sections_by_title:
            sections_by_title[b["title"]] = b
    for key, _label in FIELD_REGISTRY:
        if key in seen_keys:
            continue
        home = sections_by_title.get(default_section_of[key])
        if home is None:
            section_blocks = [b for b in blocks if b["type"] == "section"]
            if section_blocks:
                home = section_blocks[-1]
            else:
                home = {"type": "section", "title": "Other", "fields": []}
                blocks.append(home)
                sections_by_title["Other"] = home
        home["fields"].append(dict(defaults_by_key[key]))

    if "schedule" not in seen_special:
        blocks.insert(0, {"type": "schedule", "visible": True})
    if "emergency" not in seen_special:
        blocks.append({"type": "emergency", "visible": True})
    return {"version": 1, "blocks": blocks}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_info_layout.py -v`
Expected: 13 passed

- [ ] **Step 5: Commit**

```bash
git add gui/info_layout.py tests/test_info_layout.py
git commit -m "feat: normalize saved Info tab layouts against the field registry"
```

---

### Task 3: Layout model — mutation helpers for the editor

**Files:**
- Modify: `gui/info_layout.py`
- Test: `tests/test_info_layout.py`

- [ ] **Step 1: Write the failing tests** (append to `tests/test_info_layout.py`)

```python
# ── mutation helpers ───────────────────────────────────────────────────────

def _mini():
    return {"version": 1, "blocks": [
        {"type": "schedule", "visible": True},
        {"type": "section", "title": "A", "fields": [
            {"key": "first_name", "span": 1, "bold": False, "size": "normal",
             "color": "none", "visible": True},
            {"key": "dob", "span": 1, "bold": False, "size": "normal",
             "color": "none", "visible": True},
        ]},
        {"type": "section", "title": "B", "fields": [
            {"key": "cell", "span": 1, "bold": False, "size": "normal",
             "color": "none", "visible": True},
        ]},
        {"type": "emergency", "visible": True},
    ]}


def test_find_and_set_field_prop():
    from gui.info_layout import find_field, set_field_prop
    lay = _mini()
    assert find_field(lay, "dob") == (1, 1)
    assert find_field(lay, "nope") is None
    set_field_prop(lay, "dob", "bold", True)
    assert lay["blocks"][1]["fields"][1]["bold"] is True


def test_move_field_within_section_clamps():
    from gui.info_layout import move_field
    lay = _mini()
    move_field(lay, "dob", -1)
    assert [f["key"] for f in lay["blocks"][1]["fields"]] \
        == ["dob", "first_name"]
    move_field(lay, "dob", -1)   # already first: no-op
    assert lay["blocks"][1]["fields"][0]["key"] == "dob"


def test_move_field_to_section():
    from gui.info_layout import move_field_to_section, find_field
    lay = _mini()
    move_field_to_section(lay, "dob", 2)
    assert find_field(lay, "dob") == (2, 1)   # appended after "cell"
    move_field_to_section(lay, "dob", 0)      # not a section: no-op
    assert find_field(lay, "dob") == (2, 1)


def test_move_block_and_bounds():
    from gui.info_layout import move_block
    lay = _mini()
    move_block(lay, 1, 1)
    assert [b.get("title") for b in lay["blocks"]] \
        == [None, "B", "A", None]
    move_block(lay, 0, -1)   # out of range: no-op
    assert lay["blocks"][0]["type"] == "schedule"


def test_rename_and_add_section():
    from gui.info_layout import rename_section, add_section
    lay = _mini()
    rename_section(lay, 1, "  Renamed ")
    assert lay["blocks"][1]["title"] == "Renamed"
    rename_section(lay, 1, "   ")   # blank: no-op
    assert lay["blocks"][1]["title"] == "Renamed"
    add_section(lay, 1, "New")
    assert lay["blocks"][2] == {"type": "section", "title": "New",
                                "fields": []}


def test_delete_section_migrates_fields_to_previous():
    from gui.info_layout import delete_section
    lay = _mini()
    delete_section(lay, 2)   # deletes "B"; its field joins "A"
    titles = [b.get("title") for b in lay["blocks"]
              if b["type"] == "section"]
    assert titles == ["A"]
    assert [f["key"] for f in lay["blocks"][1]["fields"]] \
        == ["first_name", "dob", "cell"]


def test_delete_first_section_migrates_to_next():
    from gui.info_layout import delete_section
    lay = _mini()
    delete_section(lay, 1)   # deletes "A"; fields join "B"
    b = [blk for blk in lay["blocks"] if blk["type"] == "section"][0]
    assert b["title"] == "B"
    assert [f["key"] for f in b["fields"]] == ["cell", "first_name", "dob"]


def test_delete_last_remaining_section_refused():
    from gui.info_layout import delete_section
    lay = _mini()
    delete_section(lay, 2)
    delete_section(lay, 1)   # only section left: no-op
    assert any(b["type"] == "section" for b in lay["blocks"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_info_layout.py -v`
Expected: the 8 new tests FAIL with ImportError; earlier tests pass.

- [ ] **Step 3: Write the implementation** (append to `gui/info_layout.py`)

```python
# ── mutation helpers (the editor dialog operates through these) ────────────

def find_field(layout, key):
    """(block_index, field_index) of key, or None."""
    for bi, b in enumerate(layout["blocks"]):
        if b["type"] == "section":
            for fi, f in enumerate(b["fields"]):
                if f["key"] == key:
                    return bi, fi
    return None


def set_field_prop(layout, key, prop, value):
    pos = find_field(layout, key)
    if pos is not None:
        layout["blocks"][pos[0]]["fields"][pos[1]][prop] = value


def move_field(layout, key, delta):
    """Swap the field with its neighbor inside its section; no-op at ends."""
    pos = find_field(layout, key)
    if pos is None:
        return
    fields = layout["blocks"][pos[0]]["fields"]
    j = pos[1] + delta
    if 0 <= j < len(fields):
        fields[pos[1]], fields[j] = fields[j], fields[pos[1]]


def move_field_to_section(layout, key, block_index):
    """Append the field to the section block at block_index."""
    pos = find_field(layout, key)
    if pos is None or pos[0] == block_index:
        return
    blocks = layout["blocks"]
    if not (0 <= block_index < len(blocks)) \
            or blocks[block_index].get("type") != "section":
        return
    f = blocks[pos[0]]["fields"].pop(pos[1])
    blocks[block_index]["fields"].append(f)


def move_block(layout, index, delta):
    blocks = layout["blocks"]
    j = index + delta
    if 0 <= index < len(blocks) and 0 <= j < len(blocks):
        blocks[index], blocks[j] = blocks[j], blocks[index]


def rename_section(layout, index, title):
    b = layout["blocks"][index]
    if b["type"] == "section" and title.strip():
        b["title"] = title.strip()


def add_section(layout, after_index, title="New Section"):
    layout["blocks"].insert(
        after_index + 1, {"type": "section", "title": title, "fields": []})


def delete_section(layout, index):
    """Delete a section; its fields migrate to the previous section (or the
    next, if it was first). The last remaining section can't be deleted."""
    blocks = layout["blocks"]
    if not (0 <= index < len(blocks)) or blocks[index].get("type") != "section":
        return
    others = [i for i, b in enumerate(blocks)
              if b["type"] == "section" and i != index]
    if not others:
        return
    fields = blocks[index]["fields"]
    if fields:
        prev = [i for i in others if i < index]
        home = blocks[prev[-1]] if prev else blocks[others[0]]
        home["fields"].extend(fields)
    blocks.pop(index)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_info_layout.py -v`
Expected: 21 passed

- [ ] **Step 5: Commit**

```bash
git add gui/info_layout.py tests/test_info_layout.py
git commit -m "feat: layout mutation helpers for the Info tab editor"
```

---

### Task 4: Theme — highlight tokens and field-style QSS rules

**Files:**
- Modify: `gui/theme.py` (token dicts ~lines 7-51, `build_qss` ~line 83)
- Test: `tests/test_info_tab_render.py` (new file; QSS tests are pure string checks, no QApplication needed)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_info_tab_render.py
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


# ── theme: per-field style rules exist in both themes ──────────────────────

def test_qss_has_highlight_rules_both_themes():
    from gui.theme import build_qss, DARK, LIGHT
    for tokens in (DARK, LIGHT):
        qss = build_qss(tokens)
        for color in ("amber", "blue", "green", "red"):
            assert f'QLineEdit[hl="{color}"]' in qss
            assert tokens[f"hl_{color}"] in qss
        assert 'QLineEdit[fbold="true"]' in qss
        assert 'QLineEdit[fsize="large"]' in qss


def test_highlight_tokens_differ_between_themes():
    from gui.theme import DARK, LIGHT
    for color in ("amber", "blue", "green", "red"):
        assert DARK[f"hl_{color}"] != LIGHT[f"hl_{color}"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_info_tab_render.py -v`
Expected: 2 FAIL (KeyError `'hl_amber'` / missing rules)

- [ ] **Step 3: Implement**

In `gui/theme.py`, add to the `DARK` dict (after `"error_text"`):

```python
    # Info tab per-field highlight tints (customizable layout).
    "hl_amber":     "#3a2f10",
    "hl_blue":      "#1c2745",
    "hl_green":     "#16301f",
    "hl_red":       "#391b1b",
```

and to the `LIGHT` dict:

```python
    # Info tab per-field highlight tints (customizable layout).
    "hl_amber":     "#f7ecc8",
    "hl_blue":      "#dfe7fb",
    "hl_green":     "#ddf0e4",
    "hl_red":       "#f7dede",
```

In `build_qss`, directly after the `QLineEdit#info_field[error="true"]` block (~line 265), insert:

```python
/* Customizable Info tab per-field styling, driven by dynamic properties set
   from the saved layout (see gui/info_layout.py). General QLineEdit selectors
   on purpose: the address field's inner line edit isn't #info_field. */
QLineEdit[fbold="true"] {{ font-weight: 800; }}
QLineEdit[fsize="large"] {{ font-size: 16px; }}
QLineEdit[hl="amber"], QLineEdit[hl="amber"]:read-only {{
    background-color: {t['hl_amber']}; border-radius: 4px; padding: 3px 6px;
}}
QLineEdit[hl="blue"], QLineEdit[hl="blue"]:read-only {{
    background-color: {t['hl_blue']}; border-radius: 4px; padding: 3px 6px;
}}
QLineEdit[hl="green"], QLineEdit[hl="green"]:read-only {{
    background-color: {t['hl_green']}; border-radius: 4px; padding: 3px 6px;
}}
QLineEdit[hl="red"], QLineEdit[hl="red"]:read-only {{
    background-color: {t['hl_red']}; border-radius: 4px; padding: 3px 6px;
}}
```

(These are inside the module's f-string; `{{ }}` are literal braces.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_info_tab_render.py tests/test_settings.py -v`
Expected: all pass (test_settings.py guards against theme regressions)

- [ ] **Step 5: Commit**

```bash
git add gui/theme.py tests/test_info_tab_render.py
git commit -m "feat: theme tokens and QSS rules for Info field highlight/emphasis"
```

---

### Task 5: Render the Info tab from the layout

**Files:**
- Modify: `gui/member_tabs.py` — `MemberTabsWidget.__init__` (~line 760), `_make_info_tab` (~line 1593), `_refresh_schedule_card` (~line 1581)
- Test: `tests/test_info_tab_render.py`

- [ ] **Step 1: Write the failing tests** (append to `tests/test_info_tab_render.py`)

```python
# ── renderer: the Info tab honors the layout model ─────────────────────────

def _make_tab(qapp, layout_cfg=None, member=None):
    """Build a real Info tab on a __new__-constructed widget (no DB)."""
    from PyQt6.QtWidgets import QLabel
    import gui.member_tabs as mt
    w = mt.MemberTabsWidget.__new__(mt.MemberTabsWidget)
    w._member = member or {"first_name": "Mary", "last_name": "Chan",
                           "alt_id": None}
    w._center_id = 7
    w._api_key = ""
    w._alt_id_key = None
    w._enrollments = []
    w._authorizations = []
    w._emergency_contacts = []
    w._emergency_badge = QLabel()
    w._layout_cfg = layout_cfg
    tab = w._make_info_tab()
    return w, tab


def _grid_positions(w):
    """{widget: (row, col, rowspan, colspan)} for the Info content grid."""
    grid = w._info_content_layout
    out = {}
    for i in range(grid.count()):
        item = grid.itemAt(i)
        if item.widget() is not None:
            out[item.widget()] = grid.getItemPosition(i)
    return out


def test_default_render_places_all_visible_fields(qapp):
    w, _tab = _make_tab(qapp)
    pos = _grid_positions(w)
    assert w._info_first in pos
    assert w._info_hha in pos
    # PCP/HHA keep their full-row span (wspan 3 -> colspan 5).
    assert pos[w._info_pcp][3] == 5
    # The legacy emergency text field exists but is not placed.
    assert w._info_emergency not in pos
    assert not w._info_emergency.isVisible()


def test_custom_layout_controls_sections_and_order(qapp):
    from gui.info_layout import default_layout
    lay = default_layout()
    # Move DOB into a renamed first section and hide SSN.
    lay["blocks"][1]["title"] = "Glance"
    for f in lay["blocks"][1]["fields"]:
        if f["key"] == "ssn":
            f["visible"] = False
    w, tab = _make_tab(qapp, layout_cfg=lay)
    from PyQt6.QtWidgets import QLabel
    headers = [lbl.text() for lbl in tab.findChildren(QLabel)
               if lbl.objectName() == "section_header"]
    assert "GLANCE" in headers
    pos = _grid_positions(w)
    assert w._info_ssn not in pos
    assert not w._info_ssn.isVisible()
    # Hidden widgets still hold their value for save/discard.
    assert w._info_ssn.text() == ""


def test_layout_styling_sets_dynamic_properties(qapp):
    from gui.info_layout import default_layout
    lay = default_layout()
    for f in lay["blocks"][1]["fields"]:
        if f["key"] == "dob":
            f.update(bold=True, size="large", color="amber", span=2)
    w, _tab = _make_tab(qapp, layout_cfg=lay)
    assert w._info_dob.property("fbold") == "true"
    assert w._info_dob.property("fsize") == "large"
    assert w._info_dob.property("hl") == "amber"
    assert _grid_positions(w)[w._info_dob][3] == 3   # span 2 -> colspan 3


def test_hidden_schedule_block_skips_card(qapp):
    from gui.info_layout import default_layout
    lay = default_layout()
    lay["blocks"][0]["visible"] = False
    w, _tab = _make_tab(qapp, layout_cfg=lay)
    assert w._schedule_card is None
    w._refresh_schedule_card()   # guard: must not raise


def test_garbage_layout_falls_back_to_default(qapp):
    w, _tab = _make_tab(qapp, layout_cfg={"blocks": "corrupt"})
    pos = _grid_positions(w)
    assert w._info_first in pos
    assert w._schedule_card in pos
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_info_tab_render.py -v`
Expected: the 5 renderer tests FAIL (`_info_content_layout` is a QVBoxLayout / KeyErrors), theme tests pass.

- [ ] **Step 3: Implement**

3a. In `gui/member_tabs.py`, add a module-level helper near `_pencil_icon` (~line 560):

```python
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
```

3b. Extend `MemberTabsWidget.__init__` (~line 760) — new keyword args and state, added after `self._alt_id_key = alt_id_key`:

```python
    def __init__(self, center_id: int, db_path: str, events_path: str,
                 api_key: str = "", show_row_ids: bool = False, parent=None,
                 alt_id_key: bytes | None = None, settings: dict | None = None,
                 settings_path: str = ""):
```

```python
        # Customizable Info tab: the layout dict lives in the per-machine
        # settings JSON; without settings (tests, tools) the default is used.
        from gui.info_layout import normalize
        self._settings = settings
        self._settings_path = settings_path
        self._layout_cfg = normalize((settings or {}).get("info_tab_layout"))
```

3c. Rewrite the placement part of `_make_info_tab` (~lines 1662-1747). Everything above it — the widget construction from `m = self._member` through `schedule_card = self._build_schedule_card()` — stays, EXCEPT delete the `schedule_card = self._build_schedule_card()` line (the loop now builds it). Replace from the `# ── Dense sectioned grid …` comment through the `self._info_content_layout = cvbox` line with:

```python
        # ── Layout-driven sectioned grid (see gui/info_layout.py) ──────────
        from gui.info_layout import (
            normalize, placements, FIELD_LABELS_BY_KEY,
        )
        layout_cfg = normalize(self.__dict__.get("_layout_cfg"))
        self._layout_cfg = layout_cfg

        widgets = {
            "first_name": self._info_first, "last_name": self._info_last,
            "chinese_name": self._info_chinese, "gender": self._info_gender,
            "dob": self._info_dob, "ssn": self._info_ssn,
            "center_id": self._info_cid, "enrollment_start": enroll_lbl,
            "language": self._info_language, "alt_id": self._info_alt_id,
            "address": self._info_address, "home_tell": self._info_home_tell,
            "cell": self._info_cell, "emergency": self._info_emergency,
            "health_plan": self._info_plan,
            "member_id": self._info_member_id,
            "medicaid": self._info_medicaid, "medicare": self._info_medicare,
            "hospital": self._info_hospital, "pcp": self._info_pcp,
            "hha": self._info_hha, "case_manager": self._info_case_manager,
        }

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
```

The label text for `enrollment_start` comes from the registry now, so also delete the old `cell(...)`/`section(...)` helper definitions and calls that this replaces. Keep the `scroll = QScrollArea()` block onward unchanged (it already wraps `content`), and keep the button-row code.

3d. `_refresh_schedule_card` (~line 1581) needs no logic change — `QLayout.replaceWidget` works on the grid and the `None` guard already covers a hidden card. Update only its docstring if you touch it.

3e. In `gui/main_window.py` (~line 601) pass the settings through:

```python
        widget = MemberTabsWidget(center_id, db_path, events_path, api_key,
                                  show_row_ids,
                                  alt_id_key=self._alt_id_key(),
                                  settings=self._settings,
                                  settings_path=self._settings_path)
```

- [ ] **Step 4: Run the new tests, then the full suite**

Run: `python -m pytest tests/test_info_tab_render.py -v`
Expected: 7 passed
Run: `python -m pytest -q`
Expected: all pass (the renderer refactor must not break existing member-tab tests; `test_profile_print.py` and `test_absence_edit.py` exercise neighboring code)

- [ ] **Step 5: Commit**

```bash
git add gui/member_tabs.py gui/main_window.py tests/test_info_tab_render.py
git commit -m "feat: render the Info tab from the saved layout model"
```

---

### Task 6: Editor dialog — preview + selection

**Files:**
- Create: `gui/info_layout_editor.py`
- Test: `tests/test_info_layout_editor.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_info_layout_editor.py
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


MEMBER = {"first_name": "Mary", "last_name": "Chan", "dob": "1/2/1950",
          "cell": "9175550143"}


def test_editor_starts_from_normalized_copy(qapp):
    from gui.info_layout_editor import InfoLayoutEditor
    from gui.info_layout import default_layout
    dlg = InfoLayoutEditor(None, MEMBER)
    assert dlg.result_layout() == default_layout()
    # A layout dict passed in must not be mutated by editing.
    src = default_layout()
    dlg2 = InfoLayoutEditor(src, MEMBER)
    dlg2._layout["blocks"][1]["title"] = "Changed"
    assert src["blocks"][1]["title"] == "Identity"


def test_preview_shows_hidden_fields_dimmed(qapp):
    from gui.info_layout_editor import InfoLayoutEditor
    dlg = InfoLayoutEditor(None, MEMBER)
    # The legacy emergency field is hidden by default but must appear in the
    # preview (else it could never be re-shown).
    assert "emergency" in dlg._preview_cells


def test_clicking_a_preview_cell_selects_the_field(qapp):
    from gui.info_layout_editor import InfoLayoutEditor
    dlg = InfoLayoutEditor(None, MEMBER)
    dlg._select(("field", "dob"))
    assert dlg._selection == ("field", "dob")
    # Selecting a block works the same way.
    dlg._select(("block", 0))
    assert dlg._selection == ("block", 0)


def test_preview_rebuild_preserves_selection(qapp):
    from gui.info_layout_editor import InfoLayoutEditor
    dlg = InfoLayoutEditor(None, MEMBER)
    dlg._select(("field", "dob"))
    dlg._rebuild_preview()
    assert dlg._selection == ("field", "dob")
    assert "dob" in dlg._preview_cells
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_info_layout_editor.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'gui.info_layout_editor'`

- [ ] **Step 3: Write the implementation**

```python
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
        """Re-render after any model mutation."""
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
        self._preview_scroll.setWidget(content)

    # ── properties panel (built in Task 7) ─────────────────────────────────

    def _rebuild_props(self):
        pass
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_info_layout_editor.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add gui/info_layout_editor.py tests/test_info_layout_editor.py
git commit -m "feat: Info layout editor dialog — live preview with selection"
```

---

### Task 7: Editor dialog — properties panel

**Files:**
- Modify: `gui/info_layout_editor.py`
- Test: `tests/test_info_layout_editor.py`

- [ ] **Step 1: Write the failing tests** (append to `tests/test_info_layout_editor.py`)

```python
# ── properties panel drives the model ──────────────────────────────────────

def _dlg(qapp):
    from gui.info_layout_editor import InfoLayoutEditor
    return InfoLayoutEditor(None, MEMBER)


def test_field_props_change_model(qapp):
    from gui.info_layout import find_field
    dlg = _dlg(qapp)
    dlg._select(("field", "dob"))
    dlg._set_prop("bold", True)
    dlg._set_prop("span", 2)
    dlg._set_prop("color", "amber")
    dlg._set_prop("visible", False)
    bi, fi = find_field(dlg._layout, "dob")
    f = dlg._layout["blocks"][bi]["fields"][fi]
    assert (f["bold"], f["span"], f["color"], f["visible"]) \
        == (True, 2, "amber", False)


def test_move_field_to_other_section(qapp):
    from gui.info_layout import find_field
    dlg = _dlg(qapp)
    dlg._select(("field", "dob"))
    contact_bi = [i for i, b in enumerate(dlg._layout["blocks"])
                  if b.get("title") == "Contact"][0]
    dlg._move_to_section(contact_bi)
    assert find_field(dlg._layout, "dob")[0] == contact_bi
    assert dlg._selection == ("field", "dob")   # selection survives


def test_section_ops(qapp):
    dlg = _dlg(qapp)
    identity_bi = [i for i, b in enumerate(dlg._layout["blocks"])
                   if b.get("title") == "Identity"][0]
    dlg._select(("block", identity_bi))
    dlg._rename("My Stuff")
    assert dlg._layout["blocks"][identity_bi]["title"] == "My Stuff"
    n_before = len(dlg._layout["blocks"])
    dlg._add_section()
    assert len(dlg._layout["blocks"]) == n_before + 1
    dlg._delete_section()   # deletes "My Stuff"; fields migrate
    titles = [b.get("title") for b in dlg._layout["blocks"]
              if b["type"] == "section"]
    assert "My Stuff" not in titles
    all_keys = [f["key"] for b in dlg._layout["blocks"]
                if b["type"] == "section" for f in b["fields"]]
    assert "dob" in all_keys   # nothing lost


def test_block_move_and_visibility(qapp):
    dlg = _dlg(qapp)
    dlg._select(("block", 0))          # schedule card
    dlg._set_block_visible(False)
    assert dlg._layout["blocks"][0]["visible"] is False
    dlg._move_selected_block(1)
    assert dlg._layout["blocks"][1]["type"] == "schedule"
    assert dlg._selection == ("block", 1)


def test_result_layout_is_normalized(qapp):
    from gui.info_layout import normalize
    dlg = _dlg(qapp)
    dlg._select(("field", "dob"))
    dlg._set_prop("bold", True)
    out = dlg.result_layout()
    assert out == normalize(out)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_info_layout_editor.py -v`
Expected: the 5 new tests FAIL with `AttributeError: ... has no attribute '_set_prop'`

- [ ] **Step 3: Implement** — replace the `_rebuild_props` stub and add handlers in `gui/info_layout_editor.py`. Extend the module's imports:

```python
from PyQt6.QtWidgets import (
    QDialog, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout,
    QScrollArea, QPushButton, QFrame, QComboBox, QCheckBox, QLineEdit,
    QMessageBox,
)

from gui.info_layout import (
    normalize, default_layout, placements, FIELD_LABELS_BY_KEY, COLORS,
    find_field, set_field_prop, move_field, move_field_to_section,
    move_block, rename_section, add_section, delete_section,
)
```

Then:

```python
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
                w.deleteLater()
            elif item.layout() is not None:
                sub = item.layout()
                while sub.count():
                    sw = sub.takeAt(0).widget()
                    if sw is not None:
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
        large = QCheckBox("Large text")
        large.setChecked(cfg["size"] == "large")
        large.toggled.connect(
            lambda v: self._set_prop("size", "large" if v else "normal"))
        box.addWidget(large)

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
```

Note the delete confirmation only appears when the dialog `isVisible()` — headless tests call `_delete_section()` on an unshown dialog and skip the prompt.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_info_layout_editor.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add gui/info_layout_editor.py tests/test_info_layout_editor.py
git commit -m "feat: Info layout editor properties panel"
```

---

### Task 8: Wire the editor into the Info tab — Customize button, persist, rebuild

**Files:**
- Modify: `gui/member_tabs.py` (button row at the end of `_make_info_tab`; new methods `_open_layout_editor`, `_rebuild_info_tab`)
- Test: `tests/test_info_tab_render.py`

- [ ] **Step 1: Write the failing tests** (append to `tests/test_info_tab_render.py`)

```python
# ── wiring: apply a new layout, persist, rebuild in place ──────────────────

def test_apply_layout_persists_and_rebuilds(qapp, tmp_path):
    import json
    from PyQt6.QtWidgets import QTabWidget, QWidget
    from gui.info_layout import default_layout
    w, tab = _make_tab(qapp)
    # Give the widget a tab bar + settings the way _build_ui/__init__ do.
    w._tabs = QTabWidget()
    w._tabs.addTab(tab, "Info")
    w._tabs.addTab(QWidget(), "Other")
    w._tab_info = tab
    w._info_tab_index = 0
    w._prev_tab_index = 0
    w._lazy_tabs = {}
    w._dirty = False
    path = str(tmp_path / "settings.json")
    w._settings = {}
    w._settings_path = path
    new_layout = default_layout()
    new_layout["blocks"][1]["title"] = "Rearranged"
    w._apply_layout(new_layout)
    # Persisted:
    with open(path, "r", encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["info_tab_layout"]["blocks"][1]["title"] == "Rearranged"
    # Rebuilt in place at the same index, same count:
    assert w._tabs.count() == 2
    assert w._tabs.widget(0) is w._tab_info
    assert w._tab_info is not tab
    from PyQt6.QtWidgets import QLabel
    headers = [lbl.text() for lbl in w._tab_info.findChildren(QLabel)
               if lbl.objectName() == "section_header"]
    assert "REARRANGED" in headers


def test_open_layout_editor_blocked_while_dirty(qapp, monkeypatch):
    w, _tab = _make_tab(qapp)
    w._dirty = True
    called = {}
    from PyQt6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda *a, **k: called.setdefault("x", 1)))
    w._open_layout_editor()
    assert called   # told the user; no dialog attempted


def test_customize_button_present_on_info_tab(qapp):
    from PyQt6.QtWidgets import QPushButton
    _w, tab = _make_tab(qapp)
    texts = [b.text() for b in tab.findChildren(QPushButton)]
    assert any("Customize" in t for t in texts)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_info_tab_render.py -v`
Expected: 3 new FAIL (`AttributeError: _apply_layout` / no Customize button)

- [ ] **Step 3: Implement** in `gui/member_tabs.py`.

3a. In `_make_info_tab`'s button row (directly after `btn_row = QHBoxLayout()` and before `btn_row.addStretch()`):

```python
        btn_customize = QPushButton("✎ Customize Layout")
        btn_customize.clicked.connect(self._open_layout_editor)
        btn_row.addWidget(btn_customize)
```

3b. New methods on `MemberTabsWidget` (place after `_refresh_schedule_card`):

```python
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
        dlg = InfoLayoutEditor(self._layout_cfg, self._member, self)
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
```

**Check `_setup_dirty_tracking` before finishing:** read its body. If it connects to header widgets that survive the rebuild (the notes editor), a second call would double-connect them. If so, guard those connections (e.g. only connect notes when `self.__dict__.get("_dirty_tracking_armed")` is unset, then set it) — a duplicated `_set_dirty(True)` call is harmless but avoid duplicate *revert* wiring if any exists.

- [ ] **Step 4: Run tests, then the full suite**

Run: `python -m pytest tests/test_info_tab_render.py -v`
Expected: 10 passed
Run: `python -m pytest -q`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add gui/member_tabs.py tests/test_info_tab_render.py
git commit -m "feat: Customize Layout button — edit, persist, rebuild the Info tab"
```

---

### Task 9: Full verification + manual smoke test

**Files:** none new

- [ ] **Step 1: Run the entire test suite**

Run: `python -m pytest -q`
Expected: all pass (605 pre-existing + ~34 new)

- [ ] **Step 2: Manual smoke test in the real app**

Run the app against the test database, open a member, and verify:
1. The Info tab looks identical to before (default layout).
2. "✎ Customize Layout" opens the editor; the preview mirrors the tab.
3. Rename a section, move a field between sections, set DOB bold+amber, hide SSN, move the Schedule card down → Save → the tab re-renders accordingly.
4. Restart the app → the customized layout is still there (settings JSON).
5. Reset to Default in the editor → Save → classic layout returns.
6. Switch light/dark theme → highlights remain legible.

- [ ] **Step 3: Commit any fixes, then wrap up**

Use the superpowers:finishing-a-development-branch skill to decide merge/PR/cleanup.

---

## Self-Review (done at plan time)

- **Spec coverage:** model+registry (Tasks 1-3), theme styling (4), renderer with hidden-widget data safety (5), editor preview+props (6-7), persistence+rebuild+entry button (8), testing throughout, error handling via normalize (2) and save-failure warning (8). Out-of-scope items untouched.
- **Type consistency:** `placements()` yields `(field_dict, row, slot, span)` everywhere; mutation helpers take `(layout, key/index, ...)`; `result_layout()` returns a normalized dict; `_apply_layout(dict)` is the single write path.
- **Known judgment calls for the implementer:** exact line numbers may have drifted — anchor on the quoted code, not the numbers; `_setup_dirty_tracking` re-arm needs the check described in Task 8 Step 3.
