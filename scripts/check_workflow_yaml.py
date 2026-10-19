#!/usr/bin/env python3
"""Strict-parse YAML workflow files — hard-fail on duplicate mapping keys.

Closes the parser-divergence gap (LLT-0017/LLT-0018): GitHub's workflow
parser rejects a workflow whose one mapping has duplicate keys, while
PyYAML/Ruby Psych silently keep the last value (B5 shipped a 0-job release
because of this). This checker parses with a SafeLoader subclass that
raises on the first colliding key and reports the file, the key as written,
and the 1-based line of the *second* occurrence.

Spec of record: algorithms/workflow-yaml-strict-parse.md
Exit codes: 0 = all files clean, 1 = duplicate-key or parse-error findings,
2 = usage/environment error (no files found, missing file, PyYAML absent).

Usage:
    python3 scripts/check_workflow_yaml.py [FILE ...]  # explicit files
    python3 scripts/check_workflow_yaml.py             # .github/workflows/*.yml + *.yaml
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
from pathlib import Path

try:
    import yaml
    from yaml.nodes import MappingNode, ScalarNode
except ModuleNotFoundError:  # environment problem, not content (exit 2)
    print("PyYAML required — install pinned deps (make setup)")
    raise SystemExit(2) from None


class DuplicateKeyError(yaml.MarkedYAMLError):
    """One mapping node contains the same key twice (GitHub hard-fails this)."""

    def __init__(self, label: str, line: int) -> None:
        self.label = label
        self.line = line
        super().__init__(
            context=None,
            context_mark=None,
            problem=f"duplicate key {label!r} at line {line}",
            problem_mark=None,
        )


class StrictLoader(yaml.SafeLoader):
    """SafeLoader that hard-fails on duplicate mapping keys.

    PyYAML dispatches ``construct_mapping`` exactly once per mapping node —
    block, flow, and nested — so this single override installs the duplicate
    check on the whole parse tree with exact node positions (doc I1/I2).
    """

    def construct_mapping(self, node: MappingNode, deep: bool = False) -> dict:
        seen: set = set()
        mapping: dict = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                hash(key)
            except TypeError as exc:
                raise yaml.constructor.ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    "found unhashable key",
                    key_node.start_mark,
                ) from exc
            if key in seen:
                # Report the key as written in the source (PyYAML resolves
                # YAML 1.1 `on`/`yes`/`true` to bool, so the constructed
                # object would mislabel the message).
                label = key_node.value if isinstance(key_node, ScalarNode) else str(key)
                raise DuplicateKeyError(label, key_node.start_mark.line + 1)
            seen.add(key)
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


def check_file(path: Path) -> tuple[bool, str]:
    """Strict-parse one YAML file. Returns (ok, detail); detail is '' when ok."""
    try:
        text = path.read_text(encoding="utf-8")
        yaml.load(text, Loader=StrictLoader)
    except DuplicateKeyError as exc:
        return False, f"duplicate key '{exc.label}' at line {exc.line}"
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        # First non-empty line of the (often multi-line) YAML error.
        first_line = next((ln for ln in str(exc).splitlines() if ln.strip()), str(exc))
        return False, f"parse error: {first_line}"
    return True, ""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="check_workflow_yaml",
        description=("Strict-parse YAML workflow files; hard-fail on duplicate mapping keys."),
    )
    ap.add_argument(
        "files",
        nargs="*",
        metavar="FILE",
        help="YAML files to check (default: .github/workflows/*.yml and *.yaml)",
    )
    args = ap.parse_args(argv)

    # Usage phase (exit 2 class) precedes any parse (exit 1 class).
    files = [Path(f) for f in args.files]
    if not files:
        found: set[str] = set()
        for pattern in (".github/workflows/*.yml", ".github/workflows/*.yaml"):
            found.update(glob.glob(pattern))
        files = [Path(p) for p in sorted(found)]
        if not files:
            print("no workflow files found in .github/workflows/")
            return 2

    for path in files:
        if not path.is_file() or not os.access(path, os.R_OK):
            print(f"missing or unreadable file: {path}")
            return 2

    # Parse phase: one file's failure never stops the rest — report every file.
    findings = 0
    for path in files:
        ok, detail = check_file(path)
        if ok:
            print(f"✓ {path} OK")
        else:
            print(f"✗ {path}: {detail}")
            findings += 1
    return 0 if findings == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
