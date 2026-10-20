"""Golden tests for canonical JSON serialization (B10 WI 3; ALRK doc T8 + C1)."""

from securetrace.docs.canonical import canonical_json, sha256_hex

# Known vector: SHA-256 of the ASCII string "abc".
ABC_SHA256 = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_canonical_json_exact_bytes():
    """T8: sorted keys, indent 2, exactly one trailing newline."""
    assert canonical_json({"b": 1, "a": {"d": 2, "c": 3}}) == (
        '{\n  "a": {\n    "c": 3,\n    "d": 2\n  },\n  "b": 1\n}\n'
    )


def test_canonical_json_key_order_independent():
    """C1: the same data in different insertion order yields identical bytes."""
    a = {"x": 1, "y": {"z": 2, "w": 3}}
    b = {"y": {"w": 3, "z": 2}, "x": 1}
    assert canonical_json(a) == canonical_json(b)


def test_canonical_json_preserves_non_ascii():
    assert "DO NOT EDIT" in canonical_json({"note": "DO NOT EDIT — manual edits are blocked"})
    # ensure_ascii=False keeps the em dash readable (no \uXXXX escapes)
    assert "\\u2014" not in canonical_json({"note": "DO NOT EDIT — manual edits are blocked"})


def test_sha256_hex_known_vector():
    assert sha256_hex(b"abc") == ABC_SHA256
    assert sha256_hex("abc") == ABC_SHA256


def test_sha256_hex_text_is_utf8_encoded():
    assert sha256_hex("héllo") == sha256_hex("héllo".encode("utf-8"))
