"""Tests for nonce determinism and uniqueness."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from elpis_grid81_capability_authority.nonce import compute_nonce_digest, validate_nonce_digest
from elpis_grid81_capability_authority.source_join import load_jsonl
from elpis_grid81_capability_authority.policy import create_canonical_policy
from elpis_grid81_capability_authority.authority_context import create_authority_context

BASE = os.path.join(os.path.dirname(__file__), "..", "..")
G51B = os.path.join(BASE, "reports", "G5_1B_DeterministicStructuralAdjudicator")


def test_nonce_format():
    nonce = compute_nonce_digest("a" * 64, "b" * 64, "c" * 64)
    assert validate_nonce_digest(nonce)
    assert len(nonce) == 64


def test_nonce_deterministic():
    n1 = compute_nonce_digest("a" * 64, "b" * 64, "c" * 64)
    n2 = compute_nonce_digest("a" * 64, "b" * 64, "c" * 64)
    assert n1 == n2


def test_nonce_differs_by_request():
    n1 = compute_nonce_digest("a" * 64, "b" * 64, "c" * 64)
    n2 = compute_nonce_digest("d" * 64, "b" * 64, "c" * 64)
    assert n1 != n2


def test_nonce_differs_by_policy():
    n1 = compute_nonce_digest("a" * 64, "b" * 64, "c" * 64)
    n2 = compute_nonce_digest("a" * 64, "e" * 64, "c" * 64)
    assert n1 != n2


def test_nonce_differs_by_context():
    n1 = compute_nonce_digest("a" * 64, "b" * 64, "c" * 64)
    n2 = compute_nonce_digest("a" * 64, "b" * 64, "f" * 64)
    assert n1 != n2


def test_canonical_nonce_uniqueness():
    """All 8192 canonical nonces must be unique."""
    requests = load_jsonl(os.path.join(G51B, "G51B_CAPABILITY_REVIEW_REQUEST_INVENTORY.jsonl"))
    policy = create_canonical_policy()
    nonces = set()
    for req in requests:
        context = create_authority_context(req.get("request_digest", ""))
        nonce = compute_nonce_digest(
            req.get("request_digest", ""),
            policy["policy_digest"],
            context["authority_context_digest"],
        )
        nonces.add(nonce)
    assert len(nonces) == 8192


def test_invalid_nonce_format():
    assert not validate_nonce_digest("")
    assert not validate_nonce_digest("not_hex")
    assert not validate_nonce_digest("a" * 63)
    assert not validate_nonce_digest("a" * 65)
    assert not validate_nonce_digest("G" * 64)
