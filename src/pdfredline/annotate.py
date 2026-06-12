"""Apply review comments to a PDF as native annotations.

Each comment becomes exactly one annotation:

- ``anchor_text`` found  -> a highlight over the first match, comment in its popup
- ``rect``               -> a bordered box over the region, comment in its popup
- text not found         -> a page-level sticky note near the top-left corner,
                            so the comment is never silently dropped

Every annotation is tagged through its Subject field (``pdfredline:<id>``) and
its author field, which is what makes re-runs idempotent and lets ``strip``
remove only annotations this tool created.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF

from .schema import AUTHOR, Comment, CommentSet, TAG_PREFIX

#: Where fallback sticky notes are placed (PDF points from the top-left).
_FALLBACK_ORIGIN = (36.0, 36.0)
#: Vertical offset between stacked fallback notes on the same page.
_FALLBACK_STEP = 24.0


class AnnotateError(RuntimeError):
    """Raised when the PDF cannot be opened, annotated, or saved."""


@dataclass
class ApplyResult:
    """Outcome of one ``apply`` run."""

    highlighted: int = 0
    boxed: int = 0
    fellback: int = 0
    skipped: int = 0
    fallback_ids: list[str] = field(default_factory=list)

    @property
    def total_written(self) -> int:
        """Number of annotations created by this run."""
        return self.highlighted + self.boxed + self.fellback


def existing_tags(doc: fitz.Document) -> set[str]:
    """Return the Subject tags of all tool-created annotations in *doc*."""
    tags: set[str] = set()
    for page in doc:
        for annot in page.annots():
            subject = annot.info.get("subject", "") or ""
            if subject.startswith(TAG_PREFIX):
                tags.add(subject)
    return tags


def _popup_text(comment: Comment, fallback: bool = False) -> str:
    """Build the popup body shown when the annotation is opened."""
    suffix = " (anchor text not found; pinned to page corner)" if fallback else ""
    return f"[{comment.severity.upper()}] {comment.title}{suffix}\n\n{comment.body}"


def _find_anchor(
    doc: fitz.Document, comment: Comment
) -> tuple[int, fitz.Rect] | None:
    """Locate the first occurrence of the comment's anchor text.

    Searches the declared page, or every page when ``page`` is omitted.
    Returns ``(0-indexed page number, rect)`` or ``None``.
    """
    assert comment.anchor_text is not None
    if comment.page is not None:
        pages = [comment.page - 1]
    else:
        pages = range(doc.page_count)
    for pno in pages:
        rects = doc[pno].search_for(comment.anchor_text)
        if rects:
            return pno, rects[0]
    return None


def apply_comments(
    src: str | Path,
    comment_set: CommentSet,
    out: str | Path,
) -> ApplyResult:
    """Annotate *src* with every comment in *comment_set* and save to *out*.

    Comments whose tag already exists in the document are skipped, so applying
    the same sidecar twice does not duplicate annotations.

    Raises:
        AnnotateError: if the PDF cannot be opened/saved or a comment's
            ``page`` is out of range.
    """
    src = Path(src)
    out = Path(out)
    try:
        doc = fitz.open(src)
    except Exception as exc:
        raise AnnotateError(f"cannot open {src}: {exc}") from exc

    result = ApplyResult()
    present = existing_tags(doc)
    # Stack fallback notes per page so they do not overlap.
    fallback_counts: dict[int, int] = {}

    for comment in comment_set.comments:
        if comment.tag in present:
            result.skipped += 1
            continue

        if comment.page is not None and comment.page > doc.page_count:
            page_count = doc.page_count
            doc.close()
            raise AnnotateError(
                f"comment {comment.id!r}: page {comment.page} is out of range "
                f"(document has {page_count} pages)"
            )

        color = comment_set.color_for(comment.severity)
        info = {
            "title": AUTHOR,
            "subject": comment.tag,
            "content": _popup_text(comment),
        }

        if comment.rect is not None:
            page = doc[comment.page - 1]  # rect anchors always carry a page
            annot = page.add_rect_annot(fitz.Rect(comment.rect))
            annot.set_colors(stroke=color)
            annot.set_border(width=1.5)
            annot.set_info(info)
            annot.update()
            result.boxed += 1
            continue

        hit = _find_anchor(doc, comment)
        if hit is not None:
            pno, rect = hit
            # Keep the Page object referenced while mutating the annotation;
            # a transient doc[pno] proxy can be collected and unbind it.
            page = doc[pno]
            annot = page.add_highlight_annot(rect)
            annot.set_colors(stroke=color)
            annot.set_info(info)
            annot.update()
            result.highlighted += 1
        else:
            # Anchor text not present (rasterized, reflowed, or mistyped):
            # pin a sticky note so the comment still reaches the reviewer.
            pno = (comment.page - 1) if comment.page is not None else 0
            n = fallback_counts.get(pno, 0)
            fallback_counts[pno] = n + 1
            point = fitz.Point(
                _FALLBACK_ORIGIN[0], _FALLBACK_ORIGIN[1] + n * _FALLBACK_STEP
            )
            page = doc[pno]
            annot = page.add_text_annot(
                point, _popup_text(comment, fallback=True), icon="Note"
            )
            annot.set_colors(stroke=color)
            annot.set_info(
                {"title": AUTHOR, "subject": comment.tag}
            )
            annot.update()
            result.fellback += 1
            result.fallback_ids.append(comment.id)

    try:
        if out.resolve() == src.resolve():
            doc.saveIncr()
        else:
            doc.save(out, garbage=3, deflate=True)
    except Exception as exc:
        raise AnnotateError(f"cannot save {out}: {exc}") from exc
    finally:
        doc.close()
    return result
