"""Integrity manifest + check diagnostics for the deterministic document pipeline (B10).

``data/manifest.json`` pins, per pipeline document, the sha256 of the
authoritative store and of the rendered document at the moment of the last
render, plus the renderer version that produced them. ``check`` uses the
manifest to tell *doc modified outside the app* apart from *store modified
after render* (algorithms/deterministic-doc-pipeline.md, contract C3).

The manifest is itself stored in canonical JSON (``canonical.canonical_json``)
and written atomically (temp file + ``os.replace``).

WI 7 adds the check core (spec §3 ``CHECK``, §5.3): :func:`check_doc` is the
pure diagnosis (validate store → re-render → byte-compare → discriminate the
drift direction via the manifest entry); :func:`check_paths` is the I/O
wrapper; :func:`check_message` builds the stderr line with the exact
remediation command.

WI 8 adds the render commit path (spec §3 ``COMMIT``): :func:`write_store`
writes a validated store in canonical JSON, and :func:`commit_render` is the
one-shot store-write + doc-render + manifest-refresh pipeline that every
mutating command goes through, so the store, the rendered document, and the
manifest can never diverge silently.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

from securetrace.docs import RENDERER_VERSION
from securetrace.docs.backlog_doc import render_backlog
from securetrace.docs.canonical import CLI_VERBS, canonical_json, sha256_hex
from securetrace.docs.lessons_doc import render_lessons
from securetrace.docs.registry_doc import render_registry
from securetrace.docs.schema import SchemaError, validate_store

__all__ = [
    "DOC_KINDS",
    "DOC_MISSING",
    "DOC_MODIFIED_OUTSIDE_APP",
    "IN_SYNC",
    "MALFORMED_DOC",
    "MALFORMED_MANIFEST",
    "MALFORMED_STORE",
    "MANIFEST_VERSION",
    "STORE_DRIFT",
    "STORE_DRIFT_OR_DOC_DRIFT",
    "check_doc",
    "check_message",
    "check_paths",
    "commit_render",
    "entry_matches",
    "load_manifest",
    "make_entry",
    "manifest_text",
    "new_manifest",
    "save_manifest",
    "validate_manifest",
    "write_store",
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


def _validate_manifest_header(manifest: dict) -> dict:
    """Check the manifest header fields; return the ``docs`` mapping.

    Raises:
        SchemaError: ``manifest_version`` mismatch, empty ``renderer_version``,
            or ``docs`` not an object.
    """
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
    return docs


def _validate_manifest_entry(kind: str, entry: object) -> None:
    """Validate one ``manifest.docs[kind]`` entry.

    Raises:
        SchemaError: wrong key set, empty ``doc``/``store`` path, or a
            non-lowercase-hex sha256.
    """
    what = f"manifest.docs[{kind}]"
    if not isinstance(entry, dict) or set(entry) != set(_ENTRY_KEYS):
        raise SchemaError(f"{what} must have exactly the keys: {', '.join(_ENTRY_KEYS)}")
    for key in ("doc", "store"):
        if not isinstance(entry[key], str) or not entry[key].strip():
            raise SchemaError(f"{what}.{key} must be a non-empty string")
    for key in ("store_sha256", "doc_sha256"):
        if not isinstance(entry[key], str) or not _SHA256_RE.fullmatch(entry[key]):
            raise SchemaError(f"{what}.{key} must be a lowercase hex sha256")


def validate_manifest(manifest: object) -> None:
    """Validate a manifest dict. Raises :class:`SchemaError` on any violation."""
    if not isinstance(manifest, dict):
        raise SchemaError(f"manifest must be a JSON object, got {type(manifest).__name__}")
    docs = _validate_manifest_header(manifest)
    for kind, entry in docs.items():
        if kind not in DOC_KINDS:
            raise SchemaError(f"manifest.docs has unknown kind: {kind!r}")
        _validate_manifest_entry(kind, entry)


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


# --------------------------------------------------------------------- check (WI 7; spec §3 CHECK, §5.3)

#: The closed diagnosis set (spec §3 pseudocode + §5.3 exit-2 bucket).
IN_SYNC = "IN_SYNC"
STORE_DRIFT = "STORE_DRIFT"
STORE_DRIFT_OR_DOC_DRIFT = "STORE_DRIFT_OR_DOC_DRIFT"
DOC_MODIFIED_OUTSIDE_APP = "DOC_MODIFIED_OUTSIDE_APP"
MALFORMED_STORE = "MALFORMED_STORE"
MALFORMED_DOC = "MALFORMED_DOC"
MALFORMED_MANIFEST = "MALFORMED_MANIFEST"
DOC_MISSING = "DOC_MISSING"

#: Renderer per store kind — the single ``RENDER_DOC`` the spec §5.3 requires:
#: ``render`` and ``check`` compute expected bytes the same way, so they can
#: never disagree.
_RENDER_DOC = {
    "backlog": render_backlog,
    "lessons": render_lessons,
    "registry": render_registry,
}


def _decode_or_none(data: bytes | str) -> str | None:
    """UTF-8 decode *data* (str passes through); None when undecodable."""
    if isinstance(data, str):
        return data
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _parse_store(text: str) -> dict | None:
    """Parse store JSON text; None unless it is a JSON object."""
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def check_doc(kind: str, store_bytes: bytes | str, doc_bytes: bytes | str, entry: dict | None) -> tuple[int, str]:
    """Pure check core (no I/O). Returns ``(exit_code, diagnosis)``.

    Spec §3 ``CHECK``: validate the store (else exit 2 ``MALFORMED_STORE``),
    re-render it, and byte-compare against the actual document. A manifest
    entry discriminates the drift direction: doc moved →
    ``DOC_MODIFIED_OUTSIDE_APP``; store moved → ``STORE_DRIFT``; both moved →
    ``STORE_DRIFT_OR_DOC_DRIFT``; doc equals the fresh render but the manifest
    pins the old store → ``STORE_DRIFT``. A missing entry is malformed state
    (exit 2 ``MALFORMED_MANIFEST``).

    Raises:
        SchemaError: *kind* is not one of :data:`DOC_KINDS` (programmer error).
    """
    if kind not in DOC_KINDS:
        raise SchemaError(f"unknown doc kind: {kind!r}")

    store_text = _decode_or_none(store_bytes)
    if store_text is None:
        return 2, MALFORMED_STORE
    store = _parse_store(store_text)
    if store is None or store.get("doc") != kind:
        return 2, MALFORMED_STORE
    try:
        validate_store(store)
    except SchemaError:
        return 2, MALFORMED_STORE

    expected = _RENDER_DOC[kind](store)
    actual = _decode_or_none(doc_bytes)
    if actual is None:
        return 2, MALFORMED_DOC

    if entry is None:
        return 2, MALFORMED_MANIFEST
    store_hash = sha256_hex(store_bytes)
    if actual == expected:
        if entry_matches(entry, store_bytes, expected):
            return 0, IN_SYNC
        return 1, STORE_DRIFT
    if isinstance(entry, dict) and entry.get("store_sha256") == store_hash:
        return 1, DOC_MODIFIED_OUTSIDE_APP
    return 1, STORE_DRIFT_OR_DOC_DRIFT


def check_paths(kind: str, store_path: str | Path, doc_path: str | Path, manifest_path: str | Path) -> tuple[int, str]:
    """I/O wrapper for :func:`check_doc`: read the three files, delegate.

    File-level failures map to the spec §5.3 exit-2 bucket in the order the
    spec checks them: store (``MALFORMED_STORE``), doc (``DOC_MISSING``),
    manifest (``MALFORMED_MANIFEST``).

    Raises:
        SchemaError: *kind* is not one of :data:`DOC_KINDS` (programmer error).
    """
    if kind not in DOC_KINDS:
        raise SchemaError(f"unknown doc kind: {kind!r}")
    try:
        store_bytes = Path(store_path).read_bytes()
    except OSError:
        return 2, MALFORMED_STORE
    try:
        doc_bytes = Path(doc_path).read_bytes()
    except OSError:
        return 2, DOC_MISSING
    try:
        manifest = load_manifest(manifest_path)
    except SchemaError:
        return 2, MALFORMED_MANIFEST
    return check_doc(kind, store_bytes, doc_bytes, manifest["docs"].get(kind))


def check_message(kind: str, diagnosis: str, store_path: str) -> str:
    """Build the stderr line for a check result: diagnosis + remediation command.

    Spec §5.3: a stale check (exit 1) carries the diagnosis and the exact
    remediation command; the exit-2 diagnoses name the malformed artifact.

    Raises:
        ValueError: *kind* is unknown, or *diagnosis* is not in the closed set.
    """
    if kind not in CLI_VERBS:
        raise ValueError(f"unknown doc kind: {kind!r}")
    verb = CLI_VERBS[kind]
    render_cmd = f"securetrace {verb} render {store_path}"
    check_cmd = f"securetrace {verb} check {store_path}"
    messages = {
        IN_SYNC: f"check: {kind} is in sync with its store (doc and manifest sha256s agree)",
        DOC_MODIFIED_OUTSIDE_APP: (
            f"check: {DOC_MODIFIED_OUTSIDE_APP} — the document was modified outside the app "
            f"(store unchanged since the last render). Manual editing is not permitted: "
            f"update the store via the `{verb}` CLI commands, then re-render: {render_cmd}"
        ),
        STORE_DRIFT: (
            f"check: {STORE_DRIFT} — the store was modified after the last render. "
            f"Re-render: {render_cmd}"
        ),
        STORE_DRIFT_OR_DOC_DRIFT: (
            f"check: {STORE_DRIFT_OR_DOC_DRIFT} — the store and/or the document moved since "
            f"the last render. Re-render: {render_cmd}; then verify: {check_cmd}"
        ),
        MALFORMED_STORE: (
            f"check: {MALFORMED_STORE} — the store is missing, unreadable, or fails schema validation (exit 2)"
        ),
        MALFORMED_DOC: f"check: {MALFORMED_DOC} — the document is not valid UTF-8 text (exit 2)",
        MALFORMED_MANIFEST: (
            f"check: {MALFORMED_MANIFEST} — the manifest is missing, unreadable, or has no entry "
            f"for this doc (exit 2)"
        ),
        DOC_MISSING: f"check: {DOC_MISSING} — the document file is missing or unreadable (exit 2)",
    }
    try:
        return messages[diagnosis]
    except KeyError:
        raise ValueError(f"unknown diagnosis: {diagnosis!r}") from None


# ------------------------------------------------------------------- render commit (WI 8; spec §3 COMMIT)


def _write_text(path: Path, text: str) -> None:
    """Atomically replace *path* with *text* (temp file + ``os.replace``).

    Same pattern as :func:`save_manifest`; parent directories are created.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=".securetrace-", suffix=".tmp")
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


def write_store(path: str | Path, store: object) -> None:
    """Validate *store* and atomically write it in canonical JSON (C1).

    The canonical text (``canonical_json``) is the store's byte form of
    record; the same text's sha256 is what :func:`commit_render` pins in the
    manifest, so a store that passes here is exactly what ``check`` compares.

    Raises:
        SchemaError: *store* fails schema validation (nothing is written).
    """
    validate_store(store)
    _write_text(Path(path), canonical_json(store))


def commit_render(
    kind: str,
    store: object,
    store_path: str | Path,
    doc_path: str | Path,
    manifest_path: str | Path,
) -> None:
    """Commit one render: write the store, render the doc, refresh the manifest.

    The pipeline (spec §3 ``COMMIT``) is: validate the store → write it in
    canonical JSON (atomic) → render the document with the per-kind renderer
    → write the document (atomic) → refresh the manifest entry for *kind*
    (store + doc sha256s, preserving the other kinds' entries) → save the
    manifest (atomic). ``render`` and ``check`` compute expected bytes the
    same way (``_RENDER_DOC``), so they can never disagree (spec §5.3).

    Raises:
        SchemaError: *kind* is unknown, the store fails validation, or the
          existing manifest is malformed (nothing after that step is written).
    """
    if kind not in DOC_KINDS:
        raise SchemaError(f"unknown doc kind: {kind!r}")
    validate_store(store)
    store_text = canonical_json(store)
    write_store(store_path, store)
    doc_text = _RENDER_DOC[kind](store)
    _write_text(Path(doc_path), doc_text)
    manifest_path_p = Path(manifest_path)
    if manifest_path_p.exists():
        manifest = load_manifest(manifest_path_p)
    else:
        manifest = new_manifest(RENDERER_VERSION)
    manifest["docs"][kind] = make_entry(kind, str(doc_path), str(store_path), store_text, doc_text)
    save_manifest(manifest_path_p, manifest)
