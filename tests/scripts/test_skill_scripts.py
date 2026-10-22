"""Functional tests for the remaining vendored skill script.

`scripts/algorithm_index.py` is the ALRK prose-doc TSV index tool that the
gate still calls directly (make docs-check: `securetrace docs check-all` for
the store-rendered docs, then this script `--check` over every
`algorithms/*.md` except `INDEX.md`; make docs-render syncs the same loop).
A regression in it silently disables the ALRK staleness gate, so it carries
a real test here.

The former `scripts/backlog_index.py` and `scripts/manage_lessons.py`
wrappers were retired in B10 WI 10 — their contracts now live in the
store-based pipeline (`securetrace.cli_docs`, pinned in
`tests/test_cli_docs.py`) and the pure cores under `src/securetrace/`.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable  # scripts are stdlib-only; the venv interpreter is fine

ALGORITHM_SCRIPT = ROOT / "scripts" / "algorithm_index.py"


def run(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([PY, str(script), *args], capture_output=True, text=True, cwd=ROOT)


ALGORITHM_FIXTURE = """\
# Fixture Algorithm

<!-- INDEX:BEGIN format=tsv version=1 -->
<!-- placeholder interior line -->
<!-- INDEX:END -->

<!-- SECTION:METADATA -->
## 1. Metadata

| Field | Value |
|---|---|
| Name | Fixture |

<!-- SECTION:THEORY -->
## 2. Theory

Sums two numbers.

<!-- SECTION:TESTS -->
## 3. Tests

1 + 2 = 3
"""


def test_algorithm_index_roundtrip(tmp_path: Path) -> None:
    doc = tmp_path / "fixture-algorithm.md"
    doc.write_text(ALGORITHM_FIXTURE)

    assert run(ALGORITHM_SCRIPT, str(doc)).returncode == 0
    assert run(ALGORITHM_SCRIPT, str(doc), "--check").returncode == 0

    doc.write_text(ALGORITHM_FIXTURE + "\nnew theory line\n")
    assert run(ALGORITHM_SCRIPT, str(doc), "--check").returncode == 1

    assert run(ALGORITHM_SCRIPT, str(doc)).returncode == 0
    assert run(ALGORITHM_SCRIPT, str(doc), "--check").returncode == 0
