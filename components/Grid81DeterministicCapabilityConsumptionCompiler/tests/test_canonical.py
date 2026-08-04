"""Test canonicalization and digest computation."""
import pytest
from elpis_grid81_consumption_compiler.canonical import (
    canonical_json, canonical_digest, domain_digest, check_hex64,
)


def test_canonical_json_sorted_keys():
    obj = {"z": 1, "a": 2, "m": 3}
    result = canonical_json(obj)
    assert result == '{"a":2,"m":3,"z":1}'


def test_canonical_json_no_spaces():
    result = canonical_json({"key": "value"})
    assert " " not in result
    assert "\t" not in result


def test_canonical_json_nested():
    obj = {"b": {"z": 1, "a": 2}, "a": [3, 1, 2]}
    result = canonical_json(obj)
    assert '"a":[3,1,2]' in result


def test_canonical_digest_hex64():
    digest = canonical_digest({"test": "data"})
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)


def test_canonical_digest_deterministic():
    obj = {"key": "value", "nested": {"a": 1}}
    assert canonical_digest(obj) == canonical_digest(obj)


def test_canonical_digest_different_objects():
    obj1 = {"a": 1}
    obj2 = {"a": 2}
    assert canonical_digest(obj1) != canonical_digest(obj2)


def test_domain_digest_format():
    digest = domain_digest("test-domain", {"key": "value"})
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)


def test_check_hex64_valid():
    assert check_hex64("a" * 64) is True


def test_check_hex64_too_short():
    assert check_hex64("a" * 63) is False


def test_check_hex64_invalid_chars():
    assert check_hex64("g" * 64) is False


def test_check_hex64_empty():
    assert check_hex64("") is False


def test_check_hex64_none():
    assert check_hex64(None) is False
