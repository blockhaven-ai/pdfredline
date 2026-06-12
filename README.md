# pdfredline

Pin review comments onto PDFs as real, clickable annotations (highlights, region
boxes, sticky notes), driven by a JSON sidecar file. For document review
workflows where the reviewer cannot edit the source document.

Each comment becomes exactly one annotation:

| Anchor | Result |
|---|---|
| `anchor_text` found | highlight over the first match, comment in its popup |
| `rect` | bordered box over the region (logos, charts, image-only text) |
| `anchor_text` not found | sticky note at the top-left of the page, so the comment is not dropped |

Annotations open in any standard viewer (Preview, Acrobat, browsers) and are
replyable there.

## Install

```bash
pip install pdfredline
```

Requires Python >= 3.10. The only dependency is [PyMuPDF](https://pymupdf.readthedocs.io/).

## Quickstart

```bash
# 1. Write an example sidecar to edit
pdfredline init comments.json

# 2. Apply it
pdfredline apply input.pdf comments.json -o reviewed.pdf

# 3. Confirm one annotation per comment
pdfredline verify reviewed.pdf comments.json
```

To try it without your own document:

```bash
python3 examples/make_sample_pdf.py sample.pdf
pdfredline apply sample.pdf examples/comments.json -o sample.redlined.pdf
pdfredline verify sample.redlined.pdf examples/comments.json
```

(The example sidecar includes one deliberately unmatched anchor to demonstrate
the sticky-note fallback, so `apply` exits with code 1 there.)

## Commands

| Command | Description |
|---|---|
| `pdfredline apply INPUT.pdf COMMENTS.json [-o OUTPUT.pdf]` | annotate; default output is `INPUT.redlined.pdf` next to the source |
| `pdfredline verify ANNOTATED.pdf COMMENTS.json` | list the tool's annotations and check each comment is present exactly once |
| `pdfredline strip ANNOTATED.pdf [-o OUTPUT.pdf]` | remove the tool's annotations (in place by default); other annotations are untouched |
| `pdfredline init [PATH] [--force]` | write an example `comments.json` (default path `comments.json`) |

## Comments JSON schema

The sidecar is either a bare JSON list of comment objects, or an object with an
optional `colors` header:

```json
{
  "colors": {
    "question": [0.55, 0.25, 0.85]
  },
  "comments": [
    {
      "id": "overstated-accuracy",
      "page": 1,
      "anchor_text": "guarantees complete accuracy",
      "severity": "blocker",
      "title": "Overstated claim",
      "body": "No system guarantees complete accuracy. Rephrase."
    },
    {
      "page": 1,
      "rect": [355, 55, 535, 105],
      "severity": "minor",
      "title": "Low-resolution image",
      "body": "Replace with a vector version."
    }
  ]
}
```

### Comment fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `title` | string | yes | short label, shown first in the popup |
| `body` | string | yes | the full comment |
| `anchor_text` | string | one of these two | substring to highlight; the first match wins. Keep it short and distinctive (3-6 words) so it does not span line breaks |
| `rect` | `[x0, y0, x1, y1]` | one of these two | region to box, in PDF points, origin at the top-left of the page; requires `page`. Must satisfy `x0 < x1` and `y0 < y1` |
| `page` | integer | only with `rect` | 1-indexed. When omitted with `anchor_text`, every page is searched and the first match wins |
| `severity` | string | no | defaults to `suggestion`; case-insensitive; must be a known severity (see below) |
| `id` | string | no | stable identifier used for idempotency and `verify`/`strip` matching. When omitted, a stable id is derived from the comment's content |

Keys starting with `_` are ignored everywhere, so sidecars can carry inline
notes (`"_doc": "..."`).

### Severities and colors

Defaults:

| Severity | Color | RGB |
|---|---|---|
| `blocker` | red | `[0.86, 0.10, 0.10]` |
| `major` | orange | `[1.00, 0.55, 0.00]` |
| `minor` | yellow | `[0.90, 0.75, 0.00]` |
| `suggestion` | blue | `[0.20, 0.50, 1.00]` |

The top-level `colors` header overrides these or adds new severities. Values
are `[r, g, b]` with components in `0..1`. A comment using a severity that is
neither a default nor defined in `colors` is rejected with an error naming the
known severities.

### Validation

`apply` and `verify` validate the sidecar before touching the PDF and exit
with code 2 on the first problem, naming the offending entry. Checked:
required fields, unknown keys, unknown severities, malformed rects,
`anchor_text`/`rect` exclusivity, page bounds, duplicate ids, malformed JSON.

A *valid* comment whose `anchor_text` simply does not occur in the document is
not an error: it falls back to a sticky note (exit code 1, see below).

## Idempotency and strip semantics

Every annotation the tool creates is tagged via its PDF Subject field
(`pdfredline:<id>`) and author field (`pdfredline`).

- **Re-applying the same sidecar does not duplicate annotations.** `apply`
  skips any comment whose tag is already present in the document and reports
  it under `skipped`. Adding new comments to the sidecar and re-running
  applies only the new ones.
- **`strip` removes only the tool's annotations.** Annotations made by other
  people or tools (anything without the `pdfredline:` Subject tag) are left
  intact. By default the file is rewritten in place (atomically); pass `-o`
  to write elsewhere.
- Changing a comment's content while keeping an explicit `id` re-uses the tag,
  so the old annotation is kept and the edit is *not* re-applied; `strip` then
  `apply` to refresh.

## Exit codes

| Code | `apply` | `verify` | `strip` |
|---|---|---|---|
| 0 | every comment anchored to its text or rect | every comment present exactly once | annotations removed |
| 1 | one or more comments fell back to a sticky note | comments missing or duplicated | — |
| 2 | error (invalid JSON/schema, unreadable PDF, page out of range) | error | error |

## Development

```bash
pip install -e ".[test]"
pytest
```

## License

Apache-2.0. See [LICENSE](LICENSE).
