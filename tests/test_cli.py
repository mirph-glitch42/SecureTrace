"""Behavioral tests for the ``securetrace rmf`` command layer and CLI dispatch.

These pin the exact user-visible contract of ``securetrace.cli`` (the RMF
bundle surface: messages, streams, exit codes) and the ``securetrace``
console entrypoint (``securetrace.__main__:main``).

Conventions (pinned):
- rmf ``build`` → stdout ``{outdir}: RMF bundle written (N of M controls
  satisfied)``, 0; missing repo or uncreatable outdir → stderr
  ``securetrace: {msg}``, 2
- ``main`` dispatch: no subcommand / unknown subcommand → ``SystemExit`` 2
  with argparse usage on stderr; ``--version`` → ``SystemExit`` 0 with the
  version on stdout.

The store-based document verbs (``backlog`` / ``lessons`` / ``algorithms`` /
``docs`` / ``migrate``) and their message/exit contracts are pinned in
``tests/test_cli_docs.py``; the legacy md-file surface (``backlog sync`` /
``lessons init|add|sync|check|next-id`` / ``algorithms sync|check``) was
retired in B10 WI 10 along with the ``scripts/backlog_index.py`` and
``scripts/manage_lessons.py`` wrappers it wrapped.
"""

from __future__ import annotations

import datetime
import shutil
from pathlib import Path

import pytest

import securetrace
from securetrace import cli
from securetrace.__main__ import main

# --- __main__ dispatch -------------------------------------------------------------
# The legacy md-file dispatch tests (backlog sync / lessons next-id /
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
