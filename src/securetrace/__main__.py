"""``securetrace`` console entrypoint: argparse dispatch to ``securetrace.cli_docs``.

Usage:
    securetrace backlog {upsert,progress,show,render,check} <store> …
    securetrace lessons {add,set-intro,show,render,check} <store> …
    securetrace algorithms {upsert,show,render,check} <store> …
    securetrace docs {render-all,check-all} [--manifest FILE]
    securetrace migrate <doc> [--kind K] [--store FILE] [--force] [--manifest FILE]
    securetrace rmf build <repo> [--outdir DIR]

The positional file argument of every store-based command is the **store**
path (the in-repo JSON data store); the rendered ``.md`` doc and the
manifest default relative to the store (design D5, see
``algorithms/deterministic-doc-pipeline.md``). ``.md`` docs are never
edited directly — they are re-rendered from the store by every mutation.

``main(argv)`` returns the process exit code for command-level failures
(0/1/2); argparse-level failures (missing subcommand, unknown subcommand,
``--version``) raise ``SystemExit`` through argparse.
"""

from __future__ import annotations

import argparse
import datetime
import sys
from collections.abc import Callable

from securetrace import __version__, cli, cli_docs

# Shared option help literals (S1192: each help string lives in exactly one
# place; the argparse surface is pinned by tests/test_cli_docs.py).
_STORE_HELP = "path to the JSON store"
_BACKLOG_STORE_HELP = "path to the backlog store JSON"
_LESSONS_STORE_HELP = "path to the lessons store JSON"
_REGISTRY_STORE_HELP = "path to the registry store JSON"
_SHOW_HELP = "print the store as canonical JSON"
_ITEM_ID_HELP = "item id (B-<n>)"
_TODAY_HELP = "YYYY-MM-DD (default: today)"
_MANIFEST_STORE_HELP = "manifest path (default: <store_dir>/manifest.json)"
_MANIFEST_DOCS_HELP = "manifest path (default: data/manifest.json)"


def _compose_fields(specs: list[str] | None) -> list[dict]:
    """Turn repeated ``--field "Name: line"`` specs into item fields.

    Specs whose names match append to that field's ``lines``; the order of
    first appearance is preserved. Returns ``[]`` when no spec was given.
    """
    fields: list[dict] = []
    for spec in specs or []:
        name, _, line = spec.partition(":")
        name = name.strip()
        line = line.strip()
        for field in fields:
            if field["name"] == name:
                field["lines"].append(line)
                break
        else:
            fields.append({"name": name, "lines": [line]})
    return fields


def _store_options(sp: argparse.ArgumentParser) -> None:
    """The two D5 override options shared by every store-based subcommand."""
    sp.add_argument("--doc", default=None, help="doc path (default: <store_dir>/../<kind doc>)")
    sp.add_argument("--manifest", default=None, help=_MANIFEST_STORE_HELP)


def _render_check(sub: argparse._SubParsersAction, kind_help: str) -> None:
    """Add the shared ``render`` / ``check`` subcommands to *sub*."""
    rd = sub.add_parser("render", help=f"re-render the {kind_help} doc from the store")
    rd.add_argument("store", help=_STORE_HELP)
    _store_options(rd)
    ck = sub.add_parser(
        "check", help=f"check the {kind_help} doc; exit 0 in sync / 1 stale / 2 malformed"
    )
    ck.add_argument("store", help=_STORE_HELP)
    _store_options(ck)


def _add_backlog(sub: argparse._SubParsersAction) -> None:
    sp = sub.add_parser("backlog", help="manage the backlog store (default data/backlog.json)")
    bsub = sp.add_subparsers(dest="backlog_command", required=True)

    up = bsub.add_parser("upsert", help="add or update a backlog item, then commit the render")
    up.add_argument("store", help=_BACKLOG_STORE_HELP)
    up.add_argument("--id", required=True, help=_ITEM_ID_HELP)
    up.add_argument("--title", required=True, help="item title")
    up.add_argument("--status", required=True, help="OPEN | IN PROGRESS | DONE")
    up.add_argument(
        "--field",
        action="append",
        default=None,
        metavar="NAME: LINE",
        help="field line (repeatable; the same name appends to that field)",
    )
    up.add_argument("--date", default=None, help="YYYY-MM-DD status-line date (default: today)")
    _store_options(up)

    pg = bsub.add_parser("progress", help="append a progress line to an item, then commit")
    pg.add_argument("store", help=_BACKLOG_STORE_HELP)
    pg.add_argument("--id", required=True, help=_ITEM_ID_HELP)
    pg.add_argument("--text", required=True, help="progress text")
    pg.add_argument("--date", default=None, help=_TODAY_HELP)
    _store_options(pg)

    sh = bsub.add_parser("show", help=_SHOW_HELP)
    sh.add_argument("store", help=_BACKLOG_STORE_HELP)
    sh.add_argument("--id", default=None, help="print only this item")

    _render_check(bsub, "backlog")


def _add_lessons(sub: argparse._SubParsersAction) -> None:
    sp = sub.add_parser("lessons", help="manage the lessons store (default data/lessons.json)")
    lsub = sp.add_subparsers(dest="lessons_command", required=True)

    add = lsub.add_parser("add", help="record a new lesson, then commit the render")
    add.add_argument("store", help=_LESSONS_STORE_HELP)
    add.add_argument("--title", required=True, help="lesson title")
    add.add_argument("--context", required=True, help="context (what happened)")
    add.add_argument("--pitfall", required=True, help="pitfall (what went wrong)")
    add.add_argument("--solution", required=True, help="solution (what works)")
    add.add_argument("--id", default=None, help="explicit LLT-NNNN id (default: next free id)")
    add.add_argument("--category", default="other", help="lesson category (default: other)")
    add.add_argument("--severity", default="medium", help="low | medium | high (default: medium)")
    add.add_argument("--recorded", default=None, help=_TODAY_HELP)
    add.add_argument("--supersedes", default=None, help="LLT-NNNN of the lesson this one replaces")
    add.add_argument("--prevention", default=None, help="prevention note")
    add.add_argument("--references", default=None, help="references")
    _store_options(add)

    si = lsub.add_parser("set-intro", help="replace the intro lines, then commit the render")
    si.add_argument("store", help=_LESSONS_STORE_HELP)
    si.add_argument("--text", required=True, help="the new intro text (blank-line separated)")
    _store_options(si)

    sh = lsub.add_parser("show", help=_SHOW_HELP)
    sh.add_argument("store", help=_LESSONS_STORE_HELP)
    sh.add_argument("--id", default=None, help="print only this lesson")

    _render_check(lsub, "lessons")


def _add_algorithms(sub: argparse._SubParsersAction) -> None:
    sp = sub.add_parser(
        "algorithms", help="manage the algorithm-registry store (default data/algorithms.json)"
    )
    asub = sp.add_subparsers(dest="algorithms_command", required=True)

    up = asub.add_parser("upsert", help="add or update a registry row, then commit the render")
    up.add_argument("store", help=_REGISTRY_STORE_HELP)
    up.add_argument("--slug", required=True, help="row slug")
    up.add_argument("--name", required=True, help="algorithm name")
    up.add_argument("--version", required=True, help="document version")
    up.add_argument("--status", required=True, help="draft | implemented | superseded")
    up.add_argument("--file", required=True, help="path to the algorithm document")
    up.add_argument("--summary", required=True, help="one-line summary")
    _store_options(up)

    sh = asub.add_parser("show", help=_SHOW_HELP)
    sh.add_argument("store", help=_REGISTRY_STORE_HELP)
    sh.add_argument("--slug", default=None, help="print only this row")

    _render_check(asub, "registry")


def _add_docs(sub: argparse._SubParsersAction) -> None:
    sp = sub.add_parser("docs", help="render or check all three pipeline docs")
    dsub = sp.add_subparsers(dest="docs_command", required=True)

    ra = dsub.add_parser("render-all", help="render all three docs from their stores")
    ra.add_argument("--manifest", default=None, help=_MANIFEST_DOCS_HELP)
    ca = dsub.add_parser("check-all", help="check all three docs; exit = worst code")
    ca.add_argument("--manifest", default=None, help=_MANIFEST_DOCS_HELP)


def _add_migrate(sub: argparse._SubParsersAction) -> None:
    mg = sub.add_parser(
        "migrate", help="parse a markdown doc into its store, then commit the render"
    )
    mg.add_argument("doc", help="path to the markdown doc")
    mg.add_argument(
        "--kind",
        default=None,
        help="backlog | lessons | registry (default: infer from the doc basename)",
    )
    mg.add_argument("--store", default=None, help="store path (default: data/<kind>.json)")
    mg.add_argument("--force", action="store_true", help="replace an existing store")
    mg.add_argument("--manifest", default=None, help=_MANIFEST_STORE_HELP)


def _add_rmf(sub: argparse._SubParsersAction) -> None:
    sp = sub.add_parser("rmf", help="build RMF evidence bundles (SSP/SAP/SAR/POA&M)")
    rsub = sp.add_subparsers(dest="rmf_command", required=True)
    build = rsub.add_parser("build", help="write the RMF evidence bundle for a repository")
    build.add_argument("repo", help="repository root to collect evidence from")
    build.add_argument(
        "--outdir",
        default=None,
        help="bundle directory (default: artifacts/rmf/<today> relative to the working directory)",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="securetrace",
        description="Agentic tooling for secure, traceable software development.",
        epilog=(
            "Exit codes: 0 = ok / in sync, 1 = doc stale (check), "
            "2 = malformed file or rejected input."
        ),
    )
    parser.add_argument("--version", action="version", version=f"securetrace {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    _add_backlog(sub)
    _add_lessons(sub)
    _add_algorithms(sub)
    _add_docs(sub)
    _add_migrate(sub)
    _add_rmf(sub)
    return parser


def _run_backlog(args: argparse.Namespace) -> int:
    """Dispatch one ``backlog <command>`` (parsed args in, exit code out)."""
    if args.backlog_command == "upsert":
        item = {
            "id": args.id,
            "title": args.title,
            "status": args.status,
            "fields": _compose_fields(args.field),
        }
        date = args.date or datetime.date.today().isoformat()
        return cli_docs.run_backlog_upsert(
            args.store,
            item,
            date,
            doc_path=args.doc,
            manifest_path=args.manifest,
            prog="securetrace",
        )
    if args.backlog_command == "progress":
        date = args.date or datetime.date.today().isoformat()
        line = f"  - {date} — {args.text}"
        return cli_docs.run_backlog_progress(
            args.store,
            args.id,
            line,
            date,
            doc_path=args.doc,
            manifest_path=args.manifest,
            prog="securetrace",
        )
    if args.backlog_command == "show":
        return cli_docs.run_backlog_show(args.store, item_id=args.id)
    if args.backlog_command == "render":
        return cli_docs.run_render(
            "backlog",
            args.store,
            doc_path=args.doc,
            manifest_path=args.manifest,
            prog="securetrace",
        )
    return cli_docs.run_check(
        "backlog",
        args.store,
        doc_path=args.doc,
        manifest_path=args.manifest,
        prog="securetrace",
    )


def _run_lessons(args: argparse.Namespace) -> int:
    """Dispatch one ``lessons <command>``."""
    if args.lessons_command == "add":
        lesson = cli_docs.make_lesson(
            args.title,
            args.context,
            args.pitfall,
            args.solution,
            id=args.id,
            category=args.category,
            severity=args.severity,
            recorded=args.recorded,
            supersedes=args.supersedes,
            prevention=args.prevention,
            references=args.references,
        )
        return cli_docs.run_lessons_add(
            args.store,
            lesson,
            doc_path=args.doc,
            manifest_path=args.manifest,
            prog="securetrace",
        )
    if args.lessons_command == "set-intro":
        intro = [line for line in args.text.splitlines() if line.strip()]
        return cli_docs.run_lessons_set_intro(
            args.store,
            intro,
            doc_path=args.doc,
            manifest_path=args.manifest,
            prog="securetrace",
        )
    if args.lessons_command == "show":
        return cli_docs.run_lessons_show(args.store, lesson_id=args.id)
    if args.lessons_command == "render":
        return cli_docs.run_render(
            "lessons",
            args.store,
            doc_path=args.doc,
            manifest_path=args.manifest,
            prog="securetrace",
        )
    return cli_docs.run_check(
        "lessons",
        args.store,
        doc_path=args.doc,
        manifest_path=args.manifest,
        prog="securetrace",
    )


def _run_algorithms(args: argparse.Namespace) -> int:
    """Dispatch one ``algorithms <command>``."""
    if args.algorithms_command == "upsert":
        row = {
            "slug": args.slug,
            "name": args.name,
            "version": args.version,
            "status": args.status,
            "file": args.file,
            "summary": args.summary,
        }
        return cli_docs.run_algorithms_upsert(
            args.store,
            row,
            doc_path=args.doc,
            manifest_path=args.manifest,
            prog="securetrace",
        )
    if args.algorithms_command == "show":
        return cli_docs.run_algorithms_show(args.store, slug=args.slug)
    if args.algorithms_command == "render":
        return cli_docs.run_render(
            "registry",
            args.store,
            doc_path=args.doc,
            manifest_path=args.manifest,
            prog="securetrace",
        )
    return cli_docs.run_check(
        "registry",
        args.store,
        doc_path=args.doc,
        manifest_path=args.manifest,
        prog="securetrace",
    )


def _run_docs(args: argparse.Namespace) -> int:
    """Dispatch one ``docs <command>``."""
    if args.docs_command == "render-all":
        return cli_docs.run_render_all(manifest_path=args.manifest, prog="securetrace")
    return cli_docs.run_check_all(manifest_path=args.manifest, prog="securetrace")


def _run_migrate(args: argparse.Namespace) -> int:
    """Dispatch ``migrate``."""
    return cli_docs.run_migrate(
        args.doc,
        kind=args.kind,
        store_path=args.store,
        force=args.force,
        manifest_path=args.manifest,
        prog="securetrace",
    )


def _run_rmf(args: argparse.Namespace) -> int:
    """Dispatch ``rmf build`` (the legacy surface, exception G3)."""
    return cli.run_rmf_build(args.repo, outdir=args.outdir, prog="securetrace")


#: Command name -> dispatch handler (keeps ``main`` a one-line dispatcher).
_COMMANDS: dict[str, Callable[[argparse.Namespace], int]] = {
    "backlog": _run_backlog,
    "lessons": _run_lessons,
    "algorithms": _run_algorithms,
    "docs": _run_docs,
    "migrate": _run_migrate,
    "rmf": _run_rmf,
}


def main(argv: list[str] | None = None) -> int:
    """Parse arguments, dispatch to ``securetrace.cli_docs``, return the exit code.

    argparse-level failures (missing/unknown subcommand, ``--version``) raise
    ``SystemExit``; command-level failures return 0/1/2.
    """
    args = _build_parser().parse_args(argv)
    return _COMMANDS[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
