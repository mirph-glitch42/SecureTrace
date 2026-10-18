#!/usr/bin/env python3
"""Run pytest only for the tests that cover the staged changes (fast gate).

Pre-commit hooks must stay under ~5 s, so we map the staged diff onto test
paths and run just those. The mapping is intentionally conservative: when a
change does not clearly map to a test subset (initial commit, docs-only,
package-wide files, or anything under scripts/), we run the full suite.
The suite is small, and an over-broad run is far cheaper than a silent gap.

Mapping rules:
  src/securetrace/<mod>/...  ->  tests/<mod>/
  src/securetrace/<file>.py  ->  full suite (top-level package contract)
  scripts/*.py               ->  tests/scripts/ + full suite (gate scripts)
  BACKLOG.md / LESSONS_LEARNED.md / algorithms/**  ->  tests/scripts/
  anything else              ->  no test subset (docs/config only)

Usage: python3 scripts/changed_tests.py
Exit codes: 0 = tests passed, 1 = tests failed, 2 = usage/environment error.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYTEST = REPO_ROOT / ".venv" / "bin" / "pytest"


def run(args: list[str], **kwargs) -> str:
    return subprocess.run(
        args, check=False, capture_output=True, text=True, cwd=REPO_ROOT, **kwargs
    ).stdout


def has_head() -> bool:
    return (
        subprocess.run(
            ["git", "rev-parse", "--verify", "-q", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
        ).returncode
        == 0
    )


def staged_files() -> list[str]:
    out = run(["git", "diff", "--name-only", "--cached"])
    return [line for line in out.splitlines() if line.strip()]


def map_change(path: str) -> str:
    """Return 'full', 'scripts', a test dir, or '' (no test subset)."""
    if path.startswith("src/securetrace/"):
        parts = path.split("/")
        if len(parts) == 3:  # src/securetrace/<file>.py
            return "full"
        module = parts[2]
        test_dir = REPO_ROOT / "tests" / module
        return str(test_dir) if test_dir.is_dir() else "full"
    if path.startswith("scripts/"):
        return "scripts+full"
    if path in ("BACKLOG.md", "LESSONS_LEARNED.md") or path.startswith("algorithms/"):
        return "scripts"
    return ""


def main() -> int:
    if not PYTEST.exists():
        print("changed_tests: .venv missing — run `make setup` first", file=sys.stderr)
        return 2
    if not has_head():
        targets = ["tests"]  # initial commit: everything is new
    else:
        mapped = {map_change(p) for p in staged_files()}
        mapped.discard("")
        if "full" in mapped or "scripts+full" in mapped or not mapped:
            targets = ["tests"]
        else:
            targets = sorted({t if t != "scripts" else "tests/scripts" for t in mapped})
    cmd = [str(PYTEST), *targets]
    print(f"changed_tests: running {subprocess.list2cmdline(cmd)}")
    result = subprocess.run(cmd, cwd=REPO_ROOT)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
