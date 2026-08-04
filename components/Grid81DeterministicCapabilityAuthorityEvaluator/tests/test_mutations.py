"""Tests for mutation qualification and synthetic non-grant cases."""
import sys, os, copy
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from elpis_grid81_capability_authority.scope import create_capability_scope, validate_scope
from elpis_grid81_capability_authority.limits import create_capability_limit, validate_limit
from elpis_grid81_capability_authority.capability import create_capability, validate_capability
from elpis_grid81_capability_authority.decision import evaluate_authority
from elpis_grid81_capability_authority.policy import create_canonical_policy
from elpis_grid81_capability_authority.authority_context import create_authority_context
from elpis_grid81_capability_authority.evaluation_input import create_evaluation_input
from elpis_grid81_capability_authority.nonce import compute_nonce_digest
from elpis_grid81_capability_authority.source_join import load_jsonl

BASE = os.path.join(os.path.dirname(__file__), "..", "..")
G51B = os.path.join(BASE, "reports", "G5_1B_DeterministicStructuralAdjudicator")


def _sample_req():
    requests = load_jsonl(os.path.join(G51B, "G51B_CAPABILITY_REVIEW_REQUEST_INVENTORY.jsonl"))
    req = requests[0]
    if "source_manifest_sha256" not in req:
        req["source_manifest_sha256"] = "e24b6c097507b6b99053c1c0bc76a43101e99f850bd36ac67859de37231186b7"
    return req


def _make_cap():
    req = _sample_req()
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


def test_mutation_scope_empty():
    scope = create_capability_scope([])
    assert not validate_scope(scope), "Empty scope should be invalid"


def test_mutation_scope_exceeds_maximum():
    scope = create_capability_scope(["a" * 64, "b" * 64, "c" * 64])
    assert len(scope["authorized_proposal_digests"]) > 2


def test_mutation_max_consumptions_changed():
    limit = create_capability_limit()
    limit["max_consumptions"] = 2
    assert not validate_limit(limit)


def test_mutation_single_use_false():
    limit = create_capability_limit()
    limit["single_use"] = False
    assert not validate_limit(limit)


def test_mutation_nonce_removed():
    cap = _make_cap()
    cap["nonce_digest"] = ""
    assert not validate_capability(cap)


def test_mutation_nonce_malformed():
    cap = _make_cap()
    cap["nonce_digest"] = "not_hex"
    assert not validate_capability(cap)


def test_mutation_nontransferable_false():
    cap = _make_cap()
    cap["nontransferable"] = False
    assert not validate_capability(cap)


def test_mutation_activation_field_added():
    cap = _make_cap()
    cap["activation_state"] = "ACTIVE"
    assert not validate_capability(cap)


def test_mutation_model_identifier_added():
    cap = _make_cap()
    cap["model_identifier"] = "test"
    assert not validate_capability(cap)


def test_mutation_adapter_identifier_added():
    cap = _make_cap()
    cap["adapter_identifier"] = "test"
    assert not validate_capability(cap)


def test_mutation_revocation_policy_removed():
    cap = _make_cap()
    cap["revocation_policy_digest"] = ""
    assert not validate_capability(cap)


def test_mutation_unsupported_capability_class():
    req = _sample_req()
    req = copy.deepcopy(req)
    req["required_capability_class"] = "UNSUPPORTED_V1"
    policy = create_canonical_policy()
    context = create_authority_context(req.get("request_digest", ""))
    eval_input = create_evaluation_input(req, policy["policy_digest"], context["authority_context_digest"], req.get("source_manifest_sha256", ""))
    decision = evaluate_authority(eval_input, context, policy)
    assert decision["decision_outcome"] == "DENY_CAPABILITY"


def test_mutation_incomplete_context():
    req = _sample_req()
    policy = create_canonical_policy()
    context = {"authority_domain": "STRUCTURAL_INFLUENCE_AUTHORITY_V1"}
    eval_input = create_evaluation_input(req, policy["policy_digest"], "", req.get("source_manifest_sha256", ""))
    decision = evaluate_authority(eval_input, context, policy)
    assert decision["decision_outcome"] == "DEFER_AUTHORITY_EVALUATION"


def test_mutation_conflicting_policy():
    req = _sample_req()
    policy = create_canonical_policy()
    del policy["supported_capability_classes"]
    del policy["policy_digest"]
    context = create_authority_context(req.get("request_digest", ""))
    eval_input = create_evaluation_input(req, "", context["authority_context_digest"], req.get("source_manifest_sha256", ""))
    decision = evaluate_authority(eval_input, context, policy)
    assert decision["decision_outcome"] == "ABSTAIN_AUTHORITY_CONFLICT"


def test_mutation_invalid_request_digest():
    req = _sample_req()
    req = copy.deepcopy(req)
    req["request_digest"] = "invalid"
    policy = create_canonical_policy()
    context = create_authority_context(req.get("request_digest", ""))
    eval_input = create_evaluation_input(req, policy["policy_digest"], context["authority_context_digest"], req.get("source_manifest_sha256", ""))
    decision = evaluate_authority(eval_input, context, policy)
    assert decision["decision_outcome"] == "REJECT_INVALID_REQUEST"


def test_mutation_empty_referred_set():
    req = _sample_req()
    req = copy.deepcopy(req)
    req["referred_proposal_digests"] = []
    policy = create_canonical_policy()
    context = create_authority_context(req.get("request_digest", ""))
    eval_input = create_evaluation_input(req, policy["policy_digest"], context["authority_context_digest"], req.get("source_manifest_sha256", ""))
    decision = evaluate_authority(eval_input, context, policy)
    assert decision["decision_outcome"] == "REJECT_INVALID_REQUEST"
