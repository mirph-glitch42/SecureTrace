"""Registry parser/renderer tests (B10 WI 6; ALRK doc T4 + C1–C5).

Spec: ``algorithms/deterministic-doc-pipeline.md`` — T4 (golden roundtrip vs
the real repo ``algorithms/INDEX.md``; the row count is derived from the live
file, never hardcoded), plus C1 (determinism), C2 (lossless roundtrip),
C4 (the generated no-hand-edit header), and T10 (JSON key order irrelevant).

The registry doc is a markdown table (not a TSV-indexed doc): title, blank,
the generated header, blank, the intro blockquote lines, blank, the fixed
6-column table, blank, ``## Rules`` with strictly 1..N numbered rule lines.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from securetrace.docs import RENDERER_VERSION
from securetrace.docs.canonical import canonical_json, sha256_hex
from securetrace.docs.registry_doc import parse_registry, render_registry
from securetrace.docs.schema import SCHEMA_VERSION, SchemaError
from securetrace.errors import FormatError

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_REGISTRY = REPO_ROOT / "algorithms" / "INDEX.md"


def row(slug: str, name: str, version: str, status: str, file: str, summary: str) -> dict:
    return {
        "slug": slug,
        "name": name,
        "version": version,
        "status": status,
        "file": file,
        "summary": summary,
    }


def store_t4() -> dict:
    """The two-row store of T4 (slug-sorted; all six cells filled)."""
    return {
        "doc": "registry",
        "schema_version": SCHEMA_VERSION,
        "intro": [
            "> One row per algorithm document in this directory. Keep sorted by slug.",
            "> Update the row in the **same change** that changes the document (G8/G9).",
        ],
        "rows": [
            row(
                "alpha-pipeline",
                "Alpha Pipeline (synthetic)",
                "0.1.0",
                "draft",
                "alpha-pipeline.md",
                "A synthetic row.",
            ),
            row(
                "zeta-pipeline",
                "Zeta Pipeline (synthetic)",
                "1.2.3",
                "backfilled",
                "zeta-pipeline.md",
                "Another synthetic row.",
            ),
        ],
        "rules": [
            "Add a row when a document is created; never delete a row (mark `deprecated` instead).",
            "The `File` link is the canonical location — no copies elsewhere in the repo.",
        ],
    }


def rendered_t4() -> str:
    return render_registry(store_t4())


def strip_generated_header(text: str) -> str:
    """Drop the generated header block (and its following separator blank line)."""
    lines = text.split("\n")
    begin = next(i for i, line in enumerate(lines) if line.startswith("<!-- GENERATED:BEGIN"))
    end = next(i for i in range(begin, len(lines)) if lines[i].startswith("<!-- GENERATED:END"))
    del lines[begin : end + 1]
    if begin < len(lines) and lines[begin] == "":
        del lines[begin]
    return "\n".join(lines)


# --------------------------------------------------------------------- C1 / C2 / T10


def test_roundtrip_synthetic_is_identity():
    """C2: parse ∘ render = identity on the T4 store (both directions)."""
    store = store_t4()
    rendered = render_registry(store)
    assert parse_registry(rendered) == store
    assert render_registry(parse_registry(rendered)) == rendered


def test_render_is_pure_and_deterministic():
    """C1: two renders of the same data are byte-identical (no clock, no env)."""
    store = store_t4()
    copy = json.loads(json.dumps(store))  # independent object, same data
    assert render_registry(store) == render_registry(copy)
    assert sha256_hex(canonical_json(store)) == sha256_hex(canonical_json(copy))


def test_json_key_order_irrelevant_to_render():
    """T10: ordering comes from the slug sort, never from JSON key order."""
    store = store_t4()
    reordered = {
        "rows": store["rows"],
        "rules": store["rules"],
        "intro": store["intro"],
        "schema_version": store["schema_version"],
        "doc": store["doc"],
    }
    assert canonical_json(store) == canonical_json(reordered)
    assert render_registry(store) == render_registry(reordered)


# --------------------------------------------------------------------- C4 (header)


def test_generated_header_contract():
    """C4: the rendered doc carries the 7-line no-hand-edit generated header."""
    lines = render_registry(store_t4()).splitlines()
    assert lines[0] == "# Algorithm Registry"
    assert lines[1] == ""
    block = lines[2:9]
    assert len(block) == 7
    assert all(line.startswith("<!--") and line.endswith("-->") for line in block)
    joined = "\n".join(block)
    assert "DO NOT EDIT" in joined
    assert "manual editing is not permitted" in joined
    assert "data/algorithms.json" in joined
    assert "securetrace algorithms render data/algorithms.json" in joined
    assert "securetrace algorithms check data/algorithms.json" in joined
    assert RENDERER_VERSION in joined
    assert lines[9] == ""
    assert lines[10] == store_t4()["intro"][0]  # the intro prose follows the header


# --------------------------------------------------------------------- T4 (golden)


def test_roundtrip_real_registry_golden():
    """T4: parse → render reproduces the committed algorithms/INDEX.md.

    The registry doc has no TSV index block, so the only difference from the
    grandfathered committed file is the generated header block (7 lines + its
    separator blank line). Strip the block and the bytes must be identical —
    N/N rows lossless, N derived from the live file, never hardcoded.
    """
    real = REAL_REGISTRY.read_text(encoding="utf-8")
    store = parse_registry(real)
    n = len(store["rows"])
    assert n >= 1
    assert [r["slug"] for r in store["rows"]] == sorted(r["slug"] for r in store["rows"])
    rendered = render_registry(store)
    rendered_lines = rendered.split("\n")
    real_lines = real.split("\n")
    assert rendered_lines[2].startswith("<!-- GENERATED:BEGIN")
    assert rendered_lines[8].startswith("<!-- GENERATED:END")
    assert rendered_lines[9] == ""
    assert rendered_lines[:2] == real_lines[:2]
    assert rendered_lines[10:] == real_lines[2:]
    assert strip_generated_header(rendered) == real


def test_parse_real_registry_shape():
    """The live registry parses into well-formed rows (stable shape pins).

    The row count is live data (the registry grows with B10); byte-exact
    losslessness is pinned by the T4 golden, so this test pins the stable
    shape: all six cells, slug-sorted order, closed status vocabulary,
    and non-empty intro and rules.
    """
    store = parse_registry(REAL_REGISTRY.read_text(encoding="utf-8"))
    assert store["doc"] == "registry"
    assert store["schema_version"] == SCHEMA_VERSION
    assert len(store["intro"]) >= 3
    assert len(store["rules"]) >= 5
    for r in store["rows"]:
        assert set(r) == {"slug", "name", "version", "status", "file", "summary"}
        assert r["slug"] == Path(r["file"]).stem
        assert r["status"] in ("draft", "implemented", "backfilled", "deprecated")


# --------------------------------------------------------------------- render rejections (T7)


def test_render_rejects_duplicate_slug():
    """T7: a malformed store is rejected before any render (exit 2 upstream)."""
    store = store_t4()
    store["rows"].append(dict(store["rows"][0]))
    with pytest.raises(SchemaError, match="duplicate"):
        render_registry(store)


def test_render_rejects_unsorted_rows():
    store = store_t4()
    store["rows"].reverse()
    with pytest.raises(SchemaError, match="sorted by slug"):
        render_registry(store)


def test_render_rejects_bad_status():
    store = store_t4()
    store["rows"][0]["status"] = "vibes"
    with pytest.raises(SchemaError, match="status"):
        render_registry(store)


# --------------------------------------------------------------------- parse rejections


def test_parse_rejects_wrong_title():
    base = rendered_t4()
    text = "# Not Registry\n" + base.split("\n", 1)[1]
    with pytest.raises(FormatError, match="title"):
        parse_registry(text)


def test_parse_rejects_missing_table_header():
    lines = rendered_t4().split("\n")
    i = next(k for k, line in enumerate(lines) if line.startswith("| Slug |"))
    del lines[i]
    text = "\n".join(lines)
    with pytest.raises(FormatError, match="table header"):
        parse_registry(text)


def test_parse_rejects_missing_rules_heading():
    lines = rendered_t4().split("\n")
    i = next(k for k, line in enumerate(lines) if line == "## Rules")
    lines[i] = "## Other"
    text = "\n".join(lines)
    with pytest.raises(FormatError, match="Rules"):
        parse_registry(text)


def test_parse_rejects_bad_status_cell():
    base = rendered_t4()
    text = base.replace("`draft`", "`vibes`", 1)
    assert text != base
    with pytest.raises(FormatError, match="Status"):
        parse_registry(text)


def test_parse_rejects_bad_version_cell():
    base = rendered_t4()
    text = base.replace("| 0.1.0 |", "| 1.0 |", 1)
    assert text != base
    with pytest.raises(FormatError, match="Version"):
        parse_registry(text)


def test_parse_rejects_pipe_inside_cell():
    base = rendered_t4()
    text = base.replace("Alpha Pipeline (synthetic)", "Alpha | Pipeline (synthetic)", 1)
    assert text != base
    with pytest.raises(FormatError, match="cells"):
        parse_registry(text)


def test_parse_rejects_link_text_target_mismatch():
    base = rendered_t4()
    text = base.replace(
        "[alpha-pipeline.md](alpha-pipeline.md)", "[other.md](alpha-pipeline.md)", 1
    )
    assert text != base
    with pytest.raises(FormatError, match="File"):
        parse_registry(text)


def test_parse_rejects_bad_rule_numbering():
    base = rendered_t4()
    text = base.replace("\n2. The `File` link", "\n3. The `File` link", 1)
    assert text != base
    with pytest.raises(FormatError, match="rule"):
        parse_registry(text)


def test_parse_rejects_duplicate_slug():
    base = rendered_t4()
    text = base.replace("| `zeta-pipeline` |", "| `alpha-pipeline` |", 1)
    assert text != base
    with pytest.raises(SchemaError, match="duplicate"):
        parse_registry(text)


def test_parse_rejects_unsorted_rows():
    lines = rendered_t4().split("\n")
    a = next(k for k, line in enumerate(lines) if line.startswith("| `alpha-pipeline`"))
    b = next(k for k, line in enumerate(lines) if line.startswith("| `zeta-pipeline`"))
    lines[a], lines[b] = lines[b], lines[a]
    text = "\n".join(lines)
    with pytest.raises(SchemaError, match="sorted"):
        parse_registry(text)
