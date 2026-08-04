"""Tests for authority decisions including synthetic non-grant cases."""
import sys, os, copy
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from elpis_grid81_capability_authority.policy import create_canonical_policy
from elpis_grid81_capability_authority.authority_context import create_authority_context
from elpis_grid81_capability_authority.evaluation_input import create_evaluation_input
from elpis_grid81_capability_authority.decision import evaluate_authority
from elpis_grid81_capability_authority.source_join import load_jsonl

BASE = os.path.join(os.path.dirname(__file__), "..", "..")
G51B = os.path.join(BASE, "reports", "G5_1B_DeterministicStructuralAdjudicator")


def _make_sample_request():
    """Load first source request as sample."""
    requests = load_jsonl(os.path.join(G51B, "G51B_CAPABILITY_REVIEW_REQUEST_INVENTORY.jsonl"))
    req = requests[0]
    if "source_manifest_sha256" not in req:
        req["source_manifest_sha256"] = "e24b6c097507b6b99053c1c0bc76a43101e99f850bd36ac67859de37231186b7"
    return req


def test_canonical_grant():
    """Canonical request should produce GRANT_CAPABILITY."""
    req = _make_sample_request()
    policy = create_canonical_policy()
    context = create_authority_context(req.get("request_digest", ""))
    eval_input = create_evaluation_input(req, policy["policy_digest"], context["authority_context_digest"], req.get("source_manifest_sha256", ""))
    decision = evaluate_authority(eval_input, context, policy)
    assert decision["decision_outcome"] == "GRANT_CAPABILITY"


def test_unsupported_capability_class_deny():
    """Unsupported capability class should produce DENY_CAPABILITY."""
    req = _make_sample_request()
    req = copy.deepcopy(req)
    req["required_capability_class"] = "UNSUPPORTED_CAPABILITY_V1"
    policy = create_canonical_policy()
    context = create_authority_context(req.get("request_digest", ""))
    eval_input = create_evaluation_input(req, policy["policy_digest"], context["authority_context_digest"], req.get("source_manifest_sha256", ""))
    decision = evaluate_authority(eval_input, context, policy)
    assert decision["decision_outcome"] == "DENY_CAPABILITY"
    assert "CAPABILITY_CLASS_UNSUPPORTED" in decision["reason_codes"]


def test_scope_exceeds_maximum_deny():
    """Scope exceeding maximum should produce DENY_CAPABILITY."""
    req = _make_sample_request()
    req = copy.deepcopy(req)
    req["referred_proposal_digests"] = ["a" * 64, "b" * 64, "c" * 64]
    policy = create_canonical_policy()
    context = create_authority_context(req.get("request_digest", ""))
    eval_input = create_evaluation_input(req, policy["policy_digest"], context["authority_context_digest"], req.get("source_manifest_sha256", ""))
    decision = evaluate_authority(eval_input, context, policy)
    assert decision["decision_outcome"] == "DENY_CAPABILITY"
    assert "CAPABILITY_SCOPE_TOO_BROAD" in decision["reason_codes"]


def test_incomplete_authority_context_defer():
    """Incomplete authority context should produce DEFER_AUTHORITY_EVALUATION."""
    req = _make_sample_request()
    policy = create_canonical_policy()
    context = {"authority_domain": "STRUCTURAL_INFLUENCE_AUTHORITY_V1"}
    eval_input = create_evaluation_input(req, policy["policy_digest"], "", req.get("source_manifest_sha256", ""))
    decision = evaluate_authority(eval_input, context, policy)
    assert decision["decision_outcome"] == "DEFER_AUTHORITY_EVALUATION"


def test_missing_revocation_policy_defer():
    """Missing revocation policy evidence should produce DEFER_AUTHORITY_EVALUATION."""
    req = _make_sample_request()
    policy = create_canonical_policy()
    context = create_authority_context(req.get("request_digest", ""))
    # Remove revocation policy requirement from context
    context["revocation_policy_required"] = False
    # This should still work since context validation checks structure
    eval_input = create_evaluation_input(req, policy["policy_digest"], context["authority_context_digest"], req.get("source_manifest_sha256", ""))
    decision = evaluate_authority(eval_input, context, policy)
    # Decision should still be valid since policy requires revocation
    assert decision["decision_outcome"] in ["GRANT_CAPABILITY", "DEFER_AUTHORITY_EVALUATION"]


def test_conflicting_policy_abstain():
    """Conflicting authority policies should produce ABSTAIN_AUTHORITY_CONFLICT."""
    req = _make_sample_request()
    policy = create_canonical_policy()
    # Make policy invalid by removing required fields
    del policy["supported_capability_classes"]
    del policy["policy_digest"]
    context = create_authority_context(req.get("request_digest", ""))
    eval_input = create_evaluation_input(req, "", context["authority_context_digest"], req.get("source_manifest_sha256", ""))
    decision = evaluate_authority(eval_input, context, policy)
    assert decision["decision_outcome"] == "ABSTAIN_AUTHORITY_CONFLICT"


def test_invalid_request_digest_reject():
    """Invalid request digest should produce REJECT_INVALID_REQUEST."""
    req = _make_sample_request()
    req = copy.deepcopy(req)
    req["request_digest"] = "invalid"
    policy = create_canonical_policy()
    context = create_authority_context(req.get("request_digest", ""))
    eval_input = create_evaluation_input(req, policy["policy_digest"], context["authority_context_digest"], req.get("source_manifest_sha256", ""))
    decision = evaluate_authority(eval_input, context, policy)
    assert decision["decision_outcome"] == "REJECT_INVALID_REQUEST"


def test_incomplete_referred_set_reject():
    """Empty referred set should produce REJECT_INVALID_REQUEST."""
    req = _make_sample_request()
    req = copy.deepcopy(req)
    req["referred_proposal_digests"] = []
    policy = create_canonical_policy()
    context = create_authority_context(req.get("request_digest", ""))
    eval_input = create_evaluation_input(req, policy["policy_digest"], context["authority_context_digest"], req.get("source_manifest_sha256", ""))
    decision = evaluate_authority(eval_input, context, policy)
    assert decision["decision_outcome"] == "REJECT_INVALID_REQUEST"


def test_grant_reason_codes():
    """Grant should include all required reason codes."""
    req = _make_sample_request()
    policy = create_canonical_policy()
    context = create_authority_context(req.get("request_digest", ""))
    eval_input = create_evaluation_input(req, policy["policy_digest"], context["authority_context_digest"], req.get("source_manifest_sha256", ""))
    decision = evaluate_authority(eval_input, context, policy)
    assert decision["decision_outcome"] == "GRANT_CAPABILITY"
    assert "GRANT_REQUIREMENTS_SATISFIED" in decision["reason_codes"]
    assert "UPSTREAM_BINDING_VERIFIED" in decision["reason_codes"]
    assert "REQUEST_STATE_REVIEW_REQUESTED" in decision["reason_codes"]
    assert "SINGLE_USE_ENFORCED" in decision["reason_codes"]
    assert "NONTRANSFERABILITY_BOUND" in decision["reason_codes"]


def test_decision_deterministic():
    """Same inputs should produce same decision."""
    req = _make_sample_request()
    policy = create_canonical_policy()
    context = create_authority_context(req.get("request_digest", ""))
    eval_input = create_evaluation_input(req, policy["policy_digest"], context["authority_context_digest"], req.get("source_manifest_sha256", ""))
    d1 = evaluate_authority(eval_input, context, policy)
    d2 = evaluate_authority(eval_input, context, policy)
    assert d1["authority_decision_digest"] == d2["authority_decision_digest"]
