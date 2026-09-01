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


def test_normalize_survives_non_list_fields():
    from gui.info_layout import normalize, FIELD_REGISTRY
    lay = normalize({"version": 1, "blocks": [
        {"type": "section", "title": "X", "fields": 5},
        {"type": "section", "title": "Y", "fields": True},
    ]})
    all_keys = [f["key"] for b in lay["blocks"] if b["type"] == "section"
                for f in b["fields"]]
    assert sorted(all_keys) == sorted(k for k, _ in FIELD_REGISTRY)


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
