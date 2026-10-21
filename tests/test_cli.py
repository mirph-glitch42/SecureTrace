"""Behavioral tests for the ``securetrace`` command layer and CLI.

These pin the exact user-visible contract of ``securetrace.cli`` (messages,
streams, exit codes) and the ``securetrace`` console entrypoint
(``securetrace.__main__:main``). The contracts mirror the pinned scripts
``scripts/backlog_index.py``, ``scripts/algorithm_index.py`` (prog prefixes
``build_backlog_index`` / ``build_index``), and ``scripts/manage_lessons.py``
(prog prefix ``manage_lessons``), which become thin wrappers over this layer.

Conventions (pinned):
- ``{path}: index OK (N entries)`` / ``{path}: index updated (N entries)`` → stdout, 0
- ``{path}: index STALE -- rerun without --check`` → stderr, 1 (no prog prefix)
- structural errors → stderr ``{prog}: {msg}``, 2 (one line per error)
- ``{prog}: {msg}`` for file/IO errors and rejected ``add`` input, 2
- lessons ``init``/``add``/``sync``/``check``/``next-id`` messages → stdout, 0
- rmf ``build`` → stdout ``{outdir}: RMF bundle written (N of M controls satisfied)``, 0;
  missing repo or uncreatable outdir → stderr ``securetrace: {msg}``, 2
"""

from __future__ import annotations

import datetime
import shutil
from pathlib import Path

import pytest

import securetrace
from securetrace import cli
from securetrace.__main__ import main
from securetrace.lessons import record

BACKLOG_FIXTURE = """\
# Backlog

<!-- INDEX:BEGIN format=tsv version=1 -->
<!-- placeholder interior line -->
<!-- INDEX:END -->

<!-- BACKLOG:HEADER -->
## Status

**Queue:** B1 | **In progress:** — | **Done:** —

<!-- BACKLOG:QUEUE -->
## Queue (execution order)

1. **B1** (High) — bootstrap the project

<!-- BACKLOG:ITEM:B1 -->
## B1. Bootstrap — **OPEN**

- **Source:** user
- **Priority:** High

<!-- BACKLOG:CONSTRAINTS -->
## Standing constraints

- no bypassing gates
"""

ALGORITHM_FIXTURE = """\
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
"""


def write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def lesson(**overrides: object) -> record.NewLesson:
    kwargs: dict = {
        "title": "First lesson",
        "context": "ctx A",
        "pitfall": "pit A",
        "solution": "sol A",
        "recorded": "2026-10-18",
    }
    kwargs.update(overrides)
    return record.NewLesson(**kwargs)  # type: ignore[arg-type]


# --- backlog: check / sync ----------------------------------------------------


def test_backlog_check_ok(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    p = write(tmp_path / "BACKLOG.md", BACKLOG_FIXTURE)
    assert cli.run_backlog_sync(p, prog="build_backlog_index") == 0
    assert cli.run_backlog_check(p, prog="build_backlog_index") == 0
    out = capsys.readouterr().out
    assert f"{p}: index OK (5 entries)" in out


def test_backlog_check_stale_exit1_no_prefix(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = write(tmp_path / "BACKLOG.md", BACKLOG_FIXTURE)
    assert cli.run_backlog_check(p, prog="build_backlog_index") == 1
    err = capsys.readouterr().err
    assert err == f"{p}: index STALE -- rerun without --check\n"


def test_backlog_sync_writes_and_reports(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = write(tmp_path / "BACKLOG.md", BACKLOG_FIXTURE)
    assert cli.run_backlog_sync(p, prog="build_backlog_index") == 0
    out = capsys.readouterr().out
    assert f"{p}: index updated (5 entries)" in out
    assert "B1\tBootstrap\tOPEN\tLow" in p.read_text(encoding="utf-8")


def test_backlog_sync_idempotent_second_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = write(tmp_path / "BACKLOG.md", BACKLOG_FIXTURE)
    cli.run_backlog_sync(p, prog="build_backlog_index")
    capsys.readouterr()
    assert cli.run_backlog_sync(p, prog="build_backlog_index") == 0
    assert f"{p}: index updated (5 entries)" in capsys.readouterr().out


def test_backlog_structural_error_exit2_with_prog(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = write(tmp_path / "BAD.md", "# Backlog\n\nno markers at all\n")
    assert cli.run_backlog_check(p, prog="build_backlog_index") == 2
    err = capsys.readouterr().err
    assert err == (
        "build_backlog_index: missing <!-- INDEX:BEGIN --> / <!-- INDEX:END --> markers\n"
    )


def test_backlog_missing_file_exit2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    p = tmp_path / "NOPE.md"
    assert cli.run_backlog_sync(p, prog="build_backlog_index") == 2
    err = capsys.readouterr().err
    assert err.startswith("build_backlog_index: cannot read ")
    assert "NOPE.md" in err


# --- algorithms: check / sync -------------------------------------------------


def test_algorithm_roundtrip(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    p = write(tmp_path / "doc.md", ALGORITHM_FIXTURE)
    assert cli.run_algorithm_sync(p, prog="build_index") == 0
    assert f"{p}: index updated (3 entries)" in capsys.readouterr().out
    assert cli.run_algorithm_check(p, prog="build_index") == 0
    assert f"{p}: index OK (3 entries)" in capsys.readouterr().out


def test_algorithm_stale_then_resync(tmp_path: Path) -> None:
    p = write(tmp_path / "doc.md", ALGORITHM_FIXTURE)
    cli.run_algorithm_sync(p, prog="build_index")
    p.write_text(ALGORITHM_FIXTURE + "\nnew theory line\n", encoding="utf-8")
    assert cli.run_algorithm_check(p, prog="build_index") == 1
    assert cli.run_algorithm_sync(p, prog="build_index") == 0
    assert cli.run_algorithm_check(p, prog="build_index") == 0


def test_algorithm_structural_error_exit2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = write(tmp_path / "BAD.md", "# D\n\nno markers\n")
    assert cli.run_algorithm_sync(p, prog="build_index") == 2
    assert (
        capsys.readouterr().err
        == "build_index: missing <!-- INDEX:BEGIN --> / <!-- INDEX:END --> markers\n"
    )


# --- lessons: init -------------------------------------------------------------


def test_lessons_init_creates_template(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    p = tmp_path / "LESSONS_LEARNED.md"
    assert cli.run_lessons_init(p, force=False, prog="manage_lessons") == 0
    assert f"init: created {p}" in capsys.readouterr().out
    assert "<!-- LLT:INDEX:BEGIN -->" in p.read_text(encoding="utf-8")


def test_lessons_init_existing_llt_file_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = tmp_path / "LESSONS_LEARNED.md"
    cli.run_lessons_init(p, force=False, prog="manage_lessons")
    capsys.readouterr()
    before = p.read_text(encoding="utf-8")
    assert cli.run_lessons_init(p, force=False, prog="manage_lessons") == 0
    assert f"init: {p} already initialized (0 lessons); nothing to do" in capsys.readouterr().out
    assert p.read_text(encoding="utf-8") == before


def test_lessons_init_non_llt_file_refused_without_force(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = write(tmp_path / "README.md", "just a readme\n")
    assert cli.run_lessons_init(p, force=False, prog="manage_lessons") == 2
    err = capsys.readouterr().err
    assert err == (
        f"manage_lessons: {p} exists but is not a LESSONS_LEARNED.md file; "
        "refusing to overwrite. Re-run with --force to replace it.\n"
    )
    assert p.read_text(encoding="utf-8") == "just a readme\n"


def test_lessons_init_non_llt_file_replaced_with_force(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = write(tmp_path / "README.md", "just a readme\n")
    assert cli.run_lessons_init(p, force=True, prog="manage_lessons") == 0
    assert f"init: replaced non-LLT file at {p} with template (--force)" in capsys.readouterr().out
    assert "<!-- LLT:INDEX:BEGIN -->" in p.read_text(encoding="utf-8")


def test_lessons_init_broken_llt_skeleton_never_overwritten(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # An LLT file (has the markers) is never overwritten — even with --force.
    p = write(
        tmp_path / "LESSONS_LEARNED.md",
        "# Lessons Learned\n\n"
        "<!-- LLT:INDEX:BEGIN -->\n"
        "<!-- LLT:INDEX:END -->\n"
        "\n"
        "<!-- LLT:ENTRY:LLT-0001 -->\n"
        "## LLT-0001 — T\n\n"
        "- **Recorded:** 2026-10-18\n",
    )
    before = p.read_text(encoding="utf-8")
    assert cli.run_lessons_init(p, force=True, prog="manage_lessons") == 2
    assert "manage_lessons: index block is empty or malformed (G8)\n" in capsys.readouterr().err
    assert p.read_text(encoding="utf-8") == before


def test_lessons_init_invalid_llt_file_prints_each_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = write(
        tmp_path / "LESSONS_LEARNED.md",
        "# Lessons Learned\n\n"
        "<!-- LLT:INDEX:BEGIN -->\n"
        "id\ttitle\tcategory\tseverity\tstatus\trecorded\tstart_line\tend_line\n"
        "LLT_INDEX_BLOCK\t—\t—\t—\t—\t—\t3\t5\n"
        "<!-- LLT:INDEX:END -->\n"
        "\n"
        "<!-- LLT:ENTRY:LLT-0001 -->\n"
        "## LLT-0001 — T\n\n"
        "- **Recorded:** 2026-10-18\n",
    )
    before = p.read_text(encoding="utf-8")
    assert cli.run_lessons_init(p, force=False, prog="manage_lessons") == 2
    err = capsys.readouterr().err
    for field in ("Category", "Severity", "Status", "Context", "Pitfall", "Solution"):
        assert f"manage_lessons: entry LLT-0001: missing required field '{field}' (G6)\n" in err
    assert p.read_text(encoding="utf-8") == before


# --- lessons: add ---------------------------------------------------------------


def test_lessons_add_happy_path(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    p = tmp_path / "LESSONS_LEARNED.md"
    cli.run_lessons_init(p, force=False, prog="manage_lessons")
    capsys.readouterr()
    assert cli.run_lessons_add(p, lesson(), prog="manage_lessons") == 0
    out = capsys.readouterr().out
    assert "add: recorded LLT-0001 — First lesson" in out
    assert f"add: index updated ({p})" in out
    assert cli.run_lessons_check(p, prog="manage_lessons") == 0
    assert f"check: {p} is valid (1 lesson recorded)" in capsys.readouterr().out


def test_lessons_add_missing_file_exit2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    p = tmp_path / "NOPE.md"
    assert cli.run_lessons_add(p, lesson(), prog="manage_lessons") == 2
    assert capsys.readouterr().err == f"manage_lessons: {p} does not exist; run `init` first\n"


def test_lessons_add_rejected_input_exit2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = tmp_path / "LESSONS_LEARNED.md"
    cli.run_lessons_init(p, force=False, prog="manage_lessons")
    capsys.readouterr()
    assert cli.run_lessons_add(p, lesson(title=""), prog="manage_lessons") == 2
    assert (
        capsys.readouterr().err
        == "manage_lessons: --title is required and must be non-empty (G6)\n"
    )


def test_lessons_add_supersede(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    p = tmp_path / "LESSONS_LEARNED.md"
    cli.run_lessons_init(p, force=False, prog="manage_lessons")
    cli.run_lessons_add(p, lesson(), prog="manage_lessons")
    capsys.readouterr()
    replacement = lesson(
        title="Second lesson",
        context="ctx B",
        pitfall="pit B",
        solution="sol B",
        supersedes="LLT-0001",
    )
    assert cli.run_lessons_add(p, replacement, prog="manage_lessons") == 0
    out = capsys.readouterr().out
    assert "add: recorded LLT-0002 — Second lesson" in out
    text = p.read_text(encoding="utf-8")
    assert text.count("- **Status:** superseded") == 1
    assert "- **Supersedes:** LLT-0001" in text
    assert cli.run_lessons_check(p, prog="manage_lessons") == 0


# --- lessons: sync / check / next-id ---------------------------------------------


def test_lessons_sync_noop(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    p = tmp_path / "LESSONS_LEARNED.md"
    cli.run_lessons_init(p, force=False, prog="manage_lessons")
    capsys.readouterr()
    assert cli.run_lessons_sync(p, prog="manage_lessons") == 0
    assert f"sync: index already current ({p})" in capsys.readouterr().out


def test_lessons_check_stale_exit1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    p = tmp_path / "LESSONS_LEARNED.md"
    cli.run_lessons_init(p, force=False, prog="manage_lessons")
    cli.run_lessons_add(p, lesson(), prog="manage_lessons")
    capsys.readouterr()
    text = p.read_text(encoding="utf-8")
    p.write_text(text.replace("- **Severity:** medium", "- **Severity:** high"), encoding="utf-8")
    assert cli.run_lessons_check(p, prog="manage_lessons") == 1
    assert (
        capsys.readouterr().err
        == f"manage_lessons: {p}: index is stale; run `sync` to regenerate\n"
    )


def test_lessons_next_id(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    p = tmp_path / "LESSONS_LEARNED.md"
    cli.run_lessons_init(p, force=False, prog="manage_lessons")
    capsys.readouterr()
    assert cli.run_lessons_next_id(p, prog="manage_lessons") == 0
    assert capsys.readouterr().out == "LLT-0001\n"
    cli.run_lessons_add(p, lesson(), prog="manage_lessons")
    capsys.readouterr()
    assert cli.run_lessons_next_id(p, prog="manage_lessons") == 0
    assert capsys.readouterr().out == "LLT-0002\n"


def test_lessons_sync_missing_file_exit2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = tmp_path / "NOPE.md"
    assert cli.run_lessons_sync(p, prog="manage_lessons") == 2
    assert capsys.readouterr().err == f"manage_lessons: {p} does not exist; run `init` first\n"


def test_lessons_check_missing_file_exit2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = tmp_path / "NOPE.md"
    assert cli.run_lessons_check(p, prog="manage_lessons") == 2
    assert capsys.readouterr().err == f"manage_lessons: {p} does not exist; run `init` first\n"


# --- __main__ dispatch -------------------------------------------------------------
# WI 8: the legacy md-file dispatch tests (backlog sync / lessons next-id /
# algorithms check / legacy lessons add) were retired when __main__ was
# re-pointed at the store-based surface in securetrace.cli_docs; the new
# dispatch contract is pinned in tests/test_cli_docs.py.


def test_main_no_subcommand_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main([])
    assert excinfo.value.code == 2
    assert "usage:" in capsys.readouterr().err


def test_main_version_exits_0(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    assert securetrace.__version__ in capsys.readouterr().out


def test_main_unknown_subcommand_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["bogus"])
    assert excinfo.value.code == 2
    assert "invalid choice" in capsys.readouterr().err


# --- rmf: build ---------------------------------------------------------------

RMF_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "rmf" / "mini-repo"


def _copy_rmf_repo(tmp_path: Path) -> Path:
    dst = tmp_path / "repo"
    shutil.copytree(RMF_FIXTURE, dst)
    return dst


def test_rmf_build_writes_bundle(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = _copy_rmf_repo(tmp_path)
    out = tmp_path / "bundle"
    assert cli.run_rmf_build(repo, out) == 0
    for name in ("SSP.md", "SAP.md", "SAR.md", "POAM.md", "manifest.json"):
        assert (out / name).is_file(), name
    assert (out / "evidence" / "BACKLOG.md").is_file()
    captured = capsys.readouterr()
    assert captured.out == f"{out}: RMF bundle written (11 of 11 controls satisfied)\n"
    assert captured.err == ""


def test_rmf_build_missing_repo_exit2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    missing = tmp_path / "nope"
    assert cli.run_rmf_build(missing, tmp_path / "bundle") == 2
    err = capsys.readouterr().err
    assert err == f"securetrace: {missing}: repository root is missing or not a directory\n"


def test_rmf_build_uncreatable_outdir_exit2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _copy_rmf_repo(tmp_path)
    blocker = tmp_path / "blocker"
    blocker.write_text("a file, not a directory\n", encoding="utf-8")
    assert cli.run_rmf_build(repo, blocker / "bundle") == 2
    err = capsys.readouterr().err
    assert err.startswith("securetrace: cannot create "), err


def test_rmf_build_default_outdir_is_artifacts_rmf_today(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workdir = tmp_path / "work"
    workdir.mkdir()
    repo = workdir / "repo"
    shutil.copytree(RMF_FIXTURE, repo)
    monkeypatch.chdir(workdir)
    assert cli.run_rmf_build(repo) == 0
    today = datetime.date.today().isoformat()
    out = workdir / "artifacts" / "rmf" / today
    assert (out / "manifest.json").is_file()
    assert (out / "evidence" / "BACKLOG.md").is_file()
    capsys.readouterr()


def test_main_dispatch_rmf_build(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = _copy_rmf_repo(tmp_path)
    out = tmp_path / "bundle2"
    assert main(["rmf", "build", str(repo), "--outdir", str(out)]) == 0
    assert (out / "SSP.md").is_file()
    assert "11 of 11 controls satisfied" in capsys.readouterr().out
