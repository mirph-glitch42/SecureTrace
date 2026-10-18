#!/usr/bin/env python3
"""Manage a LESSONS_LEARNED.md file: the authoritative, machine-readable record
of lessons learned while developing a system.

Vendored from the `learned-lesson-tracker` skill (copied 2026-10-18) so git
hooks and CI can run the record checks without access to the skill directory.
Keep in sync with the skill; do not fork silently.

File shape (see references/entry-anatomy.md for the full spec):

    # Lessons Learned
    <intro prose>

    <!-- LLT:INDEX:BEGIN -->
    id	title	category	severity	status	recorded	start_line	end_line
    LLT_INDEX_BLOCK	—	—	—	—	—	<begin>	<end>
    LLT-0001	<title>	<category>	<severity>	<status>	<YYYY-MM-DD>	<start>	<end>
    <!-- LLT:INDEX:END -->

    <!-- LLT:ENTRY:LLT-0001 -->
    ## LLT-0001 — <title>

    - **Recorded:** 2026-10-14
    - **Category:** debugging
    - **Severity:** high
    - **Status:** active
    - **Context:** <what situation produced the lesson>
    - **Pitfall:** <what goes wrong, what the trap is>
    - **Solution:** <the correct approach, what was actually done>
    - **Supersedes:** —
    - **Prevention:** <how to avoid it in the future, or —>
    - **References:** <files, links, issue numbers, or —>

Invariants enforced here (guards G4–G8 in references/guards.md):

  - exactly one index block (TSV) between LLT:INDEX:BEGIN/END markers, first
    in the file; every entry listed with its final line range;
  - one `<!-- LLT:ENTRY:LLT-NNNN -->` marker per lesson; marker id == heading
    id; ids match LLT-[0-9]{4}, are unique, and strictly increase in file
    order (append-only: new ids must be greater than the current max);
  - required fields per entry (Recorded, Category, Severity, Status,
    Context, Pitfall, Solution) with a fixed vocabulary; field values are
    single-line and contain no tabs;
  - supersession is bidirectional: a superseded entry is referenced by at
    least one Supersedes field, and every Supersedes reference points to an
    entry whose Status is `superseded`.

Exit codes (all subcommands):
  0 = ok
  1 = index is stale relative to the entries (fix with `sync`)
  2 = malformed file or rejected input (structure, fields, vocabulary, ids,
      supersession, or a refusal to overwrite)

Usage:
    python3 manage_lessons.py init <file> [--force]
    python3 manage_lessons.py add <file> --title T --context C --pitfall P
                                  --solution S [--id LLT-NNNN]
                                  [--category C] [--severity S]
                                  [--recorded YYYY-MM-DD]
                                  [--supersedes LLT-NNNN]
                                  [--prevention TEXT] [--references TEXT]
    python3 manage_lessons.py sync <file>
    python3 manage_lessons.py check <file>
    python3 manage_lessons.py next-id <file>
"""

from __future__ import annotations

import argparse
import contextlib
import datetime
import os
import re
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

PROG = "manage_lessons"

BEGIN_RE = re.compile(r"^<!--\s*LLT:INDEX:BEGIN\s*-->\s*$")
END_RE = re.compile(r"^<!--\s*LLT:INDEX:END\s*-->\s*$")
ENTRY_MARKER_RE = re.compile(r"^<!--\s*LLT:ENTRY:(?P<id>LLT-[0-9]{4})\s*-->\s*$")
HEADING_RE = re.compile(r"^##\s+(?P<id>LLT-[0-9]{4})\s+—\s+(?P<title>\S.*?)\s*$")
FIELD_RE = re.compile(r"^-\s+\*\*(?P<name>[A-Za-z]+):\*\*\s*(?P<value>.*?)\s*$")

ID_RE = re.compile(r"^LLT-[0-9]{4}$")
DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")

REQUIRED_FIELDS = ("Recorded", "Category", "Severity", "Status", "Context", "Pitfall", "Solution")
OPTIONAL_FIELDS = ("Supersedes", "Prevention", "References")
ALL_FIELDS = REQUIRED_FIELDS + OPTIONAL_FIELDS

CATEGORIES = (
    "debugging",
    "architecture",
    "testing",
    "performance",
    "security",
    "dependencies",
    "tooling",
    "environment",
    "process",
    "data",
    "other",
)
SEVERITIES = ("low", "medium", "high", "critical")
STATUSES = ("active", "superseded")

INDEX_HEADER = "id\ttitle\tcategory\tseverity\tstatus\trecorded\tstart_line\tend_line"

TEMPLATE_INTRO = """# Lessons Learned

Authoritative record of lessons learned during the development of this system:
the situation, the pitfall, and the correct solution for each lesson.
Managed by the `learned-lesson-tracker` skill — do not edit the index block or
the entry markers by hand; use `scripts/manage_lessons.py` (init / add / sync /
check / next-id). The index below is machine-readable (TSV between
`LLT:INDEX:BEGIN`/`LLT:INDEX:END` markers) and lists every entry with its
line range.
"""


class FileError(Exception):
    """Malformed file or unsafe operation (exit 2)."""


class StaleIndex(Exception):
    """Index out of sync with the entries (exit 1)."""


class InputError(Exception):
    """Rejected input for `add` (exit 2)."""


@dataclass
class Entry:
    id: str
    title: str
    fields: dict = field(default_factory=dict)
    start: int = 0  # 1-indexed marker line
    end: int = 0  # 1-indexed last line of the section (inclusive)


def err(msg: str) -> None:
    print(f"{PROG}: {msg}", file=sys.stderr)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise FileError(f"cannot read {path}: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise FileError(f"{path} is not UTF-8 text: {exc}") from exc


def atomic_write(path: Path, text: str) -> None:
    directory = os.path.dirname(os.path.abspath(str(path)))
    tmp: str | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=directory, delete=False) as fh:
            tmp = fh.name
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        if tmp is not None:
            with contextlib.suppress(OSError):
                os.unlink(tmp)
        raise


def find_index_block(lines: list) -> tuple:
    """Return (begin, end) 0-indexed line numbers of the index block, or (None, None)."""
    begin = end = None
    for i, line in enumerate(lines):
        if begin is None and BEGIN_RE.match(line):
            begin = i
        elif begin is not None and END_RE.match(line):
            end = i
            break
    return begin, end


def parse_entries(lines: list) -> tuple:
    """Return (entries in file order, structural errors)."""
    errors: list = []
    entries: list = []
    seen: set = set()
    for i, line in enumerate(lines):
        m = ENTRY_MARKER_RE.match(line)
        if not m:
            continue
        eid = m.group("id")
        if eid in seen:
            errors.append(f"duplicate entry marker {eid} (line {i + 1}); ids must be unique (G4)")
        seen.add(eid)
        j = i + 1
        while j < len(lines) and not ENTRY_MARKER_RE.match(lines[j]):
            j += 1
        heading = None
        for k in range(i + 1, j):
            hm = HEADING_RE.match(lines[k])
            if hm:
                heading = (k, hm.group("id"), hm.group("title"))
                break
        title = ""
        if heading is None:
            errors.append(
                f"entry {eid}: missing heading '## {eid} — <title>' in lines {i + 1}-{j} (G8)"
            )
        else:
            if heading[1] != eid:
                errors.append(
                    f"entry marker {eid} (line {i + 1}) disagrees with heading id "
                    f"{heading[1]} (line {heading[0] + 1}); marker and heading must match (G8)"
                )
            title = heading[2]
            if "\t" in title:
                errors.append(f"entry {eid}: title contains a tab character (G6)")
        fields: dict = {}
        for k in range(i + 1, j):
            fm = FIELD_RE.match(lines[k])
            if not fm:
                continue
            name = fm.group("name")
            if name not in ALL_FIELDS:
                errors.append(
                    f"entry {eid}: unknown field '{name}' (line {k + 1}); "
                    f"allowed: {', '.join(ALL_FIELDS)}"
                )
                continue
            if name in fields:
                errors.append(f"entry {eid}: duplicate field '{name}' (line {k + 1})")
                continue
            value = fm.group("value")
            if "\t" in value:
                errors.append(f"entry {eid}: field '{name}' contains a tab character (G6)")
            fields[name] = value
        for req in REQUIRED_FIELDS:
            if req not in fields:
                errors.append(f"entry {eid}: missing required field '{req}' (G6)")
            elif not fields[req]:
                errors.append(f"entry {eid}: required field '{req}' is empty (G6)")
        recorded = fields.get("Recorded")
        if recorded and not DATE_RE.match(recorded):
            errors.append(f"entry {eid}: Recorded '{recorded}' is not YYYY-MM-DD (G6)")
        category = fields.get("Category")
        if category is not None and category not in CATEGORIES:
            errors.append(
                f"entry {eid}: Category '{category}' not in vocabulary: "
                f"{', '.join(CATEGORIES)} (G6)"
            )
        severity = fields.get("Severity")
        if severity is not None and severity not in SEVERITIES:
            errors.append(
                f"entry {eid}: Severity '{severity}' not in vocabulary: "
                f"{', '.join(SEVERITIES)} (G6)"
            )
        status = fields.get("Status")
        if status is not None and status not in STATUSES:
            errors.append(
                f"entry {eid}: Status '{status}' not in vocabulary: {', '.join(STATUSES)} (G6)"
            )
        supersedes = fields.get("Supersedes")
        if supersedes is not None and supersedes != "—" and not ID_RE.match(supersedes):
            errors.append(
                f"entry {eid}: Supersedes '{supersedes}' must be an LLT-NNNN id or — (G7)"
            )
        for opt in ("Prevention", "References"):
            if opt in fields and not fields[opt]:
                errors.append(
                    f"entry {eid}: optional field '{opt}' is empty; write — when absent (G6)"
                )
        entries.append(Entry(id=eid, title=title, fields=fields, start=i + 1, end=j))
    return entries, errors


def check_consistency(entries: list) -> list:
    """Cross-entry invariants: supersession bidirectionality and id ordering."""
    errors: list = []
    by_id: dict = {}
    for e in entries:
        by_id.setdefault(e.id, e)
    for e in entries:
        sup = e.fields.get("Supersedes", "—")
        if sup == "—":
            continue
        if sup not in by_id:
            errors.append(f"entry {e.id}: Supersedes {sup}, which does not exist (G7)")
        elif by_id[sup].fields.get("Status") != "superseded":
            errors.append(
                f"entry {e.id}: Supersedes {sup}, but {sup} is not marked superseded (G7)"
            )
    for e in entries:
        if e.fields.get("Status") != "superseded":
            continue
        successor = [x for x in entries if x.id != e.id and x.fields.get("Supersedes") == e.id]
        if not successor:
            errors.append(
                f"entry {e.id} is superseded but no entry supersedes it; "
                f"add the replacement with --supersedes {e.id} (G7)"
            )
    nums = [int(e.id[4:]) for e in entries]
    for a, b in zip(nums, nums[1:], strict=False):
        if b <= a:
            errors.append(
                "entry ids must strictly increase in file order (append-only); "
                f"found {a} followed by {b} (G4)"
            )
            break
    return errors


def structural_errors(text: str) -> list:
    """All structural/semantic errors; raises FileError for broken skeleton."""
    lines = text.split("\n")
    begin, end = find_index_block(lines)
    if begin is None or end is None:
        raise FileError("missing <!-- LLT:INDEX:BEGIN --> / <!-- LLT:INDEX:END --> markers (G8)")
    if end <= begin + 1:
        raise FileError("index block is empty or malformed (G8)")
    for i, line in enumerate(lines):
        if ENTRY_MARKER_RE.match(line) and i < begin:
            raise FileError(
                f"entry marker at line {i + 1} appears before the index block; "
                f"the index must be first (G8)"
            )
    entries, errors = parse_entries(lines)
    errors.extend(check_consistency(entries))
    return errors


def expected_index_rows(text: str) -> list:
    """The exact index interior (header + rows) the current entries require.

    Line numbers describe the *final* file: if the stored block size differs
    from the required one, entry line numbers are shifted by the delta.
    """
    lines = text.split("\n")
    begin, end = find_index_block(lines)
    if begin is None or end is None:
        raise FileError("missing index block markers (G8)")
    entries, _ = parse_entries(lines)
    new_end = begin + 3 + len(entries)  # 0-indexed END line after rewrite
    delta = new_end - end
    rows = [
        "\t".join(["LLT_INDEX_BLOCK", "—", "—", "—", "—", "—", str(begin + 1), str(new_end + 1)])
    ]
    for e in entries:
        f = e.fields
        rows.append(
            "\t".join(
                [
                    e.id,
                    e.title if e.title else "—",
                    f.get("Category", "—") or "—",
                    f.get("Severity", "—") or "—",
                    f.get("Status", "—") or "—",
                    f.get("Recorded", "—") or "—",
                    str(e.start + delta),
                    str(e.end + delta),
                ]
            )
        )
    return [INDEX_HEADER] + rows


def index_is_fresh(text: str) -> bool:
    lines = text.split("\n")
    begin, end = find_index_block(lines)
    if begin is None or end is None:
        return False
    expected = expected_index_rows(text)
    return lines[begin + 1 : end] == expected


def regenerate(text: str) -> str:
    """Rewrite the index block interior from the entries; return the new text."""
    lines = text.split("\n")
    begin, end = find_index_block(lines)
    if begin is None or end is None:
        raise FileError("missing index block markers; cannot sync (G8)")
    rows = expected_index_rows(text)
    # lines[:begin + 1] keeps the BEGIN marker; lines[end:] keeps the END
    # marker (index `end`) and everything after it.
    new_lines = lines[: begin + 1] + rows + lines[end:]
    return "\n".join(new_lines)


def build_template() -> str:
    placeholder = "\t".join(["LLT_INDEX_BLOCK", "—", "—", "—", "—", "—", "?", "?"])
    text = (
        TEMPLATE_INTRO.rstrip("\n")
        + "\n\n"
        + "<!-- LLT:INDEX:BEGIN -->\n"
        + INDEX_HEADER
        + "\n"
        + placeholder
        + "\n"
        + "<!-- LLT:INDEX:END -->\n"
    )
    lines = text.split("\n")
    begin, end = find_index_block(lines)
    lines[begin + 1 : end] = expected_index_rows(text)
    return "\n".join(lines)


def render_entry(args, entry_id: str) -> str:
    values = {
        "Recorded": args.recorded,
        "Category": args.category,
        "Severity": args.severity,
        "Status": "active",
        "Context": args.context,
        "Pitfall": args.pitfall,
        "Solution": args.solution,
        "Supersedes": args.supersedes if args.supersedes else "—",
        "Prevention": args.prevention if args.prevention else "—",
        "References": args.references if args.references else "—",
    }
    lines = [
        f"<!-- LLT:ENTRY:{entry_id} -->",
        f"## {entry_id} — {args.title}",
        "",
    ]
    for name in ALL_FIELDS:
        lines.append(f"- **{name}:** {values[name]}")
    return "\n".join(lines)


def max_id(entries: list) -> int:
    return max((int(e.id[4:]) for e in entries), default=0)


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


def cmd_init(path: Path, force: bool) -> int:
    if not path.exists():
        atomic_write(path, build_template())
        print(f"init: created {path}")
        return 0
    text = read_text(path)
    begin, end = find_index_block(text.split("\n"))
    if begin is None:
        if not force:
            raise FileError(
                f"{path} exists but is not a LESSONS_LEARNED.md file; "
                f"refusing to overwrite. Re-run with --force to replace it."
            )
        atomic_write(path, build_template())
        print(f"init: replaced non-LLT file at {path} with template (--force)")
        return 0
    # An LLT file is never overwritten, even with --force: lessons are data.
    errors = structural_errors(text)
    if errors:
        for e in errors:
            err(e)
        return 2
    entries, _ = parse_entries(text.split("\n"))
    n = len(entries)
    print(f"init: {path} already initialized ({n} lesson{'s' if n != 1 else ''}); nothing to do")
    return 0


def validate_add_args(args) -> None:
    for name in ("title", "context", "pitfall", "solution"):
        value = getattr(args, name)
        if not value or not value.strip():
            raise InputError(f"--{name} is required and must be non-empty (G6)")
        if "\t" in value or "\n" in value:
            raise InputError(f"--{name} must be a single line without tabs (G6)")
    if args.category not in CATEGORIES:
        raise InputError(
            f"--category '{args.category}' not in vocabulary: {', '.join(CATEGORIES)} (G6)"
        )
    if args.severity not in SEVERITIES:
        raise InputError(
            f"--severity '{args.severity}' not in vocabulary: {', '.join(SEVERITIES)} (G6)"
        )
    if args.recorded and not DATE_RE.match(args.recorded):
        raise InputError(f"--recorded '{args.recorded}' is not YYYY-MM-DD (G6)")
    for name in ("prevention", "references"):
        value = getattr(args, name)
        if value and ("\t" in value or "\n" in value):
            raise InputError(f"--{name} must be a single line without tabs (G6)")


def cmd_add(args) -> int:
    path = Path(args.file)
    if not path.exists():
        raise FileError(f"{path} does not exist; run `init` first")
    text = read_text(path)
    errors = structural_errors(text)
    if errors:
        for e in errors:
            err(e)
        return 2
    lines = text.split("\n")
    entries, _ = parse_entries(lines)

    args.recorded = args.recorded or datetime.date.today().isoformat()
    validate_add_args(args)

    if args.supersedes:
        if not ID_RE.match(args.supersedes):
            raise InputError(f"--supersedes '{args.supersedes}' must be an LLT-NNNN id (G7)")
        target = next((e for e in entries if e.id == args.supersedes), None)
        if target is None:
            raise InputError(f"--supersedes {args.supersedes}: no such entry (G7)")
        if target.fields.get("Status") != "active":
            raise InputError(
                f"--supersedes {args.supersedes}: that entry is not active; "
                f"supersede the newest replacement instead (G7)"
            )
        for i in range(target.start - 1, target.end):
            if lines[i].startswith("- **Status:**"):
                lines[i] = "- **Status:** superseded"
                break
        text = "\n".join(lines)

    if args.id:
        if not ID_RE.match(args.id):
            raise InputError(f"--id '{args.id}' must match LLT-[0-9]{{4}} (G4)")
        if any(e.id == args.id for e in entries):
            raise InputError(f"--id {args.id} already exists; ids are never reused (G4)")
        if int(args.id[4:]) <= max_id(entries):
            raise InputError(
                f"--id {args.id} must be greater than the current maximum "
                f"LLT-{max_id(entries):04d}; entries are appended in id order (G4)"
            )
        entry_id = args.id
    else:
        entry_id = f"LLT-{max_id(entries) + 1:04d}"

    new_text = text.rstrip("\n") + "\n\n" + render_entry(args, entry_id) + "\n"
    new_text = regenerate(new_text)
    fresh_errors = structural_errors(new_text)
    if fresh_errors:
        for e in fresh_errors:
            err(e)
        raise FileError("internal error: generated file is invalid; file not written")
    if not index_is_fresh(new_text):
        raise FileError("internal error: index not fresh after add; file not written")
    atomic_write(path, new_text)
    print(f"add: recorded {entry_id} — {args.title}")
    print(f"add: index updated ({path})")
    return 0


def cmd_sync(path: Path) -> int:
    if not path.exists():
        raise FileError(f"{path} does not exist; run `init` first")
    text = read_text(path)
    errors = structural_errors(text)
    if errors:
        for e in errors:
            err(e)
        return 2
    new_text = regenerate(text)
    if new_text == text:
        print(f"sync: index already current ({path})")
        return 0
    atomic_write(path, new_text)
    print(f"sync: index regenerated ({path})")
    return 0


def cmd_check(path: Path) -> int:
    if not path.exists():
        raise FileError(f"{path} does not exist; run `init` first")
    text = read_text(path)
    errors = structural_errors(text)
    if errors:
        for e in errors:
            err(e)
        return 2
    if not index_is_fresh(text):
        raise StaleIndex(f"{path}: index is stale; run `sync` to regenerate")
    n = len(parse_entries(text.split("\n"))[0])
    print(f"check: {path} is valid ({n} lesson{'s' if n != 1 else ''} recorded)")
    return 0


def cmd_next_id(path: Path) -> int:
    if not path.exists():
        raise FileError(f"{path} does not exist; run `init` first")
    text = read_text(path)
    errors = structural_errors(text)
    if errors:
        for e in errors:
            err(e)
        return 2
    entries, _ = parse_entries(text.split("\n"))
    print(f"LLT-{max_id(entries) + 1:04d}")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog=PROG,
        description="Manage a machine-readable LESSONS_LEARNED.md lessons record.",
        epilog="Exit codes: 0 = ok, 1 = stale index, 2 = malformed file or rejected input.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("init", help="create a new LESSONS_LEARNED.md")
    sp.add_argument("file")
    sp.add_argument(
        "--force", action="store_true", help="replace an existing non-LLT file with the template"
    )
    sp.set_defaults(func=lambda a: cmd_init(Path(a.file), a.force))

    sp = sub.add_parser("add", help="record a new lesson and update the index")
    sp.add_argument("file")
    sp.add_argument("--title", required=True)
    sp.add_argument("--context", required=True)
    sp.add_argument("--pitfall", required=True)
    sp.add_argument("--solution", required=True)
    sp.add_argument(
        "--id", default=None, help="explicit LLT-NNNN id (must be unused and greater than the max)"
    )
    sp.add_argument("--category", default="other", help="one of: " + ", ".join(CATEGORIES))
    sp.add_argument("--severity", default="medium", help="one of: " + ", ".join(SEVERITIES))
    sp.add_argument("--recorded", default=None, help="YYYY-MM-DD (default: today)")
    sp.add_argument(
        "--supersedes",
        default=None,
        help="LLT-NNNN of the lesson this one replaces (flips its status)",
    )
    sp.add_argument("--prevention", default=None)
    sp.add_argument("--references", default=None)
    sp.set_defaults(func=lambda a: cmd_add(a))

    sp = sub.add_parser("sync", help="regenerate the index block from the entries")
    sp.add_argument("file")
    sp.set_defaults(func=lambda a: cmd_sync(Path(a.file)))

    sp = sub.add_parser("check", help="validate structure, fields, and index freshness")
    sp.add_argument("file")
    sp.set_defaults(func=lambda a: cmd_check(Path(a.file)))

    sp = sub.add_parser("next-id", help="print the next LLT-NNNN id")
    sp.add_argument("file")
    sp.set_defaults(func=lambda a: cmd_next_id(Path(a.file)))

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except FileError as exc:
        err(str(exc))
        return 2
    except InputError as exc:
        err(str(exc))
        return 2
    except StaleIndex as exc:
        err(str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
