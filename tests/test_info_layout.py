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
