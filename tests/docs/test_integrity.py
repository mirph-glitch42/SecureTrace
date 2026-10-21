"""Integrity manifest tests (B10 WI 3; ALRK doc C3 manifest model)."""

import json
from pathlib import Path

import pytest

from securetrace.docs import RENDERER_VERSION
from securetrace.docs.backlog_doc import render_backlog
from securetrace.docs.canonical import canonical_json, sha256_hex
from securetrace.docs.integrity import (
    DOC_MISSING,
    DOC_MODIFIED_OUTSIDE_APP,
    IN_SYNC,
    MALFORMED_DOC,
    MALFORMED_MANIFEST,
    MALFORMED_STORE,
    STORE_DRIFT,
    STORE_DRIFT_OR_DOC_DRIFT,
    check_doc,
    check_message,
    check_paths,
    entry_matches,
    load_manifest,
    make_entry,
    manifest_text,
    new_manifest,
    save_manifest,
    validate_manifest,
)
from securetrace.docs.schema import SCHEMA_VERSION, SchemaError


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


# --------------------------------------------------------------------- WI 7: check diagnostics (spec §3 CHECK, §5.3, T5/T6/T7)


def store_v1() -> dict:
    """The one-item backlog store of ALRK doc T1 (B1, 2 progress lines, 3-line closeout)."""
    return {
        "doc": "backlog",
        "schema_version": SCHEMA_VERSION,
        "updated": "2026-10-20",
        "header": ["Tracks all SecureTrace work.", "", "**Queue:** B1 | **In progress:** B1 | **Done:** — | **Updated:** 2026-10-20"],
        "queue": ["**B1** (synthetic item)"],
        "items": [
            {
                "id": "B1",
                "title": "Synthetic item",
                "status": "IN PROGRESS",
                "fields": [
                    {"name": "Source", "lines": ["user"]},
                    {
                        "name": "Progress",
                        "lines": ["  - 2026-10-20 — started", "  - 2026-10-20 — step done"],
                    },
                    {
                        "name": "Closeout",
                        "lines": [
                            "  - 2026-10-20 — gate green (219 tests)",
                            "  - 2026-10-20 — CI green (SonarCloud/quality/security)",
                            "  - 2026-10-20 — closed with evidence",
                        ],
                    },
                ],
            }
        ],
        "constraints": ["- gate green"],
    }


def store_v2() -> dict:
    """``store_v1`` with one progress line appended after the last render (T6)."""
    store = store_v1()
    store["items"][0]["fields"][1]["lines"].append("  - 2026-10-20 — appended after render")
    return store


def entry_for(store: dict, rendered: str) -> dict:
    return make_entry("backlog", "BACKLOG.md", "data/backlog.json", canonical_json(store), rendered)


# --------------------------------------------------------------------- C3 diagnosis core


def test_check_in_sync_returns_zero():
    """C3: doc == render(store) and the manifest agrees -> (0, IN_SYNC)."""
    store = store_v1()
    rendered = render_backlog(store)
    entry = entry_for(store, rendered)
    assert check_doc("backlog", canonical_json(store), rendered, entry) == (0, IN_SYNC)


def test_check_doc_modified_outside_app():
    """T5: a 1-byte flip inside the doc body -> (1, DOC_MODIFIED_OUTSIDE_APP)."""
    store = store_v1()
    rendered = render_backlog(store)
    tampered = rendered.replace("closed with evidence", "closed with evidencs")
    assert tampered != rendered
    entry = entry_for(store, rendered)
    assert check_doc("backlog", canonical_json(store), tampered, entry) == (1, DOC_MODIFIED_OUTSIDE_APP)


def test_check_store_drift():
    """T6: the store moved after the render, the doc is stale -> a store-side diagnosis
    distinct from T5's ``DOC_MODIFIED_OUTSIDE_APP`` (spec §3: store hash mismatch with a
    mismatching doc is ``STORE_DRIFT_OR_DOC_DRIFT``)."""
    rendered = render_backlog(store_v1())
    entry = entry_for(store_v1(), rendered)
    store2 = store_v2()
    assert check_doc("backlog", canonical_json(store2), rendered, entry) == (1, STORE_DRIFT_OR_DOC_DRIFT)


def test_check_store_and_doc_both_drift():
    """Doc flipped AND the store moved -> (1, STORE_DRIFT_OR_DOC_DRIFT)."""
    store2 = store_v2()
    rendered = render_backlog(store_v1())
    tampered = rendered.replace("closed with evidence", "closed with evidencs")
    entry = entry_for(store_v1(), rendered)
    assert check_doc("backlog", canonical_json(store2), tampered, entry) == (1, STORE_DRIFT_OR_DOC_DRIFT)


def test_check_rerendered_doc_with_stale_manifest_is_store_drift():
    """Doc equals render(current store) but the manifest pins the old store -> (1, STORE_DRIFT)."""
    store2 = store_v2()
    rendered2 = render_backlog(store2)
    entry = entry_for(store_v1(), render_backlog(store_v1()))
    assert check_doc("backlog", canonical_json(store2), rendered2, entry) == (1, STORE_DRIFT)


def test_check_missing_entry_is_malformed_manifest():
    """No manifest entry for the kind is malformed state (exit 2) in either branch."""
    store = store_v1()
    rendered = render_backlog(store)
    assert check_doc("backlog", canonical_json(store), rendered, None) == (2, MALFORMED_MANIFEST)
    tampered = rendered.replace("closed with evidence", "closed with evidencs")
    assert check_doc("backlog", canonical_json(store), tampered, None) == (2, MALFORMED_MANIFEST)


def test_check_duplicate_item_id_is_malformed_store():
    """T7: duplicate item id B1 -> (2, MALFORMED_STORE), before any render."""
    bad = store_v1()
    bad["items"].append(dict(bad["items"][0]))
    rendered = render_backlog(store_v1())
    entry = entry_for(store_v1(), rendered)
    assert check_doc("backlog", canonical_json(bad), rendered, entry) == (2, MALFORMED_STORE)


def test_check_invalid_json_is_malformed_store():
    rendered = render_backlog(store_v1())
    assert check_doc("backlog", b"{not json", rendered, entry_for(store_v1(), rendered)) == (
        2,
        MALFORMED_STORE,
    )


def test_check_wrong_kind_store_is_malformed_store():
    """A store whose ``doc`` key names another kind is malformed for this check."""
    rendered = render_backlog(store_v1())
    wrong = {"doc": "notes", "schema_version": SCHEMA_VERSION}
    assert check_doc("backlog", canonical_json(wrong), rendered, entry_for(store_v1(), rendered)) == (
        2,
        MALFORMED_STORE,
    )


def test_check_doc_not_utf8_is_malformed_doc():
    store = store_v1()
    rendered = render_backlog(store)
    assert check_doc("backlog", canonical_json(store), b"\xff\xfe\x00\x01", entry_for(store, rendered)) == (
        2,
        MALFORMED_DOC,
    )


def test_check_unknown_kind_raises():
    with pytest.raises(SchemaError, match="kind"):
        check_doc("notes", b"{}", b"x", None)


# --------------------------------------------------------------------- check_paths (I/O wrapper)


def _write_scene(tmp_path: Path, store: dict, doc_text: str) -> tuple[Path, Path, Path]:
    store_path = tmp_path / "data" / "backlog.json"
    doc_path = tmp_path / "BACKLOG.md"
    manifest_path = tmp_path / "data" / "manifest.json"
    store_path.parent.mkdir(parents=True, exist_ok=True)
    store_path.write_text(canonical_json(store), encoding="utf-8")
    doc_path.write_text(doc_text, encoding="utf-8")
    m = new_manifest(RENDERER_VERSION)
    m["docs"]["backlog"] = make_entry("backlog", "BACKLOG.md", "data/backlog.json", canonical_json(store), doc_text)
    save_manifest(manifest_path, m)
    return store_path, doc_path, manifest_path


def test_check_paths_in_sync(tmp_path):
    store_path, doc_path, manifest_path = _write_scene(tmp_path, store_v1(), render_backlog(store_v1()))
    assert check_paths("backlog", store_path, doc_path, manifest_path) == (0, IN_SYNC)


def test_check_paths_missing_doc(tmp_path):
    store_path, _, manifest_path = _write_scene(tmp_path, store_v1(), render_backlog(store_v1()))
    (tmp_path / "BACKLOG.md").unlink()
    assert check_paths("backlog", store_path, tmp_path / "BACKLOG.md", manifest_path) == (2, DOC_MISSING)


def test_check_paths_missing_store(tmp_path):
    _, doc_path, manifest_path = _write_scene(tmp_path, store_v1(), render_backlog(store_v1()))
    (tmp_path / "data" / "backlog.json").unlink()
    assert check_paths("backlog", tmp_path / "data" / "backlog.json", doc_path, manifest_path) == (
        2,
        MALFORMED_STORE,
    )


def test_check_paths_missing_manifest(tmp_path):
    store_path, doc_path, _ = _write_scene(tmp_path, store_v1(), render_backlog(store_v1()))
    absent = tmp_path / "no" / "manifest.json"
    assert not absent.exists()
    assert check_paths("backlog", store_path, doc_path, absent) == (2, MALFORMED_MANIFEST)


def test_check_paths_manifest_without_entry(tmp_path):
    store_path, doc_path, manifest_path = _write_scene(tmp_path, store_v1(), render_backlog(store_v1()))
    save_manifest(manifest_path, new_manifest(RENDERER_VERSION))
    assert check_paths("backlog", store_path, doc_path, manifest_path) == (2, MALFORMED_MANIFEST)


# --------------------------------------------------------------------- check_message (stderr contract, §5.3)


def test_check_message_pins_diagnosis_and_remediation():
    msg = check_message("backlog", DOC_MODIFIED_OUTSIDE_APP, "data/backlog.json")
    assert DOC_MODIFIED_OUTSIDE_APP in msg
    assert "securetrace backlog render data/backlog.json" in msg
    assert "not permitted" in msg


def test_check_message_store_drift_names_render_command():
    msg = check_message("backlog", STORE_DRIFT, "data/backlog.json")
    assert STORE_DRIFT in msg
    assert "securetrace backlog render data/backlog.json" in msg


def test_check_message_both_drift_names_render_and_check():
    msg = check_message("backlog", STORE_DRIFT_OR_DOC_DRIFT, "data/backlog.json")
    assert STORE_DRIFT_OR_DOC_DRIFT in msg
    assert "securetrace backlog render data/backlog.json" in msg
    assert "securetrace backlog check data/backlog.json" in msg


def test_check_message_exit2_diagnoses():
    for diagnosis in (MALFORMED_STORE, MALFORMED_DOC, MALFORMED_MANIFEST, DOC_MISSING):
        msg = check_message("backlog", diagnosis, "data/backlog.json")
        assert diagnosis in msg
        assert "exit 2" in msg


def test_check_message_in_sync():
    msg = check_message("backlog", IN_SYNC, "data/backlog.json")
    assert "in sync" in msg


def test_check_message_rejects_unknown_kind_and_diagnosis():
    with pytest.raises(ValueError, match="kind"):
        check_message("notes", IN_SYNC, "n.json")
    with pytest.raises(ValueError, match="diagnosis"):
        check_message("backlog", "WET", "data/backlog.json")
