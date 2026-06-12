"""Schema validation: accepted shapes and clear error messages."""

from __future__ import annotations

import pytest

from pdfredline import DEFAULT_SEVERITY, SchemaError, parse_comments


def _comment(**overrides) -> dict:
    base = {
        "anchor_text": "some text",
        "severity": "minor",
        "title": "t",
        "body": "b",
    }
    base.update(overrides)
    return base


def test_bare_list_is_accepted():
    cs = parse_comments([_comment()])
    assert len(cs.comments) == 1
    assert cs.comments[0].severity == "minor"


def test_severity_defaults_and_is_case_insensitive():
    cs = parse_comments([_comment(severity="BLOCKER"), {k: v for k, v in _comment().items() if k != "severity"}])
    assert cs.comments[0].severity == "blocker"
    assert cs.comments[1].severity == DEFAULT_SEVERITY


def test_unknown_severity_rejected_with_known_list():
    with pytest.raises(SchemaError, match="unknown severity 'critical'"):
        parse_comments([_comment(severity="critical")])


def test_color_header_adds_severity():
    cs = parse_comments(
        {"colors": {"critical": [1, 0, 0]}, "comments": [_comment(severity="critical")]}
    )
    assert cs.color_for("critical") == (1.0, 0.0, 0.0)


def test_bad_color_value_rejected():
    with pytest.raises(SchemaError, match="three numbers in 0..1"):
        parse_comments({"colors": {"blocker": [255, 0, 0]}, "comments": [_comment()]})


@pytest.mark.parametrize(
    "rect, message",
    [
        ([1, 2, 3], "four numbers"),
        ([1, 2, 3, "x"], "four numbers"),
        ([100, 100, 50, 200], "x0 < x1"),
        ([100, 200, 300, 100], "x0 < x1"),
    ],
)
def test_malformed_rect_rejected(rect, message):
    raw = {"page": 1, "rect": rect, "title": "t", "body": "b"}
    with pytest.raises(SchemaError, match=message):
        parse_comments([raw])


def test_rect_requires_page():
    raw = {"rect": [0, 0, 10, 10], "title": "t", "body": "b"}
    with pytest.raises(SchemaError, match="require an explicit 'page'"):
        parse_comments([raw])


def test_anchor_text_and_rect_are_mutually_exclusive():
    raw = _comment(page=1, rect=[0, 0, 10, 10])
    with pytest.raises(SchemaError, match="exactly one of 'anchor_text' or 'rect'"):
        parse_comments([raw])


def test_neither_anchor_rejected():
    with pytest.raises(SchemaError, match="exactly one of 'anchor_text' or 'rect'"):
        parse_comments([{"title": "t", "body": "b"}])


@pytest.mark.parametrize("missing", ["title", "body"])
def test_title_and_body_required(missing):
    raw = _comment()
    del raw[missing]
    with pytest.raises(SchemaError, match=f"'{missing}' is required"):
        parse_comments([raw])


def test_duplicate_ids_rejected():
    with pytest.raises(SchemaError, match="duplicate comment id"):
        parse_comments([_comment(id="x"), _comment(id="x", title="other")])


def test_derived_ids_are_stable_and_distinct():
    a = parse_comments([_comment(), _comment(title="different")])
    b = parse_comments([_comment(), _comment(title="different")])
    assert a.comments[0].id == b.comments[0].id
    assert a.comments[0].id != a.comments[1].id


def test_underscore_keys_ignored():
    cs = parse_comments(
        {"_doc": "note", "comments": [_comment(_hint="ignored")]}
    )
    assert len(cs.comments) == 1


def test_unknown_comment_key_rejected():
    with pytest.raises(SchemaError, match="unknown keys"):
        parse_comments([_comment(anchor="wrong-name")])


def test_bad_page_rejected():
    with pytest.raises(SchemaError, match="positive integer"):
        parse_comments([_comment(page=0)])


def test_empty_list_rejected():
    with pytest.raises(SchemaError, match="empty"):
        parse_comments([])


def test_non_list_non_object_rejected():
    with pytest.raises(SchemaError, match="JSON list"):
        parse_comments("nope")
