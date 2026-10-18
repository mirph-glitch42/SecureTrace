"""Management of the LESSONS_LEARNED.md record.

Intended responsibilities (implemented with backlog B3):
parse the LLT index and entry markers, validate learned-lesson-tracker guards
G1–G9, add/supersede entries atomically, and keep the embedded TSV index
fresh. The vendored ``scripts/manage_lessons.py`` is the current source of
truth for add/sync/check.
"""

__all__: list[str] = []
