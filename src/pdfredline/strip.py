"""Remove the annotations this tool created, leaving everything else intact."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import fitz  # PyMuPDF

from .schema import TAG_PREFIX


class StripError(RuntimeError):
    """Raised when the PDF cannot be opened or saved."""


def strip_pdf(src: str | Path, out: str | Path | None = None) -> int:
    """Delete every annotation tagged by this tool from *src*.

    Annotations are matched on their Subject field starting with
    ``pdfredline:``; annotations from other sources are untouched.

    Args:
        src: the annotated PDF.
        out: where to write the result; when omitted, *src* is rewritten
            in place (atomically, via a temporary file).

    Returns:
        The number of annotations removed.

    Raises:
        StripError: if the file cannot be opened or saved.
    """
    src = Path(src)
    try:
        doc = fitz.open(src)
    except Exception as exc:
        raise StripError(f"cannot open {src}: {exc}") from exc

    removed = 0
    try:
        for page in doc:
            # Collect first: deleting while iterating skips annotations.
            mine = [
                a
                for a in page.annots()
                if (a.info.get("subject", "") or "").startswith(TAG_PREFIX)
            ]
            for annot in mine:
                page.delete_annot(annot)
                removed += 1

        if out is not None and Path(out).resolve() != src.resolve():
            doc.save(Path(out), garbage=3, deflate=True)
        else:
            # In-place: save to a sibling temp file, then atomically replace.
            fd, tmp = tempfile.mkstemp(suffix=".pdf", dir=src.parent)
            os.close(fd)
            try:
                doc.save(tmp, garbage=3, deflate=True)
                os.replace(tmp, src)
            except Exception:
                os.unlink(tmp)
                raise
    except StripError:
        raise
    except Exception as exc:
        raise StripError(f"cannot save stripped PDF: {exc}") from exc
    finally:
        doc.close()
    return removed
