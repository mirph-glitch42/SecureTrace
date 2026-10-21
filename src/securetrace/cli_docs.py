"""Command layer for the store-based document pipeline (B10 WI 8).

Spec: ``algorithms/deterministic-doc-pipeline.md`` §5.3 — the positional
``<store>`` argument of every ``backlog`` / ``lessons`` / ``algorithms``
subcommand is the **JSON store** path; the rendered ``.md`` is never a write
target of a mutation and is (re)built by the render commit. ``render`` and
``check`` compute expected bytes the same way (``integrity``), so they can
never disagree; ``migrate`` is the one-shot doc → store → re-render commit
that seeds a store from a grandfathered markdown document.

Each ``run_*`` function returns the process exit code and prints the pinned
user-visible lines (design D9, ALRK v0.1.5 §5.3):

- success → stdout, 0 — one mutation line (``upsert`` / ``progress`` /
  ``add`` / ``migrate``) plus the render line
  ``render: {doc} rendered from {store} (manifest: {manifest})``;
- rejected input / malformed store / IO failure → stderr
  ``securetrace: {msg}`` (one line), 2;
- ``check`` → 0 in sync (stdout) / 1 stale (diagnosis + remediation on
  stderr) / 2 malformed (diagnosis on stderr);
- ``show`` → the canonical JSON of the whole store (or one entry) on stdout,
  written verbatim (``canonical_json`` already carries the trailing newline).

Defaults (design D5) are store-relative: the doc path defaults to
``<store_dir>/../<doc>`` (``data/backlog.json`` → ``BACKLOG.md``) and the
manifest to ``<store_dir>/manifest.json``; both are overridable with
``--doc`` / ``--manifest``. ``docs render-all`` / ``docs check-all`` use the
standard repo layout (``canonical.DEFAULT_*_PATHS``, CWD-relative) with the
manifest defaulting to ``data/manifest.json``.

The clock lives in this module only (it is not T9-scanned): ``make_lesson``
defaults ``Recorded`` to today, and ``__main__`` defaults ``--date`` to
today; the pure core (``docs.mutations``) receives dates as explicit
parameters.
"""

from __future__ import annotations

import datetime
import json
import os
import sys
from pathlib import Path

from securetrace.docs import canonical
from securetrace.docs.backlog_doc import parse_backlog
from securetrace.docs.integrity import DOC_KINDS, check_message, check_paths, commit_render
from securetrace.docs.lessons_doc import parse_lessons
from securetrace.docs.mutations import (
    add_lesson,
    append_backlog_progress,
    upsert_backlog_item,
    upsert_registry_row,
)
from securetrace.docs.registry_doc import parse_registry
from securetrace.docs.schema import SchemaError
from securetrace.errors import FormatError, InvalidInput
from securetrace.lessons import record

__all__ = [
    "make_lesson",
    "run_algorithms_show",
    "run_algorithms_upsert",
    "run_backlog_progress",
    "run_backlog_show",
    "run_backlog_upsert",
    "run_check",
    "run_check_all",
    "run_lessons_add",
    "run_lessons_show",
    "run_migrate",
    "run_render",
    "run_render_all",
]

PROG = "securetrace"

#: migrate kind inference from the doc basename (design D8).
_KIND_BY_BASENAME = {
    "BACKLOG.md": "backlog",
    "LESSONS_LEARNED.md": "lessons",
    "INDEX.md": "registry",
}

#: Per-kind parse (migrate), unit words (migrate line), and store count key.
_KIND_PARSERS = {
    "backlog": parse_backlog,
    "lessons": parse_lessons,
    "registry": parse_registry,
}
_KIND_UNITS = {
    "backlog": ("item", "items"),
    "lessons": ("lesson", "lessons"),
    "registry": ("row", "rows"),
}
_KIND_COUNT_KEY = {"backlog": "items", "lessons": "lessons", "registry": "rows"}

_EM_DASH = "—"


class _StoreReadError(Exception):
    """The store file could not be read or parsed (command layer → exit 2)."""


# --------------------------------------------------------------------- helpers


def _fail(prog: str, msg: str) -> int:
    """Print ``{prog}: {msg}`` to stderr; the caller returns the exit code."""
    print(f"{prog}: {msg}", file=sys.stderr)
    return 2


def _read_store(path: Path) -> dict:
    """Read the canonical-JSON store at *path* as a dict.

    Raises:
        _StoreReadError: the file is unreadable, not valid UTF-8, not valid
            JSON, or its top level is not a JSON object (missing file, bad
            bytes, and bad JSON all surface under the same
            ``cannot read store {path}: …`` prefix, which the pinned tests
            assert with ``startswith``).
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise _StoreReadError(f"cannot read store {path}: {exc}") from exc
    try:
        store = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise _StoreReadError(f"cannot read store {path}: {exc}") from exc
    if not isinstance(store, dict):
        raise _StoreReadError(f"cannot read store {path}: top level must be a JSON object")
    return store


def _default_doc_path(kind: str, store_path: Path) -> Path:
    """Store-relative default doc path (design D5): ``<store_dir>/../<doc>``.

    ``data/backlog.json`` → ``BACKLOG.md``; ``data/algorithms.json`` →
    ``algorithms/INDEX.md`` (the result is normalized, so the printed paths
    are clean).
    """
    if kind not in canonical.DEFAULT_DOC_PATHS:
        raise ValueError(f"unknown doc kind: {kind!r}")
    return Path(
        os.path.normpath(str(Path(store_path).parent / ".." / canonical.DEFAULT_DOC_PATHS[kind]))
    )


def _default_manifest_path(store_path: Path) -> Path:
    """Store-relative default manifest path (design D5): ``<store_dir>/manifest.json``."""
    return Path(store_path).parent / "manifest.json"


def _resolve(
    kind: str, store_path: object, doc_path: object, manifest_path: object
) -> tuple[Path, Path, Path]:
    """Resolve (store, doc, manifest) paths, applying the D5 defaults."""
    sp = Path(store_path)
    doc = Path(doc_path) if doc_path is not None else _default_doc_path(kind, sp)
    man = Path(manifest_path) if manifest_path is not None else _default_manifest_path(sp)
    return sp, doc, man


def _render_line(doc: Path, sp: Path, man: Path) -> str:
    """The pinned success line printed by every render commit (design D9)."""
    return f"render: {doc} rendered from {sp} (manifest: {man})"


def _commit(kind: str, store: dict, sp: Path, doc: Path, man: Path, prog: str) -> int | None:
    """Run the render commit (design D3); return ``None`` on success.

    On failure prints the pinned stderr line and returns the exit-2 code, so
    callers can bail before printing their mutation line (a failed commit
    must not be reported as a mutation).
    """
    try:
        commit_render(kind, store, sp, doc, man)
    except SchemaError as exc:
        return _fail(prog, str(exc))
    except OSError as exc:
        return _fail(prog, f"cannot write {sp}: {exc}")
    return None


# --------------------------------------------------------------------- backlog


def run_backlog_upsert(
    store_path: str | Path,
    item: dict,
    date: str,
    *,
    doc_path: str | Path | None = None,
    manifest_path: str | Path | None = None,
    prog: str = PROG,
) -> int:
    """``backlog upsert``: mutate the store, commit the render, report (D3/D9).

    *item* is ``{id, title, status, fields[{name, lines}]}``; *date* is the
    ``YYYY-MM-DD`` used for the D4 status-line refresh. ``added`` vs
    ``updated`` reflects membership before the mutation.

    Returns:
        0: mutation + render committed (stdout: mutation line + render line).
        2: store unreadable, rejected input, schema violation, or a failed
          commit (stderr: ``securetrace: {msg}``).
    """
    kind = "backlog"
    try:
        sp, doc, man = _resolve(kind, store_path, doc_path, manifest_path)
    except ValueError as exc:
        return _fail(prog, str(exc))
    try:
        store = _read_store(sp)
    except _StoreReadError as exc:
        return _fail(prog, str(exc))
    items = store.get("items") if isinstance(store.get("items"), list) else []
    present = isinstance(item, dict) and any(
        isinstance(it, dict) and it.get("id") == item.get("id") for it in items
    )
    try:
        out = upsert_backlog_item(store, item, date)
    except (InvalidInput, SchemaError) as exc:
        return _fail(prog, str(exc))
    failed = _commit(kind, out, sp, doc, man, prog)
    if failed is not None:
        return failed
    label = "updated" if present else "added"
    print(f"upsert: {label} {item['id']} — {item['title']} ({sp})")
    print(_render_line(doc, sp, man))
    return 0


def run_backlog_progress(
    store_path: str | Path,
    item_id: str,
    line: str,
    date: str,
    *,
    doc_path: str | Path | None = None,
    manifest_path: str | Path | None = None,
    prog: str = PROG,
) -> int:
    """``backlog progress``: append *line* to the item's Progress field, commit.

    *line* is the FULL stored line (``__main__`` composes
    ``"  - {date} — {text}"``); *date* feeds the D4 status-line refresh.

    Returns:
        0: appended + rendered (stdout: progress line + render line).
        2: store unreadable, unknown item id, schema violation, failed commit
          (stderr: ``securetrace: {msg}``).
    """
    kind = "backlog"
    try:
        sp, doc, man = _resolve(kind, store_path, doc_path, manifest_path)
    except ValueError as exc:
        return _fail(prog, str(exc))
    try:
        store = _read_store(sp)
    except _StoreReadError as exc:
        return _fail(prog, str(exc))
    try:
        out = append_backlog_progress(store, item_id, line, date)
    except (InvalidInput, SchemaError) as exc:
        return _fail(prog, str(exc))
    failed = _commit(kind, out, sp, doc, man, prog)
    if failed is not None:
        return failed
    print(f"progress: appended to {item_id} ({sp})")
    print(_render_line(doc, sp, man))
    return 0


def run_backlog_show(
    store_path: str | Path,
    *,
    item_id: str | None = None,
    prog: str = PROG,
) -> int:
    """``backlog show``: print the canonical JSON of the store (or one item).

    The output is written verbatim — ``canonical_json`` already ends with
    exactly one newline (design D9).

    Returns:
        0: printed to stdout.
        2: store unreadable, or the item id is not in the store
          (stderr: ``securetrace: backlog item {id!r} not found``).
    """
    sp = Path(store_path)
    try:
        store = _read_store(sp)
    except _StoreReadError as exc:
        return _fail(prog, str(exc))
    if item_id is not None:
        items = store.get("items") if isinstance(store.get("items"), list) else []
        for it in items:
            if isinstance(it, dict) and it.get("id") == item_id:
                sys.stdout.write(canonical.canonical_json(it))
                return 0
        return _fail(prog, f"backlog item {item_id!r} not found")
    sys.stdout.write(canonical.canonical_json(store))
    return 0


# --------------------------------------------------------------------- lessons


def make_lesson(
    title: str,
    context: str,
    pitfall: str,
    solution: str,
    *,
    id: str | None = None,
    category: str = "other",
    severity: str = "medium",
    recorded: str | None = None,
    supersedes: str | None = None,
    prevention: str | None = None,
    references: str | None = None,
) -> dict:
    """Build the ``lessons add`` payload (design D7), mirroring the legacy grammar.

    All ten ``record.ALL_FIELDS`` are present in that order; absent optionals
    are the em dash; ``Recorded`` defaults to today (the clock lives in this
    module, not the pure core). A missing *id* is auto-assigned by the
    mutation core (``LLT-<max+1>``); an explicit one must be strictly
    greater than the stored max.
    """
    values = {
        "Recorded": recorded if recorded is not None else datetime.date.today().isoformat(),
        "Category": category,
        "Severity": severity,
        "Status": "active",
        "Context": context,
        "Pitfall": pitfall,
        "Solution": solution,
        "Supersedes": supersedes if supersedes is not None else _EM_DASH,
        "Prevention": prevention if prevention is not None else _EM_DASH,
        "References": references if references is not None else _EM_DASH,
    }
    return {
        "id": id,
        "title": title,
        "fields": [{"name": name, "value": values[name]} for name in record.ALL_FIELDS],
    }


def run_lessons_add(
    store_path: str | Path,
    lesson: dict,
    *,
    doc_path: str | Path | None = None,
    manifest_path: str | Path | None = None,
    prog: str = PROG,
) -> int:
    """``lessons add``: append the lesson, commit the render, report (D3/D9).

    *lesson* is ``{id: optional, title, fields[{name, value}]}`` (see
    :func:`make_lesson`); the assigned id is the appended lesson's id.

    Returns:
        0: recorded + rendered (stdout: add line + render line).
        2: store unreadable, rejected input, schema violation, failed commit
          (stderr: ``securetrace: {msg}``).
    """
    kind = "lessons"
    try:
        sp, doc, man = _resolve(kind, store_path, doc_path, manifest_path)
    except ValueError as exc:
        return _fail(prog, str(exc))
    try:
        store = _read_store(sp)
    except _StoreReadError as exc:
        return _fail(prog, str(exc))
    try:
        out = add_lesson(store, lesson)
    except (InvalidInput, SchemaError) as exc:
        return _fail(prog, str(exc))
    failed = _commit(kind, out, sp, doc, man, prog)
    if failed is not None:
        return failed
    new_lesson = out["lessons"][-1]
    print(f"add: recorded {new_lesson['id']} — {new_lesson['title']} ({sp})")
    print(_render_line(doc, sp, man))
    return 0


def run_lessons_show(
    store_path: str | Path,
    *,
    lesson_id: str | None = None,
    prog: str = PROG,
) -> int:
    """``lessons show``: print the canonical JSON of the store (or one lesson).

    Returns:
        0: printed to stdout.
        2: store unreadable, or the lesson id is not in the store
          (stderr: ``securetrace: lesson {id!r} not found``).
    """
    sp = Path(store_path)
    try:
        store = _read_store(sp)
    except _StoreReadError as exc:
        return _fail(prog, str(exc))
    if lesson_id is not None:
        lessons = store.get("lessons") if isinstance(store.get("lessons"), list) else []
        for lesson in lessons:
            if isinstance(lesson, dict) and lesson.get("id") == lesson_id:
                sys.stdout.write(canonical.canonical_json(lesson))
                return 0
        return _fail(prog, f"lesson {lesson_id!r} not found")
    sys.stdout.write(canonical.canonical_json(store))
    return 0


# --------------------------------------------------------------------- registry


def run_algorithms_upsert(
    store_path: str | Path,
    row: dict,
    *,
    doc_path: str | Path | None = None,
    manifest_path: str | Path | None = None,
    prog: str = PROG,
) -> int:
    """``algorithms upsert``: replace or slug-sorted-insert the row, commit.

    *row* is the closed six-key registry row (``{slug, name, version,
    status, file, summary}``); ``added`` vs ``updated`` reflects membership
    before the mutation.

    Returns:
        0: upserted + rendered (stdout: upsert line + render line).
        2: store unreadable, rejected row, schema violation, failed commit
          (stderr: ``securetrace: {msg}``).
    """
    kind = "registry"
    try:
        sp, doc, man = _resolve(kind, store_path, doc_path, manifest_path)
    except ValueError as exc:
        return _fail(prog, str(exc))
    try:
        store = _read_store(sp)
    except _StoreReadError as exc:
        return _fail(prog, str(exc))
    rows = store.get("rows") if isinstance(store.get("rows"), list) else []
    present = isinstance(row, dict) and any(
        isinstance(r, dict) and r.get("slug") == row.get("slug") for r in rows
    )
    try:
        out = upsert_registry_row(store, row)
    except (InvalidInput, SchemaError) as exc:
        return _fail(prog, str(exc))
    failed = _commit(kind, out, sp, doc, man, prog)
    if failed is not None:
        return failed
    label = "updated" if present else "added"
    print(f"upsert: {label} row {row['slug']} ({sp})")
    print(_render_line(doc, sp, man))
    return 0


def run_algorithms_show(
    store_path: str | Path,
    *,
    slug: str | None = None,
    prog: str = PROG,
) -> int:
    """``algorithms show``: print the canonical JSON of the store (or one row).

    Returns:
        0: printed to stdout.
        2: store unreadable, or the slug is not in the store
          (stderr: ``securetrace: registry row {slug!r} not found``).
    """
    sp = Path(store_path)
    try:
        store = _read_store(sp)
    except _StoreReadError as exc:
        return _fail(prog, str(exc))
    if slug is not None:
        rows = store.get("rows") if isinstance(store.get("rows"), list) else []
        for row in rows:
            if isinstance(row, dict) and row.get("slug") == slug:
                sys.stdout.write(canonical.canonical_json(row))
                return 0
        return _fail(prog, f"registry row {slug!r} not found")
    sys.stdout.write(canonical.canonical_json(store))
    return 0


# --------------------------------------------------------------------- render / check


def run_render(
    kind: str,
    store_path: str | Path,
    *,
    doc_path: str | Path | None = None,
    manifest_path: str | Path | None = None,
    prog: str = PROG,
) -> int:
    """``{verb} render``: re-render the doc from the store without data change.

    The store is re-written in canonical JSON and the manifest entry is
    refreshed, so a tampered document is repaired by the render.

    Returns:
        0: rendered (stdout: the render line).
        2: unknown kind, store unreadable/malformed, failed commit
          (stderr: ``securetrace: {msg}``).
    """
    try:
        sp, doc, man = _resolve(kind, store_path, doc_path, manifest_path)
    except ValueError as exc:
        return _fail(prog, str(exc))
    try:
        store = _read_store(sp)
    except _StoreReadError as exc:
        return _fail(prog, str(exc))
    failed = _commit(kind, store, sp, doc, man, prog)
    if failed is not None:
        return failed
    print(_render_line(doc, sp, man))
    return 0


def run_check(
    kind: str,
    store_path: str | Path,
    *,
    doc_path: str | Path | None = None,
    manifest_path: str | Path | None = None,
    prog: str = PROG,
) -> int:
    """``{verb} check``: store + doc + manifest agreement (spec §5.3 exit model).

    Returns:
        0: in sync (message on stdout).
        1: stale — doc modified outside the app, or store/doc drifted since
          the last render (diagnosis + remediation on stderr).
        2: malformed store/doc/manifest (diagnosis on stderr).
    """
    try:
        sp, doc, man = _resolve(kind, store_path, doc_path, manifest_path)
    except ValueError as exc:
        return _fail(prog, str(exc))
    try:
        code, diagnosis = check_paths(kind, sp, doc, man)
    except SchemaError as exc:
        return _fail(prog, str(exc))
    msg = check_message(kind, diagnosis, str(sp))
    if code == 0:
        print(msg)
    else:
        print(msg, file=sys.stderr)
    return code


def run_render_all(*, manifest_path: str | Path | None = None, prog: str = PROG) -> int:
    """``docs render-all``: render the three pipeline docs in kind order.

    Uses the standard repo layout (CWD-relative) and is fail-fast: the first
    failure stops the run (exit 2) after printing only the successful render
    lines.
    """
    man = Path(manifest_path) if manifest_path is not None else Path("data/manifest.json")
    for kind in DOC_KINDS:
        sp = Path(canonical.DEFAULT_STORE_PATHS[kind])
        doc = Path(canonical.DEFAULT_DOC_PATHS[kind])
        try:
            store = _read_store(sp)
        except _StoreReadError as exc:
            return _fail(prog, str(exc))
        failed = _commit(kind, store, sp, doc, man, prog)
        if failed is not None:
            return failed
        print(_render_line(doc, sp, man))
    return 0


def run_check_all(*, manifest_path: str | Path | None = None, prog: str = PROG) -> int:
    """``docs check-all``: check the three pipeline docs; exit = worst code.

    One ``check_message`` line per kind (stdout when 0, stderr when 1/2);
    the run always checks all three kinds and returns the maximum exit code.
    """
    man = Path(manifest_path) if manifest_path is not None else Path("data/manifest.json")
    worst = 0
    for kind in DOC_KINDS:
        sp = Path(canonical.DEFAULT_STORE_PATHS[kind])
        doc = Path(canonical.DEFAULT_DOC_PATHS[kind])
        code, diagnosis = check_paths(kind, sp, doc, man)
        msg = check_message(kind, diagnosis, str(sp))
        if code == 0:
            print(msg)
        else:
            print(msg, file=sys.stderr)
        worst = max(worst, code)
    return worst


# --------------------------------------------------------------------- migrate


def run_migrate(
    doc_path: str | Path,
    *,
    kind: str | None = None,
    store_path: str | Path | None = None,
    force: bool = False,
    manifest_path: str | Path | None = None,
    prog: str = PROG,
) -> int:
    """``migrate``: parse a markdown doc into its store, then commit the render.

    *kind* defaults to inference from the doc basename (``BACKLOG.md`` →
    backlog, ``LESSONS_LEARNED.md`` → lessons, ``INDEX.md`` → registry); an
    explicit ``--kind`` wins. A pre-existing store requires ``--force``.
    If the given doc path does not exist but the kind's default doc path
    does (``migrate INDEX.md`` → ``algorithms/INDEX.md``), the default is
    used for the read and the render commit; the printed lines carry the
    path as given. The commit then re-renders the doc from the store, so
    the result is the canonical form of the input (design D8/D9).

    Returns:
        0: migrated + rendered (stdout: migrate line + render line).
        2: kind not inferable, store exists without ``--force``, doc
          unreadable/malformed, failed commit (stderr:
          ``securetrace: {msg}``).
    """
    doc = Path(doc_path)
    if kind is None:
        kind = _KIND_BY_BASENAME.get(doc.name)
        if kind is None:
            return _fail(
                prog,
                f"cannot infer doc kind from {doc.name}; "
                "pass --kind one of: backlog, lessons, registry",
            )
    sp = Path(store_path) if store_path is not None else Path(canonical.DEFAULT_STORE_PATHS[kind])
    if sp.exists() and not force:
        return _fail(prog, f"store {sp} already exists; use --force to replace")
    # Resolve the doc: the path as given, else the kind's default doc path
    # (from the repo root a user types ``migrate INDEX.md`` for
    # ``algorithms/INDEX.md``). The commit targets the resolved path; the
    # printed lines carry the path as given (design D11).
    given = Path(doc_path)
    if not doc.exists():
        default_doc = Path(canonical.DEFAULT_DOC_PATHS[kind])
        if default_doc.exists():
            doc = default_doc
    try:
        text = doc.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return _fail(prog, f"cannot read {doc}: {exc}")
    try:
        store = _KIND_PARSERS[kind](text)
    except (FormatError, SchemaError) as exc:
        return _fail(prog, str(exc))
    man = Path(manifest_path) if manifest_path is not None else _default_manifest_path(sp)
    failed = _commit(kind, store, sp, doc, man, prog)
    if failed is not None:
        return failed
    singular, plural = _KIND_UNITS[kind]
    items = store.get(_KIND_COUNT_KEY[kind])
    count = len(items) if isinstance(items, list) else 0
    unit = singular if count == 1 else plural
    print(f"migrate: {count} {unit} from {given} → {sp}")
    print(_render_line(given, sp, man))
    return 0
