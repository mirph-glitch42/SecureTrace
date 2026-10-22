"""Lessons parser/renderer tests (B10 WI 5; ALRK doc T3 + C1–C5).

Spec: ``algorithms/deterministic-doc-pipeline.md`` — T3 (golden roundtrip vs
the real repo ``LESSONS_LEARNED.md``; N lessons derived from the live file,
never a hardcoded count), plus C1 (determinism), C2 (lossless roundtrip),
C4 (the generated no-hand-edit header), and T10 (JSON key order irrelevant).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from securetrace.docs import RENDERER_VERSION
from securetrace.docs.canonical import canonical_json, sha256_hex
from securetrace.docs.lessons_doc import parse_lessons, render_lessons
from securetrace.docs.schema import SCHEMA_VERSION, SchemaError
from securetrace.errors import FormatError
from securetrace.lessons.record import ALL_FIELDS, index_is_fresh

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_LESSONS = REPO_ROOT / "LESSONS_LEARNED.md"


def lesson(i: int) -> dict:
    """One synthetic lesson with all ten fields (canonical order)."""
    return {
        "id": f"LLT-{i:04d}",
        "title": f"Synthetic lesson {i}",
        "fields": [
            {"name": "Recorded", "value": "2026-10-20"},
            {"name": "Category", "value": "tooling"},
            {"name": "Severity", "value": "medium"},
            {"name": "Status", "value": "active"},
            {"name": "Context", "value": f"context for lesson {i}"},
            {"name": "Pitfall", "value": f"pitfall for lesson {i}"},
            {"name": "Solution", "value": f"solution for lesson {i}"},
            {"name": "Supersedes", "value": "—"},
            {"name": "Prevention", "value": "—"},
            {"name": "References", "value": "—"},
        ],
    }


def store_t3() -> dict:
    """The two-lesson store of T3 (LLT-0001, LLT-0002; all fields present)."""
    return {
        "doc": "lessons",
        "schema_version": SCHEMA_VERSION,
        "intro": [
            "Authoritative record of lessons learned during the development of this system:",
            "the situation, the pitfall, and the correct solution for each lesson.",
        ],
        "lessons": [lesson(1), lesson(2)],
    }


# --------------------------------------------------------------------- T3 / C1 / C2


def test_roundtrip_synthetic_is_identity():
    """C2: parse ∘ render = identity on the T3 store (both directions)."""
    store = store_t3()
    rendered = render_lessons(store)
    assert parse_lessons(rendered) == store
    assert render_lessons(parse_lessons(rendered)) == rendered


def test_render_is_pure_and_deterministic():
    """C1: two renders of the same data are byte-identical (no clock, no env)."""
    store = store_t3()
    copy = json.loads(json.dumps(store))  # independent object, same data
    assert render_lessons(store) == render_lessons(copy)
    assert sha256_hex(canonical_json(store)) == sha256_hex(canonical_json(copy))


def test_index_block_fresh_after_render():
    """The renderer emits an index block the legacy core accepts as fresh."""
    assert index_is_fresh(render_lessons(store_t3()))


def test_json_key_order_irrelevant_to_render():
    """T10: ordering comes from the lesson ids, never from JSON key order."""
    store = store_t3()
    reordered = {
        "lessons": store["lessons"],
        "intro": store["intro"],
        "schema_version": store["schema_version"],
        "doc": store["doc"],
    }
    assert canonical_json(store) == canonical_json(reordered)
    assert render_lessons(store) == render_lessons(reordered)


@pytest.mark.parametrize(
    "value",
    [
        "—",
        "low",
        "2026-10-20",
        "a multi-word value with — em dashes and `backticks`",
    ],
    ids=["em-dash", "plain-word", "date", "multi-word"],
)
def test_field_value_variants_roundtrip(value):
    """Every value shape the renderer can emit parses back losslessly."""
    store = store_t3()
    store["lessons"][0]["fields"][6] = {"name": "Solution", "value": value}
    rendered = render_lessons(store)
    assert parse_lessons(rendered)["lessons"][0]["fields"][6] == {
        "name": "Solution",
        "value": value,
    }


# --------------------------------------------------------------------- C4 (header)


def test_generated_header_contract():
    """C4: the rendered doc carries the 7-line no-hand-edit generated header."""
    lines = render_lessons(store_t3()).splitlines()
    assert lines[0] == "# Lessons Learned"
    assert lines[1] == ""
    block = lines[2:9]
    assert len(block) == 7
    assert all(line.startswith("<!--") and line.endswith("-->") for line in block)
    joined = "\n".join(block)
    assert "DO NOT EDIT" in joined
    assert "manual editing is not permitted" in joined
    assert "data/lessons.json" in joined
    assert "securetrace lessons render data/lessons.json" in joined
    assert "securetrace lessons check data/lessons.json" in joined
    assert RENDERER_VERSION in joined
    assert lines[9] == ""
    assert lines[10] == store_t3()["intro"][0]  # the intro prose follows the header


# --------------------------------------------------------------------- T3 (golden)


def test_roundtrip_real_lessons_golden():
    """T3: parse → render reproduces the committed LESSONS_LEARNED.md byte-for-byte.

    Since the WI 9 migration the committed doc carries the generated
    no-hand-edit header, and its TSV line numbers describe the rendered
    layout (index_is_fresh must hold on the file that exists), so the
    roundtrip is exact: parse → render must equal the committed bytes
    (N/N lessons, all fields lossless; N is derived from the live file,
    never hardcoded).
    """
    real = REAL_LESSONS.read_text(encoding="utf-8")
    store = parse_lessons(real)
    n = len(store["lessons"])
    assert [l["id"] for l in store["lessons"]] == [f"LLT-{i:04d}" for i in range(1, n + 1)]
    assert render_lessons(store) == real


def test_parse_real_lessons_shape():
    """The live record parses into well-formed lessons (stable shape pins).

    The lesson count is live data (the record is append-only and grows);
    byte-exact losslessness is pinned by the T3 golden, so this test pins
    the stable shape: ten fields in canonical order per lesson, closed
    vocabularies, and a non-empty intro.
    """
    store = parse_lessons(REAL_LESSONS.read_text(encoding="utf-8"))
    assert store["doc"] == "lessons"
    assert store["schema_version"] == SCHEMA_VERSION
    assert len(store["intro"]) >= 3
    for lesson in store["lessons"]:
        assert [f["name"] for f in lesson["fields"]] == list(ALL_FIELDS)
        values = {f["name"]: f["value"] for f in lesson["fields"]}
        assert values["Status"] in ("active", "superseded")
        assert values["Supersedes"] == "—" or values["Supersedes"].startswith("LLT-")


# --------------------------------------------------------------------- T7 (malformed store)


def test_render_rejects_duplicate_lesson_id():
    """T7: a malformed store is rejected before any render (exit 2 upstream)."""
    store = store_t3()
    store["lessons"].append(dict(store["lessons"][0]))
    with pytest.raises(SchemaError, match="duplicate"):
        render_lessons(store)


def test_render_rejects_bad_category():
    store = store_t3()
    store["lessons"][0]["fields"][1] = {"name": "Category", "value": "vibes"}
    with pytest.raises(SchemaError, match="Category"):
        render_lessons(store)


# --------------------------------------------------------------------- parse rejections


def test_parse_rejects_stale_index():
    """A hand edit that shifts the entries leaves the stored index stale."""
    real = REAL_LESSONS.read_text(encoding="utf-8")
    lines = real.split("\n")
    body = next(i for i, line in enumerate(lines) if line.startswith("Authoritative record"))
    lines.insert(body, "a hand-added line (shifts every entry's line numbers)")
    text = "\n".join(lines)
    with pytest.raises(FormatError, match="[Ii]ndex"):
        parse_lessons(text)


def test_parse_rejects_wrong_title():
    real = REAL_LESSONS.read_text(encoding="utf-8")
    text = "# Not Lessons\n" + real.split("\n", 1)[1]
    with pytest.raises(FormatError, match="title"):
        parse_lessons(text)


def test_parse_rejects_missing_index_end():
    real = REAL_LESSONS.read_text(encoding="utf-8")
    lines = real.split("\n")
    end = next(i for i, line in enumerate(lines) if line.startswith("<!-- LLT:INDEX:END"))
    del lines[end]
    text = "\n".join(lines)
    with pytest.raises(FormatError, match="END"):
        parse_lessons(text)


def test_parse_rejects_missing_required_field():
    real = REAL_LESSONS.read_text(encoding="utf-8")
    lines = real.split("\n")
    i = next(k for k, line in enumerate(lines) if line.startswith("- **Solution:**"))
    del lines[i]
    text = "\n".join(lines)
    with pytest.raises(FormatError, match="Solution"):
        parse_lessons(text)


def test_parse_rejects_bad_category():
    real = REAL_LESSONS.read_text(encoding="utf-8")
    lines = real.split("\n")
    i = next(k for k, line in enumerate(lines) if line.startswith("- **Category:** tooling"))
    lines[i] = lines[i].replace("tooling", "vibes")
    text = "\n".join(lines)
    with pytest.raises(FormatError, match="Category"):
        parse_lessons(text)


def test_parse_rejects_duplicate_id():
    real = REAL_LESSONS.read_text(encoding="utf-8")
    tampered = real.replace(
        "<!-- LLT:ENTRY:LLT-0002 -->", "<!-- LLT:ENTRY:LLT-0001 -->", 1
    ).replace("## LLT-0002 — ", "## LLT-0001 — ", 1)
    assert tampered != real
    with pytest.raises(FormatError, match="duplicate"):
        parse_lessons(tampered)


def test_parse_rejects_empty_field_value():
    real = REAL_LESSONS.read_text(encoding="utf-8")
    lines = real.split("\n")
    i = next(k for k, line in enumerate(lines) if line.startswith("- **Severity:**"))
    lines[i] = "- **Severity:**"
    text = "\n".join(lines)
    with pytest.raises(FormatError, match="empty value"):
        parse_lessons(text)
