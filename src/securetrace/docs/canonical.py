"""Canonical JSON serialization for document stores (pure, deterministic).

The canonical byte form is the store's version of record:
``sha256_hex(canonical_json(store))`` is what the integrity manifest pins
(algorithms/deterministic-doc-pipeline.md, contract C1). No clock, no
randomness, no environment — the same data always yields the same bytes.
"""

from __future__ import annotations

import hashlib
import json

__all__ = ["canonical_json", "sha256_hex"]


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
