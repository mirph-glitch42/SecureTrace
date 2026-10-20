"""Integrity manifest tests (B10 WI 3; ALRK doc C3 manifest model)."""

import json

import pytest

from securetrace.docs import RENDERER_VERSION
from securetrace.docs.canonical import canonical_json, sha256_hex
from securetrace.docs.integrity import (
    entry_matches,
    load_manifest,
    make_entry,
    manifest_text,
    new_manifest,
    save_manifest,
    validate_manifest,
)
from securetrace.docs.schema import SchemaError


def sample_manifest():
    m = new_manifest(RENDERER_VERSION)
    m["docs"]["backlog"] = make_entry(
        "backlog", "BACKLOG.md", "data/backlog.json", b'{"store": 1}', b"# Backlog\n"
    )
    return m


def test_new_manifest_shape():
    m = new_manifest(RENDERER_VERSION)
    assert m["manifest_version"] == 1
    assert m["renderer_version"] == RENDERER_VERSION
    assert m["docs"] == {}


def test_make_entry_pins_both_sha256s():
    entry = make_entry("backlog", "BACKLOG.md", "data/backlog.json", "store", "doc")
    assert set(entry) == {"doc", "store", "store_sha256", "doc_sha256"}
    assert entry["doc"] == "BACKLOG.md"
    assert entry["store"] == "data/backlog.json"
    assert entry["store_sha256"] == sha256_hex("store")
    assert entry["doc_sha256"] == sha256_hex("doc")


def test_make_entry_rejects_unknown_kind():
    with pytest.raises(SchemaError, match="kind"):
        make_entry("notes", "n.md", "data/n.json", b"x", b"y")


def test_manifest_text_is_canonical_and_roundtrips():
    m = sample_manifest()
    text = manifest_text(m)
    assert text == canonical_json(m)
    assert json.loads(text) == m


def test_manifest_roundtrip_through_disk(tmp_path):
    m = sample_manifest()
    path = tmp_path / "data" / "manifest.json"
    save_manifest(path, m)
    assert path.read_text(encoding="utf-8") == manifest_text(m)
    assert load_manifest(path) == m


def test_load_manifest_rejects_bad_sha256_shape(tmp_path):
    m = sample_manifest()
    m["docs"]["backlog"]["store_sha256"] = "not-a-hash"
    path = tmp_path / "manifest.json"
    path.write_text(canonical_json(m), encoding="utf-8")
    with pytest.raises(SchemaError, match="sha256"):
        load_manifest(path)


def test_load_manifest_rejects_unknown_doc_kind(tmp_path):
    m = sample_manifest()
    m["docs"]["notes"] = {
        "doc": "n.md",
        "store": "data/n.json",
        "store_sha256": "0" * 64,
        "doc_sha256": "0" * 64,
    }
    path = tmp_path / "manifest.json"
    path.write_text(canonical_json(m), encoding="utf-8")
    with pytest.raises(SchemaError, match="notes"):
        load_manifest(path)


def test_validate_manifest_rejects_bad_version():
    m = sample_manifest()
    m["manifest_version"] = 99
    with pytest.raises(SchemaError, match="manifest_version"):
        validate_manifest(m)


def test_entry_matches_pure_comparison():
    entry = make_entry("backlog", "B.md", "data/b.json", b"store-bytes", b"doc-bytes")
    assert entry_matches(entry, b"store-bytes", b"doc-bytes") is True
    assert entry_matches(entry, b"store-bytes", b"doc-BYTES") is False
    assert entry_matches(entry, b"OTHER-STORE", b"doc-bytes") is False
    assert entry_matches("nonsense", b"x", b"y") is False
    assert entry_matches(None, b"x", b"y") is False
