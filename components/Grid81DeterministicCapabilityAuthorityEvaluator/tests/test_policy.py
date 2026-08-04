"""Tests for authority policy."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from elpis_grid81_capability_authority.policy import create_canonical_policy, get_grant_reasons, REASON_CODES


def test_policy_structure():
    policy = create_canonical_policy()
    assert policy["schema_version"] == "capability-authority-policy.v1"
    assert policy["supported_capability_classes"] == ["STRUCTURAL_INFLUENCE_CAPABILITY_V1"]
    assert policy["supported_operation_classes"] == ["PRODUCE_BOUNDED_STRUCTURAL_INFLUENCE_V1"]
    assert policy["supported_consumer_classes"] == ["STRUCTURAL_INFLUENCE_COMPILER_V1"]


def test_policy_requirements():
    policy = create_canonical_policy()
    assert policy["single_use_required"] is True
    assert policy["logical_validity_required"] is True
    assert policy["revocation_policy_required"] is True
    assert policy["nontransferability_required"] is True


def test_policy_digest():
    policy = create_canonical_policy()
    assert len(policy["policy_digest"]) == 64
    assert all(c in "0123456789abcdef" for c in policy["policy_digest"])


def test_reason_taxonomy_digest():
    policy = create_canonical_policy()
    assert len(policy["reason_taxonomy_digest"]) == 64


def test_decision_outcomes():
    policy = create_canonical_policy()
    outcomes = policy["authority_decision_outcomes"]
    assert "GRANT_CAPABILITY" in outcomes
    assert "DENY_CAPABILITY" in outcomes
    assert "DEFER_AUTHORITY_EVALUATION" in outcomes
    assert "ABSTAIN_AUTHORITY_CONFLICT" in outcomes
    assert "REJECT_INVALID_REQUEST" in outcomes


def test_grant_reasons():
    reasons = get_grant_reasons()
    assert len(reasons) > 0
    assert reasons == sorted(reasons)
    assert len(reasons) == len(set(reasons))
    assert "GRANT_REQUIREMENTS_SATISFIED" in reasons


def test_reason_codes_count():
    assert len(REASON_CODES) == 48
    assert REASON_CODES == sorted(REASON_CODES)


def test_policy_deterministic():
    p1 = create_canonical_policy()
    p2 = create_canonical_policy()
    assert p1["policy_digest"] == p2["policy_digest"]
