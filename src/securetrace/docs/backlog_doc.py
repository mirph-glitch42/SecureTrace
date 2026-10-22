"""Backlog document parser/renderer (B10 WI 4).

``BACKLOG.md`` is a pure render of the ``backlog`` store (spec:
``algorithms/deterministic-doc-pipeline.md``, contracts C1–C4):

- :func:`render_backlog` — store → doc text. Constants (title line, section
  headings, the generated no-hand-edit header, the TSV index block) come from
  code; the data (prose lines, items, fields) come from the store. The index
  block is computed by the legacy :mod:`securetrace.backlog.index` core
  (``synced_text``), which preserves the pinned LLT-0009 priority quirk.
- :func:`parse_backlog` — doc text → store. Accepts exactly the grammar
  ``render_backlog`` emits, plus grandfathered docs that lack the generated
  header. The embedded index block must be fresh (recomputed via
  ``is_fresh``); a mismatch is a malformed document.

Both functions are pure (no file I/O, no clock, no environment). Errors:
:class:`SchemaError` for a store that fails validation (the render gate runs
first), :class:`FormatError` for a malformed document — the command layer
maps both to exit 2.
"""

from __future__ import annotations

import re

from securetrace.backlog.index import (
    TSV_HEADER,
    find_index_block,
    find_sections,
    is_fresh,
    synced_text,
)
from securetrace.docs import RENDERER_VERSION
from securetrace.docs.canonical import DOC_TITLES, generated_header, skip_generated_header
from securetrace.docs.schema import SCHEMA_VERSION, validate_store
from securetrace.errors import FormatError

__all__ = ["parse_backlog", "render_backlog"]

INDEX_BEGIN = "<!-- INDEX:BEGIN format=tsv version=1 -->"
INDEX_END = "<!-- INDEX:END -->"

#: Section heading per reserved section kind (a code constant — the store
#: carries only the prose lines under each heading).
HEADING_FOR = {
    "HEADER": "## Status",
    "QUEUE": "## Queue (execution order)",
    "CONSTRAINTS": "## Standing constraints",
}

FIELD_INLINE_RE = re.compile(r"^-\s\*\*(?P<name>[^*]+?):\*\*[ \t]+(?P<rest>\S.*)$")
FIELD_EMPTY_RE = re.compile(r"^-\s\*\*(?P<name>[^*]+?):\*\*[ \t]*$")
UPDATED_LINE_RE = re.compile(r"\*\*Updated:\*\*[ \t]*(\d{4}-\d{2}-\d{2})[ \t]*$")
_ITEM_HEADING_TEMPLATE = (
    r"^## " + r"(?P<item_id>[A-Z0-9_]+)" + r"\. (?P<title>.+?) — "
    r"\*\*(?P<status>OPEN|IN PROGRESS|DONE|CANCELLED)\*\*$"
)
_ITEM_HEADING_RE = re.compile(_ITEM_HEADING_TEMPLATE)


# --------------------------------------------------------------------- render


def _render_field(name: str, lines: list[str]) -> list[str]:
    """Render one field.

    The first line is inlined after ``- **name:**`` iff it is non-blank and
    not indented; otherwise the bullet line stands alone and the lines (which
    may be empty, blank, or indented) follow verbatim. Both forms parse back
    to the same ``{name, lines}`` (contract C2).
    """
    if not lines or not lines[0] or lines[0][0] in " \t":
        return [f"- **{name}:**", *lines]
    return [f"- **{name}:** {lines[0]}", *lines[1:]]


def render_backlog(store: dict) -> str:
    """Render a validated ``backlog`` store to the ``BACKLOG.md`` text (pure).

    The document is: title, blank, the generated no-hand-edit header, blank,
    the TSV index block, blank, the HEADER/QUEUE sections, the item sections
    in stored (strictly increasing id) order, and the CONSTRAINTS section —
    ending with exactly one trailing newline. The index block is (re)computed
    over this final layout by the legacy core, so the result is always fresh
    and ``synced_text(render_backlog(store)) == render_backlog(store)``.

    Raises:
        SchemaError: the store fails validation (the schema gate runs first).
    """
    validate_store(store)
    lines: list[str] = [
        DOC_TITLES["backlog"],
        "",
        *generated_header("backlog", renderer_version=RENDERER_VERSION),
        "",
        INDEX_BEGIN,
        TSV_HEADER,  # placeholder interior; synced_text rewrites it with the computed rows
        INDEX_END,
        "",
    ]
    lines += ["<!-- BACKLOG:HEADER -->", HEADING_FOR["HEADER"], ""]
    lines += list(store["header"])
    lines += ["", "<!-- BACKLOG:QUEUE -->", HEADING_FOR["QUEUE"], ""]
    lines += list(store["queue"])
    for item in store["items"]:
        lines += ["", f"<!-- BACKLOG:ITEM:{item['id']} -->"]
        lines += [f"## {item['id']}. {item['title']} — **{item['status']}**", ""]
        for field in item["fields"]:
            lines += _render_field(field["name"], field["lines"])
    lines += ["", "<!-- BACKLOG:CONSTRAINTS -->", HEADING_FOR["CONSTRAINTS"], ""]
    lines += list(store["constraints"])
    return synced_text("\n".join(lines) + "\n")


# --------------------------------------------------------------------- parse


def _check_section_order(sections: list) -> list:
    """Enforce HEADER, QUEUE, item sections…, CONSTRAINTS; return the items.

    Raises:
        FormatError: the reserved sections are missing or out of order, or a
            non-item section sits between the item sections.
    """
    if len(sections) < 4:
        raise FormatError(
            "backlog needs the HEADER, QUEUE, at least one item, and CONSTRAINTS sections"
        )
    if (
        sections[0].row_id != "HEADER"
        or sections[1].row_id != "QUEUE"
        or sections[-1].row_id != "CONSTRAINTS"
    ):
        got = ", ".join(section.row_id for section in sections)
        raise FormatError(
            "section order must be HEADER, QUEUE, item sections, CONSTRAINTS; "
            f"got {got}"
        )
    items = sections[2:-1]
    for section in items:
        if not section.is_item:
            raise FormatError(
                f"unexpected non-item section {section.row_id} between the item sections"
            )
    return items


def _content_range(lines: list[str], sections: list, order_index: int) -> tuple[int, int]:
    """Return the [start, stop) content-line range of one section.

    The marker must be followed by its heading line (exact match against the
    code constant) and a blank line. For non-last sections the content ends at
    the blank line separating it from the next marker; for the last section it
    runs to the end of the document, which must be a content line (exactly one
    trailing newline in the file).

    Raises:
        FormatError: heading missing/mismatched, separator blank missing, or
            the content is empty (or the document ends with a blank line).
    """
    section = sections[order_index]
    m = section.start_line - 1  # 0-indexed marker line
    expected = HEADING_FOR.get(section.row_id)  # item headings are checked by the item parser
    if m + 2 >= len(lines):
        raise FormatError(f"section {section.row_id}: marker must be followed by its heading and a blank line")
    if expected is not None and lines[m + 1] != expected:
        raise FormatError(f"section {section.row_id}: heading must be {expected!r}")
    if lines[m + 2] != "":
        raise FormatError(f"section {section.row_id}: heading must be followed by a blank line")
    start = m + 3
    if order_index + 1 < len(sections):
        stop = sections[order_index + 1].start_line - 1  # 0-indexed next marker
        if stop <= start or lines[stop - 1] != "":
            raise FormatError(f"section {section.row_id} content must be non-empty and end with a blank line")
        return start, stop - 1
    if start >= len(lines) or lines[-1] == "":
        raise FormatError("the backlog document must end with its last content line (one trailing newline)")
    return start, len(lines)


def _parse_fields(item_id: str, lines: list[str], start: int, stop: int) -> list[dict]:
    """Parse the field lines of one item into ``{name, lines}`` records.

    A field starts at ``- **name:** rest`` (inline) or ``- **name:**``
    (standalone); continuation and blank lines belong to the current field.

    Raises:
        FormatError: the content carries no field at all, or a line precedes
            the first field line.
    """
    fields: list[dict] = []
    current: dict | None = None
    for i in range(start, stop):
        line = lines[i]
        match = FIELD_INLINE_RE.match(line)
        if match is not None:
            current = {"name": match.group("name"), "lines": [match.group("rest")]}
            fields.append(current)
            continue
        match = FIELD_EMPTY_RE.match(line)
        if match is not None:
            current = {"name": match.group("name"), "lines": []}
            fields.append(current)
            continue
        if current is None:
            raise FormatError(f"item {item_id}: line {i + 1} appears before the first field line")
        current["lines"].append(line)
    if not fields:
        raise FormatError(f"item {item_id} must contain at least one field line")
    return fields


def _extract_updated(header: list[str]) -> str:
    """Return the date of the header's ``**Updated:**`` status line.

    Raises:
        FormatError: the header does not contain exactly one such line.
    """
    dates = [m.group(1) for line in header if (m := UPDATED_LINE_RE.search(line)) is not None]
    if len(dates) != 1:
        raise FormatError(
            "the backlog header must contain exactly one line ending with '**Updated:** YYYY-MM-DD'"
        )
    return dates[0]


def parse_backlog(text: str) -> dict:
    """Parse a ``BACKLOG.md`` text into the ``backlog`` store (pure).

    Accepts exactly the grammar :func:`render_backlog` emits, plus
    grandfathered docs that lack the generated header. The embedded TSV index
    block must be fresh for the body.

    Raises:
        FormatError: the document is malformed (bad title, missing or
            mis-ordered section, stale index block, bad heading, no fields,
            no ``**Updated:**`` status line).
        SchemaError: the parsed store fails schema validation (e.g. duplicate
            field names, non-increasing item ids).
    """
    if not isinstance(text, str):
        raise FormatError("the backlog document must be a UTF-8 string")
    lines = text.splitlines()
    if not lines or lines[0] != DOC_TITLES["backlog"]:
        raise FormatError(f"the backlog document must start with the title line {DOC_TITLES['backlog']!r}")
    if len(lines) < 2 or lines[1] != "":
        raise FormatError("line 2 of the backlog document must be blank")
    cursor = skip_generated_header(lines, 2)
    if cursor < len(lines) and lines[cursor] == "":
        cursor += 1
    if cursor >= len(lines) or not lines[cursor].startswith("<!-- INDEX:BEGIN"):
        raise FormatError("the index block must follow the title (and optional generated header)")
    _, end = find_index_block(lines)
    sections = find_sections(lines, end)
    items = _check_section_order(sections)
    if not is_fresh(text):
        raise FormatError(
            "index block does not match the body (the document was likely hand-edited; "
            "update it via the securetrace CLI and re-render)"
        )
    header = list(lines[slice(*_content_range(lines, sections, 0))])
    queue = list(lines[slice(*_content_range(lines, sections, 1))])
    constraints = list(lines[slice(*_content_range(lines, sections, len(sections) - 1))])
    parsed_items: list[dict] = []
    for order_index, section in enumerate(items):
        start, stop = _content_range(lines, sections, 2 + order_index)
        item_id = section.row_id
        heading_match = _ITEM_HEADING_RE.match(lines[section.start_line])
        if heading_match is None or heading_match.group("item_id") != item_id:
            raise FormatError(
                f"item {item_id} heading must be '## {item_id}. <title> — **STATUS**'"
            )
        parsed_items.append(
            {
                "id": item_id,
                "title": heading_match.group("title"),
                "status": heading_match.group("status"),
                "fields": _parse_fields(item_id, lines, start, stop),
            }
        )
    store = {
        "doc": "backlog",
        "schema_version": SCHEMA_VERSION,
        "updated": _extract_updated(header),
        "header": header,
        "queue": queue,
        "items": parsed_items,
        "constraints": constraints,
    }
    validate_store(store)
    return store
