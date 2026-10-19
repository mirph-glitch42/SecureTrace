#!/usr/bin/env python3
"""Regenerate (or check) the line index of a BACKLOG.md.

Thin wrapper over :mod:`securetrace.cli` (pure core:
:mod:`securetrace.backlog.index`; spec: ``algorithms/line-index-sync.md``).
The CLI surface, messages, and exit codes are pinned:

Exit codes: 0 = ok (or index written), 1 = index stale (--check),
2 = malformed file (missing/duplicate markers, reserved ids, no items).

Usage:
    python3 scripts/backlog_index.py <backlog.md>          # rewrite the index in place
    python3 scripts/backlog_index.py <backlog.md> --check  # verify only; exit 1 if stale
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))  # noqa: E402

from securetrace import cli  # noqa: E402

PROG = "build_backlog_index"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog=PROG, description="Regenerate the line index of a BACKLOG.md."
    )
    ap.add_argument("backlog", help="path to BACKLOG.md")
    ap.add_argument(
        "--check", action="store_true", help="verify the index is current; exit 1 if stale"
    )
    args = ap.parse_args(argv)
    path = Path(args.backlog)
    if args.check:
        return cli.run_backlog_check(path, prog=PROG)
    return cli.run_backlog_sync(path, prog=PROG)


if __name__ == "__main__":
    sys.exit(main())
