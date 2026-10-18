"""Algorithms subpackage smoke tests (behavioral tests land with backlog B3)."""

from __future__ import annotations


def test_subpackage_has_responsibility_doc() -> None:
    import securetrace.algorithms

    assert securetrace.algorithms.__doc__
    assert "algorithm" in securetrace.algorithms.__doc__.lower()


def test_registry_module_imports() -> None:
    from securetrace.algorithms import registry  # noqa: F401
