"""Canonical JSON serialization for document stores (pure, deterministic).

The canonical byte form is the store's version of record:
``sha256_hex(canonical_json(store))`` is what the integrity manifest pins
(algorithms/deterministic-doc-pipeline.md, contract C1). No clock, no
randomness, no environment — the same data always yields the same bytes.

This module also pins the per-kind document constants the renderers share:
the title line, the CLI verb, the default store path, and the generated
no-hand-edit header block (contract C4).
"""

from __future__ import annotations

import hashlib
import json

from securetrace.errors import FormatError

__all__ = [
    "CLI_VERBS",
    "DEFAULT_DOC_PATHS",
    "DOC_TITLES",
    "DEFAULT_STORE_PATHS",
    "GENERATED_BEGIN_PREFIX",
    "GENERATED_END_PREFIX",
    "canonical_json",
    "generated_header",
    "sha256_hex",
    "skip_generated_header",
]

#: Title line per pipeline doc kind (a code constant — never store data).
DOC_TITLES = {
    "backlog": "# Backlog",
    "lessons": "# Lessons Learned",
    "registry": "# Algorithm Registry",
}

#: CLI verb per store kind (the registry store is the ``algorithms`` command).
CLI_VERBS = {"backlog": "backlog", "lessons": "lessons", "registry": "algorithms"}

#: Default store path per kind (standard repo layout, relative to the repo root).
DEFAULT_STORE_PATHS = {
    "backlog": "data/backlog.json",
    "lessons": "data/lessons.json",
    "registry": "data/algorithms.json",
}

#: Default rendered-doc path per kind (standard repo layout, relative to the
#: repo root; ``docs render-all`` / ``docs check-all`` use these CWD-relative).
DEFAULT_DOC_PATHS = {
    "backlog": "BACKLOG.md",
    "lessons": "LESSONS_LEARNED.md",
    "registry": "algorithms/INDEX.md",
}


def canonical_json(store: object) -> str:
    """Serialize *store* to its unique canonical text form.

    Keys are sorted, indentation is 2 spaces, non-ASCII characters are kept
    readable (``ensure_ascii=False``), line endings are LF, and exactly one
    trailing newline is appended. Input key order never influences the output
    (contract C1).
    """
    return json.dumps(store, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def sha256_hex(data: str | bytes) -> str:
    """Return the lowercase hex sha256 of *data* (text is UTF-8 encoded)."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def generated_header(
    kind: str,
    store_path: str | None = None,
    renderer_version: str | None = None,
) -> list[str]:
    """Return the 7-line generated no-hand-edit header for *kind* (contract C4).

    The header is a code constant (it carries no store data): the
    no-manual-editing warning, the authoritative store path, the CLI commands
    to update and verify the document, and the renderer version. ``kind`` must
    be one of :data:`DOC_TITLES`; ``store_path`` defaults to the standard repo
    layout; ``renderer_version`` is required (callers pass
    :data:`securetrace.docs.RENDERER_VERSION`).

    Raises:
        ValueError: *kind* is unknown, or *renderer_version* is blank.
    """
    if kind not in DOC_TITLES:
        raise ValueError(f"unknown doc kind: {kind!r}")
    if store_path is None:
        store_path = DEFAULT_STORE_PATHS[kind]
    if renderer_version is None or not str(renderer_version).strip():
        raise ValueError("renderer_version is required (pass securetrace.docs.RENDERER_VERSION)")
    verb = CLI_VERBS[kind]
    return [
        f"<!-- GENERATED:BEGIN securetrace v{renderer_version} -->",
        "<!-- This document is rendered by the SecureTrace CLI. DO NOT EDIT BY HAND — manual editing is not permitted. -->",
        f"<!-- Authoritative store: {store_path} (update it via the `{verb}` CLI commands, then re-render). -->",
        f"<!-- Re-render: securetrace {verb} render {store_path} -->",
        f"<!-- Verify: securetrace {verb} check {store_path} (re-render + byte-compare + manifest). -->",
        f"<!-- Renderer: securetrace.docs v{renderer_version} | Spec: algorithms/deterministic-doc-pipeline.md -->",
        "<!-- GENERATED:END -->",
    ]


#: Marker line prefixes of the generated header block (contract C4).
GENERATED_BEGIN_PREFIX = "<!-- GENERATED:BEGIN"
GENERATED_END_PREFIX = "<!-- GENERATED:END"


def skip_generated_header(lines: list[str], start: int) -> int:
    """If a generated header block starts at *start*, return the index past it.

    The block is the BEGIN line, comment lines only, and the END line; one
    following blank line is consumed when present (the renderer always emits
    it; a missing one is caught later by the index-freshness check).
    Grandfathered docs have no block at all — *start* is returned unchanged.

    Raises:
        FormatError: the block is unterminated or contains a non-comment line.
    """
    if start >= len(lines) or not lines[start].startswith(GENERATED_BEGIN_PREFIX):
        return start
    end = None
    for j in range(start, len(lines)):
        if lines[j].startswith(GENERATED_END_PREFIX):
            end = j
            break
    if end is None:
        raise FormatError("generated header block is missing its <!-- GENERATED:END --> line")
    for j in range(start + 1, end):
        if not (lines[j].startswith("<!--") and lines[j].endswith("-->")):
            raise FormatError("generated header block contains a non-comment line")
    cursor = end + 1
    if cursor < len(lines) and lines[cursor] == "":
        cursor += 1
    return cursor
