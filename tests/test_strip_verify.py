"""Strip and verify behavior."""

from __future__ import annotations

import fitz

from pdfredline import (
    TAG_PREFIX,
    apply_comments,
    parse_comments,
    scan_annotations,
    strip_pdf,
    verify_pdf,
)


def _add_foreign_note(pdf) -> None:
    with fitz.open(pdf) as doc:
        a = doc[0].add_text_annot(fitz.Point(500, 700), "external note")
        a.set_info({"title": "another-reviewer", "subject": "external"})
        a.update()
        doc.saveIncr()


def test_strip_removes_only_tool_annotations(sample_pdf, comments_dict, tmp_path):
    out = tmp_path / "annotated.pdf"
    apply_comments(sample_pdf, parse_comments(comments_dict), out)
    _add_foreign_note(out)

    removed = strip_pdf(out)  # in place
    assert removed == 3

    with fitz.open(out) as doc:
        remaining = [a.info.get("subject", "") for p in doc for a in p.annots()]
    assert remaining == ["external"]


def test_strip_to_separate_output(sample_pdf, comments_dict, tmp_path):
    annotated = tmp_path / "annotated.pdf"
    stripped = tmp_path / "stripped.pdf"
    apply_comments(sample_pdf, parse_comments(comments_dict), annotated)

    removed = strip_pdf(annotated, stripped)
    assert removed == 3
    # Original untouched, output clean.
    assert len(scan_annotations(annotated)) == 3
    assert len(scan_annotations(stripped)) == 0


def test_strip_then_reapply_restores_annotations(sample_pdf, comments_dict, tmp_path):
    out = tmp_path / "annotated.pdf"
    cs = parse_comments(comments_dict)
    apply_comments(sample_pdf, cs, out)
    strip_pdf(out)
    result = apply_comments(out, cs, out)
    assert result.total_written == 3
    assert len(scan_annotations(out)) == 3


def test_verify_reports_all_present(sample_pdf, comments_dict, tmp_path):
    out = tmp_path / "annotated.pdf"
    cs = parse_comments(comments_dict)
    apply_comments(sample_pdf, cs, out)

    result = verify_pdf(out, cs)
    assert result.ok
    assert len(result.found) == 3
    assert {f.tag for f in result.found} == {c.tag for c in cs.comments}


def test_verify_reports_missing(sample_pdf, comments_dict, tmp_path):
    out = tmp_path / "annotated.pdf"
    cs = parse_comments(comments_dict)
    apply_comments(sample_pdf, cs, out)

    extended = parse_comments(
        comments_dict["comments"]
        + [
            {
                "id": "never-applied",
                "anchor_text": "14-day window",
                "title": "t",
                "body": "b",
            }
        ]
    )
    result = verify_pdf(out, extended)
    assert not result.ok
    assert result.missing_ids == ["never-applied"]


def test_verify_ignores_foreign_annotations(sample_pdf, comments_dict, tmp_path):
    out = tmp_path / "annotated.pdf"
    cs = parse_comments(comments_dict)
    apply_comments(sample_pdf, cs, out)
    _add_foreign_note(out)

    result = verify_pdf(out, cs)
    assert result.ok
    assert all(f.tag.startswith(TAG_PREFIX) for f in result.found)
