"""Pure mutation core tests (B10 WI 8; ALRK doc §5.3 CLI contract).

Spec: ``algorithms/deterministic-doc-pipeline.md`` — the mutation core is the
pure half of ``upsert`` / ``progress`` / ``add``: dict in → NEW dict out (the
input store is never mutated), the backlog status line is recomputed from the
item statuses on every backlog mutation (design decision D4), and the schema
gate (``schema.validate_store``) runs on every result. The command layer
(``securetrace.cli_docs``) maps ``SchemaError`` / ``InvalidInput`` to exit 2.

Purity (no clock, no file I/O) is enforced separately by the T9 AST ban in
``tests/docs/test_core_discipline.py``, which discovers this module
automatically.
"""

from __future__ import annotations

import copy

import pytest

from securetrace.docs.mutations import (
    add_lesson,
    append_backlog_progress,
    refresh_backlog_status,
    set_lessons_intro,
    upsert_backlog_item,
    upsert_registry_row,
)
from securetrace.docs.schema import SCHEMA_VERSION, SchemaError
from securetrace.errors import InvalidInput

# --------------------------------------------------------------------- fixtures


def backlog_store() -> dict:
    """A valid 3-item backlog store (B1 IN PROGRESS, B2 OPEN, B3 DONE)."""
    return {
        "doc": "backlog",
        "schema_version": SCHEMA_VERSION,
        "updated": "2026-10-20",
        "header": [
            "Tracks all SecureTrace work.",
            "",
            "**Queue:** B1, B2 | **In progress:** B1 | **Done:** B3 | **Updated:** 2026-10-20",
        ],
        "queue": ["**B1** (one)", "**B2** (two)", "**B3** (three)"],
        "items": [
            {
                "id": "B1",
                "title": "Item one",
                "status": "IN PROGRESS",
                "fields": [{"name": "Source", "lines": ["user"]}],
            },
            {
                "id": "B2",
                "title": "Item two",
                "status": "OPEN",
                "fields": [{"name": "Source", "lines": ["user"]}],
            },
            {
                "id": "B3",
                "title": "Item three",
                "status": "DONE",
                "fields": [{"name": "Source", "lines": ["user"]}],
            },
        ],
        "constraints": ["- gate green"],
    }


def item(id="B4", title="Item four", status="OPEN") -> dict:
    return {
        "id": id,
        "title": title,
        "status": status,
        "fields": [{"name": "Source", "lines": ["user"]}],
    }


def lesson(n: int, **over) -> dict:
    base = {
        "id": f"LLT-{n:04d}",
        "title": f"Synthetic lesson {n}",
        "fields": [
            {"name": "Recorded", "value": "2026-10-20"},
            {"name": "Category", "value": "tooling"},
            {"name": "Severity", "value": "medium"},
            {"name": "Status", "value": "active"},
            {"name": "Context", "value": f"context for {n}"},
            {"name": "Pitfall", "value": f"pitfall for {n}"},
            {"name": "Solution", "value": f"solution for {n}"},
            {"name": "Supersedes", "value": "—"},
            {"name": "Prevention", "value": "—"},
            {"name": "References", "value": "—"},
        ],
    }
    base.update(over)
    return base


def lessons_store(*nums: int) -> dict:
    return {
        "doc": "lessons",
        "schema_version": SCHEMA_VERSION,
        "intro": ["Intro one.", "Intro two."],
        "lessons": [lesson(n) for n in nums],
    }


def row(slug: str, **over) -> dict:
    base = {
        "slug": slug,
        "name": f"Name {slug}",
        "version": "0.1.0",
        "status": "implemented",
        "file": f"algorithms/{slug}.md",
        "summary": f"Summary for {slug}.",
    }
    base.update(over)
    return base


def registry_store() -> dict:
    return {
        "doc": "registry",
        "schema_version": SCHEMA_VERSION,
        "intro": ["> One row per algorithm document."],
        "rows": [row("alpha"), row("charlie")],
        "rules": ["Keep sorted by slug."],
    }


def header_line(store: dict) -> str:
    return store["header"][-1]


# --------------------------------------------------------------------- refresh_backlog_status (D4)


def test_refresh_recomputes_status_line_and_updated() -> None:
    store = backlog_store()
    frozen = copy.deepcopy(store)
    out = refresh_backlog_status(store, "2026-10-21")
    assert out["updated"] == "2026-10-21"
    assert header_line(out) == (
        "**Queue:** B1, B2 | **In progress:** B1 | **Done:** B3 | **Updated:** 2026-10-21"
    )
    assert store == frozen, "input store must not be mutated"


def test_refresh_empties_render_em_dash() -> None:
    store = backlog_store()
    store["items"] = [item("B1", "Item one", "CANCELLED")]
    out = refresh_backlog_status(store, "2026-10-20")
    assert header_line(out) == (
        "**Queue:** — | **In progress:** — | **Done:** — | **Updated:** 2026-10-20"
    )


def test_refresh_missing_status_line_raises_invalid_input() -> None:
    store = backlog_store()
    store["header"] = ["No status line here."]
    with pytest.raises(InvalidInput, match="Updated"):
        refresh_backlog_status(store, "2026-10-20")


def test_refresh_rejects_bad_date() -> None:
    store = backlog_store()
    with pytest.raises(InvalidInput, match="date"):
        refresh_backlog_status(store, "21/10/2026")


# --------------------------------------------------------------------- upsert_backlog_item


def test_upsert_appends_new_item_and_refreshes() -> None:
    store = backlog_store()
    frozen = copy.deepcopy(store)
    out = upsert_backlog_item(store, item(), "2026-10-21")
    assert [it["id"] for it in out["items"]] == ["B1", "B2", "B3", "B4"]
    assert out["updated"] == "2026-10-21"
    assert header_line(out) == (
        "**Queue:** B1, B2, B4 | **In progress:** B1 | **Done:** B3 | **Updated:** 2026-10-21"
    )
    assert store == frozen, "input store must not be mutated"


def test_upsert_replaces_existing_item_in_place() -> None:
    out = upsert_backlog_item(
        backlog_store(), item("B2", "Item two (revised)", "IN PROGRESS"), "2026-10-21"
    )
    assert len(out["items"]) == 3
    assert out["items"][1]["title"] == "Item two (revised)"
    assert out["items"][1]["status"] == "IN PROGRESS"
    assert header_line(out) == (
        "**Queue:** B1, B2 | **In progress:** B1, B2 | **Done:** B3 | **Updated:** 2026-10-21"
    )


def test_upsert_appended_id_below_max_raises_schema_error() -> None:
    store = backlog_store()
    bad = item("B0")
    with pytest.raises(SchemaError, match="strictly increasing: B0 after B3"):
        upsert_backlog_item(store, bad, "2026-10-20")


def test_upsert_bad_id_shape_raises_schema_error() -> None:
    store = backlog_store()
    bad = item("X9")
    with pytest.raises(SchemaError, match="must be B<digits>"):
        upsert_backlog_item(store, bad, "2026-10-20")


def test_upsert_bad_status_raises_schema_error() -> None:
    store = backlog_store()
    bad = item("B4", "Item four", "BOGUS")
    with pytest.raises(SchemaError, match="items\\[3\\].status must be one of:"):
        upsert_backlog_item(store, bad, "2026-10-20")


def test_upsert_malformed_item_raises_invalid_input() -> None:
    store = backlog_store()
    bad = {"id": "B4", "title": "no fields"}
    with pytest.raises(InvalidInput, match="item"):
        upsert_backlog_item(store, bad, "2026-10-20")


def test_upsert_result_passes_validate_store() -> None:
    out = upsert_backlog_item(backlog_store(), item(), "2026-10-21")
    from securetrace.docs.schema import validate_store

    assert validate_store(out) is None


# --------------------------------------------------------------------- append_backlog_progress


def test_progress_appends_to_existing_field() -> None:
    store = backlog_store()
    store["items"][0]["fields"].append({"name": "Progress", "lines": ["  - 2026-10-20 — started"]})
    frozen = copy.deepcopy(store)
    line = "  - 2026-10-21 — step done"
    out = append_backlog_progress(store, "B1", line, "2026-10-21")
    progress = out["items"][0]["fields"][1]
    assert progress["name"] == "Progress"
    assert progress["lines"] == ["  - 2026-10-20 — started", line]
    assert out["updated"] == "2026-10-21"
    assert store == frozen, "input store must not be mutated"


def test_progress_creates_field_at_end_when_absent() -> None:
    out = append_backlog_progress(backlog_store(), "B3", "  - 2026-10-21 — closed", "2026-10-21")
    fields = out["items"][2]["fields"]
    assert fields[-1] == {"name": "Progress", "lines": ["  - 2026-10-21 — closed"]}
    assert len(fields) == 2  # Source + new Progress


def test_progress_unknown_item_raises_invalid_input() -> None:
    store = backlog_store()
    with pytest.raises(InvalidInput, match="B99"):
        append_backlog_progress(store, "B99", "  - 2026-10-21 — x", "2026-10-21")


# --------------------------------------------------------------------- add_lesson


def test_add_assigns_next_id_when_omitted() -> None:
    out = add_lesson(lessons_store(1), {"title": "New lesson", "fields": lesson(2)["fields"]})
    assert [l["id"] for l in out["lessons"]] == ["LLT-0001", "LLT-0002"]
    assert out["lessons"][-1]["title"] == "New lesson"


def test_add_explicit_id_is_honored() -> None:
    new = {"id": "LLT-0002", "title": "New lesson", "fields": lesson(2)["fields"]}
    out = add_lesson(lessons_store(1), new)
    assert [l["id"] for l in out["lessons"]] == ["LLT-0001", "LLT-0002"]


def test_add_duplicate_id_raises_schema_error() -> None:
    new = {"id": "LLT-0001", "title": "New lesson", "fields": lesson(2)["fields"]}
    store = lessons_store(1)
    with pytest.raises(SchemaError, match="duplicate lesson id: LLT-0001"):
        add_lesson(store, new)


def test_add_id_below_max_raises_schema_error() -> None:
    new = {"id": "LLT-0002", "title": "New lesson", "fields": lesson(2)["fields"]}
    store = lessons_store(5)
    with pytest.raises(SchemaError, match="strictly increasing: LLT-0002 after LLT-0005"):
        add_lesson(store, new)


def test_add_supersedes_flips_target_to_superseded() -> None:
    fields = [dict(f) for f in lesson(3)["fields"]]
    for field in fields:
        if field["name"] == "Supersedes":
            field["value"] = "LLT-0002"
    out = add_lesson(lessons_store(1, 2), {"title": "New lesson", "fields": fields})
    assert [l["id"] for l in out["lessons"]] == ["LLT-0001", "LLT-0002", "LLT-0003"]
    by_id = {l["id"]: l for l in out["lessons"]}
    assert by_id["LLT-0002"]["fields"][3]["value"] == "superseded"  # Status field
    assert by_id["LLT-0003"]["fields"][3]["value"] == "active"
    assert by_id["LLT-0001"]["fields"][3]["value"] == "active"


def test_add_supersedes_missing_target_raises_invalid_input() -> None:
    fields = [dict(f) for f in lesson(2)["fields"]]
    for field in fields:
        if field["name"] == "Supersedes":
            field["value"] = "LLT-0099"
    store = lessons_store(1)
    new = {"title": "New lesson", "fields": fields}
    with pytest.raises(InvalidInput, match="LLT-0099"):
        add_lesson(store, new)


def test_add_supersedes_already_superseded_raises_invalid_input() -> None:
    store = lessons_store(1, 2)
    for field in store["lessons"][1]["fields"]:
        if field["name"] == "Status":
            field["value"] = "superseded"
    fields = [dict(f) for f in lesson(3)["fields"]]
    for field in fields:
        if field["name"] == "Supersedes":
            field["value"] = "LLT-0002"
    new = {"title": "New lesson", "fields": fields}
    with pytest.raises(InvalidInput, match="not active"):
        add_lesson(store, new)


def test_add_forces_new_lesson_status_active() -> None:
    fields = [dict(f) for f in lesson(2)["fields"]]
    for field in fields:
        if field["name"] == "Status":
            field["value"] = "superseded"
    out = add_lesson(lessons_store(1), {"title": "New lesson", "fields": fields})
    assert out["lessons"][-1]["fields"][3]["value"] == "active"


def test_add_bad_category_raises_schema_error() -> None:
    fields = [dict(f) for f in lesson(2)["fields"]]
    for field in fields:
        if field["name"] == "Category":
            field["value"] = "banana"
    store = lessons_store(1)
    new = {"title": "New lesson", "fields": fields}
    with pytest.raises(SchemaError, match="lessons\\[1\\].Category must be one of:"):
        add_lesson(store, new)


def test_add_input_not_mutated() -> None:
    store = lessons_store(1)
    new = {"title": "New lesson", "fields": [dict(f) for f in lesson(2)["fields"]]}
    frozen_store = copy.deepcopy(store)
    frozen_new = copy.deepcopy(new)
    add_lesson(store, new)
    assert store == frozen_store
    assert new == frozen_new


# --------------------------------------------------------------------- set_lessons_intro (D15)


def test_set_intro_replaces_intro_lines_and_keeps_lessons() -> None:
    store = lessons_store(1)
    out = set_lessons_intro(store, ["New intro line one.", "New intro line two."])
    assert out is not store
    assert out["intro"] == ["New intro line one.", "New intro line two."]
    assert out["lessons"] == store["lessons"]
    assert store["intro"] == ["Intro one.", "Intro two."]  # input store unmutated


def test_set_intro_result_passes_validate_store() -> None:
    out = set_lessons_intro(lessons_store(1), ["Single line."])
    from securetrace.docs.schema import validate_store

    assert validate_store(out) is None


@pytest.mark.parametrize(
    "bad_intro",
    [[], [""], ["a\tb"], ["ok", 3], "not-a-list", None],
)
def test_set_intro_rejects_bad_input(bad_intro) -> None:
    with pytest.raises(InvalidInput):
        set_lessons_intro(lessons_store(1), bad_intro)


# --------------------------------------------------------------------- upsert_registry_row


def test_upsert_row_inserts_at_slug_sorted_position() -> None:
    out = upsert_registry_row(registry_store(), row("bravo"))
    assert [r["slug"] for r in out["rows"]] == ["alpha", "bravo", "charlie"]


def test_upsert_row_replaces_existing_in_place() -> None:
    out = upsert_registry_row(registry_store(), row("alpha", summary="Revised."))
    assert [r["slug"] for r in out["rows"]] == ["alpha", "charlie"]
    assert out["rows"][0]["summary"] == "Revised."


def test_upsert_row_bad_status_raises_schema_error() -> None:
    store = registry_store()
    bad = row("bravo", status="shipped")
    with pytest.raises(SchemaError, match="status must be one of:"):
        upsert_registry_row(store, bad)


def test_upsert_row_bad_slug_raises_schema_error() -> None:
    store = registry_store()
    bad = row("bravo!")
    with pytest.raises(SchemaError, match="rows\\[1\\].slug must be kebab-case, got 'bravo!'"):
        upsert_registry_row(store, bad)


def test_upsert_row_missing_key_raises_invalid_input() -> None:
    bad = row("bravo")
    del bad["summary"]
    store = registry_store()
    with pytest.raises(InvalidInput, match="row"):
        upsert_registry_row(store, bad)


def test_upsert_row_input_not_mutated() -> None:
    store = registry_store()
    frozen = copy.deepcopy(store)
    upsert_registry_row(store, row("bravo"))
    assert store == frozen
