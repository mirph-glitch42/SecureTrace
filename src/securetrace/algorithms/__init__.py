"""Algorithm document registry management.

Intended responsibilities (implemented with backlog B3):
parse algorithm documents and their line indexes, validate
algorithm-records-keeper guards (one file per algorithm, fresh index,
registry row per document, version consistency between the registry and
document METADATA), and maintain ``algorithms/INDEX.md``. The vendored
``scripts/algorithm_index.py`` is the current source of truth for index
generation.
"""

__all__: list[str] = []
