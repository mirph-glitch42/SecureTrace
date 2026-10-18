"""Pipeline subpackage smoke tests (behavioral tests land with backlog B3)."""

from __future__ import annotations


def test_subpackage_has_responsibility_doc() -> None:
    import securetrace.pipeline

    assert securetrace.pipeline.__doc__
    assert "gate" in securetrace.pipeline.__doc__.lower()


def test_gates_module_imports() -> None:
    from securetrace.pipeline import gates  # noqa: F401
