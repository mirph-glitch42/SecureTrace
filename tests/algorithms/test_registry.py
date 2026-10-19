"""Behavioral tests for ``securetrace.algorithms.registry`` (the pure core).

These pin the exact contract of the pinned ``scripts/algorithm_index.py``
implementation (spec: ``algorithms/line-index-sync.md`` §6, cases P4 and the
shared core). The format is the same line-index core as the backlog, with
the simpler ``SECTION:<ID>`` marker model and 3-column TSV.
"""

from __future__ import annotations

import pytest

from securetrace.algorithms import registry
from securetrace.errors import FormatError

FIXTURE = """\
# Fixture Algorithm

<!-- INDEX:BEGIN format=tsv version=1 -->
<!-- placeholder interior line -->
<!-- INDEX:END -->

<!-- SECTION:METADATA -->
## 1. Metadata

| Field | Value |
|---|---|
| Name | Fixture |

<!-- SECTION:THEORY -->
## 2. Theory

Sums two numbers.

<!-- SECTION:TESTS -->
## 3. Tests

1 + 2 = 3
"""


def test_constants_match_pinned_contract() -> None:
    assert registry.TSV_HEADER == "id\tstart_line\tend_line"


# --- geometry and roundtrip (P4) --------------------------------------------


def test_index_rows_geometry() -> None:
    rows = registry.index_rows(FIXTURE)
    assert [r.id for r in rows] == ["INDEX_BLOCK", "METADATA", "THEORY", "TESTS"]
    assert rows[0] == registry.Row("INDEX_BLOCK", 3, 9)
    assert rows[1] == registry.Row("METADATA", 11, 17)
    assert rows[2] == registry.Row("THEORY", 18, 22)
    assert rows[3] == registry.Row("TESTS", 23, 26)


def test_synced_text_block_content() -> None:
    once = registry.synced_text(FIXTURE)
    lines = once.split("\n")
    assert len(lines) == 27  # 26 lines + trailing "" from the final newline
    assert lines[3] == registry.TSV_HEADER
    assert lines[4] == "INDEX_BLOCK\t3\t9"
    assert lines[5] == "METADATA\t11\t17"
    assert lines[6] == "THEORY\t18\t22"
    assert lines[7] == "TESTS\t23\t26"
    assert lines[8] == "<!-- INDEX:END -->"


def test_sync_is_idempotent() -> None:
    once = registry.synced_text(FIXTURE)
    assert registry.synced_text(once) == once


def test_placeholder_interior_is_stale() -> None:
    assert not registry.is_fresh(FIXTURE)
    assert registry.is_fresh(registry.synced_text(FIXTURE))


def test_body_edit_makes_index_stale() -> None:
    once = registry.synced_text(FIXTURE)
    stale = once + "new theory line\n"
    assert not registry.is_fresh(stale)
    assert registry.is_fresh(registry.synced_text(stale))


# --- structural guards -------------------------------------------------------


def test_missing_markers_rejected() -> None:
    with pytest.raises(FormatError, match="missing <!-- INDEX:BEGIN --> / <!-- INDEX:END --> markers"):
        registry.index_rows("# Doc\n\nno markers at all\n")


def test_empty_index_block_rejected() -> None:
    text = (
        "# D\n\n"
        "<!-- INDEX:BEGIN -->\n"
        "<!-- INDEX:END -->\n"
        "\n"
        "<!-- SECTION:THEORY -->\n"
        "## 2. Theory\n"
        "body\n"
    )
    with pytest.raises(FormatError, match="index block is empty or malformed"):
        registry.index_rows(text)


def test_duplicate_section_id_rejected() -> None:
    text = (
        "# D\n\n"
        "<!-- INDEX:BEGIN -->\n"
        "placeholder\n"
        "<!-- INDEX:END -->\n"
        "\n"
        "<!-- SECTION:THEORY -->\n"
        "## 2. Theory\n"
        "body\n"
        "\n"
        "<!-- SECTION:THEORY -->\n"
        "## 2. Theory again\n"
        "more\n"
    )
    with pytest.raises(FormatError, match="duplicate section id: THEORY"):
        registry.index_rows(text)


def test_section_inside_index_block_rejected() -> None:
    text = (
        "# D\n\n"
        "<!-- INDEX:BEGIN -->\n"
        "<!-- SECTION:METADATA -->\n"
        "<!-- INDEX:END -->\n"
        "\n"
        "<!-- SECTION:THEORY -->\n"
        "## 2. Theory\n"
        "body\n"
    )
    with pytest.raises(
        FormatError,
        match="section METADATA starts at or inside the index block",
    ):
        registry.index_rows(text)


def test_no_section_markers_rejected() -> None:
    text = (
        "# D\n\n"
        "<!-- INDEX:BEGIN -->\n"
        "placeholder\n"
        "<!-- INDEX:END -->\n"
        "\n"
        "just prose, no section markers\n"
    )
    with pytest.raises(FormatError, match="no <!-- SECTION:<ID> --> markers found"):
        registry.index_rows(text)
