"""Deterministic management of agentic BACKLOG.md files.

Intended responsibilities (implemented with backlog B3):
parse the machine-readable index and item markers, validate the backlog-manager
guards (stable ids, status vocabulary, fresh index), re-queue by priority, and
close items out with evidence. The vendored ``scripts/backlog_index.py`` is the
current source of truth for index generation.
"""

__all__: list[str] = []
