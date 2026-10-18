"""RMF subpackage smoke tests (behavioral tests land with backlog B4)."""

from __future__ import annotations


def test_subpackage_has_responsibility_doc() -> None:
    import securetrace.rmf

    assert securetrace.rmf.__doc__
    assert "RMF" in securetrace.rmf.__doc__


def test_deliverables_module_imports() -> None:
    from securetrace.rmf import deliverables  # noqa: F401
