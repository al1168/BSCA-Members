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
