#!/usr/bin/env python3
"""Build a small two-page sample PDF for trying out pdfredline.

Usage:
    python3 examples/make_sample_pdf.py [output.pdf]

Then:
    pdfredline apply sample.pdf examples/comments.json -o sample.redlined.pdf
    pdfredline verify sample.redlined.pdf examples/comments.json
"""

from __future__ import annotations

import sys

import fitz  # PyMuPDF

PAGE_1 = """Quarterly Engineering Report

Summary

The new ingestion service guarantees complete accuracy across all
input formats. Throughput improved 40% quarter over quarter, and
error rates fell as of last year.

Roadmap

The team plans to migrate the remaining batch jobs next quarter.
"""

PAGE_2 = """Appendix A: Methodology

Latency figures were sampled every 30 seconds over a 14-day window.
Results were averaged per region and rounded to the nearest millisecond.
"""


def build(path: str) -> None:
    """Write the sample PDF to *path*."""
    doc = fitz.open()
    for text in (PAGE_1, PAGE_2):
        page = doc.new_page()  # default Letter-ish A4 size
        page.insert_text(fitz.Point(72, 96), text, fontsize=12)
    # A gray box standing in for an image/logo, matching the rect anchor
    # in examples/comments.json.
    doc[0].draw_rect(fitz.Rect(360, 60, 530, 100), color=(0.5, 0.5, 0.5), fill=(0.85, 0.85, 0.85))
    doc.save(path)
    doc.close()
    print(f"wrote {path}")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "sample.pdf")
