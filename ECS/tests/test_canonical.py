"""M1A — canonical serialization / domain-separated digest primitives."""

from __future__ import annotations

import pytest

from elpis_ecs import canonical
from elpis_ecs.errors import CanonicalError


class TestCanonicalBytes:
    def test_sorted_keys(self):
        a = canonical.canonical_bytes({"b": 1, "a": 2})
        assert a == b'{"a":2,"b":1}'

    def test_compact_separators(self):
        assert b": " not in canonical.canonical_bytes({"a": 1})
        assert b", " not in canonical.canonical_bytes({"a": 1, "b": 2})

    def test_nested_sorted(self):
        obj = {"z": {"b": 1, "a": 2}, "a": [3, 1, 2]}
        assert canonical.canonical_bytes(obj) == b'{"a":[3,1,2],"z":{"a":2,"b":1}}'

    def test_non_serializable_raises(self):
        with pytest.raises(CanonicalError):
            canonical.canonical_bytes({"x": object()})

    def test_nan_raises(self):
        with pytest.raises(CanonicalError):
            canonical.canonical_bytes({"x": float("nan")})


class TestDigest:
    def test_sha256_length(self):
        assert len(canonical.digest({"a": 1})) == 64

    def test_deterministic(self):
        assert canonical.digest({"a": 1, "b": 2}) == canonical.digest({"b": 2, "a": 1})

    def test_different_payloads_differ(self):
        assert canonical.digest({"a": 1}) != canonical.digest({"a": 2})

    def test_domain_separation(self):
        # Same payload under two domains -> different digests.
        d1 = canonical.domain_digest("dom.a", {"x": 1})
        d2 = canonical.domain_digest("dom.b", {"x": 1})
        assert d1 != d2

    def test_domain_digest_matches_manual(self):
        import hashlib
        obj = {"x": 1}
        expected = hashlib.sha256(
            canonical.canonical_bytes({"domain": "d", "payload": obj})
        ).hexdigest()
        assert canonical.domain_digest("d", obj) == expected

    def test_empty_domain_raises(self):
        with pytest.raises(CanonicalError):
            canonical.domain_digest("", {"x": 1})

    def test_digest_bytes_deterministic(self):
        assert canonical.digest_bytes(b"hello") == canonical.digest_bytes(b"hello")
        assert canonical.digest_bytes(b"hello") != canonical.digest_bytes(b"world")
