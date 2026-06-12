"""Apply: annotation creation, colors, positions, idempotency, fallback."""

from __future__ import annotations

import math
from pathlib import Path

import fitz

from pdfredline import (
    AUTHOR,
    TAG_PREFIX,
    apply_comments,
    parse_comments,
)


def _tool_annots(pdf: Path) -> list[tuple[int, str, str, tuple, tuple]]:
    """Return (page, type, subject, rect, stroke_color) for tool annotations."""
    out = []
    with fitz.open(pdf) as doc:
        for pno, page in enumerate(doc, start=1):
            for a in page.annots():
                subject = a.info.get("subject", "") or ""
                if subject.startswith(TAG_PREFIX):
                    r = a.rect
                    stroke = tuple(a.colors.get("stroke") or ())
                    out.append((pno, a.type[1], subject, (r.x0, r.y0, r.x1, r.y1), stroke))
    return out


def _close(a: tuple, b: tuple, tol: float = 1e-3) -> bool:
    return all(math.isclose(x, y, abs_tol=tol) for x, y in zip(a, b))


def test_apply_creates_one_annotation_per_comment(sample_pdf, comments_dict, tmp_path):
    out = tmp_path / "out.pdf"
    cs = parse_comments(comments_dict)
    result = apply_comments(sample_pdf, cs, out)

    assert result.highlighted == 2
    assert result.boxed == 1
    assert result.fellback == 0
    assert result.skipped == 0

    annots = _tool_annots(out)
    assert len(annots) == 3
    by_tag = {a[2]: a for a in annots}

    # Text anchor on page 1 -> highlight, blocker red.
    pno, kind, _, rect, stroke = by_tag[TAG_PREFIX + "c-accuracy"]
    assert pno == 1
    assert kind == "Highlight"
    assert _close(stroke, (0.86, 0.10, 0.10), tol=0.01)

    # Page omitted -> found on page 2, minor yellow.
    pno, kind, _, _, stroke = by_tag[TAG_PREFIX + "c-window"]
    assert pno == 2
    assert kind == "Highlight"
    assert _close(stroke, (0.90, 0.75, 0.00), tol=0.01)

    # Rect anchor -> Square at the requested position, suggestion blue.
    pno, kind, _, rect, stroke = by_tag[TAG_PREFIX + "c-region"]
    assert pno == 1
    assert kind == "Square"
    assert _close(rect, (300, 50, 500, 120), tol=2.0)
    assert _close(stroke, (0.20, 0.50, 1.00), tol=0.01)

    # All carry the tool author tag.
    with fitz.open(out) as doc:
        for page in doc:
            for a in page.annots():
                assert a.info.get("title") == AUTHOR


def test_apply_is_idempotent(sample_pdf, comments_dict, tmp_path):
    out1 = tmp_path / "once.pdf"
    out2 = tmp_path / "twice.pdf"
    cs = parse_comments(comments_dict)

    apply_comments(sample_pdf, cs, out1)
    result = apply_comments(out1, cs, out2)

    assert result.total_written == 0
    assert result.skipped == 3
    assert len(_tool_annots(out2)) == 3


def test_apply_in_place_reapply_does_not_duplicate(sample_pdf, comments_dict, tmp_path):
    out = tmp_path / "out.pdf"
    cs = parse_comments(comments_dict)
    apply_comments(sample_pdf, cs, out)
    apply_comments(out, cs, out)  # same source and destination
    assert len(_tool_annots(out)) == 3


def test_missing_anchor_falls_back_to_sticky_note(sample_pdf, tmp_path):
    out = tmp_path / "out.pdf"
    cs = parse_comments(
        [
            {
                "id": "ghost",
                "page": 2,
                "anchor_text": "this text is nowhere in the document",
                "severity": "major",
                "title": "Ghost anchor",
                "body": "Should land as a sticky note on page 2.",
            }
        ]
    )
    result = apply_comments(sample_pdf, cs, out)

    assert result.fellback == 1
    assert result.fallback_ids == ["ghost"]

    annots = _tool_annots(out)
    assert len(annots) == 1
    pno, kind, subject, rect, stroke = annots[0]
    assert pno == 2
    assert kind == "Text"  # sticky note
    assert subject == TAG_PREFIX + "ghost"
    assert rect[0] >= 30 and rect[1] >= 30  # pinned near the top-left corner


def test_custom_color_header_applies(sample_pdf, tmp_path):
    out = tmp_path / "out.pdf"
    cs = parse_comments(
        {
            "colors": {"question": [0.55, 0.25, 0.85]},
            "comments": [
                {
                    "id": "q1",
                    "anchor_text": "14-day window",
                    "severity": "question",
                    "title": "Custom severity",
                    "body": "Uses the color from the header.",
                }
            ],
        }
    )
    apply_comments(sample_pdf, cs, out)
    (_, _, _, _, stroke) = _tool_annots(out)[0]
    assert _close(stroke, (0.55, 0.25, 0.85), tol=0.01)


def test_existing_foreign_annotations_are_preserved(sample_pdf, comments_dict, tmp_path):
    # Add a third-party annotation first.
    with fitz.open(sample_pdf) as doc:
        a = doc[0].add_text_annot(fitz.Point(500, 700), "someone else's note")
        a.set_info({"title": "another-reviewer", "subject": "external"})
        a.update()
        doc.saveIncr()

    out = tmp_path / "out.pdf"
    apply_comments(sample_pdf, parse_comments(comments_dict), out)

    with fitz.open(out) as doc:
        all_subjects = [
            a.info.get("subject", "") for page in doc for a in page.annots()
        ]
    assert "external" in all_subjects
    assert sum(s.startswith(TAG_PREFIX) for s in all_subjects) == 3
