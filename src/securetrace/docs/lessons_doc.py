"""Lessons document parser/renderer (B10 WI 5).

``LESSONS_LEARNED.md`` is a pure render of the ``lessons`` store (spec:
``algorithms/deterministic-doc-pipeline.md``, contracts C1–C4):

- :func:`render_lessons` — store → doc text. Constants (title line, the
  generated no-hand-edit header, the index block markers) come from code;
  the data (intro prose lines, lessons, field values) come from the store.
  The index block is computed by the legacy :mod:`securetrace.lessons.record`
  core (``regenerate``), preserving the pinned DEV(7) final-entry quirk.
- :func:`parse_lessons` — doc text → store. Accepts exactly the grammar
  :func:`render_lessons` emits, plus the grandfathered doc that lacks the
  generated header. The embedded index block must be fresh (checked via
  ``index_is_fresh``); a mismatch is a malformed document.

Both functions are pure (no file I/O, no clock, no environment). Errors:
:class:`SchemaError` for a store that fails validation (the render gate runs
first), :class:`FormatError` for a malformed document — the command layer
maps both to exit 2.
"""

from __future__ import annotations

from securetrace.docs import RENDERER_VERSION
from securetrace.docs.canonical import DOC_TITLES, generated_header, skip_generated_header
from securetrace.docs.schema import SCHEMA_VERSION, validate_store
from securetrace.errors import FormatError
from securetrace.lessons.record import (
    BEGIN_RE,
    END_RE,
    ENTRY_MARKER_RE,
    FIELD_EMPTY_RE,
    FIELD_RE,
    HEADING_RE,
    INDEX_HEADER,
    index_is_fresh,
    regenerate,
    structural_errors,
)

__all__ = ["parse_lessons", "render_lessons"]

INDEX_BEGIN = "<!-- LLT:INDEX:BEGIN -->"
INDEX_END = "<!-- LLT:INDEX:END -->"

#: Placeholder interior for the index block (the ``? ?`` row stands in for
#: the ``LLT_INDEX_BLOCK`` self-row until :func:`regenerate` recomputes the
#: interior over the final layout).
_PLACEHOLDER_INDEX_ROW = "\t".join(["LLT_INDEX_BLOCK", "—", "—", "—", "—", "—", "?", "?"])


# --------------------------------------------------------------------- render


def render_lessons(store: object) -> str:
    """Render a validated ``lessons`` store to the ``LESSONS_LEARNED.md`` text (pure).

    The document is: title, blank, the generated no-hand-edit header, blank,
    the intro prose lines, blank, the TSV index block, blank, and one
    ``<!-- LLT:ENTRY:LLT-NNNN -->`` section per lesson in stored (strictly
    increasing id) order — marker, ``## LLT-NNNN — <title>`` heading, blank
    line, then the field lines — ending with exactly one trailing newline.
    The index block is (re)computed over this final layout by the legacy
    core, so the result is always fresh and
    ``index_is_fresh(render_lessons(store))`` holds.

    Raises:
        SchemaError: the store fails validation (the schema gate runs first).
    """
    validate_store(store)
    lessons = store["lessons"]
    lines: list[str] = [
        DOC_TITLES["lessons"],
        "",
        *generated_header("lessons", renderer_version=RENDERER_VERSION),
        "",
        *store["intro"],
        "",
        INDEX_BEGIN,
        INDEX_HEADER,  # placeholder interior; regenerate rewrites it with the computed rows
        _PLACEHOLDER_INDEX_ROW,
        INDEX_END,
        "",
    ]
    for i, lesson in enumerate(lessons):
        lines += [
            f"<!-- LLT:ENTRY:{lesson['id']} -->",
            f"## {lesson['id']} — {lesson['title']}",
            "",
        ]
        for field in lesson["fields"]:
            lines.append(f"- **{field['name']}:** {field['value']}")
        if i + 1 < len(lessons):
            lines.append("")
    return regenerate("\n".join(lines) + "\n")


# --------------------------------------------------------------------- parse


def _parse_entry_section(lines: list[str], i: int, eid: str) -> tuple[str, list[dict], int]:
    """Parse one entry section starting at marker line *i* (0-indexed).

    The section is: the marker, the ``## <id> — <title>`` heading, a blank
    line, and the field lines (each ``- **Name:** value`` with a non-empty
    value). Returns the entry title, the field records, and the index of
    the first line after the field lines (the separator blank line for
    interior entries, or ``len(lines)`` for the last entry).

    Raises:
        FormatError: heading missing/mismatched, separator blank missing, or
            a line that is neither a field line nor the next entry marker.
    """
    if i + 2 >= len(lines):
        raise FormatError(f"entry {eid}: marker must be followed by its heading and a blank line")
    hm = HEADING_RE.match(lines[i + 1])
    if hm is None:
        raise FormatError(f"entry {eid}: heading must be '## {eid} — <title>'")
    if hm.group("id") != eid:
        raise FormatError(
            f"entry marker {eid} (line {i + 1}) disagrees with heading id "
            f"{hm.group('id')} (line {i + 2}); marker and heading must match"
        )
    if lines[i + 2] != "":
        raise FormatError(f"entry {eid}: heading must be followed by a blank line")
    fields: list[dict] = []
    j = i + 3
    while j < len(lines) and lines[j] != "" and not ENTRY_MARKER_RE.match(lines[j]):
        fm = FIELD_RE.match(lines[j])
        if fm is None:
            fe = FIELD_EMPTY_RE.match(lines[j])
            if fe is not None:
                raise FormatError(
                    f"entry {eid}: field '{fe.group('name')}' has an empty value; "
                    "lesson field values must be non-empty (write — when absent)"
                )
            raise FormatError(
                f"entry {eid}: line {j + 1} is not a field line; the entry section "
                "must be marker, heading, blank line, then field lines"
            )
        fields.append({"name": fm.group("name"), "value": fm.group("value")})
        j += 1
    if not fields:
        raise FormatError(f"entry {eid} must contain at least one field line")
    return hm.group("title"), fields, j


def parse_lessons(text: str) -> dict:
    """Parse a ``LESSONS_LEARNED.md`` text into the ``lessons`` store (pure).

    Accepts exactly the grammar :func:`render_lessons` emits, plus the
    grandfathered doc that lacks the generated header. The embedded TSV
    index block must be fresh for the entries, and the entries must pass
    the legacy record's structural and cross-entry checks (duplicate ids,
    closed vocabularies, required fields, supersession, id ordering).

    Raises:
        FormatError: the document is malformed (bad title, broken skeleton,
            stale index block, bad heading, empty field value, duplicate id,
            bad vocabulary, missing required field).
        SchemaError: the parsed store fails schema validation (e.g. duplicate
            field names, non-increasing lesson ids).
    """
    if not isinstance(text, str):
        raise FormatError("the lessons document must be a UTF-8 string")
    lines = text.splitlines()
    if not lines or lines[0] != DOC_TITLES["lessons"]:
        raise FormatError(
            f"the lessons document must start with the title line {DOC_TITLES['lessons']!r}"
        )
    if len(lines) < 2 or lines[1] != "":
        raise FormatError("line 2 of the lessons document must be blank")
    cursor = skip_generated_header(lines, 2)

    # --- intro: prose lines (a free ordered list in the store)
    begin = next((i for i in range(cursor, len(lines)) if BEGIN_RE.match(lines[i])), None)
    if begin is None:
        raise FormatError("the document is missing the <!-- LLT:INDEX:BEGIN --> marker")
    if begin < cursor + 2:
        raise FormatError(
            "the intro must be non-empty and end with a blank line before the index block"
        )
    if lines[begin - 1] != "":
        raise FormatError("the intro must be followed by a blank line before the index block")
    intro = list(lines[cursor : begin - 1])

    # --- index block skeleton
    end = next((i for i in range(begin + 1, len(lines)) if END_RE.match(lines[i])), None)
    if end is None:
        raise FormatError("the index block is missing its <!-- LLT:INDEX:END --> marker")
    if end <= begin + 1:
        raise FormatError("the index block is empty or malformed")

    # --- entry sections
    if end + 2 >= len(lines) or lines[end + 1] != "":
        raise FormatError(
            "the index block must be followed by a blank line before the first entry"
        )
    if not ENTRY_MARKER_RE.match(lines[end + 2]):
        raise FormatError(
            "the lessons document must contain at least one entry after the index block"
        )
    lessons: list[dict] = []
    i = end + 2
    while i < len(lines):
        m = ENTRY_MARKER_RE.match(lines[i])
        if m is None:
            raise FormatError(
                f"line {i + 1} is not an entry marker (entries are separated by one blank line)"
            )
        eid = m.group("id")
        title, fields, j = _parse_entry_section(lines, i, eid)
        if j >= len(lines):
            lessons.append({"id": eid, "title": title, "fields": fields})
            break
        if lines[j] != "":
            raise FormatError(f"entry {eid}: the line after its fields must be a blank line")
        k = j + 1
        if k >= len(lines) or not ENTRY_MARKER_RE.match(lines[k]):
            raise FormatError(
                f"entry {eid} must be followed by a blank line and the next entry marker; "
                f"line {j + 2} (if present) is not an entry marker"
            )
        lessons.append({"id": eid, "title": title, "fields": fields})
        i = k

    errors = structural_errors(text)
    if errors:
        raise FormatError("lessons document is invalid: " + "; ".join(errors))
    if not index_is_fresh(text):
        raise FormatError(
            "index block does not match the entries (the document was likely hand-edited; "
            "update it via the securetrace CLI and re-render)"
        )
    store = {
        "doc": "lessons",
        "schema_version": SCHEMA_VERSION,
        "intro": intro,
        "lessons": lessons,
    }
    validate_store(store)
    return store
