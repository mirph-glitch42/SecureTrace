#!/usr/bin/env python3
"""Manage a machine-readable LESSONS_LEARNED.md lessons record.

Thin wrapper over :mod:`securetrace.cli` (pure core:
:mod:`securetrace.lessons.record`; spec: ``algorithms/lessons-record.md``).
The CLI surface, messages, and exit codes are pinned:

Exit codes: 0 = ok, 1 = stale index, 2 = malformed file or rejected input.

Usage:
    python3 scripts/manage_lessons.py init <file> [--force]
    python3 scripts/manage_lessons.py add <file> --title … --context … --pitfall … --solution …
    python3 scripts/manage_lessons.py sync <file>
    python3 scripts/manage_lessons.py check <file>
    python3 scripts/manage_lessons.py next-id <file>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))  # noqa: E402

from securetrace import cli  # noqa: E402
from securetrace.lessons import record  # noqa: E402

PROG = "manage_lessons"


def _init(args: argparse.Namespace) -> int:
    return cli.run_lessons_init(Path(args.file), force=args.force, prog=PROG)


def _add(args: argparse.Namespace) -> int:
    lesson = record.NewLesson(
        title=args.title,
        context=args.context,
        pitfall=args.pitfall,
        solution=args.solution,
        id=args.id,
        category=args.category,
        severity=args.severity,
        recorded=args.recorded,
        supersedes=args.supersedes,
        prevention=args.prevention,
        references=args.references,
    )
    return cli.run_lessons_add(Path(args.file), lesson, prog=PROG)


def _sync(args: argparse.Namespace) -> int:
    return cli.run_lessons_sync(Path(args.file), prog=PROG)


def _check(args: argparse.Namespace) -> int:
    return cli.run_lessons_check(Path(args.file), prog=PROG)


def _next_id(args: argparse.Namespace) -> int:
    return cli.run_lessons_next_id(Path(args.file), prog=PROG)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog=PROG,
        description="Manage a machine-readable LESSONS_LEARNED.md lessons record.",
        epilog="Exit codes: 0 = ok, 1 = stale index, 2 = malformed file or rejected input.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("init", help="create a new LESSONS_LEARNED.md")
    sp.add_argument("file")
    sp.add_argument(
        "--force", action="store_true", help="replace an existing non-LLT file with the template"
    )
    sp.set_defaults(func=_init)

    sp = sub.add_parser("add", help="record a new lesson and update the index")
    sp.add_argument("file")
    sp.add_argument("--title", required=True)
    sp.add_argument("--context", required=True)
    sp.add_argument("--pitfall", required=True)
    sp.add_argument("--solution", required=True)
    sp.add_argument(
        "--id", default=None, help="explicit LLT-NNNN id (must be unused and greater than the max)"
    )
    sp.add_argument("--category", default="other", help="one of: " + ", ".join(record.CATEGORIES))
    sp.add_argument("--severity", default="medium", help="one of: " + ", ".join(record.SEVERITIES))
    sp.add_argument("--recorded", default=None, help="YYYY-MM-DD (default: today)")
    sp.add_argument(
        "--supersedes",
        default=None,
        help="LLT-NNNN of the lesson this one replaces (flips its status)",
    )
    sp.add_argument("--prevention", default=None)
    sp.add_argument("--references", default=None)
    sp.set_defaults(func=_add)

    sp = sub.add_parser("sync", help="regenerate the index block from the entries")
    sp.add_argument("file")
    sp.set_defaults(func=_sync)

    sp = sub.add_parser("check", help="validate structure, fields, and index freshness")
    sp.add_argument("file")
    sp.set_defaults(func=_check)

    sp = sub.add_parser("next-id", help="print the next LLT-NNNN id")
    sp.add_argument("file")
    sp.set_defaults(func=_next_id)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
