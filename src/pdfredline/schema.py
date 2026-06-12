"""Parse and validate the comments JSON sidecar.

The sidecar is either a bare list of comment objects, or an object with an
optional ``colors`` header and a ``comments`` list::

    {
      "colors": {"blocker": [0.8, 0.0, 0.0]},
      "comments": [ {...}, {...} ]
    }

Any key starting with ``_`` (at the top level or inside a comment object) is
ignored, so files can carry inline documentation.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: Tag written into each annotation's Subject field, namespaced per comment id.
TAG_PREFIX = "pdfredline:"

#: Author (Title field) recorded on every annotation the tool creates.
AUTHOR = "pdfredline"

#: Default severity -> stroke color (RGB, components in 0..1).
DEFAULT_COLORS: dict[str, tuple[float, float, float]] = {
    "blocker": (0.86, 0.10, 0.10),  # red
    "major": (1.00, 0.55, 0.00),  # orange
    "minor": (0.90, 0.75, 0.00),  # yellow
    "suggestion": (0.20, 0.50, 1.00),  # blue
}

#: Severity used when a comment omits the field.
DEFAULT_SEVERITY = "suggestion"


class SchemaError(ValueError):
    """Raised when the comments JSON is malformed or fails validation."""


@dataclass(frozen=True)
class Comment:
    """One review comment, anchored to text or to a rectangle."""

    id: str
    title: str
    body: str
    severity: str = DEFAULT_SEVERITY
    page: int | None = None  # 1-indexed; None = search all pages
    anchor_text: str | None = None
    rect: tuple[float, float, float, float] | None = None

    @property
    def tag(self) -> str:
        """Subject-field tag identifying this comment's annotation."""
        return TAG_PREFIX + self.id


@dataclass
class CommentSet:
    """A parsed sidecar: the comments plus the effective color map."""

    comments: list[Comment]
    colors: dict[str, tuple[float, float, float]] = field(
        default_factory=lambda: dict(DEFAULT_COLORS)
    )

    def color_for(self, severity: str) -> tuple[float, float, float]:
        """Return the stroke color for a (already validated) severity."""
        return self.colors[severity]


def _derive_id(raw: dict[str, Any], index: int) -> str:
    """Build a stable id from the comment's content.

    Re-running ``apply`` with an unchanged comments file therefore matches the
    annotations already present in the PDF.
    """
    basis = json.dumps(
        {
            "page": raw.get("page"),
            "anchor_text": raw.get("anchor_text"),
            "rect": raw.get("rect"),
            "severity": raw.get("severity"),
            "title": raw.get("title"),
            "body": raw.get("body"),
        },
        sort_keys=True,
    )
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:12]


def _parse_color(name: str, value: Any) -> tuple[float, float, float]:
    """Validate one ``colors`` header entry."""
    if (
        not isinstance(value, (list, tuple))
        or len(value) != 3
        or not all(isinstance(c, (int, float)) and 0 <= c <= 1 for c in value)
    ):
        raise SchemaError(
            f"colors[{name!r}]: expected three numbers in 0..1, got {value!r}"
        )
    return (float(value[0]), float(value[1]), float(value[2]))


def _parse_rect(value: Any, where: str) -> tuple[float, float, float, float]:
    """Validate a ``rect`` value: [x0, y0, x1, y1] with x0 < x1 and y0 < y1."""
    if (
        not isinstance(value, (list, tuple))
        or len(value) != 4
        or not all(isinstance(c, (int, float)) for c in value)
    ):
        raise SchemaError(
            f"{where}: rect must be four numbers [x0, y0, x1, y1], got {value!r}"
        )
    x0, y0, x1, y1 = (float(c) for c in value)
    if x0 >= x1 or y0 >= y1:
        raise SchemaError(
            f"{where}: rect must satisfy x0 < x1 and y0 < y1, got {value!r}"
        )
    return (x0, y0, x1, y1)


def _parse_comment(
    raw: Any,
    index: int,
    colors: dict[str, tuple[float, float, float]],
    seen_ids: set[str],
) -> Comment:
    """Validate a single comment object."""
    where = f"comments[{index}]"
    if not isinstance(raw, dict):
        raise SchemaError(f"{where}: expected an object, got {type(raw).__name__}")
    raw = {k: v for k, v in raw.items() if not k.startswith("_")}

    known = {"id", "page", "anchor_text", "rect", "severity", "title", "body"}
    unknown = set(raw) - known
    if unknown:
        raise SchemaError(f"{where}: unknown keys {sorted(unknown)}")

    title = raw.get("title")
    body = raw.get("body")
    if not isinstance(title, str) or not title.strip():
        raise SchemaError(f"{where}: 'title' is required and must be a non-empty string")
    if not isinstance(body, str) or not body.strip():
        raise SchemaError(f"{where}: 'body' is required and must be a non-empty string")

    severity = raw.get("severity", DEFAULT_SEVERITY)
    if not isinstance(severity, str):
        raise SchemaError(f"{where}: 'severity' must be a string")
    severity = severity.lower()
    if severity not in colors:
        raise SchemaError(
            f"{where}: unknown severity {severity!r}; "
            f"known severities: {sorted(colors)} "
            f"(add custom ones via the top-level 'colors' header)"
        )

    page = raw.get("page")
    if page is not None and (not isinstance(page, int) or page < 1):
        raise SchemaError(f"{where}: 'page' must be a positive integer (1-indexed)")

    anchor_text = raw.get("anchor_text")
    rect_raw = raw.get("rect")
    if (anchor_text is None) == (rect_raw is None):
        raise SchemaError(
            f"{where}: exactly one of 'anchor_text' or 'rect' is required"
        )

    rect: tuple[float, float, float, float] | None = None
    if rect_raw is not None:
        rect = _parse_rect(rect_raw, where)
        if page is None:
            raise SchemaError(
                f"{where}: 'rect' anchors require an explicit 'page' "
                f"(coordinates are page-relative)"
            )
    elif not isinstance(anchor_text, str) or not anchor_text.strip():
        raise SchemaError(f"{where}: 'anchor_text' must be a non-empty string")

    cid = raw.get("id")
    if cid is None:
        cid = _derive_id(raw, index)
    elif not isinstance(cid, str) or not cid.strip():
        raise SchemaError(f"{where}: 'id' must be a non-empty string")
    if cid in seen_ids:
        raise SchemaError(f"{where}: duplicate comment id {cid!r}")
    seen_ids.add(cid)

    return Comment(
        id=cid,
        title=title,
        body=body,
        severity=severity,
        page=page,
        anchor_text=anchor_text,
        rect=rect,
    )


def parse_comments(data: Any) -> CommentSet:
    """Parse already-decoded JSON into a validated :class:`CommentSet`.

    Raises:
        SchemaError: on any structural or value problem; the message names the
            offending entry.
    """
    colors = dict(DEFAULT_COLORS)
    if isinstance(data, dict):
        data = {k: v for k, v in data.items() if not k.startswith("_")}
        unknown = set(data) - {"colors", "comments"}
        if unknown:
            raise SchemaError(f"unknown top-level keys {sorted(unknown)}")
        header = data.get("colors", {})
        if not isinstance(header, dict):
            raise SchemaError("'colors' must be an object mapping severity to [r, g, b]")
        for name, value in header.items():
            if name.startswith("_"):
                continue
            colors[name.lower()] = _parse_color(name, value)
        raw_comments = data.get("comments")
        if not isinstance(raw_comments, list):
            raise SchemaError("'comments' is required and must be a list")
    elif isinstance(data, list):
        raw_comments = data
    else:
        raise SchemaError(
            "comments file must be a JSON list of comments, or an object "
            "with a 'comments' list"
        )

    if not raw_comments:
        raise SchemaError("the comments list is empty")

    seen_ids: set[str] = set()
    comments = [
        _parse_comment(raw, i, colors, seen_ids) for i, raw in enumerate(raw_comments)
    ]
    return CommentSet(comments=comments, colors=colors)


def load_comments(path: str | Path) -> CommentSet:
    """Read and validate a comments JSON file.

    Raises:
        SchemaError: if the file is unreadable, not valid JSON, or invalid.
    """
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SchemaError(f"cannot read {path}: {exc}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SchemaError(f"{path} is not valid JSON: {exc}") from exc
    return parse_comments(data)
