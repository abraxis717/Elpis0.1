"""Tests for semantic identity invariance and sensitivity."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from elpis_grid81_capability_authority.semantic_identity import (
    compute_semantic_digest, run_invariance_checks, run_sensitivity_checks
)
from elpis_grid81_capability_authority.capability import create_capability
from elpis_grid81_capability_authority.policy import create_canonical_policy
from elpis_grid81_capability_authority.authority_context import create_authority_context
from elpis_grid81_capability_authority.source_join import load_jsonl

BASE = os.path.join(os.path.dirname(__file__), "..", "..")
G51B = os.path.join(BASE, "reports", "G5_1B_DeterministicStructuralAdjudicator")


def _make_cap():
    requests = load_jsonl(os.path.join(G51B, "G51B_CAPABILITY_REVIEW_REQUEST_INVENTORY.jsonl"))
    req = requests[0]
    policy = create_canonical_policy()
    context = create_authority_context(req.get("request_digest", ""))
    return create_capability(
        source_request_digest=req.get("request_digest", ""),
        source_adjudication_record_digest=req.get("adjudication_record_digest", ""),
        source_proposal_set_digest=req.get("proposal_set_digest", ""),
        authorized_proposal_digests=req.get("referred_proposal_digests", []),
        authority_policy_digest=policy["policy_digest"],
        authority_context=context,
    )


def test_semantic_digest_format():
    cap = _make_cap()
    digest = compute_semantic_digest(cap)
    assert len(digest) == 64


def test_invariance_all_pass():
    cap = _make_cap()
    checks = run_invariance_checks(cap)
    assert len(checks) > 0
    for check in checks:
        assert check["pass"], f"Invariance failed: {check['check_id']}"


def test_sensitivity_all_pass():
    cap = _make_cap()
    policy = create_canonical_policy()
    context = create_authority_context(cap.get("source_request_digest", ""))
    checks = run_sensitivity_checks(cap, context)
    assert len(checks) > 0
    for check in checks:
        assert check["pass"], f"Sensitivity failed: {check['check_id']}"


def test_semantic_digest_deterministic():
    cap = _make_cap()
    d1 = compute_semantic_digest(cap)
    d2 = compute_semantic_digest(cap)
    assert d1 == d2
