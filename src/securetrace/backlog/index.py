"""Pure core of deterministic BACKLOG.md line-index sync.

Works on plain text only (no file I/O, no printing): malformed documents
raise :class:`securetrace.errors.FormatError`. File I/O, user-facing
messages, and exit codes live in :mod:`securetrace.cli`.

This module is a faithful port of the pinned ``scripts/backlog_index.py``
(spec: ``algorithms/line-index-sync.md``), including the intentional
priority-parsing quirk documented as LLT-0009: a bulleted
``- **Priority:** X`` line never matches ``PRIORITY_RE``, so such items are
indexed as ``Low``. The quirk is preserved on purpose; fixing it is a
separate, doc-first change.

Behavior contract (mirrors the pinned script exactly):

- the index block is delimited by ``<!-- INDEX:BEGIN … -->`` /
  ``<!-- INDEX:END -->``; its interior is a TSV table whose first row always
  describes the block itself, followed by one row per section marker
  (``<!-- BACKLOG:HEADER|QUEUE|CONSTRAINTS -->`` or
  ``<!-- BACKLOG:ITEM:<ID> -->``);
- reported line numbers are 1-indexed and correct for the file *after* the
  rewrite (single-pass delta computation — no fixed-point iteration);
- the sync is idempotent: ``synced_text(synced_text(t)) == synced_text(t)``;
- input newlines are normalized exactly as universal-newline text reads do
  (``\\r\\n`` and ``\\r`` → ``\\n``), output is always LF, and a trailing
  newline is preserved iff the input had one (LLT-0011).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from securetrace.errors import FormatError

__all__ = [
    "DEFAULT_PRIORITY",
    "PRIORITY_MAP",
    "RESERVED",
    "Row",
    "Section",
    "TSV_HEADER",
    "find_index_block",
    "find_sections",
    "index_rows",
    "is_fresh",
    "synced_text",
]

BEGIN_RE = re.compile(r"^<!--\s*INDEX:BEGIN\b.*?-->\s*$")
END_RE = re.compile(r"^<!--\s*INDEX:END\s*-->\s*$")
KIND_MARKER_RE = re.compile(r"^<!--\s*BACKLOG:(?P<kind>[A-Z][A-Z0-9_]*)\s*-->\s*$")
ITEM_MARKER_RE = re.compile(r"^<!--\s*BACKLOG:ITEM:(?P<item>[A-Z][A-Z0-9_]*)\s*-->\s*$")
TSV_HEADER = "id\ttitle\tstatus\tpriority\tstart_line\tend_line"
RESERVED = ("HEADER", "QUEUE", "CONSTRAINTS")
PRIORITY_RE = re.compile(r"^\s*\*\*Priority:\*\*\s*(?P<val>.+)$", re.IGNORECASE)
PRIORITY_MAP = {"HIGH": "High", "MEDIUM": "Medium", "LOW": "Low"}
DEFAULT_PRIORITY = "Low"


@dataclass(frozen=True)
class Row:
    """One row of the regenerated TSV index (line numbers of the post-rewrite file)."""

    id: str
    title: str
    status: str
    priority: str
    start_line: int
    end_line: int


@dataclass(frozen=True)
class Section:
    """A section marker occurrence in file order (1-indexed start line)."""

    row_id: str
    start_line: int
    is_item: bool


def _normalize_newlines(text: str) -> str:
    """Mirror universal-newline text reads: CRLF and lone CR become LF (LLT-0011)."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def find_index_block(lines: list[str]) -> tuple[int, int]:
    """Return (begin, end) 0-indexed line numbers of the first index block.

    Raises:
        FormatError: markers missing, or no interior lines between them.
    """
    begin = end = None
    for i, line in enumerate(lines):
        if begin is None and BEGIN_RE.match(line):
            begin = i
        elif begin is not None and END_RE.match(line):
            end = i
            break
    if begin is None or end is None:
        raise FormatError("missing <!-- INDEX:BEGIN --> / <!-- INDEX:END --> markers")
    if end <= begin + 1:
        raise FormatError(
            "index block is empty or malformed (needs interior lines between BEGIN and END)"
        )
    return begin, end


def _marker_on_line(line: str) -> tuple[str, str | None] | None:
    """Parse one section marker line.

    Returns ``(kind, item_id)``: a reserved kind (``HEADER``/``QUEUE``/
    ``CONSTRAINTS``) with ``item_id`` ``None``, or ``"ITEM:<id>"`` with the
    item id. ``None`` means "not a marker" — unknown kinds (and the bare word
    ``ITEM``) are ignored, exactly as with the former single-regex form.
    """
    m = KIND_MARKER_RE.match(line)
    if m is not None:
        kind = m.group("kind")
        return (kind, None) if kind in RESERVED else None
    m = ITEM_MARKER_RE.match(line)
    if m is not None:
        return (f"ITEM:{m.group('item')}", m.group("item"))
    return None


def find_sections(lines: list[str], index_end: int) -> list[Section]:
    """Return all section markers in file order.

    Guard order is pinned (inside-block check first, then reserved item ids,
    then duplicates). A marker used twice, a reserved id used as an item id,
    or a marker at/inside the index block makes the file malformed.

    Raises:
        FormatError: any of the structural guards above fails.
    """
    sections: list[Section] = []
    seen: set[str] = set()
    for i, line in enumerate(lines):
        marker = _marker_on_line(line)
        if marker is None:
            continue
        if i <= index_end:
            raise FormatError(
                f"marker at line {i + 1} is at or inside the index block; "
                "markers must come after INDEX:END"
            )
        kind, item_id = marker
        is_item = kind.startswith("ITEM:")
        row_id = item_id if is_item else kind
        if is_item and row_id in RESERVED:
            raise FormatError(
                f"item id {row_id} is reserved for a section name; "
                f"item ids must not be {', '.join(RESERVED)}"
            )
        if kind in seen:
            raise FormatError(f"duplicate section marker: {kind}")
        seen.add(kind)
        sections.append(Section(row_id=row_id, start_line=i + 1, is_item=is_item))
    if not any(section.is_item for section in sections):
        raise FormatError("no <!-- BACKLOG:ITEM:<ID> --> markers found")
    return sections


def parse_item_heading(item_id: str, lines: list[str], start: int, stop: int) -> tuple[str, str]:
    """Return (title, status) from the first ``## <ID>. …`` heading in lines[start:stop].

    Args are 0-indexed (stop exclusive). Both are ``""`` when the heading is
    missing or carries no status. Status is normalized: ``IN PROGRESS`` →
    ``IN_PROGRESS``.

    The strict form requires ``— **STATUS**`` with STATUS in
    OPEN/IN PROGRESS/DONE/CANCELLED (case-insensitive); a loose ``## <ID>.
    <title>`` heading without a status is accepted with empty status.
    """
    strict = re.compile(
        r"^\s*##\s+" + re.escape(item_id) + r"\.\s+(?P<title>.+?)\s*[—–-]\s*"
        r"\*\*(?P<status>OPEN|IN PROGRESS|DONE|CANCELLED)\b[^*]*\*\*\s*$",
        re.IGNORECASE,
    )
    loose = re.compile(r"^\s*##\s+" + re.escape(item_id) + r"\.\s+(?P<title>.*\S)\s*$")
    for line in lines[start:stop]:
        m = strict.match(line)
        if m:
            return m.group("title").strip(), m.group("status").upper().replace(" ", "_")
        m = loose.match(line)
        if m:
            return m.group("title").strip(), ""
    return "", ""


def parse_priority(item_id: str, lines: list[str], start: int, stop: int) -> str:
    """Return the item's effective priority from the first ``**Priority:**`` line.

    Args are 0-indexed (stop exclusive). Input is case-insensitive, output is
    normalized to High/Medium/Low; absent → :data:`DEFAULT_PRIORITY` (G9).

    Raises:
        FormatError: the value is present but not in the High/Medium/Low
            vocabulary.

    Note (LLT-0009, pinned): a bulleted ``- **Priority:** X`` line never
    matches ``PRIORITY_RE``, so it is silently ignored and the item indexes
    as ``Low``. Preserved on purpose.
    """
    for line in lines[start:stop]:
        m = PRIORITY_RE.match(line)
        if m:
            val = PRIORITY_MAP.get(m.group("val").strip().upper())
            if val is None:
                raise FormatError(
                    f"item {item_id}: priority '{m.group('val').strip()}' "
                    "is not one of High, Medium, Low (G9)"
                )
            return val
    return DEFAULT_PRIORITY


def build_rows(
    sections: list[Section],
    lines: list[str],
    total_lines: int,
    begin: int,
    end: int,
) -> list[Row]:
    """Compute the TSV rows for the current body, in post-rewrite line numbers.

    Rewriting the index interior changes its length, which shifts every
    section that follows (all of them — markers must come after INDEX:END).
    ``delta`` is that shift; every reported line number already includes it,
    so the result is idempotent under a fresh check.
    """
    old_interior = end - begin - 1
    n_rows = 1 + len(sections)  # INDEX_BLOCK + one row per section
    new_interior = 1 + n_rows  # TSV header + rows
    delta = new_interior - old_interior

    rows: list[Row] = [Row("INDEX_BLOCK", "-", "-", "-", begin + 1, begin + new_interior + 2)]
    for idx, section in enumerate(sections):
        stop = sections[idx + 1].start_line - 1 if idx + 1 < len(sections) else total_lines
        title, status, priority = "-", "-", "-"
        if section.is_item:
            t, s = parse_item_heading(section.row_id, lines, section.start_line - 1, stop - 1)
            title, status = t or "-", s or "-"
            priority = parse_priority(section.row_id, lines, section.start_line - 1, stop - 1)
        rows.append(
            Row(
                id=section.row_id,
                title=title,
                status=status,
                priority=priority,
                start_line=section.start_line + delta,
                end_line=stop + delta,
            )
        )
    return rows


def _cell(s: str) -> str:
    """Render a TSV cell: tabs become spaces, empty becomes ``-``."""
    return s.replace("\t", " ").strip() or "-"


def render(rows: list[Row]) -> list[str]:
    """Render rows as TSV lines (header first)."""
    out = [TSV_HEADER]
    out.extend(
        f"{_cell(r.id)}\t{_cell(r.title)}\t{_cell(r.status)}\t{_cell(r.priority)}"
        f"\t{r.start_line}\t{r.end_line}"
        for r in rows
    )
    return out


def index_rows(text: str) -> list[Row]:
    """Parse ``text`` and return the TSV rows its index block must contain.

    Line numbers are 1-indexed and describe the file *after* a sync rewrite.

    Raises:
        FormatError: structural guard failure (see :func:`find_sections`) or
            an out-of-vocabulary priority value.
    """
    normalized = _normalize_newlines(text)
    lines = normalized.splitlines()
    begin, end = find_index_block(lines)
    sections = find_sections(lines, end)
    return build_rows(sections, lines, len(lines), begin, end)


def synced_text(text: str) -> str:
    """Return ``text`` with the index-block interior rewritten from the body.

    Output is always LF-terminated; a trailing newline is preserved iff the
    input had one. Idempotent.

    Raises:
        FormatError: structural guard failure or out-of-vocabulary priority.
    """
    normalized = _normalize_newlines(text)
    had_trailing_newline = normalized.endswith("\n")
    lines = normalized.splitlines()
    begin, end = find_index_block(lines)
    sections = find_sections(lines, end)
    rows = build_rows(sections, lines, len(lines), begin, end)
    block = render(rows)
    new_lines = lines[: begin + 1] + block + lines[end:]
    out = "\n".join(new_lines)
    if had_trailing_newline:
        out += "\n"
    return out


def is_fresh(text: str) -> bool:
    """Return True iff the stored index block is exactly what the body requires.

    Equivalent to the pinned ``lines[begin+1:end] == block`` comparison for
    valid text. Malformed text (which callers reject before asking) counts
    as not fresh rather than raising.
    """
    try:
        return synced_text(text) == _normalize_newlines(text)
    except FormatError:
        return False
