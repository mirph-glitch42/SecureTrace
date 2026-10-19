"""Command layer for ``securetrace``: file I/O, user-facing messages, exit codes.

Each ``run_*`` function takes a path and a ``prog`` prefix and returns the
process exit code (``0`` ok, ``1`` stale index, ``2`` malformed file or
rejected input). The pure core (``securetrace.backlog.index``,
``securetrace.algorithms.registry``, ``securetrace.lessons.record``) raises
``FormatError``/``InvalidInput``; this layer turns those into the pinned
stdout/stderr messages.

Pinned messages (mirrored exactly from the historical scripts, whose prog
prefixes are ``build_backlog_index`` / ``build_index`` / ``manage_lessons``;
the ``securetrace`` CLI passes ``prog="securetrace"``):

- ``{path}: index OK (N entries)`` / ``{path}: index updated (N entries)`` → stdout, 0
- ``{path}: index STALE -- rerun without --check`` → stderr, 1 (no prog prefix)
- structural/semantic errors → stderr ``{prog}: {msg}`` (one line each), 2
- ``{prog}: {msg}`` for file/IO errors and rejected ``add`` input, 2
"""

from __future__ import annotations

import contextlib
import datetime
import os
import sys
import tempfile
from pathlib import Path

from securetrace.algorithms import registry
from securetrace.backlog import index as backlog_index
from securetrace.errors import FormatError, InvalidInput
from securetrace.lessons import record
from securetrace.rmf import deliverables

__all__ = [
    "run_algorithm_check",
    "run_algorithm_sync",
    "run_backlog_check",
    "run_backlog_sync",
    "run_lessons_add",
    "run_lessons_check",
    "run_lessons_init",
    "run_lessons_next_id",
    "run_lessons_sync",
    "run_rmf_build",
]

PROG = "securetrace"


def _read_text(path: Path) -> str:
    """Read a UTF-8 text file.

    Raises:
        FormatError: the file cannot be read (OSError) or is not UTF-8.
    """
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise FormatError(f"cannot read {path}: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise FormatError(f"{path} is not UTF-8 text: {exc}") from exc


def _write_text(path: Path, text: str) -> None:
    """Atomically replace ``path`` with ``text`` (temp file + ``os.replace``)."""
    directory = os.path.dirname(os.path.abspath(str(path)))
    tmp: str | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=directory, delete=False) as fh:
            tmp = fh.name
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        if tmp is not None:
            with contextlib.suppress(OSError):
                os.unlink(tmp)
        raise


def _fail(prog: str, msg: str) -> int:
    """Print ``{prog}: {msg}`` to stderr; the caller returns the exit code."""
    print(f"{prog}: {msg}", file=sys.stderr)
    return 2


def _stale(path: Path) -> int:
    """Print the pinned stale-index message (no prog prefix); the caller returns 1."""
    print(f"{path}: index STALE -- rerun without --check", file=sys.stderr)
    return 1


def _missing_file(path: Path, prog: str) -> int:
    return _fail(prog, f"{path} does not exist; run `init` first")


def _print_lesson_errors(errors: list[str], prog: str) -> int:
    """Print one ``{prog}: {error}`` line per finding; the caller returns 2."""
    for error in errors:
        print(f"{prog}: {error}", file=sys.stderr)
    return 2


def _guard_lessons(text: str, prog: str) -> list[str] | int:
    """Run the lessons structural guards.

    Returns the (empty when clean) list of entry-level findings to print, or
    the failure exit code after printing: a broken skeleton (FormatError)
    prints one line; entry-level findings print one line each.
    """
    try:
        return record.structural_errors(text)
    except FormatError as exc:
        return _fail(prog, str(exc))


def _finish_lessons_guard(findings: list[str] | int, prog: str) -> int | None:
    """Finish a :func:`_guard_lessons` failure; ``None`` means the record is clean."""
    if isinstance(findings, int):
        return findings
    if findings:
        return _print_lesson_errors(findings, prog)
    return None


# --- backlog -------------------------------------------------------------------


def run_backlog_check(path: Path, prog: str = PROG) -> int:
    """Verify the BACKLOG.md index is current.

    Returns:
        0: index fresh (``{path}: index OK (N entries)`` on stdout)
        1: index stale (``{path}: index STALE -- rerun without --check`` on stderr)
        2: unreadable file or structural error (``{prog}: …`` on stderr)
    """
    path = Path(path)
    try:
        text = _read_text(path)
        rows = backlog_index.index_rows(text)
    except FormatError as exc:
        return _fail(prog, str(exc))
    if backlog_index.is_fresh(text):
        print(f"{path}: index OK ({len(rows)} entries)")
        return 0
    return _stale(path)


def run_backlog_sync(path: Path, prog: str = PROG) -> int:
    """Rewrite the BACKLOG.md index block in place (idempotent).

    Returns:
        0: index written (``{path}: index updated (N entries)`` on stdout)
        2: unreadable file or structural error (``{prog}: …`` on stderr)
    """
    path = Path(path)
    try:
        text = _read_text(path)
        rows = backlog_index.index_rows(text)
        new_text = backlog_index.synced_text(text)
    except FormatError as exc:
        return _fail(prog, str(exc))
    _write_text(path, new_text)
    print(f"{path}: index updated ({len(rows)} entries)")
    return 0


# --- algorithms ------------------------------------------------------------------


def run_algorithm_check(path: Path, prog: str = PROG) -> int:
    """Verify the algorithm document index is current.

    Returns:
        0: index fresh (``{path}: index OK (N entries)`` on stdout)
        1: index stale (``{path}: index STALE -- rerun without --check`` on stderr)
        2: unreadable file or structural error (``{prog}: …`` on stderr)
    """
    path = Path(path)
    try:
        text = _read_text(path)
        rows = registry.index_rows(text)
    except FormatError as exc:
        return _fail(prog, str(exc))
    if registry.is_fresh(text):
        print(f"{path}: index OK ({len(rows)} entries)")
        return 0
    return _stale(path)


def run_algorithm_sync(path: Path, prog: str = PROG) -> int:
    """Rewrite the algorithm document index block in place (idempotent).

    Returns:
        0: index written (``{path}: index updated (N entries)`` on stdout)
        2: unreadable file or structural error (``{prog}: …`` on stderr)
    """
    path = Path(path)
    try:
        text = _read_text(path)
        rows = registry.index_rows(text)
        new_text = registry.synced_text(text)
    except FormatError as exc:
        return _fail(prog, str(exc))
    _write_text(path, new_text)
    print(f"{path}: index updated ({len(rows)} entries)")
    return 0


# --- lessons ----------------------------------------------------------------------


def run_lessons_init(path: Path, force: bool = False, prog: str = PROG) -> int:
    """Create a new LESSONS_LEARNED.md, or report an existing one.

    A file without the LLT markers is a "non-LLT file": refused without
    ``--force``, replaced with the template with ``--force``. A file *with*
    the markers is an LLT record: never overwritten (lessons are data); its
    structure is validated and any findings reported.

    Returns:
        0: created / replaced (``--force``) / already initialized
        2: refused non-LLT overwrite, or structural findings (one stderr line each)
    """
    path = Path(path)
    if not path.exists():
        _write_text(path, record.build_template())
        print(f"init: created {path}")
        return 0
    try:
        text = _read_text(path)
        begin, _end = record.find_index_block(text.split("\n"))
    except FormatError as exc:
        return _fail(prog, str(exc))
    if begin is None:
        if not force:
            return _fail(
                prog,
                f"{path} exists but is not a LESSONS_LEARNED.md file; "
                "refusing to overwrite. Re-run with --force to replace it.",
            )
        _write_text(path, record.build_template())
        print(f"init: replaced non-LLT file at {path} with template (--force)")
        return 0
    # An LLT record is never overwritten, even with --force: lessons are data.
    findings = _guard_lessons(text, prog)
    code = _finish_lessons_guard(findings, prog)
    if code is not None:
        return code
    entries, _ = record.parse_entries(text.split("\n"))
    n = len(entries)
    print(f"init: {path} already initialized ({n} lesson{'s' if n != 1 else ''}); nothing to do")
    return 0


def run_lessons_add(path: Path, lesson: record.NewLesson, prog: str = PROG) -> int:
    """Append ``lesson`` to the record and rewrite its index block.

    Returns:
        0: recorded (``add: recorded LLT-NNNN — <title>`` on stdout)
        2: missing file, structural findings, or rejected input (``{prog}: …`` on stderr)
    """
    path = Path(path)
    if not path.exists():
        return _missing_file(path, prog)
    try:
        text = _read_text(path)
    except FormatError as exc:
        return _fail(prog, str(exc))
    findings = _guard_lessons(text, prog)
    code = _finish_lessons_guard(findings, prog)
    if code is not None:
        return code
    today = datetime.date.today().isoformat()
    try:
        result = record.add_lesson(text, lesson, today=today)
    except InvalidInput as exc:
        return _fail(prog, str(exc))
    except FormatError as exc:
        return _fail(prog, str(exc))
    _write_text(path, result.new_text)
    print(f"add: recorded {result.entry_id} — {lesson.title}")
    print(f"add: index updated ({path})")
    return 0


def run_lessons_sync(path: Path, prog: str = PROG) -> int:
    """Regenerate the record's index block from its entries.

    Returns:
        0: already current (``sync: index already current ({path})``) or
            regenerated (``sync: index regenerated ({path})``)
        2: missing file, structural findings, or broken skeleton (``{prog}: …`` on stderr)
    """
    path = Path(path)
    if not path.exists():
        return _missing_file(path, prog)
    try:
        text = _read_text(path)
    except FormatError as exc:
        return _fail(prog, str(exc))
    findings = _guard_lessons(text, prog)
    code = _finish_lessons_guard(findings, prog)
    if code is not None:
        return code
    try:
        new_text = record.regenerate(text)
    except FormatError as exc:
        return _fail(prog, str(exc))
    if new_text == text:
        print(f"sync: index already current ({path})")
        return 0
    _write_text(path, new_text)
    print(f"sync: index regenerated ({path})")
    return 0


def run_lessons_check(path: Path, prog: str = PROG) -> int:
    """Validate the record: structure, fields, cross-entry invariants, index freshness.

    Returns:
        0: valid (``check: {path} is valid (N lesson[s] recorded)`` on stdout)
        1: index stale (``{prog}: {path}: index is stale; run `sync` to regenerate`` on stderr)
        2: missing file, structural findings, or broken skeleton (``{prog}: …`` on stderr)
    """
    path = Path(path)
    if not path.exists():
        return _missing_file(path, prog)
    try:
        text = _read_text(path)
    except FormatError as exc:
        return _fail(prog, str(exc))
    findings = _guard_lessons(text, prog)
    code = _finish_lessons_guard(findings, prog)
    if code is not None:
        return code
    if not record.index_is_fresh(text):
        # Pinned: stale index exits 1 (not 2) — _fail would print the same
        # message but return 2, so this branch prints and returns directly.
        print(f"{prog}: {path}: index is stale; run `sync` to regenerate", file=sys.stderr)
        return 1
    entries, _ = record.parse_entries(text.split("\n"))
    n = len(entries)
    print(f"check: {path} is valid ({n} lesson{'s' if n != 1 else ''} recorded)")
    return 0


def run_lessons_next_id(path: Path, prog: str = PROG) -> int:
    """Print the next available LLT id (``LLT-NNNN``) for the record.

    Returns:
        0: id printed on stdout
        2: missing file, structural findings, or broken skeleton (``{prog}: …`` on stderr)
    """
    path = Path(path)
    if not path.exists():
        return _missing_file(path, prog)
    try:
        text = _read_text(path)
    except FormatError as exc:
        return _fail(prog, str(exc))
    findings = _guard_lessons(text, prog)
    code = _finish_lessons_guard(findings, prog)
    if code is not None:
        return code
    entries, _ = record.parse_entries(text.split("\n"))
    print(record.next_id(entries))
    return 0


# --- rmf -----------------------------------------------------------------------


def run_rmf_build(repo: str | Path, outdir: str | Path | None = None, prog: str = PROG) -> int:
    """Build the deterministic RMF evidence bundle for ``repo`` (backlog B4).

    With no ``--outdir`` the bundle directory is ``artifacts/rmf/<YYYY-MM-DD>``
    relative to the current working directory — the only place a date appears
    (the bundle bytes themselves are clock-free, per the spec).

    Returns:
        0: bundle written (``{outdir}: RMF bundle written (N of M controls satisfied)`` on stdout)
        2: repo missing/not a directory, or outdir uncreatable (``{prog}: …`` on stderr)
    """
    if outdir is None:
        outdir = Path("artifacts") / "rmf" / datetime.date.today().isoformat()
    try:
        evidence = deliverables.collect_evidence(repo)
        bundle = deliverables.package(evidence, repo, outdir)
    except FormatError as exc:
        return _fail(prog, str(exc))
    except OSError as exc:
        return _fail(prog, f"cannot create {outdir}: {exc}")
    satisfied = sum(1 for control in evidence.controls if control.satisfied)
    total = len(evidence.controls)
    print(f"{bundle}: RMF bundle written ({satisfied} of {total} controls satisfied)")
    return 0
