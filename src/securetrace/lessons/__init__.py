"""Management of the LESSONS_LEARNED.md record.

Intended responsibilities (implemented with backlog B3):
parse the LLT index and entry markers, validate learned-lesson-tracker guards
G1–G9, add/supersede entries atomically, and keep the embedded TSV index
fresh. :mod:`securetrace.lessons.record` is the source of truth for
add/sync/check (the vendored ``scripts/manage_lessons.py`` wrapper was
retired in B10 WI 10; the store pipeline is ``securetrace.cli_docs``).
"""

__all__: list[str] = []
