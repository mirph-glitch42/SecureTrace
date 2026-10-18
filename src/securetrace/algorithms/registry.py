"""Algorithm registry model (skeleton — lands with backlog B3).

Planned public API:
- ``parse_registry(path) -> Registry``: parse algorithms/INDEX.md rows.
- ``check_registry(algorithms_dir) -> list[str]``: enforce registry rules
  (every document has exactly one row; every row points at an existing file;
  versions match document METADATA).
"""
