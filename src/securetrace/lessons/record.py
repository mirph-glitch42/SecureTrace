"""Lessons-learned record model (skeleton — lands with backlog B3).

Planned public API:
- ``parse_lessons(text) -> list[Lesson]``: parse marked entries + fields.
- ``check(text) -> list[str]``: validate LLT guards and return findings.
- ``supersede(text, old_id, new_entry) -> str``: atomic supersession.
"""
