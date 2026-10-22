#!/usr/bin/env python3
"""Regenerate (or check) the line index of an algorithm document.

Self-contained wrapper over the pure core
(:mod:`securetrace.algorithms.registry`; spec:
``algorithms/line-index-sync.md``). The CLI surface, messages, and exit
codes are pinned:

Exit codes: 0 = ok (or index written), 1 = index stale (--check),
2 = malformed file (missing/duplicate markers, no sections).

- ``{path}: index OK (N entries)`` / ``{path}: index updated (N entries)`` → stdout, 0
- ``{path}: index STALE -- rerun without --check`` → stderr, 1 (no prog prefix)
- structural/semantic errors → stderr ``{prog}: {msg}`` (one line each), 2

Usage:
    python3 scripts/algorithm_index.py <doc.md>          # rewrite the index in place
    python3 scripts/algorithm_index.py <doc.md> --check  # verify only; exit 1 if stale
"""

from __future__ import annotations

import argparse
import contextlib
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))  # noqa: E402

from securetrace.algorithms import registry  # noqa: E402
from securetrace.errors import FormatError  # noqa: E402

PROG = "build_index"


def _read_text(path: Path) -> str:
    """Read a UTF-8 text file (FormatError on OSError / non-UTF-8)."""
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


def check(path: Path, prog: str = PROG) -> int:
    """Verify the index block is current.

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


def sync(path: Path, prog: str = PROG) -> int:
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog=PROG, description="Regenerate the line index of an algorithm document."
    )
    ap.add_argument("doc", help="path to the algorithm document")
    ap.add_argument(
        "--check", action="store_true", help="verify the index is current; exit 1 if stale"
    )
    args = ap.parse_args(argv)
    path = Path(args.doc)
    if args.check:
        return check(path, prog=PROG)
    return sync(path, prog=PROG)


if __name__ == "__main__":
    sys.exit(main())
