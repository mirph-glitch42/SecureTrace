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

__all__ = [
    "CLI_VERBS",
    "DOC_TITLES",
    "DEFAULT_STORE_PATHS",
    "canonical_json",
    "generated_header",
    "sha256_hex",
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
