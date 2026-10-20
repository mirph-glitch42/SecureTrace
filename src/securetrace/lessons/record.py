"""Pure core of the LESSONS_LEARNED.md record (append-only entry log).

Works on plain text only (no file I/O, no printing): malformed records raise
:class:`securetrace.errors.FormatError`, rejected ``add`` input raises
:class:`securetrace.errors.InvalidInput`. File I/O, user-facing messages,
and exit codes live in :mod:`securetrace.cli`.

Faithful port of the pinned ``scripts/manage_lessons.py``
(spec: ``algorithms/lessons-record.md``), including the verified quirks:

- **DEV(3):** ``Recorded`` is format-only (``YYYY-MM-DD`` shape) — a
  non-existent date such as ``2026-99-99`` is accepted;
- **DEV(4):** index freshness covers the six indexed fields plus line
  ranges, so a same-line body edit is **not** stale while an indexed-field
  change **is** stale;
- **DEV(7):** the final entry's reported ``end_line`` overshoots by one
  (the ``text.split("\\n")`` trailing element) while interior entries are
  span-inclusive.

File shape: one index block (TSV between ``LLT:INDEX:BEGIN``/``END``
markers, first in the file) followed by one
``<!-- LLT:ENTRY:LLT-NNNN -->`` section per lesson, each with a matching
``## LLT-NNNN — <title>`` heading and a fixed set of ``- **Field:** value``
lines (guards G4–G8).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from securetrace.errors import FormatError, InvalidInput

__all__ = [
    "ALL_FIELDS",
    "CATEGORIES",
    "Entry",
    "INDEX_HEADER",
    "NewLesson",
    "AddResult",
    "OPTIONAL_FIELDS",
    "REQUIRED_FIELDS",
    "SEVERITIES",
    "STATUSES",
    "add_lesson",
    "build_template",
    "check_consistency",
    "expected_index_rows",
    "find_index_block",
    "index_is_fresh",
    "max_id",
    "next_id",
    "parse_entries",
    "regenerate",
    "render_entry",
    "structural_errors",
]

BEGIN_RE = re.compile(r"^<!--\s*LLT:INDEX:BEGIN\s*-->\s*$")
END_RE = re.compile(r"^<!--\s*LLT:INDEX:END\s*-->\s*$")
ENTRY_MARKER_RE = re.compile(r"^<!--\s*LLT:ENTRY:(?P<id>LLT-(?a:\d){4})\s*-->\s*$")
HEADING_RE = re.compile(r"^##\s+(?P<id>LLT-(?a:\d){4})\s+—\s+(?P<title>\S+(?:\s+\S+)*)\s*$")
FIELD_RE = re.compile(r"^-\s+\*\*(?P<name>[A-Za-z]+):\*\*\s*(?P<value>\S*(?:\s+\S+)*)\s*$")

ID_RE = re.compile(r"^LLT-(?a:\d){4}$")
DATE_RE = re.compile(r"^(?a:\d){4}-(?a:\d){2}-(?a:\d){2}$")

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


@dataclass
class Entry:
    """One parsed lesson entry (1-indexed line span)."""

    id: str
    title: str
    fields: dict[str, str] = field(default_factory=dict)
    start: int = 0  # 1-indexed marker line
    end: int = 0  # 1-indexed last line of the section (inclusive)


@dataclass
class NewLesson:
    """Typed input for :func:`add_lesson` (the ``add`` command's arguments).

    Defaults mirror the pinned argparse defaults: category ``other``,
    severity ``medium``, everything else ``None`` (``Recorded`` defaults to
    the caller-supplied ``today`` at add time).
    """

    title: str
    context: str
    pitfall: str
    solution: str
    id: str | None = None
    category: str = "other"
    severity: str = "medium"
    recorded: str | None = None
    supersedes: str | None = None
    prevention: str | None = None
    references: str | None = None


@dataclass(frozen=True)
class AddResult:
    """The rewritten record text plus the id assigned to the new entry."""

    new_text: str
    entry_id: str


def find_index_block(lines: list[str]) -> tuple[int | None, int | None]:
    """Return (begin, end) 0-indexed line numbers of the first index block, or (None, None)."""
    begin = end = None
    for i, line in enumerate(lines):
        if begin is None and BEGIN_RE.match(line):
            begin = i
        elif begin is not None and END_RE.match(line):
            end = i
            break
    return begin, end


def _find_heading(lines: list[str], i: int, j: int) -> tuple[int, str, str] | None:
    """First ``## LLT-NNNN — <title>`` heading inside the entry span, if any."""
    for k in range(i + 1, j):
        hm = HEADING_RE.match(lines[k])
        if hm:
            return k, hm.group("id"), hm.group("title")
    return None


def _check_heading(errors: list[str], eid: str, i: int, j: int, lines: list[str]) -> str:
    """Validate the entry heading; return its title ('' when the heading is missing)."""
    heading = _find_heading(lines, i, j)
    if heading is None:
        errors.append(
            f"entry {eid}: missing heading '## {eid} — <title>' in lines {i + 1}-{j} (G8)"
        )
        return ""
    title = heading[2]
    if heading[1] != eid:
        errors.append(
            f"entry marker {eid} (line {i + 1}) disagrees with heading id "
            f"{heading[1]} (line {heading[0] + 1}); marker and heading must match (G8)"
        )
    if "\t" in title:
        errors.append(f"entry {eid}: title contains a tab character (G6)")
    return title


def _parse_fields(errors: list[str], eid: str, lines: list[str], i: int, j: int) -> dict[str, str]:
    """Collect the entry's field lines into a dict, recording field-level errors."""
    fields: dict[str, str] = {}
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
    return fields


def _check_required_fields(errors: list[str], eid: str, fields: dict[str, str]) -> None:
    """Required fields present and non-empty, in pinned order (G6)."""
    for req in REQUIRED_FIELDS:
        if req not in fields:
            errors.append(f"entry {eid}: missing required field '{req}' (G6)")
        elif not fields[req]:
            errors.append(f"entry {eid}: required field '{req}' is empty (G6)")


def _check_field_vocabularies(errors: list[str], eid: str, fields: dict[str, str]) -> None:
    """Date shape (format-only, DEV(3)) and vocabulary guards for present fields (G6/G7)."""
    recorded = fields.get("Recorded")
    if recorded and not DATE_RE.match(recorded):
        errors.append(f"entry {eid}: Recorded '{recorded}' is not YYYY-MM-DD (G6)")
    category = fields.get("Category")
    if category is not None and category not in CATEGORIES:
        errors.append(
            f"entry {eid}: Category '{category}' not in vocabulary: {', '.join(CATEGORIES)} (G6)"
        )
    severity = fields.get("Severity")
    if severity is not None and severity not in SEVERITIES:
        errors.append(
            f"entry {eid}: Severity '{severity}' not in vocabulary: {', '.join(SEVERITIES)} (G6)"
        )
    status = fields.get("Status")
    if status is not None and status not in STATUSES:
        errors.append(
            f"entry {eid}: Status '{status}' not in vocabulary: {', '.join(STATUSES)} (G6)"
        )
    supersedes = fields.get("Supersedes")
    if supersedes is not None and supersedes != "—" and not ID_RE.match(supersedes):
        errors.append(f"entry {eid}: Supersedes '{supersedes}' must be an LLT-NNNN id or — (G7)")


def _check_optional_fields(errors: list[str], eid: str, fields: dict[str, str]) -> None:
    """Optional fields, when present, must be non-empty (write — when absent)."""
    for opt in ("Prevention", "References"):
        if opt in fields and not fields[opt]:
            errors.append(f"entry {eid}: optional field '{opt}' is empty; write — when absent (G6)")


def parse_entries(lines: list[str]) -> tuple[list[Entry], list[str]]:
    """Parse every entry section; return (entries in file order, structural errors).

    Per-entry checks (pinned order, collected not fail-fast): duplicate marker
    (G4), heading presence/agreement (G8), tab-free title (G6), known and
    unique field names, tab-free values, required fields present and
    non-empty (G6), ``Recorded`` date shape (format-only, DEV(3)),
    category/severity/status vocabularies (G6), ``Supersedes`` id shape
    (G7), and non-empty optional fields (G6).
    """
    errors: list[str] = []
    entries: list[Entry] = []
    seen: set[str] = set()
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
        title = _check_heading(errors, eid, i, j, lines)
        fields = _parse_fields(errors, eid, lines, i, j)
        _check_required_fields(errors, eid, fields)
        _check_field_vocabularies(errors, eid, fields)
        _check_optional_fields(errors, eid, fields)
        entries.append(Entry(id=eid, title=title, fields=fields, start=i + 1, end=j))
    return entries, errors


def _check_supersession(entries: list[Entry]) -> list[str]:
    """Every ``Supersedes`` target must exist and be marked superseded (G7)."""
    errors: list[str] = []
    by_id: dict[str, Entry] = {}
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
    return errors


def _check_superseded_have_successor(entries: list[Entry]) -> list[str]:
    """A superseded entry must be superseded by some entry (G7)."""
    errors: list[str] = []
    for e in entries:
        if e.fields.get("Status") != "superseded":
            continue
        successor = [x for x in entries if x.id != e.id and x.fields.get("Supersedes") == e.id]
        if not successor:
            errors.append(
                f"entry {e.id} is superseded but no entry supersedes it; "
                f"add the replacement with --supersedes {e.id} (G7)"
            )
    return errors


def _check_id_order(entries: list[Entry]) -> list[str]:
    """Ids must strictly increase in file order (G4); report the first violation."""
    nums = [int(e.id[4:]) for e in entries]
    for a, b in zip(nums, nums[1:], strict=False):
        if b <= a:
            return [
                "entry ids must strictly increase in file order (append-only); "
                f"found {a} followed by {b} (G4)"
            ]
    return []


def check_consistency(entries: list[Entry]) -> list[str]:
    """Cross-entry invariants: supersession bidirectionality and id ordering."""
    return (
        _check_supersession(entries)
        + _check_superseded_have_successor(entries)
        + _check_id_order(entries)
    )


def structural_errors(text: str) -> list[str]:
    """Return all structural/semantic errors in ``text``.

    Raises:
        FormatError: the record skeleton itself is broken (missing/empty
            index block, or an entry marker before the index block) — these
            cannot be listed as findings.
    """
    lines = text.split("\n")
    begin, end = find_index_block(lines)
    if begin is None or end is None:
        raise FormatError("missing <!-- LLT:INDEX:BEGIN --> / <!-- LLT:INDEX:END --> markers (G8)")
    if end <= begin + 1:
        raise FormatError("index block is empty or malformed (G8)")
    for i, line in enumerate(lines):
        if ENTRY_MARKER_RE.match(line) and i < begin:
            raise FormatError(
                f"entry marker at line {i + 1} appears before the index block; "
                f"the index must be first (G8)"
            )
    entries, errors = parse_entries(lines)
    errors.extend(check_consistency(entries))
    return errors


def expected_index_rows(text: str) -> list[str]:
    """The exact index interior (header + rows) the current entries require.

    Line numbers describe the *final* file: if the stored block size differs
    from the required one, entry line numbers are shifted by the delta.

    Raises:
        FormatError: no index block markers.
    """
    lines = text.split("\n")
    begin, end = find_index_block(lines)
    if begin is None or end is None:
        raise FormatError("missing index block markers (G8)")
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
    """True iff the stored index interior is exactly what the entries require."""
    lines = text.split("\n")
    begin, end = find_index_block(lines)
    if begin is None or end is None:
        return False
    expected = expected_index_rows(text)
    return lines[begin + 1 : end] == expected


def regenerate(text: str) -> str:
    """Rewrite the index block interior from the entries; return the new text.

    Raises:
        FormatError: no index block markers.
    """
    lines = text.split("\n")
    begin, end = find_index_block(lines)
    if begin is None or end is None:
        raise FormatError("missing index block markers; cannot sync (G8)")
    rows = expected_index_rows(text)
    # lines[:begin + 1] keeps the BEGIN marker; lines[end:] keeps the END
    # marker (index `end`) and everything after it.
    new_lines = lines[: begin + 1] + rows + lines[end:]
    return "\n".join(new_lines)


def build_template() -> str:
    """Return the empty record: intro, a fresh (zero-entry) index block."""
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
    assert begin is not None and end is not None  # template always has the block
    lines[begin + 1 : end] = expected_index_rows(text)
    return "\n".join(lines)


def render_entry(lesson: NewLesson, entry_id: str) -> str:
    """Render one entry section (marker, heading, blank line, all fields)."""
    values = {
        "Recorded": lesson.recorded,
        "Category": lesson.category,
        "Severity": lesson.severity,
        "Status": "active",
        "Context": lesson.context,
        "Pitfall": lesson.pitfall,
        "Solution": lesson.solution,
        "Supersedes": lesson.supersedes if lesson.supersedes else "—",
        "Prevention": lesson.prevention if lesson.prevention else "—",
        "References": lesson.references if lesson.references else "—",
    }
    lines = [
        f"<!-- LLT:ENTRY:{entry_id} -->",
        f"## {entry_id} — {lesson.title}",
        "",
    ]
    for name in ALL_FIELDS:
        lines.append(f"- **{name}:** {values[name]}")
    return "\n".join(lines)


def max_id(entries: list[Entry]) -> int:
    """Numeric part of the largest entry id (0 for an empty record)."""
    return max((int(e.id[4:]) for e in entries), default=0)


def next_id(entries: list[Entry]) -> str:
    """The id the next appended entry must have (max + 1, zero-padded to 4)."""
    return f"LLT-{max_id(entries) + 1:04d}"


def _validate_required(lesson: NewLesson) -> None:
    """Required ``--title/--context/--pitfall/--solution``: non-empty, single line (G6)."""
    for name in ("title", "context", "pitfall", "solution"):
        value = getattr(lesson, name)
        if not value or not value.strip():
            raise InvalidInput(f"--{name} is required and must be non-empty (G6)")
        if "\t" in value or "\n" in value:
            raise InvalidInput(f"--{name} must be a single line without tabs (G6)")


def _validate_vocabularies(lesson: NewLesson) -> None:
    """Category/severity vocabulary and ``recorded`` date shape (G6)."""
    if lesson.category not in CATEGORIES:
        raise InvalidInput(
            f"--category '{lesson.category}' not in vocabulary: {', '.join(CATEGORIES)} (G6)"
        )
    if lesson.severity not in SEVERITIES:
        raise InvalidInput(
            f"--severity '{lesson.severity}' not in vocabulary: low, medium, high, critical (G6)"
        )
    if lesson.recorded and not DATE_RE.match(lesson.recorded):
        raise InvalidInput(f"--recorded '{lesson.recorded}' is not YYYY-MM-DD (G6)")


def _validate_optional_single_line(lesson: NewLesson) -> None:
    """Optional ``--prevention/--references``, when given, single line without tabs (G6)."""
    for name in ("prevention", "references"):
        value = getattr(lesson, name)
        if value and ("\t" in value or "\n" in value):
            raise InvalidInput(f"--{name} must be a single line without tabs (G6)")


def _validate_new_lesson(lesson: NewLesson) -> None:
    """Guard the ``add`` inputs (G6 vocabulary/shape guards).

    Order is pinned: required fields (title, context, pitfall, solution),
    then category, severity, recorded date shape, then the optional
    prevention/references single-line checks.

    Raises:
        InvalidInput: the first violated guard, with its pinned message.
    """
    _validate_required(lesson)
    _validate_vocabularies(lesson)
    _validate_optional_single_line(lesson)


def _supersede_target(text: str, entries: list[Entry], lesson: NewLesson) -> str:
    """Flip the ``Supersedes`` target's ``Status`` to superseded (G7).

    Raises:
        InvalidInput: the pinned supersession guards, in order (id shape,
            target existence, target active).
    """
    lines = text.split("\n")
    if not ID_RE.match(lesson.supersedes):
        raise InvalidInput(f"--supersedes '{lesson.supersedes}' must be an LLT-NNNN id (G7)")
    target = next((e for e in entries if e.id == lesson.supersedes), None)
    if target is None:
        raise InvalidInput(f"--supersedes {lesson.supersedes}: no such entry (G7)")
    if target.fields.get("Status") != "active":
        raise InvalidInput(
            f"--supersedes {lesson.supersedes}: that entry is not active; "
            "supersede the newest replacement instead (G7)"
        )
    for i in range(target.start - 1, target.end):
        if lines[i].startswith("- **Status:**"):
            lines[i] = "- **Status:** superseded"
            break
    return "\n".join(lines)


def _assign_entry_id(entries: list[Entry], lesson: NewLesson) -> str:
    """The new entry's id: a validated explicit ``--id`` or max+1 (G4).

    Raises:
        InvalidInput: the pinned id guards, in order (shape, not reused,
            above the current maximum).
    """
    if lesson.id:
        if not ID_RE.match(lesson.id):
            raise InvalidInput(f"--id '{lesson.id}' must match LLT-[0-9]{{4}} (G4)")
        if any(e.id == lesson.id for e in entries):
            raise InvalidInput(f"--id {lesson.id} already exists; ids are never reused (G4)")
        if int(lesson.id[4:]) <= max_id(entries):
            raise InvalidInput(
                f"--id {lesson.id} must be greater than the current maximum "
                f"LLT-{max_id(entries):04d}; entries are appended in id order (G4)"
            )
        return lesson.id
    return f"LLT-{max_id(entries) + 1:04d}"


def add_lesson(text: str, lesson: NewLesson, today: str) -> AddResult:
    """Append a lesson to ``text`` and return the rewritten record.

    ``today`` is the ISO date used when ``lesson.recorded`` is unset (the
    command layer supplies ``datetime.date.today().isoformat()``). The
    record is assumed structurally valid — the command layer runs
    :func:`structural_errors` first; this function re-validates the
    *generated* text as an internal invariant.

    Steps (pinned order): default ``recorded`` → validate inputs →
    supersede the target entry (flip its Status) → assign the id → append
    the entry and regenerate the index → re-validate.

    Raises:
        InvalidInput: rejected input (see :func:`_validate_new_lesson`,
            supersession guards G7, id guards G4).
        FormatError: internal invariant failure (the generated text is
            invalid or its index is not fresh) — nothing is returned.
    """
    lines = text.split("\n")
    entries, _ = parse_entries(lines)

    recorded = lesson.recorded if lesson.recorded else today
    _validate_new_lesson(lesson)

    if lesson.supersedes:
        text = _supersede_target(text, entries, lesson)

    entry_id = _assign_entry_id(entries, lesson)

    rendered = render_entry(
        NewLesson(
            title=lesson.title,
            context=lesson.context,
            pitfall=lesson.pitfall,
            solution=lesson.solution,
            category=lesson.category,
            severity=lesson.severity,
            recorded=recorded,
            supersedes=lesson.supersedes,
            prevention=lesson.prevention,
            references=lesson.references,
        ),
        entry_id,
    )
    new_text = text.rstrip("\n") + "\n\n" + rendered + "\n"
    new_text = regenerate(new_text)

    fresh_errors = structural_errors(new_text)
    if fresh_errors:
        raise FormatError("internal error: generated file is invalid; file not written")
    if not index_is_fresh(new_text):
        raise FormatError("internal error: index not fresh after add; file not written")

    return AddResult(new_text=new_text, entry_id=entry_id)
