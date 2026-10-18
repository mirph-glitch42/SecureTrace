"""Backlog index and item model (skeleton — lands with backlog B3).

Planned public API:
- ``parse_index(text) -> Index``: parse the TSV index block of a BACKLOG.md.
- ``parse_items(text) -> dict[str, Item]``: parse marked items with fields.
- ``check(text) -> list[str]``: validate guards G1–G9 and return findings.

Nothing here is implemented yet; the module exists so the package layout is
stable and tests can pin import paths before behavior lands (TDD: tests for
the API are written when B3 starts, per @algorithm-records-keeper).
"""
