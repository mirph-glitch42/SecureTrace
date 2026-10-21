"""Command-layer tests for the store-based document pipeline (B10 WI 8).

Spec: ``algorithms/deterministic-doc-pipeline.md`` §5.3 — the positional file
arg of ``backlog`` / ``lessons`` / ``algorithms`` is the **store** path;
``render`` and ``check`` compute expected bytes the same way; ``migrate`` is
the one-shot doc → store → re-render commit. Pinned here:

- exact stdout success lines and exit 0 (D9 message conventions)
- exact ``securetrace: {msg}`` stderr lines and exit 2 (rejected input,
  missing store, id collision, store already present without ``--force``)
- the check exit model: 0 in sync (stdout) / 1 stale (diagnosis + remediation
  on stderr) / 2 malformed (exit-2 bucket)
- ``docs render-all`` / ``docs check-all`` over the standard repo layout
- ``securetrace.__main__:main`` dispatch for the re-pointed surface (replaces
  the legacy ``backlog sync`` / ``lessons next-id`` / ``algorithms check`` /
  legacy ``lessons add`` dispatch tests)
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path

import pytest

from securetrace.__main__ import main
from securetrace.cli_docs import (
    make_lesson,
    run_algorithms_show,
    run_algorithms_upsert,
    run_backlog_progress,
    run_backlog_show,
    run_backlog_upsert,
    run_check,
    run_check_all,
    run_lessons_add,
    run_lessons_show,
    run_migrate,
    run_render,
    run_render_all,
)
from securetrace.docs.backlog_doc import render_backlog
from securetrace.docs.canonical import canonical_json
from securetrace.docs.integrity import (
    DOC_MISSING,
    DOC_MODIFIED_OUTSIDE_APP,
    IN_SYNC,
    MALFORMED_MANIFEST,
    MALFORMED_STORE,
    STORE_DRIFT,
    STORE_DRIFT_OR_DOC_DRIFT,
    check_message,
    commit_render,
)
from securetrace.docs.lessons_doc import render_lessons
from securetrace.docs.registry_doc import render_registry
from securetrace.docs.schema import SCHEMA_VERSION
from securetrace.lessons.record import ALL_FIELDS

# --------------------------------------------------------------------- scenes


def backlog_store() -> dict:
    return {
        "doc": "backlog",
        "schema_version": SCHEMA_VERSION,
        "updated": "2026-10-20",
        "header": [
            "Tracks all SecureTrace work.",
            "",
            "**Queue:** B1 | **In progress:** B1 | **Done:** B2 | **Updated:** 2026-10-20",
        ],
        "queue": ["**B1** (one)", "**B2** (two)"],
        "items": [
            {
                "id": "B1",
                "title": "Item one",
                "status": "IN PROGRESS",
                "fields": [
                    {"name": "Source", "lines": ["user"]},
                    {"name": "Progress", "lines": ["  - 2026-10-20 — started"]},
                ],
            },
            {
                "id": "B2",
                "title": "Item two",
                "status": "DONE",
                "fields": [{"name": "Source", "lines": ["user"]}],
            },
        ],
        "constraints": ["- gate green"],
    }


def lessons_store() -> dict:
    return {
        "doc": "lessons",
        "schema_version": SCHEMA_VERSION,
        "intro": ["Intro one.", "Intro two."],
        "lessons": [
            {
                "id": "LLT-0001",
                "title": "First lesson",
                "fields": [
                    {"name": "Recorded", "value": "2026-10-20"},
                    {"name": "Category", "value": "tooling"},
                    {"name": "Severity", "value": "medium"},
                    {"name": "Status", "value": "active"},
                    {"name": "Context", "value": "context one"},
                    {"name": "Pitfall", "value": "pitfall one"},
                    {"name": "Solution", "value": "solution one"},
                    {"name": "Supersedes", "value": "—"},
                    {"name": "Prevention", "value": "—"},
                    {"name": "References", "value": "—"},
                ],
            }
        ],
    }


def registry_store() -> dict:
    def row(slug: str) -> dict:
        return {
            "slug": slug,
            "name": f"Name {slug}",
            "version": "0.1.0",
            "status": "implemented",
            "file": f"algorithms/{slug}.md",
            "summary": f"Summary for {slug}.",
        }

    return {
        "doc": "registry",
        "schema_version": SCHEMA_VERSION,
        "intro": ["> One row per algorithm document."],
        "rows": [row("alpha"), row("charlie")],
        "rules": ["Keep sorted by slug."],
    }


def scene_all(tmp_path: Path) -> None:
    """Commit all three kinds under the standard repo layout (CWD = repo root)."""
    commit_render(
        "backlog", backlog_store(), "data/backlog.json", "BACKLOG.md", "data/manifest.json"
    )
    commit_render(
        "lessons", lessons_store(), "data/lessons.json", "LESSONS_LEARNED.md", "data/manifest.json"
    )
    commit_render(
        "registry",
        registry_store(),
        "data/algorithms.json",
        "algorithms/INDEX.md",
        "data/manifest.json",
    )


def read_store(tmp_path: Path, name: str) -> dict:
    return json.loads((tmp_path / "data" / name).read_text(encoding="utf-8"))


def render_line(doc: str, store: str, manifest: str) -> str:
    return f"render: {doc} rendered from {store} (manifest: {manifest})"


# ------------------------------------------------------- backlog upsert / progress / show


def test_backlog_upsert_adds_item(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    scene_all(tmp_path)
    item = {
        "id": "B3",
        "title": "New work",
        "status": "OPEN",
        "fields": [{"name": "Source", "lines": ["user"]}],
    }
    code = run_backlog_upsert("data/backlog.json", item, "2026-10-21")
    assert code == 0
    out = capsys.readouterr().out
    assert out == (
        "upsert: added B3 — New work (data/backlog.json)\n"
        + render_line("BACKLOG.md", "data/backlog.json", "data/manifest.json")
        + "\n"
    )
    store = read_store(tmp_path, "backlog.json")
    assert [it["id"] for it in store["items"]] == ["B1", "B2", "B3"]
    assert store["updated"] == "2026-10-21"
    assert (tmp_path / "BACKLOG.md").read_text(encoding="utf-8") == render_backlog(store)


def test_backlog_upsert_updates_existing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    scene_all(tmp_path)
    item = {
        "id": "B1",
        "title": "Item one (revised)",
        "status": "DONE",
        "fields": [{"name": "Source", "lines": ["user"]}],
    }
    code = run_backlog_upsert("data/backlog.json", item, "2026-10-21")
    assert code == 0
    out = capsys.readouterr().out
    assert out.startswith("upsert: updated B1 — Item one (revised) (data/backlog.json)\n")
    store = read_store(tmp_path, "backlog.json")
    assert [it["id"] for it in store["items"]] == ["B1", "B2"]
    assert store["items"][0]["title"] == "Item one (revised)"


def test_backlog_upsert_missing_store_exit2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    item = {
        "id": "B1",
        "title": "t",
        "status": "OPEN",
        "fields": [{"name": "Source", "lines": ["user"]}],
    }
    code = run_backlog_upsert("data/backlog.json", item, "2026-10-21")
    assert code == 2
    err = capsys.readouterr().err
    assert err.startswith("securetrace: cannot read store data/backlog.json:")
    assert capsys.readouterr().out == ""


def test_backlog_upsert_id_collision_exit2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    scene_all(tmp_path)
    item = {
        "id": "B0",
        "title": "nope",
        "status": "OPEN",
        "fields": [{"name": "Source", "lines": ["user"]}],
    }
    code = run_backlog_upsert("data/backlog.json", item, "2026-10-21")
    assert code == 2
    assert capsys.readouterr().err == (
        "securetrace: backlog item ids must be strictly increasing: B0 after B2\n"
    )


def test_backlog_upsert_bad_status_exit2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    scene_all(tmp_path)
    item = {
        "id": "B3",
        "title": "t",
        "status": "BOGUS",
        "fields": [{"name": "Source", "lines": ["user"]}],
    }
    code = run_backlog_upsert("data/backlog.json", item, "2026-10-21")
    assert code == 2
    assert capsys.readouterr().err == (
        "securetrace: items[2].status must be one of: OPEN, IN PROGRESS, DONE, CANCELLED\n"
    )


def test_backlog_progress_appends_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    scene_all(tmp_path)
    code = run_backlog_progress(
        "data/backlog.json", "B1", "  - 2026-10-21 — step done", "2026-10-21"
    )
    assert code == 0
    out = capsys.readouterr().out
    assert out == (
        "progress: appended to B1 (data/backlog.json)\n"
        + render_line("BACKLOG.md", "data/backlog.json", "data/manifest.json")
        + "\n"
    )
    store = read_store(tmp_path, "backlog.json")
    progress = store["items"][0]["fields"][1]
    assert progress["lines"] == ["  - 2026-10-20 — started", "  - 2026-10-21 — step done"]


def test_backlog_progress_unknown_item_exit2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    scene_all(tmp_path)
    code = run_backlog_progress("data/backlog.json", "B99", "  - 2026-10-21 — x", "2026-10-21")
    assert code == 2
    assert capsys.readouterr().err == "securetrace: backlog item 'B99' not found\n"


def test_backlog_show_whole_store(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    scene_all(tmp_path)
    assert run_backlog_show("data/backlog.json") == 0
    assert capsys.readouterr().out == canonical_json(read_store(tmp_path, "backlog.json"))


def test_backlog_show_single_item(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    scene_all(tmp_path)
    assert run_backlog_show("data/backlog.json", item_id="B1") == 0
    store = read_store(tmp_path, "backlog.json")
    assert capsys.readouterr().out == canonical_json(store["items"][0])


def test_backlog_show_item_not_found_exit2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    scene_all(tmp_path)
    assert run_backlog_show("data/backlog.json", item_id="B99") == 2
    assert capsys.readouterr().err == "securetrace: backlog item 'B99' not found\n"


def test_backlog_show_missing_store_exit2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert run_backlog_show("data/backlog.json") == 2
    assert capsys.readouterr().err.startswith("securetrace: cannot read store data/backlog.json:")


# --------------------------------------------------------------------- lessons add / show


def test_lessons_add_records_lesson(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    scene_all(tmp_path)
    lesson = make_lesson("New lesson", "context", "pitfall", "solution", recorded="2026-10-21")
    code = run_lessons_add("data/lessons.json", lesson)
    assert code == 0
    out = capsys.readouterr().out
    assert out == (
        "add: recorded LLT-0002 — New lesson (data/lessons.json)\n"
        + render_line("LESSONS_LEARNED.md", "data/lessons.json", "data/manifest.json")
        + "\n"
    )
    store = read_store(tmp_path, "lessons.json")
    assert [lesson["id"] for lesson in store["lessons"]] == ["LLT-0001", "LLT-0002"]
    assert (tmp_path / "LESSONS_LEARNED.md").read_text(encoding="utf-8") == render_lessons(store)


def test_lessons_add_rejected_category_exit2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    scene_all(tmp_path)
    lesson = make_lesson(
        "New lesson", "context", "pitfall", "solution", recorded="2026-10-21", category="banana"
    )
    code = run_lessons_add("data/lessons.json", lesson)
    assert code == 2
    assert capsys.readouterr().err == (
        "securetrace: lessons[1].Category must be one of: debugging, architecture, "
        "testing, performance, security, dependencies, tooling, environment, "
        "process, data, other\n"
    )


def test_lessons_add_supersedes_flips_target(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    scene_all(tmp_path)
    store = read_store(tmp_path, "lessons.json")
    # Add a second active lesson first so there is a valid target.
    lesson2 = make_lesson("Second lesson", "c", "p", "s", recorded="2026-10-21")
    assert run_lessons_add("data/lessons.json", lesson2) == 0
    capsys.readouterr()
    lesson3 = make_lesson(
        "Third lesson", "c", "p", "s", recorded="2026-10-21", supersedes="LLT-0002"
    )
    assert run_lessons_add("data/lessons.json", lesson3) == 0
    out = capsys.readouterr().out
    assert out.startswith("add: recorded LLT-0003 — Third lesson (data/lessons.json)\n")
    store = read_store(tmp_path, "lessons.json")
    by_id = {
        lesson["id"]: {f["name"]: f["value"] for f in lesson["fields"]}
        for lesson in store["lessons"]
    }
    assert by_id["LLT-0002"]["Status"] == "superseded"
    assert by_id["LLT-0003"]["Status"] == "active"
    assert by_id["LLT-0003"]["Supersedes"] == "LLT-0002"


def test_lessons_add_supersedes_missing_exit2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    scene_all(tmp_path)
    lesson = make_lesson("New lesson", "c", "p", "s", recorded="2026-10-21", supersedes="LLT-0099")
    assert run_lessons_add("data/lessons.json", lesson) == 2
    err = capsys.readouterr().err
    assert "securetrace:" in err
    assert "LLT-0099" in err


def test_lessons_show_single_and_not_found(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    scene_all(tmp_path)
    assert run_lessons_show("data/lessons.json") == 0
    whole = capsys.readouterr().out
    assert whole == canonical_json(read_store(tmp_path, "lessons.json"))
    assert run_lessons_show("data/lessons.json", lesson_id="LLT-0001") == 0
    store = read_store(tmp_path, "lessons.json")
    assert capsys.readouterr().out == canonical_json(store["lessons"][0])
    assert run_lessons_show("data/lessons.json", lesson_id="LLT-0099") == 2
    assert capsys.readouterr().err == "securetrace: lesson 'LLT-0099' not found\n"


# --------------------------------------------------------------------- algorithms upsert / show


def test_algorithms_upsert_adds_row(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    scene_all(tmp_path)
    row = {
        "slug": "bravo",
        "name": "Bravo",
        "version": "0.1.0",
        "status": "draft",
        "file": "algorithms/bravo.md",
        "summary": "A row.",
    }
    code = run_algorithms_upsert("data/algorithms.json", row)
    assert code == 0
    out = capsys.readouterr().out
    assert out == (
        "upsert: added row bravo (data/algorithms.json)\n"
        + render_line("algorithms/INDEX.md", "data/algorithms.json", "data/manifest.json")
        + "\n"
    )
    store = read_store(tmp_path, "algorithms.json")
    assert [r["slug"] for r in store["rows"]] == ["alpha", "bravo", "charlie"]
    assert (tmp_path / "algorithms" / "INDEX.md").read_text(encoding="utf-8") == render_registry(
        store
    )


def test_algorithms_upsert_replaces_row(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    scene_all(tmp_path)
    row = {
        "slug": "alpha",
        "name": "Alpha (revised)",
        "version": "0.2.0",
        "status": "implemented",
        "file": "algorithms/alpha.md",
        "summary": "Revised.",
    }
    code = run_algorithms_upsert("data/algorithms.json", row)
    assert code == 0
    out = capsys.readouterr().out
    assert out.startswith("upsert: updated row alpha (data/algorithms.json)\n")
    store = read_store(tmp_path, "algorithms.json")
    assert [r["slug"] for r in store["rows"]] == ["alpha", "charlie"]
    assert store["rows"][0]["name"] == "Alpha (revised)"


def test_algorithms_upsert_bad_slug_exit2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    scene_all(tmp_path)
    row = {
        "slug": "bravo!",
        "name": "n",
        "version": "0.1.0",
        "status": "draft",
        "file": "algorithms/bravo.md",
        "summary": "s",
    }
    code = run_algorithms_upsert("data/algorithms.json", row)
    assert code == 2
    assert capsys.readouterr().err == "securetrace: rows[1].slug must be kebab-case, got 'bravo!'\n"


def test_algorithms_show_row_and_not_found(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    scene_all(tmp_path)
    assert run_algorithms_show("data/algorithms.json") == 0
    assert capsys.readouterr().out == canonical_json(read_store(tmp_path, "algorithms.json"))
    assert run_algorithms_show("data/algorithms.json", slug="alpha") == 0
    store = read_store(tmp_path, "algorithms.json")
    assert capsys.readouterr().out == canonical_json(store["rows"][0])
    assert run_algorithms_show("data/algorithms.json", slug="zulu") == 2
    assert capsys.readouterr().err == "securetrace: registry row 'zulu' not found\n"


# --------------------------------------------------------------------- render / check


def test_render_rewrites_doc_and_manifest(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    scene_all(tmp_path)
    doc = tmp_path / "BACKLOG.md"
    doc.write_text(doc.read_text(encoding="utf-8") + "TAMPERED\n", encoding="utf-8")
    code = run_render("backlog", "data/backlog.json")
    assert code == 0
    assert capsys.readouterr().out == (
        render_line("BACKLOG.md", "data/backlog.json", "data/manifest.json") + "\n"
    )
    store = read_store(tmp_path, "backlog.json")
    assert doc.read_text(encoding="utf-8") == render_backlog(store)


def test_render_missing_store_exit2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert run_render("backlog", "data/backlog.json") == 2
    assert capsys.readouterr().err.startswith("securetrace: cannot read store data/backlog.json:")


def test_render_malformed_store_exit2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "backlog.json").write_text(
        '{"doc": "backlog", "schema_version": 99}\n', encoding="utf-8"
    )
    assert run_render("backlog", "data/backlog.json") == 2
    assert "schema_version must be 1" in capsys.readouterr().err


def test_check_in_sync_exit0_stdout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    scene_all(tmp_path)
    code = run_check("backlog", "data/backlog.json")
    assert code == 0
    expected = check_message("backlog", IN_SYNC, "data/backlog.json")
    assert capsys.readouterr().out == expected + "\n"
    assert capsys.readouterr().err == ""


def test_check_doc_modified_exit1_stderr(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    scene_all(tmp_path)
    doc = tmp_path / "BACKLOG.md"
    doc.write_text(doc.read_text(encoding="utf-8") + "TAMPERED\n", encoding="utf-8")
    code = run_check("backlog", "data/backlog.json")
    assert code == 1
    expected = check_message("backlog", DOC_MODIFIED_OUTSIDE_APP, "data/backlog.json")
    assert capsys.readouterr().err == expected + "\n"
    assert "securetrace backlog render data/backlog.json" in expected


def test_check_store_drift_exit1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    scene_all(tmp_path)
    store = read_store(tmp_path, "backlog.json")
    store["items"][0]["fields"][1]["lines"].append("  - 2026-10-21 — after render")
    (tmp_path / "data" / "backlog.json").write_text(canonical_json(store), encoding="utf-8")
    (tmp_path / "BACKLOG.md").write_text(render_backlog(store), encoding="utf-8")
    code = run_check("backlog", "data/backlog.json")
    assert code == 1
    expected = check_message("backlog", STORE_DRIFT, "data/backlog.json")
    assert capsys.readouterr().err == expected + "\n"


def test_check_store_and_doc_drift_exit1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    scene_all(tmp_path)
    store = read_store(tmp_path, "backlog.json")
    store["items"][0]["fields"][1]["lines"].append("  - 2026-10-21 — after render")
    (tmp_path / "data" / "backlog.json").write_text(canonical_json(store), encoding="utf-8")
    # doc left at the pre-drift render → both store and doc disagree with the manifest
    code = run_check("backlog", "data/backlog.json")
    assert code == 1
    expected = check_message("backlog", STORE_DRIFT_OR_DOC_DRIFT, "data/backlog.json")
    assert capsys.readouterr().err == expected + "\n"


@pytest.mark.parametrize(
    ("diagnosis", "delete"),
    [
        (MALFORMED_STORE, "data/backlog.json"),
        (DOC_MISSING, "BACKLOG.md"),
        (MALFORMED_MANIFEST, "data/manifest.json"),
    ],
)
def test_check_exit2_bucket(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch, diagnosis, delete
) -> None:
    monkeypatch.chdir(tmp_path)
    scene_all(tmp_path)
    (tmp_path / delete).unlink()
    code = run_check("backlog", "data/backlog.json")
    assert code == 2
    expected = check_message("backlog", diagnosis, "data/backlog.json")
    assert capsys.readouterr().err == expected + "\n"


# --------------------------------------------------------------------- docs render-all / check-all


def test_render_all_three_kinds_in_order(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    scene_all(tmp_path)
    code = run_render_all()
    assert code == 0
    manifest = "data/manifest.json"
    assert capsys.readouterr().out == (
        render_line("BACKLOG.md", "data/backlog.json", manifest)
        + "\n"
        + render_line("LESSONS_LEARNED.md", "data/lessons.json", manifest)
        + "\n"
        + render_line("algorithms/INDEX.md", "data/algorithms.json", manifest)
        + "\n"
    )


def test_render_all_fail_fast_exit2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    commit_render(
        "backlog", backlog_store(), "data/backlog.json", "BACKLOG.md", "data/manifest.json"
    )
    code = run_render_all()
    assert code == 2
    captured = capsys.readouterr()
    assert (
        captured.out == render_line("BACKLOG.md", "data/backlog.json", "data/manifest.json") + "\n"
    )
    assert captured.err.startswith("securetrace: cannot read store data/lessons.json:")


def test_check_all_all_in_sync_exit0(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    scene_all(tmp_path)
    code = run_check_all()
    assert code == 0
    out = capsys.readouterr().out
    assert check_message("backlog", IN_SYNC, "data/backlog.json") in out
    assert check_message("lessons", IN_SYNC, "data/lessons.json") in out
    assert check_message("registry", IN_SYNC, "data/algorithms.json") in out


def test_check_all_worst_exit_code(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    scene_all(tmp_path)
    doc = tmp_path / "LESSONS_LEARNED.md"
    doc.write_text(doc.read_text(encoding="utf-8") + "TAMPERED\n", encoding="utf-8")
    code = run_check_all()
    assert code == 1
    out = capsys.readouterr()
    assert check_message("backlog", IN_SYNC, "data/backlog.json") in out.out
    assert check_message("lessons", DOC_MODIFIED_OUTSIDE_APP, "data/lessons.json") in out.err
    assert check_message("registry", IN_SYNC, "data/algorithms.json") in out.out


# --------------------------------------------------------------------- migrate


def test_migrate_backlog_items(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    store = backlog_store()
    (tmp_path / "BACKLOG.md").write_text(render_backlog(store), encoding="utf-8")
    code = run_migrate("BACKLOG.md")
    assert code == 0
    assert capsys.readouterr().out == (
        "migrate: 2 items from BACKLOG.md → data/backlog.json\n"
        + render_line("BACKLOG.md", "data/backlog.json", "data/manifest.json")
        + "\n"
    )
    migrated = read_store(tmp_path, "backlog.json")
    assert migrated["doc"] == "backlog"
    assert [it["id"] for it in migrated["items"]] == ["B1", "B2"]
    assert (tmp_path / "data" / "manifest.json").is_file()


def test_migrate_lessons_singular(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    store = lessons_store()
    (tmp_path / "LESSONS_LEARNED.md").write_text(render_lessons(store), encoding="utf-8")
    code = run_migrate("LESSONS_LEARNED.md")
    assert code == 0
    assert capsys.readouterr().out == (
        "migrate: 1 lesson from LESSONS_LEARNED.md → data/lessons.json\n"
        + render_line("LESSONS_LEARNED.md", "data/lessons.json", "data/manifest.json")
        + "\n"
    )


def test_migrate_registry_rows(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    store = registry_store()
    (tmp_path / "algorithms").mkdir()
    (tmp_path / "algorithms" / "INDEX.md").write_text(render_registry(store), encoding="utf-8")
    code = run_migrate("INDEX.md")
    assert code == 0
    assert capsys.readouterr().out == (
        "migrate: 2 rows from INDEX.md → data/algorithms.json\n"
        + render_line("INDEX.md", "data/algorithms.json", "data/manifest.json")
        + "\n"
    )


def test_migrate_store_exists_without_force_exit2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    scene_all(tmp_path)
    (tmp_path / "BACKLOG.md").write_text(render_backlog(backlog_store()), encoding="utf-8")
    code = run_migrate("BACKLOG.md")
    assert code == 2
    assert capsys.readouterr().err == (
        "securetrace: store data/backlog.json already exists; use --force to replace\n"
    )


def test_migrate_store_exists_with_force_ok(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    scene_all(tmp_path)
    (tmp_path / "BACKLOG.md").write_text(render_backlog(backlog_store()), encoding="utf-8")
    code = run_migrate("BACKLOG.md", force=True)
    assert code == 0
    assert "migrate: 2 items from BACKLOG.md → data/backlog.json" in capsys.readouterr().out


def test_migrate_unknown_basename_exit2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "NOTES.md").write_text("# Notes\n", encoding="utf-8")
    code = run_migrate("NOTES.md")
    assert code == 2
    assert capsys.readouterr().err == (
        "securetrace: cannot infer doc kind from NOTES.md; "
        "pass --kind one of: backlog, lessons, registry\n"
    )


def test_migrate_explicit_kind_overrides_basename(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "custom.md").write_text(render_backlog(backlog_store()), encoding="utf-8")
    code = run_migrate("custom.md", kind="backlog")
    assert code == 0
    assert "migrate: 2 items from custom.md → data/backlog.json" in capsys.readouterr().out


def test_migrate_malformed_doc_exit2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "BACKLOG.md").write_text("# Wrong Title\n\nbody\n", encoding="utf-8")
    code = run_migrate("BACKLOG.md")
    assert code == 2
    err = capsys.readouterr().err
    assert err.startswith("securetrace: ")


def test_migrate_missing_doc_exit2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    code = run_migrate("MISSING.md", kind="backlog")
    assert code == 2
    assert capsys.readouterr().err.startswith("securetrace: cannot read MISSING.md:")


# --------------------------------------------------------------------- make_lesson (D7)


def test_make_lesson_defaults() -> None:
    lesson = make_lesson("T", "C", "P", "S", recorded="2026-10-21")
    assert lesson["id"] is None
    assert lesson["title"] == "T"
    names = [f["name"] for f in lesson["fields"]]
    assert names == list(ALL_FIELDS)
    values = {f["name"]: f["value"] for f in lesson["fields"]}
    assert values["Recorded"] == "2026-10-21"
    assert values["Category"] == "other"
    assert values["Severity"] == "medium"
    assert values["Status"] == "active"
    assert values["Context"] == "C"
    assert values["Pitfall"] == "P"
    assert values["Solution"] == "S"
    assert values["Supersedes"] == "—"
    assert values["Prevention"] == "—"
    assert values["References"] == "—"


def test_make_lesson_recorded_defaults_to_today() -> None:
    lesson = make_lesson("T", "C", "P", "S")
    values = {f["name"]: f["value"] for f in lesson["fields"]}
    assert values["Recorded"] == datetime.date.today().isoformat()


def test_make_lesson_optionals_pass_through() -> None:
    lesson = make_lesson(
        "T",
        "C",
        "P",
        "S",
        id="LLT-0007",
        category="testing",
        severity="high",
        recorded="2026-01-02",
        supersedes="LLT-0001",
        prevention="pre",
        references="ref",
    )
    assert lesson["id"] == "LLT-0007"
    values = {f["name"]: f["value"] for f in lesson["fields"]}
    assert values["Category"] == "testing"
    assert values["Severity"] == "high"
    assert values["Recorded"] == "2026-01-02"
    assert values["Supersedes"] == "LLT-0001"
    assert values["Prevention"] == "pre"
    assert values["References"] == "ref"


# ------------------------------------------------------- main() dispatch (re-pointed surface)


def test_main_dispatch_backlog_upsert(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    scene_all(tmp_path)
    code = main(
        [
            "backlog",
            "upsert",
            "data/backlog.json",
            "--id",
            "B3",
            "--title",
            "New work",
            "--status",
            "OPEN",
            "--field",
            "Source: user",
            "--date",
            "2026-10-21",
        ]
    )
    assert code == 0
    assert "upsert: added B3 — New work (data/backlog.json)" in capsys.readouterr().out


def test_main_dispatch_backlog_progress(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    scene_all(tmp_path)
    code = main(
        [
            "backlog",
            "progress",
            "data/backlog.json",
            "--id",
            "B1",
            "--text",
            "step done",
            "--date",
            "2026-10-21",
        ]
    )
    assert code == 0
    assert "progress: appended to B1 (data/backlog.json)" in capsys.readouterr().out
    store = read_store(tmp_path, "backlog.json")
    assert store["items"][0]["fields"][1]["lines"][-1] == "  - 2026-10-21 — step done"


def test_main_dispatch_backlog_check_in_sync(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    scene_all(tmp_path)
    code = main(["backlog", "check", "data/backlog.json"])
    assert code == 0
    assert check_message("backlog", IN_SYNC, "data/backlog.json") in capsys.readouterr().out


def test_main_dispatch_lessons_add(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    scene_all(tmp_path)
    code = main(
        [
            "lessons",
            "add",
            "data/lessons.json",
            "--title",
            "New lesson",
            "--context",
            "c",
            "--pitfall",
            "p",
            "--solution",
            "s",
            "--recorded",
            "2026-10-21",
        ]
    )
    assert code == 0
    assert "add: recorded LLT-0002 — New lesson (data/lessons.json)" in capsys.readouterr().out


def test_main_dispatch_lessons_add_rejected_category_exit2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    scene_all(tmp_path)
    code = main(
        [
            "lessons",
            "add",
            "data/lessons.json",
            "--title",
            "t",
            "--context",
            "c",
            "--pitfall",
            "p",
            "--solution",
            "s",
            "--recorded",
            "2026-10-21",
            "--category",
            "banana",
        ]
    )
    assert code == 2
    assert "securetrace: lessons[1].Category must be one of:" in capsys.readouterr().err


def test_main_dispatch_algorithms_upsert(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    scene_all(tmp_path)
    code = main(
        [
            "algorithms",
            "upsert",
            "data/algorithms.json",
            "--slug",
            "bravo",
            "--name",
            "Bravo",
            "--version",
            "0.1.0",
            "--status",
            "draft",
            "--file",
            "algorithms/bravo.md",
            "--summary",
            "A row.",
        ]
    )
    assert code == 0
    assert "upsert: added row bravo (data/algorithms.json)" in capsys.readouterr().out


def test_main_dispatch_docs_check_all(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    scene_all(tmp_path)
    code = main(["docs", "check-all"])
    assert code == 0
    out = capsys.readouterr().out
    assert out.count("is in sync with its store") == 3


def test_main_dispatch_migrate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "BACKLOG.md").write_text(render_backlog(backlog_store()), encoding="utf-8")
    code = main(["migrate", "BACKLOG.md"])
    assert code == 0
    assert "migrate: 2 items from BACKLOG.md → data/backlog.json" in capsys.readouterr().out


def test_main_dispatch_migrate_force(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    scene_all(tmp_path)
    (tmp_path / "BACKLOG.md").write_text(render_backlog(backlog_store()), encoding="utf-8")
    assert main(["migrate", "BACKLOG.md"]) == 2
    capsys.readouterr()
    code = main(["migrate", "BACKLOG.md", "--force"])
    assert code == 0
    assert "migrate: 2 items from BACKLOG.md → data/backlog.json" in capsys.readouterr().out
