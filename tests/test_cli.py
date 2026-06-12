"""CLI subcommands and exit codes."""

from __future__ import annotations

import json
from pathlib import Path

from pdfredline import load_comments, scan_annotations
from pdfredline.cli import main


def _write_comments(tmp_path: Path, data) -> Path:
    path = tmp_path / "comments.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_apply_exit_0_when_all_anchored(sample_pdf, comments_dict, tmp_path):
    comments = _write_comments(tmp_path, comments_dict)
    out = tmp_path / "out.pdf"
    code = main(["apply", str(sample_pdf), str(comments), "-o", str(out)])
    assert code == 0
    assert len(scan_annotations(out)) == 3


def test_apply_exit_1_on_fallback(sample_pdf, tmp_path):
    comments = _write_comments(
        tmp_path,
        [
            {
                "anchor_text": "not present anywhere",
                "title": "t",
                "body": "b",
            }
        ],
    )
    out = tmp_path / "out.pdf"
    code = main(["apply", str(sample_pdf), str(comments), "-o", str(out)])
    assert code == 1
    assert len(scan_annotations(out)) == 1


def test_apply_exit_2_on_schema_error(sample_pdf, tmp_path):
    comments = _write_comments(tmp_path, [{"title": "t", "body": "b"}])
    code = main(["apply", str(sample_pdf), str(comments)])
    assert code == 2


def test_apply_exit_2_on_missing_pdf(tmp_path, comments_dict):
    comments = _write_comments(tmp_path, comments_dict)
    code = main(["apply", str(tmp_path / "nope.pdf"), str(comments)])
    assert code == 2


def test_apply_exit_2_on_page_out_of_range(sample_pdf, tmp_path):
    comments = _write_comments(
        tmp_path,
        [{"page": 99, "anchor_text": "x", "title": "t", "body": "b"}],
    )
    code = main(["apply", str(sample_pdf), str(comments)])
    assert code == 2


def test_apply_default_output_name(sample_pdf, comments_dict, tmp_path):
    comments = _write_comments(tmp_path, comments_dict)
    code = main(["apply", str(sample_pdf), str(comments)])
    assert code == 0
    assert (sample_pdf.parent / "sample.redlined.pdf").exists()


def test_verify_exit_codes(sample_pdf, comments_dict, tmp_path):
    comments = _write_comments(tmp_path, comments_dict)
    out = tmp_path / "out.pdf"
    main(["apply", str(sample_pdf), str(comments), "-o", str(out)])

    assert main(["verify", str(out), str(comments)]) == 0
    # Un-annotated source -> everything missing -> exit 1.
    assert main(["verify", str(sample_pdf), str(comments)]) == 1


def test_strip_cli(sample_pdf, comments_dict, tmp_path):
    comments = _write_comments(tmp_path, comments_dict)
    out = tmp_path / "out.pdf"
    main(["apply", str(sample_pdf), str(comments), "-o", str(out)])

    assert main(["strip", str(out)]) == 0
    assert len(scan_annotations(out)) == 0


def test_init_writes_loadable_example(tmp_path):
    target = tmp_path / "comments.json"
    assert main(["init", str(target)]) == 0
    cs = load_comments(target)
    assert len(cs.comments) == 3
    assert "question" in cs.colors
    # Refuses to overwrite without --force.
    assert main(["init", str(target)]) == 2
    assert main(["init", str(target), "--force"]) == 0
