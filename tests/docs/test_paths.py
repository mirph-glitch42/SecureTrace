"""Path-containment tests for CLI-supplied paths (S8707 trust boundary).

The CLI is the trust boundary (C4, ALRK v0.1.6): every user-supplied path —
``<store>``, ``--doc``, ``--manifest``, ``migrate <doc>`` — must resolve
inside the workspace base (the current working directory by default) before
any file I/O. ``docs.paths.resolve_within`` performs the containment check;
the command layer surfaces a rejected path as exit 2 with the pinned
``securetrace:`` stderr prefix (CC-001), before any read or write happens.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from securetrace.cli_docs import (
    run_algorithms_show,
    run_backlog_show,
    run_check_all,
    run_lessons_show,
    run_migrate,
    run_render,
    run_render_all,
)
from securetrace.docs.paths import PathEscapeError, resolve_within

ESCAPE_MSG = "escapes the workspace base"


# ------------------------------------------------------------- resolve_within


def test_relative_inside_base_is_allowed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert resolve_within("data/backlog.json") == Path("data/backlog.json")


def test_relative_is_returned_as_given(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert resolve_within("data/../backlog.json") == Path("data/../backlog.json")


def test_dot_resolves_to_the_base(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert resolve_within(".").resolve() == tmp_path.resolve()


def test_relative_escape_is_rejected(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(PathEscapeError, match=ESCAPE_MSG):
        resolve_within("../outside.json")


def test_absolute_outside_base_is_rejected(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    outside = tmp_path.parent / "outside.json"
    with pytest.raises(PathEscapeError, match=ESCAPE_MSG):
        resolve_within(outside)


def test_absolute_inside_base_is_allowed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    inside = tmp_path / "data" / "backlog.json"
    assert resolve_within(inside) == inside.resolve()


def test_base_parameter_overrides_the_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    base = tmp_path / "sub"
    assert resolve_within("a.json", base=base) == Path("a.json")
    with pytest.raises(PathEscapeError, match=ESCAPE_MSG):
        resolve_within("../outside.json", base=base)


def test_error_names_the_base():
    err = None
    try:
        resolve_within("/definitely/not/inside", base="/somewhere/base")
    except PathEscapeError as exc:
        err = str(exc)
    assert err is not None
    assert "/somewhere/base" in err
    assert "CLI paths must stay inside the working directory" in err


# ------------------------------------------------------------- CLI enforcement


def test_backlog_show_rejects_store_escape(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    code = run_backlog_show("../outside.json")
    err = capsys.readouterr().err
    assert code == 2
    assert err.startswith("securetrace:")
    assert ESCAPE_MSG in err


def test_lessons_show_rejects_store_escape(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    code = run_lessons_show("../outside.json")
    err = capsys.readouterr().err
    assert code == 2
    assert ESCAPE_MSG in err


def test_algorithms_show_rejects_store_escape(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    code = run_algorithms_show("../outside.json")
    err = capsys.readouterr().err
    assert code == 2
    assert ESCAPE_MSG in err


def test_render_rejects_manifest_escape(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    code = run_render("backlog", "data/backlog.json", manifest_path="../outside.json")
    err = capsys.readouterr().err
    assert code == 2
    assert ESCAPE_MSG in err


def test_render_rejects_doc_escape(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    code = run_render("backlog", "data/backlog.json", doc_path="../outside.md")
    err = capsys.readouterr().err
    assert code == 2
    assert ESCAPE_MSG in err


def test_render_all_rejects_manifest_escape(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    code = run_render_all(manifest_path="../outside.json")
    err = capsys.readouterr().err
    assert code == 2
    assert ESCAPE_MSG in err


def test_check_all_rejects_manifest_escape(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    code = run_check_all(manifest_path="../outside.json")
    err = capsys.readouterr().err
    assert code == 2
    assert ESCAPE_MSG in err


def test_migrate_rejects_doc_escape(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    code = run_migrate("../outside.md")
    err = capsys.readouterr().err
    assert code == 2
    assert ESCAPE_MSG in err


def test_migrate_rejects_store_escape(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    code = run_migrate("BACKLOG.md", store_path="../outside.json")
    err = capsys.readouterr().err
    assert code == 2
    assert ESCAPE_MSG in err


def test_migrate_rejects_manifest_escape(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    code = run_migrate("BACKLOG.md", manifest_path="../outside.json")
    err = capsys.readouterr().err
    assert code == 2
    assert ESCAPE_MSG in err
