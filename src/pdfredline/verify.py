"""Check that an annotated PDF contains one annotation per comment."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF

from .schema import CommentSet, TAG_PREFIX


class VerifyError(RuntimeError):
    """Raised when the annotated PDF cannot be opened."""


@dataclass
class FoundAnnotation:
    """One tool-created annotation discovered in the PDF."""

    tag: str
    page: int  # 1-indexed
    kind: str  # PyMuPDF annotation type name, e.g. "Highlight"
    rect: tuple[float, float, float, float]
    summary: str  # first line of the popup content


@dataclass
class VerifyResult:
    """Outcome of one ``verify`` run."""

    found: list[FoundAnnotation] = field(default_factory=list)
    missing_ids: list[str] = field(default_factory=list)
    duplicate_ids: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True when every comment maps to exactly one annotation."""
        return not self.missing_ids and not self.duplicate_ids


def scan_annotations(pdf: str | Path) -> list[FoundAnnotation]:
    """List every tool-created annotation in *pdf*.

    Raises:
        VerifyError: if the file cannot be opened.
    """
    try:
        doc = fitz.open(Path(pdf))
    except Exception as exc:
        raise VerifyError(f"cannot open {pdf}: {exc}") from exc

    found: list[FoundAnnotation] = []
    with doc:
        for pno, page in enumerate(doc, start=1):
            for annot in page.annots():
                subject = annot.info.get("subject", "") or ""
                if not subject.startswith(TAG_PREFIX):
                    continue
                content = annot.info.get("content", "") or ""
                summary = content.splitlines()[0] if content else ""
                r = annot.rect
                found.append(
                    FoundAnnotation(
                        tag=subject,
                        page=pno,
                        kind=annot.type[1],
                        rect=(r.x0, r.y0, r.x1, r.y1),
                        summary=summary,
                    )
                )
    return found


def verify_pdf(pdf: str | Path, comment_set: CommentSet) -> VerifyResult:
    """Match the comments in *comment_set* against the annotations in *pdf*."""
    found = scan_annotations(pdf)
    counts: dict[str, int] = {}
    for f in found:
        counts[f.tag] = counts.get(f.tag, 0) + 1

    result = VerifyResult(found=found)
    for comment in comment_set.comments:
        n = counts.get(comment.tag, 0)
        if n == 0:
            result.missing_ids.append(comment.id)
        elif n > 1:
            result.duplicate_ids.append(comment.id)
    return result
