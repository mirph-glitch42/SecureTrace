"""Registry document parser/renderer (B10 WI 6).

``algorithms/INDEX.md`` is a pure render of the ``registry`` store (spec:
``algorithms/deterministic-doc-pipeline.md``, contracts C1–C4):

- :func:`render_registry` — store → doc text. Constants (title line, the
  generated no-hand-edit header, the table header/separator lines, the
  rules heading) come from code; the data (intro blockquote lines, rows,
  rule texts) come from the store. Rows are emitted in stored (slug-sorted)
  order and the rules are numbered 1..N.
- :func:`parse_registry` — doc text → store. Accepts exactly the grammar
  :func:`render_registry` emits, plus the grandfathered doc that lacks the
  generated header. The row cell grammar is strict: the Slug and Status
  cells are backticked, the File cell is ``[<file>](<file>)`` with link
  text equal to the target, and a row cell containing `` | `` is
  unparseable by construction (the split must yield exactly 6 cells).

Both functions are pure (no file I/O, no clock, no environment). Errors:
:class:`SchemaError` for a store that fails validation (the render gate
runs first; the parser runs it on the parsed store too — duplicate slugs,
unsorted rows), :class:`FormatError` for a malformed document — the
command layer maps both to exit 2.
"""

from __future__ import annotations

import re

from securetrace.docs import RENDERER_VERSION
from securetrace.docs.canonical import DOC_TITLES, generated_header, skip_generated_header
from securetrace.docs.schema import (
    REGISTRY_ROW_KEYS,
    SCHEMA_VERSION,
    validate_store,
)
from securetrace.errors import FormatError

__all__ = ["parse_registry", "render_registry"]

TABLE_HEADER = "| Slug | Name | Version | Status | File | One-line summary |"
TABLE_SEPARATOR = "|---|---|---|---|---|---|"
RULES_HEADING = "## Rules"

#: Cell grammars (strict — they must invert :func:`_render_row` exactly).
SLUG_CELL_RE = re.compile(r"^`(?P<slug>[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)`$")
VERSION_CELL_RE = re.compile(r"^(?P<version>\d+\.\d+\.\d+)$")
STATUS_CELL_RE = re.compile(r"^`(?P<status>draft|implemented|backfilled|deprecated)`$")
FILE_CELL_RE = re.compile(r"^\[(?P<text>[^\[\]]+)\]\((?P<target>[^()\s]+)\)$")
RULE_LINE_RE = re.compile(r"^(?P<num>\d+)\. (?P<text>\S.*)$")


# --------------------------------------------------------------------- render


def _render_row(row: dict) -> str:
    """Render one registry row.

    The Slug and Status cells are backticked, the File cell is a markdown
    link whose text equals its target (the relative .md path), and the
    three prose cells are plain — joined by `` | `` between ``| `` and
    `` |``. Every cell is validated non-empty by the schema gate, so the
    rendered line always splits back into exactly six cells.
    """
    cells = (
        f"`{row['slug']}`",
        row["name"],
        row["version"],
        f"`{row['status']}`",
        f"[{row['file']}]({row['file']})",
        row["summary"],
    )
    return "| " + " | ".join(cells) + " |"


def render_registry(store: dict) -> str:
    """Render a validated ``registry`` store to the ``algorithms/INDEX.md`` text (pure).

    The document is: title, blank, the generated no-hand-edit header, blank,
    the intro blockquote lines, blank, the fixed six-column table (header,
    separator, one row per algorithm in stored slug-sorted order), blank,
    the ``## Rules`` heading, blank, and the rule lines numbered 1..N —
    ending with exactly one trailing newline.

    Raises:
        SchemaError: the store fails validation (the schema gate runs first).
    """
    validate_store(store)
    lines: list[str] = [
        DOC_TITLES["registry"],
        "",
        *generated_header("registry", renderer_version=RENDERER_VERSION),
        "",
        *store["intro"],
        "",
        TABLE_HEADER,
        TABLE_SEPARATOR,
    ]
    for row in store["rows"]:
        lines.append(_render_row(row))
    lines += ["", RULES_HEADING, ""]
    for num, rule in enumerate(store["rules"], start=1):
        lines.append(f"{num}. {rule}")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------- parse


def _split_row_cells(line: str, lineno: int) -> list[str]:
    """Split one row line into its six cells.

    Raises:
        FormatError: the line is not a row, or the split yields a cell count
            other than 6 (a cell containing `` | `` is unparseable by
            construction).
    """
    if not line.startswith("| ") or not line.endswith(" |"):
        raise FormatError(
            f"line {lineno} is not a registry row (a row is '| cell | … | cell |')"
        )
    cells = line[2:-2].split(" | ")
    if len(cells) != 6:
        raise FormatError(
            f"line {lineno} has {len(cells)} cells; a registry row has exactly 6 "
            "(a cell containing ' | ' is unparseable)"
        )
    return cells


def _parse_row(line: str, lineno: int) -> dict:
    """Parse one row line into the row record (keys in canonical order).

    Raises:
        FormatError: any cell fails its grammar (backticked kebab-case slug,
            non-empty prose cell, MAJOR.MINOR.PATCH version, backticked
            closed-vocabulary status, ``[<file>](<file>)`` with text equal to
            target).
    """
    cells = _split_row_cells(line, lineno)
    slug_m = SLUG_CELL_RE.match(cells[0])
    if slug_m is None:
        raise FormatError(
            f"line {lineno}: the Slug cell must be a backticked kebab-case slug, "
            f"got {cells[0]!r}"
        )
    if not cells[1].strip():
        raise FormatError(f"line {lineno}: the Name cell must be non-empty")
    if VERSION_CELL_RE.match(cells[2]) is None:
        raise FormatError(
            f"line {lineno}: the Version cell must be MAJOR.MINOR.PATCH, got {cells[2]!r}"
        )
    status_m = STATUS_CELL_RE.match(cells[3])
    if status_m is None:
        raise FormatError(
            f"line {lineno}: the Status cell must be a backticked one of "
            f"draft/implemented/backfilled/deprecated, got {cells[3]!r}"
        )
    file_m = FILE_CELL_RE.match(cells[4])
    if file_m is None or file_m.group("text") != file_m.group("target"):
        raise FormatError(
            f"line {lineno}: the File cell must be '[<file>](<file>)' with the link "
            f"text equal to the target, got {cells[4]!r}"
        )
    if not cells[5].strip():
        raise FormatError(f"line {lineno}: the summary cell must be non-empty")
    return {
        "slug": slug_m.group("slug"),
        "name": cells[1],
        "version": cells[2],
        "status": status_m.group("status"),
        "file": file_m.group("target"),
        "summary": cells[5],
    }


def _parse_rules(lines: list[str], start: int, expected: int) -> list[str]:
    """Parse the strictly numbered rule lines at *start* (0-indexed).

    Every line must be ``<n>. <text>`` with *n* the 1-based position, and
    the block must run exactly to the end of the document.

    Raises:
        FormatError: a line is not a rule line, the numbering is not
            strictly 1..N, or the block does not end at the document end.
    """
    if start + expected > len(lines):
        raise FormatError(f"the rules section must contain {expected} rule lines")
    rules: list[str] = []
    for offset in range(expected):
        line = lines[start + offset]
        m = RULE_LINE_RE.match(line)
        if m is None or int(m.group("num")) != offset + 1:
            raise FormatError(
                f"line {start + offset + 1} is not rule line {offset + 1}; the rules "
                "must be numbered strictly 1..N"
            )
        rules.append(m.group("text"))
    return rules


def _parse_table_section(lines: list[str], cursor: int) -> tuple[list[str], list[dict], int]:
    """Parse the intro prose and the slug table.

    Returns the intro lines, the row records, and the index of the first
    blank line after the table.

    Raises:
        FormatError: table header missing, intro empty or not blank-
            terminated, separator line missing, or the table has no rows.
    """
    header = next((i for i in range(cursor, len(lines)) if lines[i] == TABLE_HEADER), None)
    if header is None:
        raise FormatError(
            f"the registry document is missing its table header line {TABLE_HEADER!r}"
        )
    if header < cursor + 2:
        raise FormatError(
            "the intro must be non-empty and end with a blank line before the table"
        )
    if lines[header - 1] != "":
        raise FormatError("the intro must be followed by a blank line before the table")
    intro = list(lines[cursor : header - 1])
    if header + 1 >= len(lines) or lines[header + 1] != TABLE_SEPARATOR:
        raise FormatError(
            f"the table header must be followed by the separator line {TABLE_SEPARATOR!r}"
        )
    j = header + 2
    while j < len(lines) and lines[j] != "":
        j += 1
    rows = [_parse_row(lines[k], k + 1) for k in range(header + 2, j)]
    if not rows:
        raise FormatError("the registry table must contain at least one row")
    return intro, rows, j


def _parse_rules_section(lines: list[str], j: int) -> list[str]:
    """Parse the ``## Rules`` section that follows the table blank line.

    Raises:
        FormatError: the blank-line / rules-heading preamble is missing, or
            the rules block is empty or mis-numbered.
    """
    if j >= len(lines):
        raise FormatError("the table must be followed by a blank line before the rules section")
    if j + 2 >= len(lines) or lines[j + 1] != RULES_HEADING or lines[j + 2] != "":
        raise FormatError(
            "the table must be followed by a blank line and the '## Rules' heading"
        )
    rules_start = j + 3
    if rules_start >= len(lines):
        raise FormatError("the rules section must contain at least one rule line")
    return _parse_rules(lines, rules_start, len(lines) - rules_start)


def parse_registry(text: str) -> dict:
    """Parse an ``algorithms/INDEX.md`` text into the ``registry`` store (pure).

    Accepts exactly the grammar :func:`render_registry` emits, plus the
    grandfathered doc that lacks the generated header. The rows must pass
    schema validation (slug-sorted, no duplicates, closed vocabularies).

    Raises:
        FormatError: the document is malformed (bad title, missing table
            header or separator, missing rules heading, bad cell grammar,
            unparseable cell, non-sequential rule numbering).
        SchemaError: the parsed store fails schema validation (e.g.
            duplicate slugs, rows not sorted by slug).
    """
    if not isinstance(text, str):
        raise FormatError("the registry document must be a UTF-8 string")
    lines = text.splitlines()
    if not lines or lines[0] != DOC_TITLES["registry"]:
        raise FormatError(
            f"the registry document must start with the title line {DOC_TITLES['registry']!r}"
        )
    if len(lines) < 2 or lines[1] != "":
        raise FormatError("line 2 of the registry document must be blank")
    cursor = skip_generated_header(lines, 2)
    intro, rows, j = _parse_table_section(lines, cursor)
    rules = _parse_rules_section(lines, j)

    store = {
        "doc": "registry",
        "schema_version": SCHEMA_VERSION,
        "intro": intro,
        "rows": rows,
        "rules": rules,
    }
    validate_store(store)
    return store
