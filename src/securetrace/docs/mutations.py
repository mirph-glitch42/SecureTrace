"""Pure mutation core for the store-based document pipeline (B10 WI 8).

The pure half of ``upsert`` / ``progress`` / ``add`` (spec:
``algorithms/deterministic-doc-pipeline.md`` §3): dict in → NEW dict out
(``copy.deepcopy`` first — the input store and input payload are never
mutated), no clock, no I/O. Every backlog mutation recomputes the
``**Queue:** … | **In progress:** … | **Done:** … | **Updated:** …`` header
line from the item statuses (design decision D4, ALRK doc v0.1.5 §5.3), and
every result passes the schema gate (``schema.validate_store``) before it is
returned, so a mutation can never leave a store behind that ``check`` would
call malformed.

Error contract (the command layer maps both to exit 2):

- :class:`~securetrace.errors.InvalidInput` — the caller's payload is
  malformed (wrong key set, unknown item id, missing supersedes target, …);
- :class:`~securetrace.docs.schema.SchemaError` — the resulting store fails
  schema validation (id collision, id below the max, bad vocabulary, …).

Purity is enforced by the T9 AST ban in ``tests/docs/test_core_discipline.py``
(no ``datetime``/``time``/``random``/``uuid``/``os``/``subprocess``/
``socket``/``urllib`` top-level imports); dates arrive as explicit
``YYYY-MM-DD`` parameters (the same no-clock precedent as
``record.add_lesson(text, lesson, today)``).
"""

from __future__ import annotations

import copy

from securetrace.docs.schema import DATE_RE, REGISTRY_ROW_KEYS, UPDATED_LINE_RE, validate_store
from securetrace.errors import InvalidInput

__all__ = [
    "add_lesson",
    "append_backlog_progress",
    "refresh_backlog_status",
    "set_lessons_intro",
    "upsert_backlog_item",
    "upsert_registry_row",
]

#: The closed payload key sets (InvalidInput gate; the schema gate repeats
#: them for the store result).
_ITEM_KEYS = frozenset({"id", "title", "status", "fields"})
_LESSON_KEYS = frozenset({"id", "title", "fields"})

#: D4 status-line derivation: Queue = OPEN or IN PROGRESS (stored order);
#: CANCELLED items appear in none of the three lists.
_QUEUE_STATUSES = ("OPEN", "IN PROGRESS")
_PROGRESS_FIELD = "Progress"
_EM_DASH = "—"


# --------------------------------------------------------------------- helpers


def _field_value(payload: dict, name: str) -> str | None:
    """Return the ``{name, value}`` field value of a lessons/entry payload."""
    fields = payload.get("fields")
    if not isinstance(fields, list):
        return None
    for field in fields:
        if isinstance(field, dict) and field.get("name") == name:
            return field.get("value")
    return None


def _set_field(payload: dict, name: str, value: str) -> None:
    """Set (or append) a ``{name, value}`` field on a lessons/entry payload."""
    fields = payload.get("fields")
    if not isinstance(fields, list):
        return  # leave a malformed fields value for validate_store to reject
    for field in fields:
        if isinstance(field, dict) and field.get("name") == name:
            field["value"] = value
            return
    fields.append({"name": name, "value": value})


def _next_lesson_id(lessons: list) -> str:
    """Return ``LLT-<max+1>`` (four digits) for the stored lesson ids."""
    max_num = 0
    for existing in lessons:
        if not isinstance(existing, dict):
            continue
        value = existing.get("id")
        if isinstance(value, str) and value.startswith("LLT-") and value[4:].isdigit():
            max_num = max(max_num, int(value[4:]))
    return f"LLT-{max_num + 1:04d}"


def _derived_status_line(items: object, date: str) -> str:
    """Compute the D4 backlog header line from the item statuses (pure).

    Queue = OPEN or IN PROGRESS (stored order), In progress = IN PROGRESS,
    Done = DONE; CANCELLED is excluded from all three lists; an empty list
    renders as an em dash; ids are ``", "``-separated.
    """

    def _ids(statuses: tuple[str, ...]) -> str:
        if not isinstance(items, list):
            return _EM_DASH
        ids = [
            it["id"]
            for it in items
            if isinstance(it, dict)
            and isinstance(it.get("id"), str)
            and it.get("status") in statuses
        ]
        return ", ".join(ids) if ids else _EM_DASH

    return (
        f"**Queue:** {_ids(_QUEUE_STATUSES)}"
        f" | **In progress:** {_ids(('IN PROGRESS',))}"
        f" | **Done:** {_ids(('DONE',))}"
        f" | **Updated:** {date}"
    )


def _sorted_slug_index(rows: list, slug: object) -> int:
    """Return the index where *slug* keeps the row list slug-sorted."""
    index = len(rows)
    for i, existing in enumerate(rows):
        existing_slug = existing.get("slug") if isinstance(existing, dict) else None
        if isinstance(existing_slug, str) and isinstance(slug, str) and existing_slug > slug:
            index = i
            break
    return index


# --------------------------------------------------------------------- backlog


def refresh_backlog_status(store: dict, date: str) -> dict:
    """Return a NEW backlog store with the D4 status line recomputed.

    The first header line matching ``schema.UPDATED_LINE_RE`` is replaced
    with the line derived from the item statuses, and ``updated`` is set to
    *date* (so the schema's updated/header-date agreement holds again).
    The input store is never mutated.

    Raises:
        InvalidInput: *date* is not a ``YYYY-MM-DD`` string, *store* is not a
            backlog store with a header line list, or the header has no
            ``**Updated:** YYYY-MM-DD`` line.
    """
    if not isinstance(date, str) or not DATE_RE.fullmatch(date):
        raise InvalidInput(f"date must be a YYYY-MM-DD string, got {date!r}")
    if not isinstance(store, dict) or not isinstance(store.get("header"), list):
        raise InvalidInput("store must be a backlog store with a header line list")
    out = copy.deepcopy(store)
    for i, line in enumerate(out["header"]):
        if isinstance(line, str) and UPDATED_LINE_RE.search(line):
            out["header"][i] = _derived_status_line(out.get("items"), date)
            out["updated"] = date
            return out
    raise InvalidInput("backlog header has no '**Updated:** YYYY-MM-DD' status line")


def upsert_backlog_item(store: dict, item: dict, date: str) -> dict:
    """Return a NEW store with *item* replaced in place (same id) or appended.

    *item* is ``{id, title, status, fields[{name, lines}]}``. After the
    upsert the D4 status line is recomputed with *date* and the result is
    schema-validated (id shape, strictly increasing ids, status vocabulary).

    Raises:
        InvalidInput: *item* is not an object with exactly the four keys, or
            the refresh invariants of :func:`refresh_backlog_status` fail.
        SchemaError: the resulting store fails ``schema.validate_store``.
    """
    if not isinstance(item, dict) or set(item) != _ITEM_KEYS:
        raise InvalidInput("backlog item must have exactly the keys 'id', 'title', 'status', 'fields'")
    out = copy.deepcopy(store)
    items = out.get("items")
    if not isinstance(items, list):
        items = []
        out["items"] = items
    new_item = copy.deepcopy(item)
    item_id = item.get("id")
    for i, existing in enumerate(items):
        if isinstance(existing, dict) and existing.get("id") == item_id:
            items[i] = new_item
            break
    else:
        items.append(new_item)
    refreshed = refresh_backlog_status(out, date)
    validate_store(refreshed)
    return refreshed


def _find_item(items: list, item_id: str) -> dict | None:
    """Return the first item in *items* whose ``id`` equals *item_id*.

    Non-dict entries are skipped.
    """
    for item in items:
        if isinstance(item, dict) and item.get("id") == item_id:
            return item
    return None


def _append_field_line(fields: list, name: str, line: str) -> None:
    """Append *line* to the field named *name*, creating it at the end."""
    for field in fields:
        if isinstance(field, dict) and field.get("name") == name:
            lines = field.get("lines")
            if not isinstance(lines, list):
                lines = []
                field["lines"] = lines
            lines.append(line)
            return
    fields.append({"name": name, "lines": [line]})


def append_backlog_progress(store: dict, item_id: str, line: str, date: str) -> dict:
    """Return a NEW store with *line* appended to the item's Progress field.

    *line* is the FULL stored line — the command layer composes
    ``"  - {date} — {text}"`` and passes it in. The line goes into the item's
    existing ``Progress`` field or a new one created at the end of its
    fields; the D4 status line is then recomputed with *date*.

    Raises:
        InvalidInput: no item with *item_id* exists, *line* is not a string,
            or the refresh invariants of :func:`refresh_backlog_status` fail.
        SchemaError: the resulting store fails ``schema.validate_store``.
    """
    if not isinstance(line, str):
        raise InvalidInput(f"progress line must be a string, got {type(line).__name__}")
    out = copy.deepcopy(store)
    items = out.get("items") if isinstance(out.get("items"), list) else []
    target = _find_item(items, item_id)
    if target is None:
        raise InvalidInput(f"backlog item {item_id!r} not found")
    fields = target.get("fields")
    if not isinstance(fields, list):
        fields = []
        target["fields"] = fields
    _append_field_line(fields, _PROGRESS_FIELD, line)
    refreshed = refresh_backlog_status(out, date)
    validate_store(refreshed)
    return refreshed


# --------------------------------------------------------------------- lessons


def _apply_supersedes(new_lesson: dict, lessons: list) -> None:
    """Flip the ``Supersedes`` target to ``superseded`` (if one is named).

    A missing or em-dash ``Supersedes`` value is a no-op.

    Raises:
        InvalidInput: the named target does not exist, or is not ``active``.
    """
    supersedes = _field_value(new_lesson, "Supersedes")
    if supersedes is None or supersedes == _EM_DASH:
        return
    target = _find_item(lessons, supersedes)
    if target is None:
        raise InvalidInput(f"supersedes target {supersedes!r} not found")
    if _field_value(target, "Status") != "active":
        raise InvalidInput(f"superseded lesson {supersedes!r} is not active")
    _set_field(target, "Status", "superseded")


def add_lesson(store: dict, lesson: dict) -> dict:
    """Return a NEW lessons store with *lesson* appended (schema-validated).

    *lesson* is ``{id: optional, title, fields[{name, value}]}``. A missing
    id is auto-assigned as ``LLT-<max+1>``; an explicit id must stay strictly
    increasing and unique (schema gate). A ``Supersedes`` value other than
    the em dash names a target that must exist and be ``active``; the target
    is flipped to ``superseded``. The new lesson's ``Status`` is forced to
    ``active`` (a new lesson can never be born superseded).

    Raises:
        InvalidInput: *lesson* is not an object with a title and fields (plus
            an optional id); a ``Supersedes`` target is missing or not active.
        SchemaError: the resulting store fails ``schema.validate_store``
            (duplicate id, id below the max, vocabularies, …).
    """
    if not isinstance(lesson, dict) or "title" not in lesson or "fields" not in lesson:
        raise InvalidInput("lesson must have a 'title' and 'fields' (plus an optional 'id')")
    extra = set(lesson) - _LESSON_KEYS
    if extra:
        raise InvalidInput(f"lesson has unexpected key(s): {', '.join(sorted(extra))}")
    out = copy.deepcopy(store)
    lessons = out.get("lessons")
    if not isinstance(lessons, list):
        raise InvalidInput("lessons store is missing its lessons list")
    new_lesson = copy.deepcopy(lesson)
    if new_lesson.get("id") is None:
        new_lesson["id"] = _next_lesson_id(lessons)
    _set_field(new_lesson, "Status", "active")
    _apply_supersedes(new_lesson, lessons)
    lessons.append(new_lesson)
    validate_store(out)
    return out


def set_lessons_intro(store: dict, intro: list[str]) -> dict:
    """Return a NEW lessons store with the ``intro`` lines replaced (D15).

    *intro* must be a non-empty list of non-empty, tab-free strings; the
    schema gate (``schema.validate_store``) then re-validates the whole
    store, so the mutation can never leave a store behind that ``check``
    would call malformed. Lessons and every other field are untouched.

    Raises:
        InvalidInput: *intro* is not a list of non-empty, tab-free strings.
        SchemaError: the resulting store fails ``schema.validate_store``.
    """
    if not isinstance(intro, list) or not intro:
        raise InvalidInput("intro must be a non-empty list of lines")
    for line in intro:
        if not isinstance(line, str):
            raise InvalidInput("intro lines must be strings")
        if not line:
            raise InvalidInput("intro lines must be non-empty")
        if "\t" in line:
            raise InvalidInput("intro lines must not contain tabs")
    out = copy.deepcopy(store)
    out["intro"] = copy.deepcopy(intro)
    validate_store(out)
    return out


# --------------------------------------------------------------------- registry


def upsert_registry_row(store: dict, row: dict) -> dict:
    """Return a NEW registry store with *row* replaced or slug-sorted-inserted.

    *row* is ``{slug, name, version, status, file, summary}`` (the closed
    :data:`schema.REGISTRY_ROW_KEYS` set). A row with an existing slug is
    replaced in place; a new slug is inserted at its slug-sorted position.
    The result is schema-validated (slug shape, version, status vocabulary,
    sorted and unique slugs).

    Raises:
        InvalidInput: *row* is not an object with exactly the six keys.
        SchemaError: the resulting store fails ``schema.validate_store``.
    """
    if not isinstance(row, dict) or set(row) != set(REGISTRY_ROW_KEYS):
        raise InvalidInput(f"registry row must have exactly the keys: {', '.join(REGISTRY_ROW_KEYS)}")
    out = copy.deepcopy(store)
    rows = out.get("rows")
    if not isinstance(rows, list):
        rows = []
        out["rows"] = rows
    new_row = copy.deepcopy(row)
    slug = row.get("slug")
    for i, existing in enumerate(rows):
        if isinstance(existing, dict) and existing.get("slug") == slug:
            rows[i] = new_row
            break
    else:
        rows.insert(_sorted_slug_index(rows, slug), new_row)
    validate_store(out)
    return out
