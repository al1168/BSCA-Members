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
