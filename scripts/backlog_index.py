#!/usr/bin/env python3
"""Regenerate the machine-parsable line index of a BACKLOG.md file.

Vendored from the `backlog-manager` skill (copied 2026-10-18) so git hooks
and CI can run the index checks without access to the skill directory.
Keep in sync with the skill; do not fork silently.

A backlog file contains:
  - a block delimited by `<!-- INDEX:BEGIN ... -->` and `<!-- INDEX:END -->`
  - sections, each starting with a marker line:
      <!-- BACKLOG:HEADER -->
      <!-- BACKLOG:QUEUE -->
      <!-- BACKLOG:ITEM:B1 -->        (item ID matches [A-Z][A-Z0-9_]*)
      <!-- BACKLOG:CONSTRAINTS -->

A section spans from its marker line to the line before the next section's
marker, or to the last line of the file for the final section.

This script rewrites the interior of the index block as a TSV table:

    id	title	status	priority	start_line	end_line
    INDEX_BLOCK	-	-	-	3	9
    HEADER	-	-	-	11	15
    QUEUE	-	-	-	17	22
    B1	Add export	OPEN	Low	24	40
    CONSTRAINTS	-	-	-	42	46

- Line numbers are 1-indexed and count every physical line of the file.
- The first row always describes the index block itself, so the index is
  inclusive of itself.
- For item rows, `title` and `status` are parsed from the section's first
  `## <ID>. <title> — **STATUS**` heading (`-` when absent), and `priority`
  from the first `**Priority:**` line in the body: one of `High`, `Medium`,
  `Low` (case-insensitive; default `Low` when the line is absent, per G9).
  Any other value is a malformed file (exit 2).

Exit codes: 0 = ok (or index written), 1 = index stale (--check),
2 = malformed file (missing/duplicate markers, reserved ids, no items).

Usage:
    python3 build_backlog_index.py <backlog.md>          # rewrite the index in place
    python3 build_backlog_index.py <backlog.md> --check  # verify only; exit 1 if stale
"""

from __future__ import annotations

import argparse
import re
import sys

BEGIN_RE = re.compile(r"^<!--\s*INDEX:BEGIN\b.*?-->\s*$")
END_RE = re.compile(r"^<!--\s*INDEX:END\s*-->\s*$")
MARKER_RE = re.compile(
    r"^<!--\s*BACKLOG:(?P<kind>HEADER|QUEUE|CONSTRAINTS|ITEM:(?P<item>[A-Z][A-Z0-9_]*))\s*-->\s*$"
)
TSV_HEADER = "id\ttitle\tstatus\tpriority\tstart_line\tend_line"
RESERVED = ("HEADER", "QUEUE", "CONSTRAINTS")
PRIORITY_RE = re.compile(r"^\s*\*\*Priority:\*\*\s*(?P<val>.+?)\s*$", re.IGNORECASE)
PRIORITY_MAP = {"HIGH": "High", "MEDIUM": "Medium", "LOW": "Low"}
DEFAULT_PRIORITY = "Low"


def fail(msg: str) -> None:
    print(f"build_backlog_index: {msg}", file=sys.stderr)
    sys.exit(2)


def find_index_block(lines: list[str]) -> tuple[int, int]:
    begin = end = None
    for i, line in enumerate(lines):
        if begin is None and BEGIN_RE.match(line):
            begin = i
        elif begin is not None and END_RE.match(line):
            end = i
            break
    if begin is None or end is None:
        fail("missing <!-- INDEX:BEGIN --> / <!-- INDEX:END --> markers")
    if end <= begin + 1:
        fail("index block is empty or malformed (needs interior lines between BEGIN and END)")
    return begin, end


def find_sections(lines: list[str], index_end: int) -> list[tuple[str, int, bool]]:
    """Return (row_id, start_line_1indexed, is_item) pairs in file order.

    `row_id` is the section name for HEADER/QUEUE/CONSTRAINTS and the item
    id for item markers. A marker used twice fails the file (G3/G5).
    """
    sections: list[tuple[str, int, bool]] = []
    seen: set[str] = set()
    for i, line in enumerate(lines):
        m = MARKER_RE.match(line)
        if not m:
            continue
        if i <= index_end:
            fail(
                f"marker at line {i + 1} is at or inside the index block; "
                "markers must come after INDEX:END"
            )
        kind = m.group("kind")
        is_item = kind.startswith("ITEM:")
        row_id = m.group("item") if is_item else kind
        if is_item and row_id in RESERVED:
            fail(
                f"item id {row_id} is reserved for a section name; "
                f"item ids must not be {', '.join(RESERVED)}"
            )
        if kind in seen:
            fail(f"duplicate section marker: {kind}")
        seen.add(kind)
        sections.append((row_id, i + 1, is_item))
    if not any(is_item for _, _, is_item in sections):
        fail("no <!-- BACKLOG:ITEM:<ID> --> markers found")
    return sections


def parse_item_heading(item_id: str, lines: list[str], start: int, stop: int) -> tuple[str, str]:
    """Return (title, status) from the first `## <ID>. ...` heading in
    lines[start:stop] (0-indexed, stop exclusive). Both '' when the heading
    is missing or carries no status. status is normalized:
    "IN PROGRESS" -> "IN_PROGRESS"."""
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
    """Return the item's effective priority from the first `**Priority:**`
    line in lines[start:stop] (0-indexed, stop exclusive). One of
    `High`, `Medium`, `Low` (case-insensitive input, normalized output).
    Absent -> DEFAULT_PRIORITY (G9: items default to Low).
    Present but out of vocabulary -> malformed file (exit 2)."""
    for line in lines[start:stop]:
        m = PRIORITY_RE.match(line)
        if m:
            val = PRIORITY_MAP.get(m.group("val").strip().upper())
            if val is None:
                fail(
                    f"item {item_id}: priority '{m.group('val').strip()}' "
                    f"is not one of High, Medium, Low (G9)"
                )
            return val
    return DEFAULT_PRIORITY


def build_rows(
    sections: list[tuple[str, int, bool]],
    lines: list[str],
    total_lines: int,
    begin: int,
    end: int,
) -> list[tuple[str, str, str, str, int, int]]:
    """Rows are expressed in the line numbers of the FILE AFTER REWRITE.

    Rewriting the index interior changes its length, which shifts every
    section that follows (all of them — markers must come after INDEX:END).
    `delta` is that shift; every reported line number already includes it,
    so the result is idempotent under --check.
    """
    old_interior = end - begin - 1
    n_rows = 1 + len(sections)  # INDEX_BLOCK + one row per section
    new_interior = 1 + n_rows  # TSV header + rows
    delta = new_interior - old_interior

    rows = [("INDEX_BLOCK", "-", "-", "-", begin + 1, begin + new_interior + 2)]
    for idx, (sid, start, is_item) in enumerate(sections):
        stop = sections[idx + 1][1] - 1 if idx + 1 < len(sections) else total_lines
        title, status, priority = "-", "-", "-"
        if is_item:
            t, s = parse_item_heading(sid, lines, start - 1, stop - 1)
            title, status = t or "-", s or "-"
            priority = parse_priority(sid, lines, start - 1, stop - 1)
        rows.append((sid, title, status, priority, start + delta, stop + delta))
    return rows


def _cell(s: str) -> str:
    return s.replace("\t", " ").strip() or "-"


def render(rows: list[tuple[str, str, str, str, int, int]]) -> list[str]:
    out = [TSV_HEADER]
    out.extend(
        f"{_cell(sid)}\t{_cell(title)}\t{_cell(status)}\t{_cell(priority)}\t{a}\t{b}"
        for sid, title, status, priority, a, b in rows
    )
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Regenerate the line index of a BACKLOG.md.")
    ap.add_argument("backlog", help="path to BACKLOG.md")
    ap.add_argument(
        "--check", action="store_true", help="verify the index is current; exit 1 if stale"
    )
    args = ap.parse_args()

    with open(args.backlog, encoding="utf-8") as fh:
        raw = fh.read()
    had_trailing_newline = raw.endswith("\n")
    lines = raw.splitlines()
    total = len(lines)

    begin, end = find_index_block(lines)
    sections = find_sections(lines, end)
    rows = build_rows(sections, lines, total, begin, end)
    block = render(rows)

    if args.check:
        if lines[begin + 1 : end] == block:
            print(f"{args.backlog}: index OK ({len(rows)} entries)")
            return
        print(f"{args.backlog}: index STALE -- rerun without --check", file=sys.stderr)
        sys.exit(1)

    new_lines = lines[: begin + 1] + block + lines[end:]
    out = "\n".join(new_lines)
    if had_trailing_newline:
        out += "\n"
    with open(args.backlog, "w", encoding="utf-8") as fh:
        fh.write(out)
    print(f"{args.backlog}: index updated ({len(rows)} entries)")


if __name__ == "__main__":
    main()
