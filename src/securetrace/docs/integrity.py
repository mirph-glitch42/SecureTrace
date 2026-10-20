"""Integrity manifest for the deterministic document pipeline (B10).

``data/manifest.json`` pins, per pipeline document, the sha256 of the
authoritative store and of the rendered document at the moment of the last
render, plus the renderer version that produced them. ``check`` uses the
manifest to tell *doc modified outside the app* apart from *store modified
after render* (algorithms/deterministic-doc-pipeline.md, contract C3).

The manifest is itself stored in canonical JSON (``canonical.canonical_json``)
and written atomically (temp file + ``os.replace``).
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

from securetrace.docs.canonical import canonical_json, sha256_hex
from securetrace.docs.schema import SchemaError

__all__ = [
    "DOC_KINDS",
    "MANIFEST_VERSION",
    "entry_matches",
    "load_manifest",
    "make_entry",
    "manifest_text",
    "new_manifest",
    "save_manifest",
    "validate_manifest",
]

MANIFEST_VERSION = 1
DOC_KINDS = ("backlog", "lessons", "registry")
_ENTRY_KEYS = ("doc", "store", "store_sha256", "doc_sha256")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def new_manifest(renderer_version: str) -> dict:
    """Return an empty manifest for *renderer_version*."""
    if not isinstance(renderer_version, str) or not renderer_version.strip():
        raise SchemaError("renderer_version must be a non-empty string")
    return {
        "manifest_version": MANIFEST_VERSION,
        "renderer_version": renderer_version,
        "docs": {},
    }


def make_entry(
    kind: str,
    doc_path: str,
    store_path: str,
    store_bytes: bytes | str,
    doc_bytes: bytes | str,
) -> dict:
    """Build a manifest entry pinning the sha256 of store and rendered doc."""
    if kind not in DOC_KINDS:
        raise SchemaError(f"unknown doc kind: {kind!r}")
    return {
        "doc": doc_path,
        "store": store_path,
        "store_sha256": sha256_hex(store_bytes),
        "doc_sha256": sha256_hex(doc_bytes),
    }


def validate_manifest(manifest: object) -> None:
    """Validate a manifest dict. Raises :class:`SchemaError` on any violation."""
    if not isinstance(manifest, dict):
        raise SchemaError(f"manifest must be a JSON object, got {type(manifest).__name__}")
    if manifest.get("manifest_version") != MANIFEST_VERSION:
        raise SchemaError(
            "manifest_version must be "
            f"{MANIFEST_VERSION}, got {manifest.get('manifest_version')!r}"
        )
    if not isinstance(manifest.get("renderer_version"), str) or not manifest["renderer_version"].strip():
        raise SchemaError("manifest.renderer_version must be a non-empty string")
    docs = manifest.get("docs")
    if not isinstance(docs, dict):
        raise SchemaError("manifest.docs must be an object")
    for kind, entry in docs.items():
        if kind not in DOC_KINDS:
            raise SchemaError(f"manifest.docs has unknown kind: {kind!r}")
        what = f"manifest.docs[{kind}]"
        if not isinstance(entry, dict) or set(entry) != set(_ENTRY_KEYS):
            raise SchemaError(f"{what} must have exactly the keys: {', '.join(_ENTRY_KEYS)}")
        for key in ("doc", "store"):
            if not isinstance(entry[key], str) or not entry[key].strip():
                raise SchemaError(f"{what}.{key} must be a non-empty string")
        for key in ("store_sha256", "doc_sha256"):
            if not isinstance(entry[key], str) or not _SHA256_RE.fullmatch(entry[key]):
                raise SchemaError(f"{what}.{key} must be a lowercase hex sha256")


def manifest_text(manifest: object) -> str:
    """Return the canonical JSON text of a validated manifest."""
    validate_manifest(manifest)
    return canonical_json(manifest)


def load_manifest(path: str | Path) -> dict:
    """Read and validate the manifest at *path*. Raises :class:`SchemaError`."""
    p = Path(path)
    try:
        raw = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise SchemaError(f"cannot read manifest {p}: {exc}") from exc
    try:
        manifest = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SchemaError(f"manifest {p} is not valid JSON: {exc}") from exc
    validate_manifest(manifest)
    return manifest


def save_manifest(path: str | Path, manifest: object) -> None:
    """Atomically write the canonical manifest to *path* (parent dirs created)."""
    text = manifest_text(manifest)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=".manifest-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.replace(tmp, p)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def entry_matches(entry: object, store_bytes: bytes | str, doc_bytes: bytes | str) -> bool:
    """Return True iff *entry* pins exactly these store and doc bytes (pure)."""
    if not isinstance(entry, dict):
        return False
    return (
        entry.get("store_sha256") == sha256_hex(store_bytes)
        and entry.get("doc_sha256") == sha256_hex(doc_bytes)
    )
