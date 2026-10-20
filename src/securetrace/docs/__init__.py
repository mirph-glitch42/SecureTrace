"""Deterministic document pipeline (B10).

The three pipeline documents (``BACKLOG.md``, ``LESSONS_LEARNED.md``,
``algorithms/INDEX.md``) are pure renders of canonical-JSON stores under
``data/``; ``data/manifest.json`` pins the sha256 of store and rendered doc
so out-of-band edits are diagnosable (user requirement: CLI-only mutation +
tamper detection + auto-built .md docs).

This subpackage is the pure core:

- :mod:`securetrace.docs.canonical` — canonical JSON + sha256 helpers;
- :mod:`securetrace.docs.schema` — store schema validation (exit 2 upstream);
- :mod:`securetrace.docs.integrity` — the integrity manifest model.

Parsers and renderers land with B10 WI 4–6. Spec:
``algorithms/deterministic-doc-pipeline.md``.
"""

__all__ = ["RENDERER_VERSION"]

#: Version of the renderers; stamped into every generated header and the
#: manifest. Bumping it changes expected doc bytes (pinned by tests).
RENDERER_VERSION = "0.1.0"
