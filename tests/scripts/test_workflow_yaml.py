"""Tests for scripts/check_workflow_yaml.py (B8).

The checker closes the parser-divergence gap from the B5 incident
(LLT-0017/LLT-0018): GitHub's workflow parser hard-fails a workflow with
duplicate mapping keys in one mapping, while PyYAML/Ruby Psych silently
keep the last value. The checker must therefore hard-fail locally,
reporting file + key + 1-based line of the *second* occurrence, under the
0/1/2 exit contract pinned in algorithms/workflow-yaml-strict-parse.md:

  0  all files clean
  1  >= 1 duplicate-key finding or parse error (content findings)
  2  usage/environment error (no files, missing explicit file, no PyYAML)
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable  # the venv interpreter (PyYAML is a pinned dev dependency)
SCRIPT = ROOT / "scripts" / "check_workflow_yaml.py"

# --- fixtures (one per test-table row in the algorithm doc, §6) ------------

CLEAN = """\
name: ci
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
"""

DUP_TOP_LEVEL = """\
on: push
on: pull_request
jobs: {}
"""

DUP_NESTED = """\
jobs:
  a:
    permissions:
      contents: read
      contents: write
"""

FLOW_DUP = """\
jobs: {a: {steps: [{run: x, run: y}]}}
"""

SAME_KEY_DIFFERENT_MAPPINGS = """\
jobs:
  a:
    steps:
      - run: x
  b:
    steps:
      - run: y
"""

MALFORMED = """\
jobs:
  a:
   steps: [x
"""


def run(*args: str) -> subprocess.CompletedProcess[str]:
    """Run the checker with the repo root as CWD (default discovery depends on it)."""
    if not SCRIPT.exists():
        raise AssertionError(f"B8 WI 3 (RED): {SCRIPT} does not exist yet")
    return subprocess.run([PY, str(SCRIPT), *args], capture_output=True, text=True, cwd=ROOT)


def test_clean_file_passes(tmp_path: Path) -> None:
    wf = tmp_path / "clean.yml"
    wf.write_text(CLEAN)
    result = run(str(wf))
    assert result.returncode == 0, result.stdout
    assert f"✓ {wf} OK" in result.stdout


def test_duplicate_top_level_key_fails_with_key_and_line(tmp_path: Path) -> None:
    wf = tmp_path / "dup.yml"
    wf.write_text(DUP_TOP_LEVEL)
    result = run(str(wf))
    assert result.returncode == 1
    # The key label is the source text ('on'), not the constructed bool ('True').
    assert f"✗ {wf}: duplicate key 'on' at line 2" in result.stdout


def test_duplicate_nested_key_fails(tmp_path: Path) -> None:
    wf = tmp_path / "nested.yml"
    wf.write_text(DUP_NESTED)
    result = run(str(wf))
    assert result.returncode == 1
    assert f"✗ {wf}: duplicate key 'contents' at line 5" in result.stdout


def test_flow_style_duplicate_fails(tmp_path: Path) -> None:
    wf = tmp_path / "flow.yml"
    wf.write_text(FLOW_DUP)
    result = run(str(wf))
    assert result.returncode == 1
    assert f"✗ {wf}: duplicate key 'run' at line 1" in result.stdout


def test_same_key_in_different_mappings_passes(tmp_path: Path) -> None:
    wf = tmp_path / "siblings.yml"
    wf.write_text(SAME_KEY_DIFFERENT_MAPPINGS)
    result = run(str(wf))
    assert result.returncode == 0, result.stdout
    assert f"✓ {wf} OK" in result.stdout


def test_malformed_yaml_is_parse_error_exit_1(tmp_path: Path) -> None:
    wf = tmp_path / "bad.yml"
    wf.write_text(MALFORMED)
    result = run(str(wf))
    assert result.returncode == 1
    assert f"✗ {wf}: parse error:" in result.stdout


def test_missing_explicit_file_exit_2(tmp_path: Path) -> None:
    missing = tmp_path / "nope.yml"
    result = run(str(missing))
    assert result.returncode == 2
    assert f"missing or unreadable file: {missing}" in result.stdout


def test_default_discovery_passes_repo_workflows() -> None:
    result = run()
    assert result.returncode == 0, result.stdout
    assert "ci.yml" in result.stdout
    assert "release.yml" in result.stdout
    assert result.stdout.count("✓") == 2


def test_one_failure_does_not_stop_the_rest(tmp_path: Path) -> None:
    good = tmp_path / "good.yml"
    bad = tmp_path / "bad.yml"
    good.write_text(CLEAN)
    bad.write_text(DUP_TOP_LEVEL)
    result = run(str(good), str(bad))
    assert result.returncode == 1
    assert f"✓ {good} OK" in result.stdout
    assert f"✗ {bad}: duplicate key 'on' at line 2" in result.stdout
