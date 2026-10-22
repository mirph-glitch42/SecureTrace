"""Command layer for ``securetrace rmf``: I/O, user-facing messages, exit codes.

``run_rmf_build`` takes the repo path and an optional outdir and returns the
process exit code (``0`` bundle written, ``2`` repo missing/not a directory
or outdir uncreatable — ``{prog}: …`` on stderr). The pure core
(``securetrace.rmf.deliverables``) raises ``FormatError``; this layer turns
that into the pinned stderr message.

The store-based document verbs (``backlog`` / ``lessons`` / ``algorithms`` /
``docs`` / ``migrate``) live in :mod:`securetrace.cli_docs`; B10 WI 10
removed the legacy ``backlog sync`` / ``lessons init|add|sync|check|next-id``
/ ``algorithms sync|check`` command layer from this module (the rendered
docs are now committed through the ``cli_docs`` store pipeline, and the
vendored ``scripts/backlog_index.py`` / ``scripts/manage_lessons.py``
wrappers were deleted).
"""

from __future__ import annotations

import datetime
import sys
from pathlib import Path

from securetrace.errors import FormatError
from securetrace.rmf import deliverables

__all__ = [
    "run_rmf_build",
]

PROG = "securetrace"


def _fail(prog: str, msg: str) -> int:
    """Print ``{prog}: {msg}`` to stderr; the caller returns the exit code."""
    print(f"{prog}: {msg}", file=sys.stderr)
    return 2


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
