"""Backlog parser/renderer tests (B10 WI 4; ALRK doc T1, T2, T7, T10 + C4).

Spec: ``algorithms/deterministic-doc-pipeline.md`` — T1 (synthetic roundtrip,
sha256 stable across runs), T2 (golden roundtrip vs the real repo BACKLOG.md,
10 items), T7 (malformed store → SchemaError, exit 2 upstream), T10 (JSON key
order irrelevant), and contract C4 (the generated no-hand-edit header).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from securetrace.backlog.index import is_fresh, synced_text
from securetrace.docs import RENDERER_VERSION
from securetrace.docs.backlog_doc import parse_backlog, render_backlog
from securetrace.docs.canonical import canonical_json, sha256_hex
from securetrace.docs.schema import SCHEMA_VERSION, SchemaError
from securetrace.errors import FormatError

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_BACKLOG = REPO_ROOT / "BACKLOG.md"

STATUS_LINE = "**Queue:** B1 | **In progress:** B1 | **Done:** — | **Updated:** 2026-10-20"


def store_t1() -> dict:
    """The one-item backlog store of ALRK doc T1 (B1, 2 progress lines, 3-line closeout)."""
    return {
        "doc": "backlog",
        "schema_version": SCHEMA_VERSION,
        "updated": "2026-10-20",
        "header": ["Tracks all SecureTrace work.", "", STATUS_LINE],
        "queue": ["**B1** (synthetic item)"],
        "items": [
            {
                "id": "B1",
                "title": "Synthetic item",
                "status": "IN PROGRESS",
                "fields": [
                    {"name": "Source", "lines": ["user"]},
                    {
                        "name": "Progress",
                        "lines": ["  - 2026-10-20 — started", "  - 2026-10-20 — step done"],
                    },
                    {
                        "name": "Closeout",
                        "lines": [
                            "  - 2026-10-20 — gate green (219 tests)",
                            "  - 2026-10-20 — CI green (SonarCloud/quality/security)",
                            "  - 2026-10-20 — closed with evidence",
                        ],
                    },
                ],
            }
        ],
        "constraints": ["- gate green"],
    }


def strip_generated_header(text: str) -> str:
    """Drop the generated header block (and its following separator blank line)."""
    lines = text.split("\n")
    begin = next(i for i, line in enumerate(lines) if line.startswith("<!-- GENERATED:BEGIN"))
    end = next(i for i in range(begin, len(lines)) if lines[i].startswith("<!-- GENERATED:END"))
    del lines[begin : end + 1]
    if begin < len(lines) and lines[begin] == "":
        del lines[begin]
    return "\n".join(lines)


def shift_index_numbers(text: str, delta: int) -> str:
    """Add *delta* to the start/end line-number cells of the TSV index block."""
    lines = text.split("\n")
    begin = next(i for i, line in enumerate(lines) if line.startswith("<!-- INDEX:BEGIN"))
    end = next(i for i in range(begin, len(lines)) if lines[i].startswith("<!-- INDEX:END"))
    for i in range(begin + 1, end):
        cells = lines[i].split("\t")
        if len(cells) == 6 and cells[4].isdigit() and cells[5].isdigit():
            cells[4] = str(int(cells[4]) + delta)
            cells[5] = str(int(cells[5]) + delta)
            lines[i] = "\t".join(cells)
    return "\n".join(lines)


# --------------------------------------------------------------------- T1 / C1 / C2


def test_roundtrip_synthetic_is_identity():
    """T1: parse ∘ render = identity on the T1 store (C2)."""
    store = store_t1()
    rendered = render_backlog(store)
    assert parse_backlog(rendered) == store
    assert render_backlog(parse_backlog(rendered)) == rendered


def test_render_is_pure_and_deterministic():
    """C1: two renders of the same data are byte-identical (no clock, no env)."""
    store = store_t1()
    copy = json.loads(json.dumps(store))  # independent object, same data
    assert render_backlog(store) == render_backlog(copy)
    assert sha256_hex(canonical_json(store)) == sha256_hex(canonical_json(copy))


def test_index_block_fresh_after_render():
    """The renderer emits an index block the legacy core accepts as fresh."""
    assert is_fresh(render_backlog(store_t1()))


def test_json_key_order_irrelevant_to_render():
    """T10: ordering comes from the id, never from JSON key order."""
    store = store_t1()
    reordered = {
        "updated": store["updated"],
        "queue": store["queue"],
        "items": store["items"],
        "header": store["header"],
        "constraints": store["constraints"],
        "schema_version": store["schema_version"],
        "doc": store["doc"],
    }
    assert canonical_json(store) == canonical_json(reordered)
    assert render_backlog(store) == render_backlog(reordered)


@pytest.mark.parametrize(
    "field_lines",
    [
        [],
        ["value"],
        ["  cont"],
        ["v1", "  c1", "  c2"],
        ["", "x"],
    ],
    ids=["empty", "inline", "indented", "inline-plus-continuations", "blank-then-line"],
)
def test_field_line_variants_roundtrip(field_lines):
    """Every field-line shape the renderer can emit parses back losslessly."""
    store = store_t1()
    store["items"][0]["fields"] = [{"name": "F", "lines": field_lines}]
    rendered = render_backlog(store)
    assert parse_backlog(rendered)["items"][0]["fields"] == [{"name": "F", "lines": field_lines}]


# --------------------------------------------------------------------- C4 (header)


def test_generated_header_contract():
    """C4: the rendered doc carries the 7-line no-hand-edit generated header."""
    lines = render_backlog(store_t1()).splitlines()
    assert lines[0] == "# Backlog"
    assert lines[1] == ""
    block = lines[2:9]
    assert len(block) == 7
    assert all(line.startswith("<!--") and line.endswith("-->") for line in block)
    joined = "\n".join(block)
    assert "DO NOT EDIT" in joined
    assert "manual editing is not permitted" in joined
    assert "data/backlog.json" in joined
    assert "securetrace backlog render data/backlog.json" in joined
    assert "securetrace backlog check data/backlog.json" in joined
    assert RENDERER_VERSION in joined
    assert lines[9] == ""
    assert lines[10].startswith("<!-- INDEX:BEGIN")


# --------------------------------------------------------------------- T2 (golden)


def test_roundtrip_real_backlog_golden():
    """T2: parse → render reproduces the committed BACKLOG.md (modulo header).

    The rendered doc's TSV line numbers describe the *rendered* layout
    (is_fresh must hold on the file that exists), so the only differences
    from the grandfathered committed file are the generated header block and
    the TSV numbers it shifts. Strip the block, shift the numbers back, and
    the bytes must be identical (10/10 items, all fields lossless).
    """
    real = REAL_BACKLOG.read_text(encoding="utf-8")
    store = parse_backlog(real)
    assert [item["id"] for item in store["items"]] == [f"B{n}" for n in range(1, 11)]
    assert store["updated"] == "2026-10-21"
    rendered = render_backlog(store)

    def index_begin(text: str) -> int:
        return next(
            i for i, line in enumerate(text.split("\n")) if line.startswith("<!-- INDEX:BEGIN")
        )

    offset = index_begin(rendered) - index_begin(real)
    assert offset == 8  # 7 generated header lines + 1 separator blank line
    assert shift_index_numbers(strip_generated_header(rendered), -offset) == real


def test_parse_real_backlog_b10_shape():
    """The live B10 item parses into its 12 fields, IN PROGRESS.

    The Progress count is live data — it grows with each WI closeout
    (4 at WI 4 time); byte-exact losslessness is pinned by the T2 golden,
    so this test pins the stable shape (field names, status) plus a floor
    and anchor on the progress list.
    """
    store = parse_backlog(REAL_BACKLOG.read_text(encoding="utf-8"))
    b10 = store["items"][9]
    assert b10["status"] == "IN PROGRESS"
    assert [f["name"] for f in b10["fields"]] == [
        "Source",
        "Requested",
        "Priority",
        "Request (verbatim)",
        "Problem / evidence",
        "Chosen approach",
        "Scope decision (recorded)",
        "Work items (in order)",
        "Blast radius",
        "Acceptance criteria",
        "Ordering",
        "Progress",
    ]
    progress = next(f for f in b10["fields"] if f["name"] == "Progress")
    assert len(progress["lines"]) >= 4  # WI 1–4 closeouts; grows with the record
    assert progress["lines"][0].startswith("  - 2026-10-20 — status → IN PROGRESS")


# --------------------------------------------------------------------- T7 (malformed store)


def test_render_rejects_duplicate_item_id():
    """T7: a malformed store is rejected before any render (exit 2 upstream)."""
    store = store_t1()
    store["items"].append(dict(store["items"][0]))
    with pytest.raises(SchemaError, match="duplicate"):
        render_backlog(store)


def test_render_rejects_updated_mismatch():
    store = dict(store_t1(), updated="2026-01-01")
    with pytest.raises(SchemaError, match="updated"):
        render_backlog(store)


# --------------------------------------------------------------------- parse rejections


def test_parse_rejects_stale_index():
    real = REAL_BACKLOG.read_text(encoding="utf-8")
    tampered = real.rstrip("\n") + "\n- a hand-added constraint\n"
    with pytest.raises(FormatError, match="[Ii]ndex"):
        parse_backlog(tampered)


def test_parse_rejects_wrong_title():
    real = REAL_BACKLOG.read_text(encoding="utf-8")
    with pytest.raises(FormatError, match="title"):
        parse_backlog("# Not A Backlog\n" + real.split("\n", 1)[1])


def test_parse_rejects_missing_constraints_marker():
    real = REAL_BACKLOG.read_text(encoding="utf-8")
    lines = real.split("\n")
    marker = next(i for i, line in enumerate(lines) if line.strip() == "<!-- BACKLOG:CONSTRAINTS -->")
    del lines[marker : marker + 3]  # marker + heading + separator blank; keep the constraint lines
    with pytest.raises(FormatError, match="CONSTRAINTS"):
        parse_backlog("\n".join(lines))


def test_parse_rejects_missing_updated_line():
    doc = render_backlog(store_t1())
    lines = doc.split("\n")
    i = next(k for k, line in enumerate(lines) if line.startswith("**Queue:**"))
    lines[i] = lines[i].replace(" | **Updated:** 2026-10-20", "")
    text = synced_text("\n".join(lines))  # re-sync the index so the Updated check is what fires
    with pytest.raises(FormatError, match="Updated"):
        parse_backlog(text)
