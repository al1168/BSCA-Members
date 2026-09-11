# gui/info_layout.py
"""Layout model for the customizable member Info tab.

Pure Python (no Qt): the field registry, the default layout matching the
classic tab, saved-layout normalization, the 3-column flow placement used by
both the tab renderer and the editor preview, and the mutation helpers the
editor dialog calls. The layout dict is stored per-machine under the
``info_tab_layout`` settings key.

Layout schema (version 1)::

    {"version": 1, "label_size": "normal", "blocks": [
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
    ("group", "Group"),
)
FIELD_LABELS_BY_KEY = dict(FIELD_REGISTRY)

NCOLS = 3
# NB: these names overlap with gui.theme.TEXT_SIZES ("large"/"xlarge" = the
# app-wide 25/30px modes) but are a separate, per-field vocabulary persisted
# in the layout JSON.
# Value text sizes -> 11/13/16/20/25/30px at Normal app text size ("normal" is
# the un-ruled 13px base). All multiply with the app-wide text size factor.
SIZES = ("small", "normal", "large", "xlarge", "xxlarge", "xxxlarge")
# Global field-label sizes -> 9/11/13/20/25/30px ("normal" is the un-ruled base).
LABEL_SIZES = ("small", "normal", "large", "xlarge", "xxlarge", "xxxlarge")
COLORS = ("none", "amber", "blue", "green", "red")


def _field(key, span=1, visible=True):
    return {"key": key, "span": span, "bold": False, "size": "normal",
            "color": "none", "visible": visible}


def default_layout() -> dict:
    """The classic Info tab, expressed as a layout dict."""
    return {"version": 1, "label_size": "normal", "blocks": [
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
            _field("case_manager"), _field("group"),
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
    schedule/emergency blocks appear exactly once, values are clamped, and
    the global `label_size` is clamped to LABEL_SIZES.
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
            raw_fields = raw.get("fields")
            for rf in (raw_fields if isinstance(raw_fields, list) else []):
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
    label_size = layout.get("label_size")
    if label_size not in LABEL_SIZES:
        label_size = "normal"
    return {"version": 1, "label_size": label_size, "blocks": blocks}


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
    """Set one property on the field with the given key (no-op if absent)."""
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
    """Swap the block at index with its neighbor; no-op out of bounds."""
    blocks = layout["blocks"]
    j = index + delta
    if 0 <= index < len(blocks) and 0 <= j < len(blocks):
        blocks[index], blocks[j] = blocks[j], blocks[index]


def rename_section(layout, index, title):
    """Rename a section; blank titles and non-section blocks are no-ops."""
    blocks = layout["blocks"]
    if not (0 <= index < len(blocks)):
        return
    b = blocks[index]
    if b["type"] == "section" and title.strip():
        b["title"] = title.strip()


def add_section(layout, after_index, title="New Section"):
    """Insert a new empty section right after after_index."""
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
