"""No-clock / no-environment discipline for the securetrace.docs core (T9, C5).

Every pure core module must import nothing that can read the wall clock
(``datetime``/``time``), produce randomness (``random``/``uuid``), or touch
the environment and process side channels (``os``, ``subprocess``,
``socket``, ``urllib``) — spec ``algorithms/deterministic-doc-pipeline.md``
§5.2 rule 1 and test T9. ``integrity.py`` is the documented exception: it is
the manifest I/O module (temp file + ``os.replace``), so it is excluded. The
core module set is discovered dynamically, so WIs 5/6 (``lessons_doc``,
``registry_doc``) are covered without editing this test.
"""

from __future__ import annotations

import ast
from pathlib import Path

import securetrace.docs

BANNED_TOP_MODULES = frozenset(
    {"datetime", "time", "random", "uuid", "os", "subprocess", "socket", "urllib"}
)
EXCLUDED_FILES = frozenset({"__init__.py", "integrity.py"})


def _core_module_paths() -> list[Path]:
    package_dir = Path(securetrace.docs.__file__).resolve().parent
    paths = sorted(p for p in package_dir.glob("*.py") if p.name not in EXCLUDED_FILES)
    assert paths, "securetrace/docs/ must contain at least one core module"
    return paths


def test_core_module_set_grows_with_wis():
    """The pure core grows as WIs land; the discipline test covers all of it."""
    names = {p.name for p in _core_module_paths()}
    assert {"canonical.py", "schema.py", "backlog_doc.py"} <= names


def test_core_modules_import_no_clock_randomness_or_env():
    """T9: AST ban on clock, randomness, and environment side channels."""
    for path in _core_module_paths():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    assert top not in BANNED_TOP_MODULES, (
                        f"{path.name}: core module imports banned module {alias.name!r}"
                    )
            elif isinstance(node, ast.ImportFrom):
                top = (node.module or "").split(".")[0]
                assert top not in BANNED_TOP_MODULES, (
                    f"{path.name}: core module imports from banned module {node.module!r}"
                )
