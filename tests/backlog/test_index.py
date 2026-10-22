"""Behavioral tests for ``securetrace.backlog.index`` (the pure core).

These pin the exact contract of the pinned ``scripts/backlog_index.py``
implementation (spec: ``algorithms/line-index-sync.md`` §6, cases P1–P13),
including the intentional priority-parsing quirks, both preserved on
purpose — fixing either is a separate, doc-first change (deferred out of
B3):

- DEV(7), LLT-0009: bulleted ``- **Priority:** X`` lines are never parsed,
  so such items index as ``Low`` and an out-of-vocabulary bulleted value is
  never rejected.
- DEV(8), LLT-0012: the scan window ``lines[start-1 : stop-1]`` (0-indexed)
  excludes the section's last line — the file's last line for the final
  section — so a heading or priority on that line is never parsed; an
  out-of-vocabulary value there is not rejected.

The pure core works on plain text and raises ``FormatError`` (exit 2);
file I/O, messages, and exit codes live in ``securetrace.cli_docs`` (document
verbs) and ``securetrace.cli`` (RMF) and are tested in ``tests/test_cli_docs.py``
and ``tests/test_cli.py``.
"""

from __future__ import annotations

import pytest

from securetrace.backlog import index
from securetrace.errors import FormatError

FIXTURE = """\
# Backlog

<!-- INDEX:BEGIN format=tsv version=1 -->
<!-- placeholder interior line -->
<!-- INDEX:END -->

<!-- BACKLOG:HEADER -->
## Status

**Queue:** B1 | **In progress:** — | **Done:** — | **Updated:** 2026-10-18

<!-- BACKLOG:QUEUE -->
## Queue (execution order)

1. **B1** (High) — bootstrap the project

<!-- BACKLOG:ITEM:B1 -->
## B1. Bootstrap — **OPEN**

- **Source:** user
- **Priority:** High
- **Acceptance criteria:** gates green

<!-- BACKLOG:CONSTRAINTS -->
## Standing constraints

- no bypassing gates
"""

# Minimal valid backlog: one item, bulleted priority (the common form).
SINGLE = """\
# Backlog

<!-- INDEX:BEGIN -->
<!-- placeholder -->
<!-- INDEX:END -->

<!-- BACKLOG:ITEM:B1 -->
## B1. Work — **OPEN**

- **Priority:** High
"""


# --- model -----------------------------------------------------------------


def test_row_dataclass_fields() -> None:
    row = index.Row(id="B1", title="Work", status="OPEN", priority="Low", start_line=9, end_line=12)
    assert row.id == "B1"
    assert row.title == "Work"
    assert row.status == "OPEN"
    assert row.priority == "Low"
    assert row.start_line == 9
    assert row.end_line == 12


def test_section_dataclass_fields() -> None:
    section = index.Section(row_id="B1", start_line=7, is_item=True)
    assert section.row_id == "B1"
    assert section.start_line == 7
    assert section.is_item is True


def test_constants_match_pinned_contract() -> None:
    assert index.TSV_HEADER == "id\ttitle\tstatus\tpriority\tstart_line\tend_line"
    assert index.RESERVED == ("HEADER", "QUEUE", "CONSTRAINTS")
    assert index.DEFAULT_PRIORITY == "Low"
    assert index.PRIORITY_MAP == {"HIGH": "High", "MEDIUM": "Medium", "LOW": "Low"}


# --- P1/P11: happy path, geometry, idempotence ------------------------------


def test_index_rows_geometry() -> None:
    rows = index.index_rows(FIXTURE)
    assert [r.id for r in rows] == ["INDEX_BLOCK", "HEADER", "QUEUE", "B1", "CONSTRAINTS"]
    assert rows[0] == index.Row("INDEX_BLOCK", "-", "-", "-", 3, 10)
    assert rows[1] == index.Row("HEADER", "-", "-", "-", 12, 16)
    assert rows[2] == index.Row("QUEUE", "-", "-", "-", 17, 21)
    # B1 priority is Low: the bulleted form never matches PRIORITY_RE (DEV(7)).
    assert rows[3] == index.Row("B1", "Bootstrap", "OPEN", "Low", 22, 28)
    assert rows[4] == index.Row("CONSTRAINTS", "-", "-", "-", 29, 32)


def test_synced_text_block_content() -> None:
    once = index.synced_text(FIXTURE)
    lines = once.split("\n")
    assert len(lines) == 33  # 32 lines + trailing "" from the final newline
    assert lines[3] == index.TSV_HEADER
    assert lines[4] == "INDEX_BLOCK\t-\t-\t-\t3\t10"
    assert lines[5] == "HEADER\t-\t-\t-\t12\t16"
    assert lines[6] == "QUEUE\t-\t-\t-\t17\t21"
    assert lines[7] == "B1\tBootstrap\tOPEN\tLow\t22\t28"
    assert lines[8] == "CONSTRAINTS\t-\t-\t-\t29\t32"
    assert lines[9] == "<!-- INDEX:END -->"


def test_single_item_rows() -> None:
    rows = index.index_rows(SINGLE)
    assert len(rows) == 2
    assert rows[1] == index.Row("B1", "Work", "OPEN", "Low", 9, 12)


def test_sync_is_idempotent() -> None:
    once = index.synced_text(FIXTURE)
    assert index.synced_text(once) == once


# --- P2: staleness ----------------------------------------------------------


def test_placeholder_interior_is_stale() -> None:
    assert not index.is_fresh(FIXTURE)
    assert index.is_fresh(index.synced_text(FIXTURE))


def test_body_edit_makes_index_stale() -> None:
    once = index.synced_text(FIXTURE)
    stale = once + "extra progress line\n"
    assert not index.is_fresh(stale)
    assert index.is_fresh(index.synced_text(stale))


# --- P3–P8: structural guards ------------------------------------------------


def test_missing_markers_rejected() -> None:
    with pytest.raises(
        FormatError, match="missing <!-- INDEX:BEGIN --> / <!-- INDEX:END --> markers"
    ):
        index.index_rows("# Backlog\n\nno markers at all\n")


def test_empty_index_block_rejected() -> None:
    text = (
        "# B\n\n"
        "<!-- INDEX:BEGIN -->\n"
        "<!-- INDEX:END -->\n"
        "\n"
        "<!-- BACKLOG:ITEM:B1 -->\n"
        "## B1. Work — **OPEN**\n"
    )
    with pytest.raises(FormatError, match="index block is empty or malformed"):
        index.index_rows(text)


def test_marker_inside_index_block_rejected() -> None:
    text = (
        "# B\n\n"
        "<!-- INDEX:BEGIN -->\n"
        "<!-- BACKLOG:HEADER -->\n"
        "<!-- INDEX:END -->\n"
        "\n"
        "<!-- BACKLOG:ITEM:B1 -->\n"
        "## B1. Work — **OPEN**\n"
    )
    with pytest.raises(FormatError, match="marker at line 4 is at or inside the index block"):
        index.index_rows(text)


def test_no_item_markers_rejected() -> None:
    text = (
        "# B\n\n"
        "<!-- INDEX:BEGIN -->\n"
        "placeholder\n"
        "<!-- INDEX:END -->\n"
        "\n"
        "<!-- BACKLOG:HEADER -->\n"
        "## Status\n"
        "\n"
        "<!-- BACKLOG:QUEUE -->\n"
        "## Queue\n"
    )
    with pytest.raises(FormatError, match="no <!-- BACKLOG:ITEM:<ID> --> markers found"):
        index.index_rows(text)


def test_reserved_item_id_rejected() -> None:
    text = (
        "# B\n\n"
        "<!-- INDEX:BEGIN -->\n"
        "placeholder\n"
        "<!-- INDEX:END -->\n"
        "\n"
        "<!-- BACKLOG:ITEM:HEADER -->\n"
        "## HEADER. Work — **OPEN**\n"
    )
    with pytest.raises(FormatError, match="item id HEADER is reserved for a section name"):
        index.index_rows(text)


def test_duplicate_section_marker_rejected() -> None:
    text = (
        "# B\n\n"
        "<!-- INDEX:BEGIN -->\n"
        "placeholder\n"
        "<!-- INDEX:END -->\n"
        "\n"
        "<!-- BACKLOG:QUEUE -->\n"
        "## Q\n"
        "\n"
        "<!-- BACKLOG:QUEUE -->\n"
        "## Q again\n"
        "\n"
        "<!-- BACKLOG:ITEM:B1 -->\n"
        "## B1. Work — **OPEN**\n"
    )
    with pytest.raises(FormatError, match="duplicate section marker: QUEUE"):
        index.index_rows(text)


def test_second_index_pair_is_stale_but_not_an_error() -> None:
    once = index.synced_text(FIXTURE)
    twice = once + "\n<!-- INDEX:BEGIN -->\nextra interior\n<!-- INDEX:END -->\n"
    # DEV(3): not an error, and not inert — the body text shifts the last row's end.
    assert not index.is_fresh(twice)
    resynced = index.synced_text(twice)
    assert index.is_fresh(resynced)
    assert "extra interior" in resynced


# --- P9: priority quirk (LLT-0009) and vocabulary ----------------------------


def test_bulleted_priority_is_ignored_quirk() -> None:
    # P9a: `- **Priority:** High` never matches PRIORITY_RE -> row priority Low.
    assert index.index_rows(SINGLE)[1].priority == "Low"


def test_unbulleted_priority_out_of_vocabulary_rejected() -> None:
    # DEV(8): the scan window excludes the file's last line, so the priority
    # line must not be the file's last line for the guard to see it.
    text = SINGLE.replace("- **Priority:** High", "**Priority:** Urgent\n\nbody line")
    with pytest.raises(FormatError, match="priority 'Urgent' is not one of High, Medium, Low"):
        index.index_rows(text)


def test_unbulleted_priority_in_vocabulary_parsed() -> None:
    text = SINGLE.replace("- **Priority:** High", "**Priority:** High\n\nbody line")
    assert index.index_rows(text)[1].priority == "High"


def test_priority_input_is_case_insensitive() -> None:
    text = SINGLE.replace("- **Priority:** High", "**Priority:** medium\n\nbody line")
    assert index.index_rows(text)[1].priority == "Medium"


def test_priority_on_final_line_not_scanned_quirk() -> None:
    # DEV(8): the pinned scan window is lines[start-1 : stop-1] (0-indexed),
    # which excludes the last line of the section — for the final section, the
    # file's last line. An unbulleted out-of-vocabulary value there is NOT
    # rejected and the row silently falls back to Low (pinned behavior).
    text = SINGLE.replace("- **Priority:** High", "**Priority:** Urgent")
    assert index.index_rows(text)[1].priority == "Low"


# --- P10/P12: headings, status, newlines -------------------------------------


def test_status_normalization_in_progress() -> None:
    text = SINGLE.replace("**OPEN**", "**IN PROGRESS**")
    assert index.index_rows(text)[1].status == "IN_PROGRESS"


def test_loose_heading_without_status() -> None:
    text = (
        "# B\n\n"
        "<!-- INDEX:BEGIN -->\n"
        "placeholder\n"
        "<!-- INDEX:END -->\n"
        "\n"
        "<!-- BACKLOG:ITEM:B1 -->\n"
        "## B1. Work\n"
        "\n"
        "body line\n"
    )
    row = index.index_rows(text)[1]
    assert row.title == "Work"
    assert row.status == "-"


def test_crlf_input_is_normalized_and_roundtrips() -> None:
    crlf = FIXTURE.replace("\n", "\r\n")
    once = index.synced_text(crlf)
    assert "\r" not in once
    assert index.is_fresh(once)
