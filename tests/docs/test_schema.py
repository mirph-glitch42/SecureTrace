"""Schema validation tests for the three pipeline stores (B10 WI 3; ALRK doc T7)."""

import pytest

from securetrace.docs.schema import (
    BACKLOG_STATUSES,
    REGISTRY_STATUSES,
    SCHEMA_VERSION,
    SchemaError,
    validate_backlog,
    validate_lessons,
    validate_registry,
    validate_store,
)


# --------------------------------------------------------------------------- factories


def backlog_item(i, status="DONE", title=None, fields=None):
    return {
        "id": f"B{i}",
        "title": title or f"item {i}",
        "status": status,
        "fields": fields
        or [
            {"name": "Source", "lines": ["user"]},
            {"name": "Progress", "lines": ["  - 2026-10-20 — done"]},
        ],
    }


def backlog_store(items=None):
    return {
        "doc": "backlog",
        "schema_version": SCHEMA_VERSION,
        "updated": "2026-10-20",
        # prose lines only — the section headings are renderer constants, not store data
        "header": [
            "Tracks all SecureTrace work.",
            "",
            "**Queue:** — | **In progress:** — | **Done:** B1 | **Updated:** 2026-10-20",
        ],
        "queue": ["— (queue is empty; all items done)"],
        "items": [backlog_item(1)] if items is None else items,
        "constraints": ["- gate green"],
    }


def lesson(i, fields=None):
    return {
        "id": f"LLT-{i:04d}",
        "title": f"lesson {i}",
        "fields": fields
        or [
            {"name": "Recorded", "value": "2026-10-18"},
            {"name": "Category", "value": "tooling"},
            {"name": "Severity", "value": "medium"},
            {"name": "Status", "value": "active"},
            {"name": "Context", "value": "ctx"},
            {"name": "Pitfall", "value": "pit"},
            {"name": "Solution", "value": "sol"},
        ],
    }


def lessons_store(lessons=None):
    return {
        "doc": "lessons",
        "schema_version": SCHEMA_VERSION,
        "intro": ["# Lessons Learned", "", "Authoritative record of lessons learned.", ""],
        "lessons": [lesson(1), lesson(2)] if lessons is None else lessons,
    }


def registry_row(slug, **overrides):
    row = {
        "slug": slug,
        "name": slug.title(),
        "version": "0.1.0",
        "status": "draft",
        "file": f"{slug}.md",
        "summary": "a one-line summary",
    }
    row.update(overrides)
    return row


def registry_store(rows=None):
    return {
        "doc": "registry",
        "schema_version": SCHEMA_VERSION,
        "intro": ["> One row per algorithm document in this directory. Keep sorted by slug."],
        "rows": [registry_row("alpha"), registry_row("beta")] if rows is None else rows,
        "rules": ["1. Add a row when a document is created; never delete a row."],
    }


# --------------------------------------------------------------------------- backlog


def test_backlog_valid_passes():
    validate_backlog(backlog_store())
    validate_store(backlog_store())


def test_backlog_duplicate_item_id_rejected():
    """T7: duplicate item ids are malformed (exit 2 upstream)."""
    store = backlog_store(items=[backlog_item(1), backlog_item(1)])
    with pytest.raises(SchemaError, match="duplicate"):
        validate_backlog(store)


def test_backlog_item_ids_must_increase():
    store = backlog_store(items=[backlog_item(2), backlog_item(1)])
    with pytest.raises(SchemaError, match="increasing"):
        validate_backlog(store)


def test_backlog_unknown_status_rejected():
    store = backlog_store(items=[backlog_item(1, status="FROB")])
    with pytest.raises(SchemaError, match="status"):
        validate_backlog(store)


def test_backlog_all_statuses_accepted():
    for status in BACKLOG_STATUSES:
        validate_backlog(backlog_store(items=[backlog_item(1, status=status)]))


def test_backlog_missing_payload_key_rejected():
    store = backlog_store()
    del store["constraints"]
    with pytest.raises(SchemaError, match="constraints"):
        validate_backlog(store)


def test_backlog_extra_payload_key_rejected():
    store = backlog_store()
    store["extra"] = []
    with pytest.raises(SchemaError, match="extra"):
        validate_backlog(store)


def test_backlog_bad_updated_rejected():
    store = backlog_store()
    store["updated"] = "2026-10-20T00:00:00Z"
    with pytest.raises(SchemaError, match="updated"):
        validate_backlog(store)


def test_backlog_duplicate_field_names_rejected():
    item = backlog_item(
        1,
        fields=[
            {"name": "Source", "lines": ["user"]},
            {"name": "Source", "lines": ["agent"]},
        ],
    )
    store = backlog_store(items=[item])
    with pytest.raises(SchemaError, match="duplicate"):
        validate_backlog(store)


def test_backlog_field_must_carry_lines():
    item = backlog_item(1, fields=[{"name": "Source", "value": "user"}])
    store = backlog_store(items=[item])
    with pytest.raises(SchemaError, match="lines"):
        validate_backlog(store)


# --------------------------------------------------------------------------- lessons


def test_lessons_valid_passes():
    validate_lessons(lessons_store())
    validate_store(lessons_store())


def test_lessons_duplicate_id_rejected():
    store = lessons_store(lessons=[lesson(1), lesson(1)])
    with pytest.raises(SchemaError, match="duplicate"):
        validate_lessons(store)


def test_lessons_ids_must_increase():
    store = lessons_store(lessons=[lesson(2), lesson(1)])
    with pytest.raises(SchemaError, match="increasing"):
        validate_lessons(store)


def test_lessons_missing_required_field_rejected():
    l = lesson(1)
    l["fields"] = [f for f in l["fields"] if f["name"] != "Solution"]
    store = lessons_store(lessons=[l])
    with pytest.raises(SchemaError, match="Solution"):
        validate_lessons(store)


def test_lessons_unknown_field_rejected():
    l = lesson(1)
    l["fields"].append({"name": "Vibes", "value": "good"})
    store = lessons_store(lessons=[l])
    with pytest.raises(SchemaError, match="Vibes"):
        validate_lessons(store)


def test_lessons_bad_vocabulary_rejected():
    for field_name, bad in (("Category", "vibes"), ("Severity", "mega"), ("Status", "frobbed")):
        l = lesson(1)
        for f in l["fields"]:
            if f["name"] == field_name:
                f["value"] = bad
        store = lessons_store(lessons=[l])
        with pytest.raises(SchemaError, match=field_name):
            validate_lessons(store)


def test_lessons_bad_recorded_date_rejected():
    l = lesson(1)
    for f in l["fields"]:
        if f["name"] == "Recorded":
            f["value"] = "18/10/2026"
    store = lessons_store(lessons=[l])
    with pytest.raises(SchemaError, match="Recorded"):
        validate_lessons(store)


# --------------------------------------------------------------------------- registry


def test_registry_valid_passes():
    validate_registry(registry_store())
    validate_store(registry_store())


def test_registry_duplicate_slug_rejected():
    store = registry_store(rows=[registry_row("alpha"), registry_row("alpha")])
    with pytest.raises(SchemaError, match="duplicate"):
        validate_registry(store)


def test_registry_unsorted_rows_rejected():
    store = registry_store(rows=[registry_row("beta"), registry_row("alpha")])
    with pytest.raises(SchemaError, match="sorted"):
        validate_registry(store)


def test_registry_bad_version_rejected():
    store = registry_store(rows=[registry_row("alpha", version="0.1")])
    with pytest.raises(SchemaError, match="version"):
        validate_registry(store)


def test_registry_unknown_status_rejected():
    store = registry_store(rows=[registry_row("alpha", status="wip")])
    with pytest.raises(SchemaError, match="status"):
        validate_registry(store)


def test_registry_all_statuses_accepted():
    for status in REGISTRY_STATUSES:
        validate_registry(registry_store(rows=[registry_row("alpha", status=status)]))


def test_registry_bad_slug_rejected():
    store = registry_store(rows=[registry_row("Alpha-Beta")])
    with pytest.raises(SchemaError, match="slug"):
        validate_registry(store)


# --------------------------------------------------------------------------- envelope


def test_unknown_kind_rejected():
    bad = {"doc": "notes", "schema_version": SCHEMA_VERSION}
    with pytest.raises(SchemaError, match="unknown"):
        validate_store(bad)


def test_bad_schema_version_rejected():
    store = backlog_store()
    store["schema_version"] = 2
    with pytest.raises(SchemaError, match="schema_version"):
        validate_backlog(store)


def test_non_dict_store_rejected():
    bad = [1, 2, 3]
    with pytest.raises(SchemaError):
        validate_store(bad)
