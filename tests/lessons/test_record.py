"""Lessons subpackage smoke tests (behavioral tests land with backlog B3)."""

from __future__ import annotations


def test_subpackage_has_responsibility_doc() -> None:
    import securetrace.lessons

    assert securetrace.lessons.__doc__
    assert "LESSONS_LEARNED" in securetrace.lessons.__doc__


def test_record_module_imports() -> None:
    from securetrace.lessons import record  # noqa: F401
