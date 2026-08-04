"""Tests for capability scope."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from elpis_grid81_capability_authority.scope import create_capability_scope, validate_scope


def test_scope_creation():
    scope = create_capability_scope(["a" * 64, "b" * 64])
    assert validate_scope(scope)
    assert len(scope["authorized_proposal_digests"]) == 2
    assert scope["capability_class"] == "STRUCTURAL_INFLUENCE_CAPABILITY_V1"


def test_scope_sorted_unique():
    scope = create_capability_scope(["b" * 64, "a" * 64])
    assert scope["authorized_proposal_digests"] == ["a" * 64, "b" * 64]


def test_scope_dedup():
    scope = create_capability_scope(["a" * 64, "a" * 64])
    assert len(scope["authorized_proposal_digests"]) == 1


def test_scope_empty_invalid():
    scope = create_capability_scope([])
    assert not validate_scope(scope)


def test_scope_digest_valid():
    scope = create_capability_scope(["a" * 64])
    assert len(scope["scope_digest"]) == 64


def test_scope_deterministic():
    s1 = create_capability_scope(["a" * 64, "b" * 64])
    s2 = create_capability_scope(["a" * 64, "b" * 64])
    assert s1["scope_digest"] == s2["scope_digest"]
