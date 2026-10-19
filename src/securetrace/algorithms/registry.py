"""Pure core of deterministic algorithm-document line-index sync.

Works on plain text only (no file I/O, no printing): malformed documents
raise :class:`securetrace.errors.FormatError`. File I/O, user-facing
messages, and exit codes live in :mod:`securetrace.cli`.

Same delta core as :mod:`securetrace.backlog.index`, with the simpler
``<!-- SECTION:<ID> -->`` marker model (``[A-Z0-9_]+``) and the 3-column
TSV ``id/start_line/end_line``. Faithful port of the pinned
``scripts/algorithm_index.py`` (spec: ``algorithms/line-index-sync.md``).
Guard order is pinned per script: the duplicate check runs **first**, then
the inside-block check (unlike the backlog variant).

Behavior contract (mirrors the pinned script exactly):

- the index block is delimited by ``<!-- INDEX:BEGIN … -->`` /
  ``<!-- INDEX:END -->``; its interior is a TSV table whose first row always
  describes the block itself, followed by one row per section;
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
    "Row",
    "TSV_HEADER",
    "find_index_block",
    "find_sections",
    "index_rows",
    "is_fresh",
    "synced_text",
]

BEGIN_RE = re.compile(r"^<!--\s*INDEX:BEGIN\b.*?-->\s*$")
END_RE = re.compile(r"^<!--\s*INDEX:END\s*-->\s*$")
SECTION_RE = re.compile(r"^<!--\s*SECTION:([A-Z0-9_]+)\s*-->\s*$")
TSV_HEADER = "id\tstart_line\tend_line"


@dataclass(frozen=True)
class Row:
    """One row of the regenerated TSV index (line numbers of the post-rewrite file)."""

    id: str
    start_line: int
    end_line: int


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


def find_sections(lines: list[str], index_end: int) -> list[tuple[str, int]]:
    """Return (section_id, start_line_1indexed) pairs in file order.

    Guard order is pinned (duplicate check first, then inside-block).

    Raises:
        FormatError: a section id is used twice, a section starts at/inside
            the index block, or no section markers exist.
    """
    sections: list[tuple[str, int]] = []
    seen: set[str] = set()
    for i, line in enumerate(lines):
        m = SECTION_RE.match(line)
        if not m:
            continue
        sid = m.group(1)
        if sid in seen:
            raise FormatError(f"duplicate section id: {sid}")
        seen.add(sid)
        if i <= index_end:
            raise FormatError(
                f"section {sid} starts at or inside the index block; "
                "sections must come after INDEX:END"
            )
        sections.append((sid, i + 1))
    if not sections:
        raise FormatError("no <!-- SECTION:<ID> --> markers found")
    return sections


def build_rows(
    sections: list[tuple[str, int]], total_lines: int, begin: int, end: int
) -> list[Row]:
    """Compute the TSV rows for the current body, in post-rewrite line numbers.

    Rewriting the index interior changes its length, which shifts every
    section that follows (all of them — sections must come after INDEX:END).
    ``delta`` is that shift; every reported line number already includes it,
    so the result is idempotent under a fresh check.
    """
    old_interior = end - begin - 1
    n_rows = 1 + len(sections)  # INDEX_BLOCK + one row per section
    new_interior = 1 + n_rows  # TSV header + rows
    delta = new_interior - old_interior

    rows: list[Row] = [Row("INDEX_BLOCK", begin + 1, begin + new_interior + 2)]
    for idx, (sid, start) in enumerate(sections):
        stop = sections[idx + 1][1] - 1 + delta if idx + 1 < len(sections) else total_lines + delta
        rows.append(Row(sid, start + delta, stop))
    return rows


def render(rows: list[Row]) -> list[str]:
    """Render rows as TSV lines (header first)."""
    out = [TSV_HEADER]
    out.extend(f"{r.id}\t{r.start_line}\t{r.end_line}" for r in rows)
    return out


def index_rows(text: str) -> list[Row]:
    """Parse ``text`` and return the TSV rows its index block must contain.

    Line numbers are 1-indexed and describe the file *after* a sync rewrite.

    Raises:
        FormatError: structural guard failure (see :func:`find_sections`).
    """
    normalized = _normalize_newlines(text)
    lines = normalized.splitlines()
    begin, end = find_index_block(lines)
    sections = find_sections(lines, end)
    return build_rows(sections, len(lines), begin, end)


def synced_text(text: str) -> str:
    """Return ``text`` with the index-block interior rewritten from the body.

    Output is always LF-terminated; a trailing newline is preserved iff the
    input had one. Idempotent.

    Raises:
        FormatError: structural guard failure.
    """
    normalized = _normalize_newlines(text)
    had_trailing_newline = normalized.endswith("\n")
    lines = normalized.splitlines()
    begin, end = find_index_block(lines)
    sections = find_sections(lines, end)
    rows = build_rows(sections, len(lines), begin, end)
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
