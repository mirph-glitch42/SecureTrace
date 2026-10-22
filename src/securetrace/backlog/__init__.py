"""Deterministic management of agentic BACKLOG.md files.

Intended responsibilities (implemented with backlog B3):
parse the machine-readable index and item markers, validate the backlog-manager
guards (stable ids, status vocabulary, fresh index), re-queue by priority, and
close items out with evidence. :mod:`securetrace.backlog.index` is the source
of truth for index generation (the vendored ``scripts/backlog_index.py``
wrapper was retired in B10 WI 10; the store pipeline is
``securetrace.cli_docs``).
"""

__all__: list[str] = []
