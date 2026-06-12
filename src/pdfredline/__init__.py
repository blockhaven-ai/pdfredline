"""pdfredline: pin review comments onto PDFs as real, clickable annotations."""

from .annotate import AnnotateError, ApplyResult, apply_comments
from .schema import (
    AUTHOR,
    DEFAULT_COLORS,
    DEFAULT_SEVERITY,
    TAG_PREFIX,
    Comment,
    CommentSet,
    SchemaError,
    load_comments,
    parse_comments,
)
from .strip import StripError, strip_pdf
from .verify import VerifyError, VerifyResult, scan_annotations, verify_pdf

__version__ = "0.1.0"

__all__ = [
    "AUTHOR",
    "AnnotateError",
    "ApplyResult",
    "Comment",
    "CommentSet",
    "DEFAULT_COLORS",
    "DEFAULT_SEVERITY",
    "SchemaError",
    "StripError",
    "TAG_PREFIX",
    "VerifyError",
    "VerifyResult",
    "__version__",
    "apply_comments",
    "load_comments",
    "parse_comments",
    "scan_annotations",
    "strip_pdf",
    "verify_pdf",
]
