"""Command-line interface.

Subcommands:
    apply   annotate a PDF from a comments JSON sidecar
    verify  check an annotated PDF against the sidecar
    strip   remove the annotations this tool added
    init    write an example comments.json

Exit codes (``apply``):
    0  every comment anchored to its text or rect
    1  one or more comments fell back to a sticky note
    2  error (bad arguments, invalid JSON, unreadable PDF, ...)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .annotate import AnnotateError, apply_comments
from .schema import SchemaError, load_comments
from .strip import StripError, strip_pdf
from .verify import VerifyError, verify_pdf

_EXAMPLE_SIDECAR = """\
{
  "_doc": "pdfredline comments sidecar. Keys starting with '_' are ignored.",
  "_severities": "Defaults: blocker (red), major (orange), minor (yellow), suggestion (blue).",

  "colors": {
    "_doc": "Optional. Override or add severities as [r, g, b] with components in 0..1.",
    "question": [0.55, 0.25, 0.85]
  },

  "comments": [
    {
      "_doc": "Text anchor: highlights the first match of 'anchor_text'. 'page' is 1-indexed; omit it to search every page. Keep anchors short and distinctive (3-6 words) so they do not span line breaks.",
      "id": "intro-overstated",
      "page": 1,
      "anchor_text": "guarantees complete accuracy",
      "severity": "major",
      "title": "Overstated claim",
      "body": "No system guarantees complete accuracy. Soften to 'is designed to improve accuracy'."
    },
    {
      "_doc": "Rect anchor: boxes a region (logos, charts, image-only text). [x0, y0, x1, y1] in PDF points, origin at the top-left of the page. Rect anchors require an explicit 'page'.",
      "id": "logo-resolution",
      "page": 1,
      "rect": [350, 50, 540, 110],
      "severity": "minor",
      "title": "Low-resolution image",
      "body": "Replace this image with a vector or higher-resolution version."
    },
    {
      "_doc": "'id' is optional; when omitted, a stable id is derived from the comment's content. 'severity' is optional and defaults to 'suggestion'.",
      "anchor_text": "as of last year",
      "title": "Date the reference",
      "body": "Replace the relative date with an explicit one."
    }
  ]
}
"""


def _cmd_apply(args: argparse.Namespace) -> int:
    """Run ``pdfredline apply``."""
    try:
        comment_set = load_comments(args.comments)
    except SchemaError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    src = Path(args.pdf)
    out = Path(args.output) if args.output else src.with_name(src.stem + ".redlined.pdf")
    try:
        result = apply_comments(src, comment_set, out)
    except AnnotateError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"wrote {out}")
    print(f"  highlights:      {result.highlighted}")
    print(f"  boxes:           {result.boxed}")
    print(f"  fallback notes:  {result.fellback}")
    print(f"  skipped (already applied): {result.skipped}")
    if result.fallback_ids:
        print("anchor text not found for:", file=sys.stderr)
        for cid in result.fallback_ids:
            print(f"  - {cid} (pinned as a sticky note)", file=sys.stderr)
        return 1
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    """Run ``pdfredline verify``."""
    try:
        comment_set = load_comments(args.comments)
        result = verify_pdf(args.pdf, comment_set)
    except (SchemaError, VerifyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    for f in result.found:
        x0, y0, x1, y1 = f.rect
        print(
            f"p{f.page:>3}  {f.kind:<10} ({x0:.0f},{y0:.0f})-({x1:.0f},{y1:.0f})  "
            f"{f.summary}"
        )
    print(
        f"\n{len(result.found)} tool annotation(s) in PDF, "
        f"{len(comment_set.comments)} comment(s) in sidecar"
    )
    if result.missing_ids:
        print("missing:", ", ".join(result.missing_ids), file=sys.stderr)
    if result.duplicate_ids:
        print("duplicated:", ", ".join(result.duplicate_ids), file=sys.stderr)
    return 0 if result.ok else 1


def _cmd_strip(args: argparse.Namespace) -> int:
    """Run ``pdfredline strip``."""
    try:
        removed = strip_pdf(args.pdf, args.output)
    except StripError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    target = args.output or args.pdf
    print(f"removed {removed} annotation(s); wrote {target}")
    return 0


def _cmd_init(args: argparse.Namespace) -> int:
    """Run ``pdfredline init``."""
    path = Path(args.path)
    if path.exists() and not args.force:
        print(f"error: {path} already exists (use --force to overwrite)", file=sys.stderr)
        return 2
    path.write_text(_EXAMPLE_SIDECAR, encoding="utf-8")
    print(f"wrote {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser."""
    parser = argparse.ArgumentParser(
        prog="pdfredline",
        description="Pin review comments onto PDFs as real, clickable annotations.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_apply = sub.add_parser(
        "apply", help="annotate a PDF from a comments JSON sidecar"
    )
    p_apply.add_argument("pdf", help="source PDF")
    p_apply.add_argument("comments", help="comments JSON sidecar")
    p_apply.add_argument(
        "-o",
        "--output",
        help="output path (default: <input>.redlined.pdf next to the source)",
    )
    p_apply.set_defaults(func=_cmd_apply)

    p_verify = sub.add_parser(
        "verify", help="check an annotated PDF against the sidecar"
    )
    p_verify.add_argument("pdf", help="annotated PDF")
    p_verify.add_argument("comments", help="comments JSON sidecar")
    p_verify.set_defaults(func=_cmd_verify)

    p_strip = sub.add_parser(
        "strip", help="remove the annotations this tool added"
    )
    p_strip.add_argument("pdf", help="annotated PDF")
    p_strip.add_argument(
        "-o",
        "--output",
        help="output path (default: rewrite the input in place)",
    )
    p_strip.set_defaults(func=_cmd_strip)

    p_init = sub.add_parser("init", help="write an example comments.json")
    p_init.add_argument(
        "path",
        nargs="?",
        default="comments.json",
        help="where to write the example (default: comments.json)",
    )
    p_init.add_argument(
        "--force", action="store_true", help="overwrite an existing file"
    )
    p_init.set_defaults(func=_cmd_init)

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns the process exit code."""
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
