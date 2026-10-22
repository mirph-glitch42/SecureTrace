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


def run(script: Path, *args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run([PY, str(script), *args], capture_output=True, text=True, cwd=cwd)


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
    # cwd=tmp_path: the doc lives inside the working directory, which is the
    # only place the guard (S8707) allows reads/writes.
    doc = tmp_path / "fixture-algorithm.md"
    doc.write_text(ALGORITHM_FIXTURE)

    assert run(ALGORITHM_SCRIPT, str(doc), cwd=tmp_path).returncode == 0
    assert run(ALGORITHM_SCRIPT, str(doc), "--check", cwd=tmp_path).returncode == 0

    doc.write_text(ALGORITHM_FIXTURE + "\nnew theory line\n")
    assert run(ALGORITHM_SCRIPT, str(doc), "--check", cwd=tmp_path).returncode == 1

    assert run(ALGORITHM_SCRIPT, str(doc), cwd=tmp_path).returncode == 0
    assert run(ALGORITHM_SCRIPT, str(doc), "--check", cwd=tmp_path).returncode == 0


def test_path_escaping_cwd_is_rejected(tmp_path: Path) -> None:
    """S8707: LLM-supplied doc paths must stay inside the working directory.

    An escaping path (absolute or ``..`` traversal) is a structural error:
    pinned exit 2 with the ``{prog}: {msg}`` stderr shape, in both sync and
    check modes, and nothing outside the working directory is touched.
    """
    outside = ROOT / "algorithms" / "line-index-sync.md"

    res = run(ALGORITHM_SCRIPT, str(outside), "--check", cwd=tmp_path)
    assert res.returncode == 2
    assert "build_index: path escapes the working directory" in res.stderr

    res = run(ALGORITHM_SCRIPT, str(outside), cwd=tmp_path)
    assert res.returncode == 2
    assert "build_index: path escapes the working directory" in res.stderr

    res = run(ALGORITHM_SCRIPT, "../escape-target.md", "--check", cwd=tmp_path)
    assert res.returncode == 2
    assert "build_index: path escapes the working directory" in res.stderr
