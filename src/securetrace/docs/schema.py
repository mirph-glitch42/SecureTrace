"""Store schema validation for the deterministic document pipeline (B10).

A *store* is the canonical-JSON source of truth for one pipeline document:

- ``backlog``  → ``BACKLOG.md``          payload: updated, header, queue, items, constraints
- ``lessons``  → ``LESSONS_LEARNED.md``  payload: intro, lessons
- ``registry`` → ``algorithms/INDEX.md`` payload: intro, rows, rules

Validation is pure (dict in → :class:`SchemaError` or nothing). The command
layer maps ``SchemaError`` to exit 2 (malformed store). Closed vocabularies
reuse the legacy cores' definitions (``securetrace.lessons.record``), so the
pipeline cannot drift from the record's grammar.
"""

from __future__ import annotations

import re

from securetrace.errors import SecureTraceError
from securetrace.lessons.record import ALL_FIELDS, CATEGORIES, REQUIRED_FIELDS, SEVERITIES, STATUSES

__all__ = [
    "BACKLOG_STATUSES",
    "REGISTRY_ROW_KEYS",
    "REGISTRY_STATUSES",
    "SCHEMA_VERSION",
    "SchemaError",
    "validate_backlog",
    "validate_lessons",
    "validate_registry",
    "validate_store",
]

SCHEMA_VERSION = 1

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
UPDATED_LINE_RE = re.compile(r"\*\*Updated:\*\*[ \t]*(\d{4}-\d{2}-\d{2})[ \t]*$")
BACKLOG_ITEM_ID_RE = re.compile(r"^B\d+$")
LESSON_ID_RE = re.compile(r"^LLT-\d{4}$")
REGISTRY_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
REGISTRY_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
REGISTRY_FILE_RE = re.compile(r"^[A-Za-z0-9._/-]+\.md$")

#: Item statuses, in heading form (the TSV normalizes ``IN PROGRESS`` to
#: ``IN_PROGRESS`` itself — see ``securetrace.backlog.index.parse_item_heading``).
BACKLOG_STATUSES = ("OPEN", "IN PROGRESS", "DONE", "CANCELLED")
REGISTRY_STATUSES = ("draft", "implemented", "backfilled", "deprecated")
REGISTRY_ROW_KEYS = ("slug", "name", "version", "status", "file", "summary")

BACKLOG_PAYLOAD_KEYS = frozenset({"updated", "header", "queue", "items", "constraints"})
LESSONS_PAYLOAD_KEYS = frozenset({"intro", "lessons"})
REGISTRY_PAYLOAD_KEYS = frozenset({"intro", "rows", "rules"})

_PAYLOAD_KEYS = {
    "backlog": BACKLOG_PAYLOAD_KEYS,
    "lessons": LESSONS_PAYLOAD_KEYS,
    "registry": REGISTRY_PAYLOAD_KEYS,
}


class SchemaError(SecureTraceError):
    """The store fails schema validation (command layer: exit 2)."""


# --------------------------------------------------------------------- helpers


def _payload(store: object, kind: str) -> dict:
    """Validate the envelope and return the store for its exact payload keys."""
    if not isinstance(store, dict):
        raise SchemaError(f"store must be a JSON object, got {type(store).__name__}")
    if store.get("doc") != kind:
        raise SchemaError(f"store kind is {store.get('doc')!r}, expected {kind!r}")
    if store.get("schema_version") != SCHEMA_VERSION:
        raise SchemaError(
            f"store schema_version must be {SCHEMA_VERSION}, got {store.get('schema_version')!r}"
        )
    keys = set(store) - {"doc", "schema_version"}
    allowed = _PAYLOAD_KEYS[kind]
    missing = sorted(allowed - keys)
    if missing:
        raise SchemaError(f"{kind} store is missing payload keys: {', '.join(missing)}")
    extra = sorted(keys - allowed)
    if extra:
        raise SchemaError(f"{kind} store has unexpected payload keys: {', '.join(extra)}")
    return store


def _lines(value: object, what: str) -> None:
    if not isinstance(value, list) or not value:
        raise SchemaError(f"{what} must be a non-empty list")
    if not all(isinstance(line, str) for line in value):
        raise SchemaError(f"{what} must contain only strings")


def _nonempty_str(value: object, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SchemaError(f"{what} must be a non-empty string, got {value!r}")
    return value


def _field(name: object, lines: object, what: str) -> str:
    """Validate a backlog field ``{name, lines}`` and return the field name."""
    if not isinstance(name, str) or not name.strip():
        raise SchemaError(f"{what}.name must be a non-empty string, got {name!r}")
    if not isinstance(lines, list) or not all(isinstance(line, str) for line in lines):
        raise SchemaError(f"{what}.lines must be a list of strings")
    return name


def _value(name: object, value: object, what: str) -> str:
    """Validate a lessons field ``{name, value}`` and return the field name."""
    if not isinstance(name, str) or not name.strip():
        raise SchemaError(f"{what}.name must be a non-empty string, got {name!r}")
    if not isinstance(value, str) or not value.strip():
        raise SchemaError(f"{what}.value must be a non-empty string, got {value!r}")
    return name


# --------------------------------------------------------------------- backlog


def _validate_backlog_item(item: object, index: int) -> str:
    what = f"items[{index}]"
    if not isinstance(item, dict):
        raise SchemaError(f"{what} must be an object")
    if set(item) != {"id", "title", "status", "fields"}:
        raise SchemaError(f"{what} must have exactly the keys 'id', 'title', 'status', 'fields'")
    item_id = _nonempty_str(item["id"], f"{what}.id")
    if not BACKLOG_ITEM_ID_RE.fullmatch(item_id):
        raise SchemaError(f"{what}.id must be B<digits>, got {item_id!r}")
    _nonempty_str(item["title"], f"{what}.title")
    status = item["status"]
    if status not in BACKLOG_STATUSES:
        raise SchemaError(f"{what}.status must be one of: {', '.join(BACKLOG_STATUSES)}")
    fields = item["fields"]
    if not isinstance(fields, list) or not fields:
        raise SchemaError(f"{what}.fields must be a non-empty list")
    seen: set[str] = set()
    for fi, field in enumerate(fields):
        fwhat = f"{what}.fields[{fi}]"
        if not isinstance(field, dict) or set(field) != {"name", "lines"}:
            raise SchemaError(f"{fwhat} must have exactly the keys 'name' and 'lines'")
        name = _field(field["name"], field["lines"], fwhat)
        if name in seen:
            raise SchemaError(f"{what} has duplicate field: {name}")
        seen.add(name)
    return item_id


def validate_backlog(store: object) -> None:
    """Validate a ``backlog`` store. Raises :class:`SchemaError` on any violation."""
    s = _payload(store, "backlog")
    updated = s["updated"]
    if not isinstance(updated, str) or not DATE_RE.fullmatch(updated):
        raise SchemaError(f"backlog.updated must be a YYYY-MM-DD date string, got {updated!r}")
    _lines(s["header"], "backlog.header")
    _lines(s["queue"], "backlog.queue")
    _lines(s["constraints"], "backlog.constraints")
    header_dates = [
        m.group(1) for line in s["header"] if (m := UPDATED_LINE_RE.search(line)) is not None
    ]
    if len(header_dates) != 1:
        raise SchemaError(
            "backlog.header must contain exactly one line ending with '**Updated:** YYYY-MM-DD'"
        )
    if header_dates[0] != updated:
        raise SchemaError(
            f"backlog.updated ({updated!r}) does not match the header status line date "
            f"({header_dates[0]!r})"
        )
    items = s["items"]
    if not isinstance(items, list) or not items:
        raise SchemaError("backlog.items must be a non-empty list")
    seen: set[str] = set()
    prev_num: int | None = None
    for i, item in enumerate(items):
        item_id = _validate_backlog_item(item, i)
        if item_id in seen:
            raise SchemaError(f"duplicate backlog item id: {item_id}")
        seen.add(item_id)
        num = int(item_id[1:])
        if prev_num is not None and num <= prev_num:
            raise SchemaError(
                f"backlog item ids must be strictly increasing: {item_id} after B{prev_num}"
            )
        prev_num = num


# --------------------------------------------------------------------- lessons


def _check_field_vocab(what: str, values: dict[str, str]) -> None:
    """Check the closed vocabularies of a lesson's optional fields.

    Raises:
        SchemaError: ``Category``/``Severity``/``Status`` outside the closed
            set, or ``Recorded`` not a YYYY-MM-DD date.
    """
    category = values.get("Category")
    if category is not None and category not in CATEGORIES:
        raise SchemaError(f"{what}.Category must be one of: {', '.join(CATEGORIES)}")
    severity = values.get("Severity")
    if severity is not None and severity not in SEVERITIES:
        raise SchemaError(f"{what}.Severity must be one of: {', '.join(SEVERITIES)}")
    status = values.get("Status")
    if status is not None and status not in STATUSES:
        raise SchemaError(f"{what}.Status must be one of: {', '.join(STATUSES)}")
    recorded = values.get("Recorded")
    if recorded is not None and not DATE_RE.fullmatch(recorded):
        raise SchemaError(f"{what}.Recorded must be a YYYY-MM-DD date string, got {recorded!r}")


def _validate_lesson(lesson: object, index: int) -> str:
    what = f"lessons[{index}]"
    if not isinstance(lesson, dict):
        raise SchemaError(f"{what} must be an object")
    if set(lesson) != {"id", "title", "fields"}:
        raise SchemaError(f"{what} must have exactly the keys 'id', 'title', 'fields'")
    lesson_id = _nonempty_str(lesson["id"], f"{what}.id")
    if not LESSON_ID_RE.fullmatch(lesson_id):
        raise SchemaError(f"{what}.id must match LLT-NNNN, got {lesson_id!r}")
    _nonempty_str(lesson["title"], f"{what}.title")
    fields = lesson["fields"]
    if not isinstance(fields, list) or not fields:
        raise SchemaError(f"{what}.fields must be a non-empty list")
    names: set[str] = set()
    values: dict[str, str] = {}
    for fi, field in enumerate(fields):
        fwhat = f"{what}.fields[{fi}]"
        if not isinstance(field, dict) or set(field) != {"name", "value"}:
            raise SchemaError(f"{fwhat} must have exactly the keys 'name' and 'value'")
        name = _value(field["name"], field["value"], fwhat)
        if name in names:
            raise SchemaError(f"{what} has duplicate field: {name}")
        names.add(name)
        values[name] = field["value"]
    missing = [name for name in REQUIRED_FIELDS if name not in names]
    if missing:
        raise SchemaError(f"{what} is missing required field(s): {', '.join(missing)}")
    unknown = names - set(ALL_FIELDS)
    if unknown:
        raise SchemaError(f"{what} has unknown field(s): {', '.join(sorted(unknown))}")
    _check_field_vocab(what, values)
    return lesson_id


def validate_lessons(store: object) -> None:
    """Validate a ``lessons`` store. Raises :class:`SchemaError` on any violation."""
    s = _payload(store, "lessons")
    _lines(s["intro"], "lessons.intro")
    lessons = s["lessons"]
    if not isinstance(lessons, list) or not lessons:
        raise SchemaError("lessons.lessons must be a non-empty list")
    seen: set[str] = set()
    prev_num: int | None = None
    for i, lesson in enumerate(lessons):
        lesson_id = _validate_lesson(lesson, i)
        if lesson_id in seen:
            raise SchemaError(f"duplicate lesson id: {lesson_id}")
        seen.add(lesson_id)
        num = int(lesson_id[4:])
        if prev_num is not None and num <= prev_num:
            after = f"LLT-{prev_num:04d}"
            raise SchemaError(f"lesson ids must be strictly increasing: {lesson_id} after {after}")
        prev_num = num


# --------------------------------------------------------------------- registry


def _validate_registry_row(row: object, index: int) -> str:
    what = f"rows[{index}]"
    if not isinstance(row, dict):
        raise SchemaError(f"{what} must be an object")
    if set(row) != set(REGISTRY_ROW_KEYS):
        raise SchemaError(f"{what} must have exactly the keys: {', '.join(REGISTRY_ROW_KEYS)}")
    for key in REGISTRY_ROW_KEYS:
        _nonempty_str(row[key], f"{what}.{key}")
    slug = row["slug"]
    if not REGISTRY_SLUG_RE.fullmatch(slug):
        raise SchemaError(f"{what}.slug must be kebab-case, got {slug!r}")
    version = row["version"]
    if not REGISTRY_VERSION_RE.fullmatch(version):
        raise SchemaError(f"{what}.version must be MAJOR.MINOR.PATCH, got {version!r}")
    status = row["status"]
    if status not in REGISTRY_STATUSES:
        raise SchemaError(f"{what}.status must be one of: {', '.join(REGISTRY_STATUSES)}")
    if not REGISTRY_FILE_RE.fullmatch(row["file"]):
        raise SchemaError(f"{what}.file must be a relative .md path, got {row['file']!r}")
    return slug


def validate_registry(store: object) -> None:
    """Validate a ``registry`` store. Raises :class:`SchemaError` on any violation."""
    s = _payload(store, "registry")
    _lines(s["intro"], "registry.intro")
    _lines(s["rules"], "registry.rules")
    rows = s["rows"]
    if not isinstance(rows, list) or not rows:
        raise SchemaError("registry.rows must be a non-empty list")
    slugs: list[str] = []
    for i, row in enumerate(rows):
        slug = _validate_registry_row(row, i)
        slugs.append(slug)
    duplicates = sorted({slug for slug in slugs if slugs.count(slug) > 1})
    if duplicates:
        raise SchemaError(f"duplicate registry slug(s): {', '.join(duplicates)}")
    if slugs != sorted(slugs):
        raise SchemaError("registry rows must be sorted by slug")


# --------------------------------------------------------------------- dispatch


_VALIDATORS = {
    "backlog": validate_backlog,
    "lessons": validate_lessons,
    "registry": validate_registry,
}


def validate_store(store: object) -> None:
    """Validate a store of any known kind. Raises :class:`SchemaError` otherwise."""
    if not isinstance(store, dict) or "doc" not in store:
        raise SchemaError("store must be an object with a 'doc' key")
    kind = store["doc"]
    if kind not in _VALIDATORS:
        raise SchemaError(f"unknown store kind: {kind!r}")
    _VALIDATORS[kind](store)
