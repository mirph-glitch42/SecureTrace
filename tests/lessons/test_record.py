"""Behavioral tests for ``securetrace.lessons.record`` (the pure core).

These pin the exact contract of the pinned ``scripts/manage_lessons.py``
implementation (spec: ``algorithms/lessons-record.md`` §6, cases L1–L21 and
W1), including the verified quirks:

- DEV(3): ``Recorded`` is format-only (``2026-99-99`` accepted);
- DEV(4): index freshness covers the six indexed fields + line ranges, so a
  same-line body edit is NOT stale while an indexed-field change IS stale;
- DEV(7): the final entry's reported ``end_line`` overshoots by one
  (``text.split("\\n")`` trailing element), while interior entries are
  span-inclusive.

The pure core works on plain text and raises ``FormatError`` /
``InvalidInput`` (exit 2); file I/O, messages, and exit codes live in
``securetrace.cli`` and are tested in ``tests/test_cli.py``.
"""

from __future__ import annotations

import pytest

from securetrace.errors import FormatError, InvalidInput
from securetrace.lessons import record

TODAY = "2026-10-18"


def lesson(**overrides: object) -> record.NewLesson:
    kwargs: dict = {
        "title": "First lesson",
        "context": "ctx A",
        "pitfall": "pit A",
        "solution": "sol A",
        "recorded": TODAY,
    }
    kwargs.update(overrides)
    return record.NewLesson(**kwargs)  # type: ignore[arg-type]


def base_record() -> str:
    """A valid 1-lesson record (template + LLT-0001) — W1 step 2, 29 lines."""
    return record.add_lesson(record.build_template(), lesson(), today=TODAY).new_text


def two_entry_record() -> str:
    """W1 step 3: LLT-0001 superseded by LLT-0002 — 44 lines."""
    text = base_record()
    replacement = record.NewLesson(
        title="Second lesson",
        context="ctx B",
        pitfall="pit B",
        solution="sol B",
        recorded=TODAY,
        supersedes="LLT-0001",
    )
    return record.add_lesson(text, replacement, today=TODAY).new_text


def replace_after(text: str, anchor: str, old: str, new: str) -> str:
    """Surgically replace ``old`` in the part of ``text`` after ``anchor``."""
    head, sep, tail = text.partition(anchor)
    assert sep, f"anchor not found: {anchor!r}"
    assert old in tail, f"target not found after anchor: {old!r}"
    return head + sep + tail.replace(old, new, 1)


# Exception-test fixtures (Sonar S5778): an exception-test body may carry
# exactly one invocation possibly throwing an exception, so every setup
# object a flagged test passes to record.add_lesson is prebuilt here.
TEMPLATE = record.build_template()
BASE = base_record()
TWO = two_entry_record()
EMPTY_TITLE = lesson(title="")
BLANK_CONTEXT = lesson(context="   ")
TAB_SOLUTION = lesson(solution="sol\tA")
BANANA_CATEGORY = lesson(category="banana")
URGENT_SEVERITY = lesson(severity="urgent")
BAD_DATE = lesson(recorded="2026-1-1")
DUPLICATE_ID = lesson(id="LLT-0001")
BELOW_MAX_ID = lesson(id="LLT-0004")
MALFORMED_ID = lesson(id="LLT-1")
UNKNOWN_SUPERSEDES = lesson(supersedes="LLT-9999")
SUPERSEDED_TARGET = lesson(supersedes="LLT-0001")
MALFORMED_SUPERSEDES = lesson(supersedes="nope")


# --- model and constants ------------------------------------------------------


def test_entry_dataclass_fields() -> None:
    entry = record.Entry(
        id="LLT-0001",
        title="First lesson",
        fields={"Status": "active"},
        start=17,
        end=30,
    )
    assert entry.id == "LLT-0001"
    assert entry.title == "First lesson"
    assert entry.fields["Status"] == "active"
    assert entry.start == 17
    assert entry.end == 30


def test_new_lesson_defaults() -> None:
    new_lesson = record.NewLesson(title="t", context="c", pitfall="p", solution="s")
    assert new_lesson.id is None
    assert new_lesson.category == "other"
    assert new_lesson.severity == "medium"
    assert new_lesson.recorded is None
    assert new_lesson.supersedes is None
    assert new_lesson.prevention is None
    assert new_lesson.references is None


def test_constants_match_pinned_contract() -> None:
    assert record.INDEX_HEADER == (
        "id\ttitle\tcategory\tseverity\tstatus\trecorded\tstart_line\tend_line"
    )
    assert record.REQUIRED_FIELDS == (
        "Recorded",
        "Category",
        "Severity",
        "Status",
        "Context",
        "Pitfall",
        "Solution",
    )
    assert record.OPTIONAL_FIELDS == ("Supersedes", "Prevention", "References")
    assert record.CATEGORIES[-1] == "other"
    assert record.SEVERITIES == ("low", "medium", "high", "critical")
    assert record.STATUSES == ("active", "superseded")


# --- L1: template -------------------------------------------------------------


def test_template_shape() -> None:
    template = record.build_template()
    lines = template.split("\n")
    assert len(lines) == 15  # 14 lines + trailing "" from the final newline
    assert lines[10] == "<!-- LLT:INDEX:BEGIN -->"
    assert lines[11] == record.INDEX_HEADER
    assert lines[12] == "LLT_INDEX_BLOCK\t—\t—\t—\t—\t—\t11\t14"
    assert lines[13] == "<!-- LLT:INDEX:END -->"
    assert record.index_is_fresh(template)
    entries, errors = record.parse_entries(lines)
    assert entries == []
    assert errors == []
    assert record.next_id(entries) == "LLT-0001"


# --- W1: add lifecycle geometry ------------------------------------------------


def test_add_single_lesson_geometry() -> None:
    text = base_record()
    lines = text.split("\n")
    assert len(lines) == 30  # 29 lines + trailing ""
    assert lines[12] == "LLT_INDEX_BLOCK\t—\t—\t—\t—\t—\t11\t15"
    assert lines[13] == "LLT-0001\tFirst lesson\tother\tmedium\tactive\t2026-10-18\t17\t30"
    assert lines[14] == "<!-- LLT:INDEX:END -->"
    assert lines[16] == "<!-- LLT:ENTRY:LLT-0001 -->"
    assert lines[17] == "## LLT-0001 — First lesson"
    assert lines[19] == "- **Recorded:** 2026-10-18"
    assert lines[28] == "- **References:** —"
    assert record.index_is_fresh(text)


def test_add_result_carries_entry_id() -> None:
    result = record.add_lesson(record.build_template(), lesson(), today=TODAY)
    assert result.entry_id == "LLT-0001"
    assert result.new_text == base_record()


def test_add_supersedes_geometry_and_flip() -> None:
    text = two_entry_record()
    lines = text.split("\n")
    assert len(lines) == 45  # 44 lines + trailing ""
    assert lines[12] == "LLT_INDEX_BLOCK\t—\t—\t—\t—\t—\t11\t16"
    assert lines[13] == "LLT-0001\tFirst lesson\tother\tmedium\tsuperseded\t2026-10-18\t18\t31"
    assert lines[14] == "LLT-0002\tSecond lesson\tother\tmedium\tactive\t2026-10-18\t32\t45"
    assert lines[17] == "<!-- LLT:ENTRY:LLT-0001 -->"
    assert lines[23] == "- **Status:** superseded"  # exactly one flip, inside entry 1
    assert lines[31] == "<!-- LLT:ENTRY:LLT-0002 -->"
    assert lines[41] == "- **Supersedes:** LLT-0001"
    assert text.count("- **Status:** superseded") == 1
    assert record.index_is_fresh(text)


def test_add_default_recorded_is_today() -> None:
    new_lesson = lesson(recorded=None)
    result = record.add_lesson(record.build_template(), new_lesson, today=TODAY)
    assert f"- **Recorded:** {TODAY}" in result.new_text


def test_add_optional_fields_rendered() -> None:
    new_lesson = lesson(
        category="testing",
        severity="high",
        prevention="add a gate",
        references="LLT-0001, docs/x.md",
    )
    text = record.add_lesson(record.build_template(), new_lesson, today=TODAY).new_text
    assert "- **Category:** testing" in text
    assert "- **Severity:** high" in text
    assert "- **Prevention:** add a gate" in text
    assert "- **References:** LLT-0001, docs/x.md" in text


# --- add: input validation (L5–L7, L9–L13) --------------------------------------


def test_add_missing_title_rejected() -> None:
    with pytest.raises(InvalidInput, match="--title is required and must be non-empty \\(G6\\)"):
        record.add_lesson(TEMPLATE, EMPTY_TITLE, today=TODAY)


def test_add_blank_context_rejected() -> None:
    with pytest.raises(InvalidInput, match="--context is required and must be non-empty \\(G6\\)"):
        record.add_lesson(TEMPLATE, BLANK_CONTEXT, today=TODAY)


def test_add_tab_in_solution_rejected() -> None:
    with pytest.raises(
        InvalidInput, match="--solution must be a single line without tabs \\(G6\\)"
    ):
        record.add_lesson(TEMPLATE, TAB_SOLUTION, today=TODAY)


def test_add_out_of_vocabulary_category_rejected() -> None:
    with pytest.raises(InvalidInput, match="--category 'banana' not in vocabulary:.*\\(G6\\)"):
        record.add_lesson(TEMPLATE, BANANA_CATEGORY, today=TODAY)


def test_add_out_of_vocabulary_severity_rejected() -> None:
    with pytest.raises(
        InvalidInput,
        match="--severity 'urgent' not in vocabulary: low, medium, high, critical \\(G6\\)",
    ):
        record.add_lesson(TEMPLATE, URGENT_SEVERITY, today=TODAY)


def test_add_bad_date_shape_rejected() -> None:
    with pytest.raises(InvalidInput, match="--recorded '2026-1-1' is not YYYY-MM-DD \\(G6\\)"):
        record.add_lesson(TEMPLATE, BAD_DATE, today=TODAY)


def test_add_format_only_date_accepted() -> None:
    # DEV(3) pinned: DATE_RE is format-only; 2026-99-99 passes.
    result = record.add_lesson(record.build_template(), lesson(recorded="2026-99-99"), today=TODAY)
    assert "- **Recorded:** 2026-99-99" in result.new_text


def test_add_explicit_id() -> None:
    result = record.add_lesson(record.build_template(), lesson(id="LLT-0005"), today=TODAY)
    assert result.entry_id == "LLT-0005"
    entries, _ = record.parse_entries(result.new_text.split("\n"))
    assert record.next_id(entries) == "LLT-0006"


def test_add_duplicate_id_rejected() -> None:
    with pytest.raises(
        InvalidInput, match="--id LLT-0001 already exists; ids are never reused \\(G4\\)"
    ):
        record.add_lesson(BASE, DUPLICATE_ID, today=TODAY)


def test_add_id_below_max_rejected() -> None:
    text = record.add_lesson(record.build_template(), lesson(id="LLT-0005"), today=TODAY).new_text
    with pytest.raises(
        InvalidInput,
        match="--id LLT-0004 must be greater than the current maximum LLT-0005",
    ):
        record.add_lesson(text, BELOW_MAX_ID, today=TODAY)


def test_add_malformed_id_rejected() -> None:
    with pytest.raises(InvalidInput, match="--id 'LLT-1' must match LLT-\\[0-9\\]\\{4\\} \\(G4\\)"):
        record.add_lesson(TEMPLATE, MALFORMED_ID, today=TODAY)


def test_add_supersedes_unknown_rejected() -> None:
    with pytest.raises(InvalidInput, match="--supersedes LLT-9999: no such entry \\(G7\\)"):
        record.add_lesson(BASE, UNKNOWN_SUPERSEDES, today=TODAY)


def test_add_supersedes_superseded_rejected() -> None:
    with pytest.raises(
        InvalidInput,
        match="--supersedes LLT-0001: that entry is not active; supersede the newest replacement",
    ):
        record.add_lesson(TWO, SUPERSEDED_TARGET, today=TODAY)


def test_add_supersedes_malformed_rejected() -> None:
    with pytest.raises(InvalidInput, match="--supersedes 'nope' must be an LLT-NNNN id \\(G7\\)"):
        record.add_lesson(BASE, MALFORMED_SUPERSEDES, today=TODAY)


# --- structural errors (L14–L17d, G4–G8) ---------------------------------------


def test_structural_missing_markers_rejected() -> None:
    with pytest.raises(
        FormatError,
        match="missing <!-- LLT:INDEX:BEGIN --> / <!-- LLT:INDEX:END --> markers \\(G8\\)",
    ):
        record.structural_errors("# Lessons Learned\n\nno markers at all\n")


def test_structural_empty_index_block_rejected() -> None:
    text = (
        "# Lessons Learned\n\n"
        "<!-- LLT:INDEX:BEGIN -->\n"
        "<!-- LLT:INDEX:END -->\n"
        "\n"
        "<!-- LLT:ENTRY:LLT-0001 -->\n"
        "## LLT-0001 — T\n\n"
        "- **Recorded:** 2026-10-18\n"
    )
    with pytest.raises(FormatError, match="index block is empty or malformed \\(G8\\)"):
        record.structural_errors(text)


def test_structural_marker_before_index_block_rejected() -> None:
    text = "<!-- LLT:ENTRY:LLT-0001 -->\n" + record.build_template()
    with pytest.raises(
        FormatError,
        match="entry marker at line 1 appears before the index block; the index "
        "must be first \\(G8\\)",
    ):
        record.structural_errors(text)


def test_duplicate_entry_marker_rejected() -> None:
    text = base_record()
    lines = text.split("\n")
    block = "\n".join(lines[16:29])  # marker, heading, blank, 10 fields
    text = text.rstrip("\n") + "\n\n" + block + "\n"
    errors = record.structural_errors(text)
    assert "duplicate entry marker LLT-0001 (line 31); ids must be unique (G4)" in errors


def test_ids_not_strictly_increasing_rejected() -> None:
    text = two_entry_record()
    lines = text.split("\n")
    e1 = "\n".join(lines[17:31])  # entry LLT-0001 (marker@18 .. line 31)
    e2 = "\n".join(lines[31:44])  # entry LLT-0002 (marker@32 .. line 44)
    head = "\n".join(lines[:17])  # through the blank line 17
    text = head + "\n" + e2 + "\n\n" + e1 + "\n"
    errors = record.structural_errors(text)
    assert (
        "entry ids must strictly increase in file order (append-only); found 2 followed by 1 (G4)"
        in errors
    )


def test_missing_required_field_rejected() -> None:
    text = base_record().replace("- **Pitfall:** pit A\n", "")
    assert record.structural_errors(text) == [
        "entry LLT-0001: missing required field 'Pitfall' (G6)"
    ]


def test_empty_required_field_rejected() -> None:
    text = base_record().replace("- **Pitfall:** pit A", "- **Pitfall:**")
    assert record.structural_errors(text) == [
        "entry LLT-0001: required field 'Pitfall' is empty (G6)"
    ]


def test_out_of_vocabulary_severity_rejected() -> None:
    text = base_record().replace("- **Severity:** medium", "- **Severity:** urgent")
    assert record.structural_errors(text) == [
        "entry LLT-0001: Severity 'urgent' not in vocabulary: low, medium, high, critical (G6)"
    ]


def test_marker_heading_mismatch_rejected() -> None:
    text = base_record().replace("## LLT-0001 — First lesson", "## LLT-0002 — First lesson")
    assert record.structural_errors(text) == [
        "entry marker LLT-0001 (line 17) disagrees with heading id LLT-0002 (line 18); "
        "marker and heading must match (G8)"
    ]


def test_missing_heading_rejected() -> None:
    text = base_record().replace("## LLT-0001 — First lesson", "prose without a heading")
    assert record.structural_errors(text) == [
        "entry LLT-0001: missing heading '## LLT-0001 — <title>' in lines 17-30 (G8)"
    ]


def test_tab_in_title_rejected() -> None:
    text = base_record().replace("## LLT-0001 — First lesson", "## LLT-0001 — First\tlesson")
    assert record.structural_errors(text) == ["entry LLT-0001: title contains a tab character (G6)"]


def test_tab_in_field_rejected() -> None:
    text = base_record().replace("- **Context:** ctx A", "- **Context:** ctx\tA")
    assert record.structural_errors(text) == [
        "entry LLT-0001: field 'Context' contains a tab character (G6)"
    ]


def test_empty_optional_field_rejected() -> None:
    text = base_record().replace("- **Prevention:** —", "- **Prevention:**")
    assert record.structural_errors(text) == [
        "entry LLT-0001: optional field 'Prevention' is empty; write — when absent (G6)"
    ]


def test_unknown_field_rejected() -> None:
    text = base_record().replace("- **References:** —", "- **References:** —\n- **Bogus:** value")
    errors = record.structural_errors(text)
    assert any(e.startswith("entry LLT-0001: unknown field 'Bogus' (line") for e in errors)


def test_duplicate_field_rejected() -> None:
    text = base_record().replace(
        "- **Context:** ctx A", "- **Context:** ctx A\n- **Context:** again"
    )
    assert any(
        e.startswith("entry LLT-0001: duplicate field 'Context' (line")
        for e in record.structural_errors(text)
    )


def test_bad_recorded_format_rejected() -> None:
    text = base_record().replace("- **Recorded:** 2026-10-18", "- **Recorded:** 2026-1-1")
    assert record.structural_errors(text) == [
        "entry LLT-0001: Recorded '2026-1-1' is not YYYY-MM-DD (G6)"
    ]


def test_bad_status_rejected() -> None:
    text = base_record().replace("- **Status:** active", "- **Status:** pending")
    assert record.structural_errors(text) == [
        "entry LLT-0001: Status 'pending' not in vocabulary: active, superseded (G6)"
    ]


def test_bad_supersedes_value_rejected() -> None:
    # A malformed value fires BOTH guards (pinned order: per-entry shape check
    # first, then the cross-entry existence check — spec §4.1, verified against
    # the pinned script): it does not match ID_RE, and it does not name an entry.
    text = base_record().replace("- **Supersedes:** —", "- **Supersedes:** LLT-1")
    assert record.structural_errors(text) == [
        "entry LLT-0001: Supersedes 'LLT-1' must be an LLT-NNNN id or — (G7)",
        "entry LLT-0001: Supersedes LLT-1, which does not exist (G7)",
    ]


def test_supersedes_unknown_entry_rejected() -> None:
    text = base_record().replace("- **Supersedes:** —", "- **Supersedes:** LLT-9999")
    assert record.structural_errors(text) == [
        "entry LLT-0001: Supersedes LLT-9999, which does not exist (G7)"
    ]


def test_superseded_without_successor_rejected() -> None:
    text = two_entry_record().replace("- **Supersedes:** LLT-0001\n", "")
    assert record.structural_errors(text) == [
        "entry LLT-0001 is superseded but no entry supersedes it; "
        "add the replacement with --supersedes LLT-0001 (G7)"
    ]


def test_supersedes_target_not_marked_superseded_rejected() -> None:
    text = base_record()
    added = record.NewLesson(title="Second", context="c", pitfall="p", solution="s", recorded=TODAY)
    text = record.add_lesson(text, added, today=TODAY).new_text
    # LLT-0002 now points at LLT-0001, which is still active.
    text = replace_after(text, "## LLT-0002", "- **Supersedes:** —", "- **Supersedes:** LLT-0001")
    assert record.structural_errors(text) == [
        "entry LLT-0002: Supersedes LLT-0001, but LLT-0001 is not marked superseded (G7)"
    ]


# --- freshness semantics (L19, L21, DEV(4)) -------------------------------------


def test_same_line_body_edit_is_not_stale() -> None:
    # DEV(4): body content is not indexed; a same-line rewrite stays fresh.
    text = base_record().replace("- **Context:** ctx A", "- **Context:** rewritten ctx")
    assert record.index_is_fresh(text)


def test_indexed_field_change_is_stale() -> None:
    text = base_record().replace("- **Severity:** medium", "- **Severity:** high")
    assert not record.index_is_fresh(text)
    healed = record.regenerate(text)
    assert record.index_is_fresh(healed)
    assert "LLT-0001\tFirst lesson\tother\thigh\tactive" in healed


def test_line_count_change_is_stale() -> None:
    text = base_record() + "extra body line\n"
    assert not record.index_is_fresh(text)


def test_second_index_pair_is_stale_then_heals() -> None:
    # L21: not an error, and not inert — body text shifts the last row's end.
    text = base_record() + "\n<!-- LLT:INDEX:BEGIN -->\nstray interior\n<!-- LLT:INDEX:END -->\n"
    assert not record.index_is_fresh(text)
    assert record.structural_errors(text) == []
    healed = record.regenerate(text)
    assert record.index_is_fresh(healed)
    assert "stray interior" in healed


def test_regenerate_is_idempotent() -> None:
    once = record.regenerate(base_record())
    assert record.regenerate(once) == once


# --- regenerate / expected_index_rows guards -------------------------------------


def test_regenerate_requires_block() -> None:
    with pytest.raises(FormatError, match="missing index block markers; cannot sync \\(G8\\)"):
        record.regenerate("# Lessons Learned\n\nno markers at all\n")


def test_expected_index_rows_requires_block() -> None:
    with pytest.raises(FormatError, match="missing index block markers \\(G8\\)"):
        record.expected_index_rows("# Lessons Learned\n\nno markers at all\n")


# --- max_id / next_id ------------------------------------------------------------


def test_next_id_empty_template() -> None:
    entries, _ = record.parse_entries(record.build_template().split("\n"))
    assert record.max_id(entries) == 0
    assert record.next_id(entries) == "LLT-0001"


def test_next_id_after_two_entries() -> None:
    entries, _ = record.parse_entries(two_entry_record().split("\n"))
    assert record.max_id(entries) == 2
    assert record.next_id(entries) == "LLT-0003"
