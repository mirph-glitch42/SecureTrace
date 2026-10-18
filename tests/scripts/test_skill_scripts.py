"""Functional tests for the vendored skill scripts.

These scripts are the source of truth for the document index checks that run
in pre-commit hooks and CI (make docs-check). A regression in them silently
disables the staleness gates, so they carry real tests here.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable  # scripts are stdlib-only; the venv interpreter is fine

BACKLOG_SCRIPT = ROOT / "scripts" / "backlog_index.py"
LESSONS_SCRIPT = ROOT / "scripts" / "manage_lessons.py"
ALGORITHM_SCRIPT = ROOT / "scripts" / "algorithm_index.py"


def run(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([PY, str(script), *args], capture_output=True, text=True, cwd=ROOT)


BACKLOG_FIXTURE = """\
# Backlog

<!-- INDEX:BEGIN format=tsv version=1 -->
<!-- placeholder interior line -->
<!-- INDEX:END -->

<!-- BACKLOG:HEADER -->
## Status

**Queue:** B1 | **In progress:** — | **Done:** — | **Updated:** 2026-10-18

<!-- BACKLOG:QUEUE -->
## Queue (execution order)

1. **B1** (High) — bootstrap the project

<!-- BACKLOG:ITEM:B1 -->
## B1. Bootstrap — **OPEN**

- **Source:** user
- **Priority:** High
- **Acceptance criteria:** gates green

<!-- BACKLOG:CONSTRAINTS -->
## Standing constraints

- no bypassing gates
"""


def test_backlog_index_roundtrip(tmp_path: Path) -> None:
    backlog = tmp_path / "BACKLOG.md"
    backlog.write_text(BACKLOG_FIXTURE)

    assert run(BACKLOG_SCRIPT, str(backlog)).returncode == 0
    assert run(BACKLOG_SCRIPT, str(backlog), "--check").returncode == 0

    # A body edit must make --check report a stale index (exit 1).
    backlog.write_text(BACKLOG_FIXTURE + "\nextra progress line\n")
    stale = run(BACKLOG_SCRIPT, str(backlog), "--check")
    assert stale.returncode == 1

    # Regenerating clears the staleness.
    assert run(BACKLOG_SCRIPT, str(backlog)).returncode == 0
    assert run(BACKLOG_SCRIPT, str(backlog), "--check").returncode == 0


def test_backlog_index_rejects_missing_markers(tmp_path: Path) -> None:
    bad = tmp_path / "BAD.md"
    bad.write_text("# Backlog\n\nno markers at all\n")
    assert run(BACKLOG_SCRIPT, str(bad), "--check").returncode == 2


def test_lessons_init_add_supersede(tmp_path: Path) -> None:
    record = tmp_path / "LESSONS_LEARNED.md"
    assert run(LESSONS_SCRIPT, "init", str(record)).returncode == 0
    assert run(LESSONS_SCRIPT, "check", str(record)).returncode == 0

    add = run(
        LESSONS_SCRIPT,
        "add",
        str(record),
        "--title",
        "fixture lesson",
        "--context",
        "unit-testing the script",
        "--pitfall",
        "stale index goes unnoticed",
        "--solution",
        "run --check in CI",
        "--category",
        "testing",
        "--severity",
        "medium",
    )
    assert add.returncode == 0, add.stderr
    assert run(LESSONS_SCRIPT, "check", str(record)).returncode == 0

    supersede = run(
        LESSONS_SCRIPT,
        "add",
        str(record),
        "--title",
        "fixture lesson replacement",
        "--context",
        "superseding the first lesson",
        "--pitfall",
        "contradictory lessons",
        "--solution",
        "use --supersedes",
        "--category",
        "process",
        "--severity",
        "low",
        "--supersedes",
        "LLT-0001",
    )
    assert supersede.returncode == 0, supersede.stderr
    assert run(LESSONS_SCRIPT, "check", str(record)).returncode == 0

    assert run(LESSONS_SCRIPT, "next-id", str(record)).stdout.strip() == "LLT-0003"


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
