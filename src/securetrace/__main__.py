"""``securetrace`` console entrypoint: argparse dispatch to ``securetrace.cli``.

Usage:
    securetrace backlog {check,sync} <file>
    securetrace lessons {init,add,sync,check,next-id} …
    securetrace algorithms {check,sync} <doc>

``main(argv)`` returns the process exit code for command-level failures
(0/1/2); argparse-level failures (missing subcommand, unknown subcommand,
``--version``) raise ``SystemExit`` through argparse.
"""

from __future__ import annotations

import argparse
import sys

from securetrace import __version__, cli
from securetrace.lessons import record


def _add_backlog(sub: argparse._SubParsersAction) -> None:
    sp = sub.add_parser("backlog", help="manage the BACKLOG.md line index")
    bsub = sp.add_subparsers(dest="backlog_command", required=True)
    bcheck = bsub.add_parser("check", help="verify the index is current; exit 1 if stale")
    bcheck.add_argument("file", help="path to BACKLOG.md")
    bsync = bsub.add_parser("sync", help="rewrite the index in place (idempotent)")
    bsync.add_argument("file", help="path to BACKLOG.md")


def _add_lessons(sub: argparse._SubParsersAction) -> None:
    sp = sub.add_parser("lessons", help="manage a LESSONS_LEARNED.md record")
    lsub = sp.add_subparsers(dest="lessons_command", required=True)

    linit = lsub.add_parser("init", help="create a new LESSONS_LEARNED.md")
    linit.add_argument("file")
    linit.add_argument(
        "--force", action="store_true", help="replace an existing non-LLT file with the template"
    )

    ladd = lsub.add_parser("add", help="record a new lesson and update the index")
    ladd.add_argument("file")
    ladd.add_argument("--title", required=True)
    ladd.add_argument("--context", required=True)
    ladd.add_argument("--pitfall", required=True)
    ladd.add_argument("--solution", required=True)
    ladd.add_argument(
        "--id", default=None, help="explicit LLT-NNNN id (must be unused and greater than the max)"
    )
    ladd.add_argument("--category", default="other", help="one of: " + ", ".join(record.CATEGORIES))
    ladd.add_argument(
        "--severity", default="medium", help="one of: " + ", ".join(record.SEVERITIES)
    )
    ladd.add_argument("--recorded", default=None, help="YYYY-MM-DD (default: today)")
    ladd.add_argument(
        "--supersedes",
        default=None,
        help="LLT-NNNN of the lesson this one replaces (flips its status)",
    )
    ladd.add_argument("--prevention", default=None)
    ladd.add_argument("--references", default=None)

    lsync = lsub.add_parser("sync", help="regenerate the index block from the entries")
    lsync.add_argument("file")

    lcheck = lsub.add_parser("check", help="validate structure, fields, and index freshness")
    lcheck.add_argument("file")

    lnext = lsub.add_parser("next-id", help="print the next LLT-NNNN id")
    lnext.add_argument("file")


def _add_algorithms(sub: argparse._SubParsersAction) -> None:
    sp = sub.add_parser("algorithms", help="manage algorithm-document line indexes")
    asub = sp.add_subparsers(dest="algorithms_command", required=True)
    acheck = asub.add_parser("check", help="verify the index is current; exit 1 if stale")
    acheck.add_argument("doc", help="path to the algorithm document")
    as_sync = asub.add_parser("sync", help="rewrite the index in place (idempotent)")
    as_sync.add_argument("doc", help="path to the algorithm document")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="securetrace",
        description="Agentic tooling for secure, traceable software development.",
        epilog="Exit codes: 0 = ok, 1 = stale index, 2 = malformed file or rejected input.",
    )
    parser.add_argument("--version", action="version", version=f"securetrace {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    _add_backlog(sub)
    _add_lessons(sub)
    _add_algorithms(sub)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Parse arguments, dispatch to ``securetrace.cli``, and return the exit code.

    argparse-level failures (missing/unknown subcommand, ``--version``) raise
    ``SystemExit``; command-level failures return 0/1/2.
    """
    args = _build_parser().parse_args(argv)
    if args.command == "backlog":
        path = args.file
        if args.backlog_command == "check":
            return cli.run_backlog_check(path, prog="securetrace")
        return cli.run_backlog_sync(path, prog="securetrace")
    if args.command == "lessons":
        path = args.file
        if args.lessons_command == "init":
            return cli.run_lessons_init(path, force=args.force, prog="securetrace")
        if args.lessons_command == "add":
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
            return cli.run_lessons_add(path, lesson, prog="securetrace")
        if args.lessons_command == "sync":
            return cli.run_lessons_sync(path, prog="securetrace")
        if args.lessons_command == "check":
            return cli.run_lessons_check(path, prog="securetrace")
        return cli.run_lessons_next_id(path, prog="securetrace")
    # algorithms
    path = args.doc
    if args.algorithms_command == "check":
        return cli.run_algorithm_check(path, prog="securetrace")
    return cli.run_algorithm_sync(path, prog="securetrace")


if __name__ == "__main__":
    sys.exit(main())
