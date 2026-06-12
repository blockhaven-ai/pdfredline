"""Shared fixtures: build small PDFs in-test with PyMuPDF."""

from __future__ import annotations

from pathlib import Path

import fitz
import pytest

PAGE_1_TEXT = """Quarterly Report

The ingestion service guarantees complete accuracy across all inputs.
Throughput improved 40% quarter over quarter.
"""

PAGE_2_TEXT = """Appendix

Latency was sampled over a 14-day window and averaged per region.
"""


@pytest.fixture()
def sample_pdf(tmp_path: Path) -> Path:
    """A two-page PDF with known text on each page."""
    path = tmp_path / "sample.pdf"
    doc = fitz.open()
    for text in (PAGE_1_TEXT, PAGE_2_TEXT):
        page = doc.new_page()
        page.insert_text(fitz.Point(72, 96), text, fontsize=12)
    doc.save(path)
    doc.close()
    return path


@pytest.fixture()
def comments_dict() -> dict:
    """A valid sidecar covering text, all-page search, and rect anchors."""
    return {
        "comments": [
            {
                "id": "c-accuracy",
                "page": 1,
                "anchor_text": "guarantees complete accuracy",
                "severity": "blocker",
                "title": "Overstated claim",
                "body": "Rephrase: nothing guarantees complete accuracy.",
            },
            {
                "id": "c-window",
                "anchor_text": "14-day window",
                "severity": "minor",
                "title": "Justify the window",
                "body": "Explain why 14 days. (No page: searches all pages.)",
            },
            {
                "id": "c-region",
                "page": 1,
                "rect": [300, 50, 500, 120],
                "severity": "suggestion",
                "title": "Header region",
                "body": "Box over a fixed region.",
            },
        ]
    }
