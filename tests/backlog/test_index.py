"""Backlog subpackage smoke tests (behavioral tests land with backlog B3)."""

from __future__ import annotations


def test_subpackage_has_responsibility_doc() -> None:
    import securetrace.backlog

    assert securetrace.backlog.__doc__
    assert "BACKLOG" in securetrace.backlog.__doc__


def test_index_module_imports() -> None:
    from securetrace.backlog import index  # noqa: F401
