"""Test rejection outcomes and precedence for capability consumption transactions."""
import pytest
from elpis_grid81_consumption_compiler.canonical import canonical_digest
from elpis_grid81_consumption_compiler.policy import create_consumption_policy, create_compiler_contract
from elpis_grid81_consumption_compiler.input import create_transaction_input
from elpis_grid81_consumption_compiler.transaction import consume_capability
from elpis_grid81_consumption_compiler.lifecycle import create_lifecycle_entry


def _make_capability(scope_size=1):
    proposals = [canonical_digest({"proposal": i, "scope": scope_size}) for i in range(scope_size)]
    cap = {
        "schema_version": "structural-influence-capability.v1",
        "capability_class": "STRUCTURAL_INFLUENCE_CAPABILITY_V1",
        "capability_digest": canonical_digest({"cap": scope_size}),
        "capability_semantic_digest": canonical_digest({"sem": scope_size}),
        "nonce_digest": canonical_digest({"nonce": scope_size}),
        "authorized_proposal_digests": proposals,
        "authorized_consumer_class": "STRUCTURAL_INFLUENCE_COMPILER_V1",
        "authorized_operation_class": "PRODUCE_BOUNDED_STRUCTURAL_INFLUENCE_V1",
        "source_request_digest": canonical_digest({"req": scope_size}),
        "source_adjudication_record_digest": canonical_digest({"adj": scope_size}),
        "source_proposal_set_digest": canonical_digest({"set": scope_size}),
    }
    return cap


def _build_transaction(cap, life, consumer_class="STRUCTURAL_INFLUENCE_COMPILER_V1",
                       operation="PRODUCE_BOUNDED_STRUCTURAL_INFLUENCE_V1",
                       proposals=None, nonce=None, logical_tick=0):
    policy = create_consumption_policy()
    contract = create_compiler_contract()
    req = create_transaction_input(
        capability=cap, lifecycle=life,
        consumer_class=consumer_class,
        consumer_contract_digest=contract["compiler_contract_digest"],
        requested_operation_class=operation,
        logical_tick=logical_tick, consumption_ordinal=1,
        consumption_policy_digest=policy["policy_digest"],
        claims_not_made=["test claim"],
    )
    if proposals is not None:
        req["requested_proposal_digests"] = proposals
    if nonce is not None:
        req["nonce_digest"] = nonce
    return consume_capability(
        capability=cap, lifecycle=life, request=req,
        policy=policy, compiler_contract=contract,
    ), policy, contract


def test_replay_rejection():
    cap = _make_capability()
    life = create_lifecycle_entry(cap["capability_digest"], cap["nonce_digest"])
    life["current_state"] = "CONSUMED"
    life["initial_lifecycle_state"] = "CONSUMED"
    life["consumption_count"] = 1
    result, *_ = _build_transaction(cap, life)
    assert result["transaction_outcome"] == "CONSUMPTION_REJECTED_REPLAY"
    assert result["structural_influence_artifact"] is None
    assert result["rejection_record"] is not None


def test_revoked_rejection():
    cap = _make_capability()
    life = create_lifecycle_entry(cap["capability_digest"], cap["nonce_digest"])
    life["revocation_state"] = "REVOKED"
    result, *_ = _build_transaction(cap, life)
    assert result["transaction_outcome"] == "CONSUMPTION_REJECTED_REVOKED"
    assert result["structural_influence_artifact"] is None


def test_consumer_mismatch_rejection():
    cap = _make_capability()
    life = create_lifecycle_entry(cap["capability_digest"], cap["nonce_digest"])
    result, *_ = _build_transaction(cap, life, consumer_class="BAD_CONSUMER")
    assert result["transaction_outcome"] == "CONSUMPTION_REJECTED_CONSUMER_MISMATCH"
    assert result["structural_influence_artifact"] is None


def test_scope_mismatch_rejection():
    cap = _make_capability()
    life = create_lifecycle_entry(cap["capability_digest"], cap["nonce_digest"])
    wrong_proposals = [canonical_digest({"wrong": 999})]
    result, *_ = _build_transaction(cap, life, proposals=wrong_proposals)
    assert result["transaction_outcome"] == "CONSUMPTION_REJECTED_SCOPE_MISMATCH"
    assert result["structural_influence_artifact"] is None


def test_nonce_mismatch_rejection():
    cap = _make_capability()
    life = create_lifecycle_entry(cap["capability_digest"], cap["nonce_digest"])
    wrong_nonce = canonical_digest({"wrong_nonce": 999})
    result, *_ = _build_transaction(cap, life, nonce=wrong_nonce)
    assert result["transaction_outcome"] == "CONSUMPTION_REJECTED_INVALID_CAPABILITY"
    assert result["structural_influence_artifact"] is None


def test_rejection_preserves_lifecycle():
    cap = _make_capability()
    life = create_lifecycle_entry(cap["capability_digest"], cap["nonce_digest"])
    life["revocation_state"] = "REVOKED"
    result, *_ = _build_transaction(cap, life)
    lt = result["lifecycle_transition"]
    assert lt["previous_lifecycle_state"] == lt["resulting_lifecycle_state"]
    assert lt["previous_consumption_count"] == lt["resulting_consumption_count"]


def test_rejection_produces_rejection_record():
    cap = _make_capability()
    life = create_lifecycle_entry(cap["capability_digest"], cap["nonce_digest"])
    life["revocation_state"] = "REVOKED"
    result, *_ = _build_transaction(cap, life)
    rr = result["rejection_record"]
    assert rr["schema_version"] == "consumption-rejection-record.v1"
    assert rr["rejection_outcome"] == "CONSUMPTION_REJECTED_REVOKED"
    assert len(rr["rejection_digest"]) == 64


def test_rejection_no_consumption_count_increment():
    cap = _make_capability()
    life = create_lifecycle_entry(cap["capability_digest"], cap["nonce_digest"])
    life["revocation_state"] = "REVOKED"
    result, *_ = _build_transaction(cap, life)
    lt = result["lifecycle_transition"]
    assert lt["resulting_consumption_count"] == 0


def test_invalid_capability_class():
    cap = _make_capability()
    cap["capability_class"] = "INVALID_CLASS"
    life = create_lifecycle_entry(cap["capability_digest"], cap["nonce_digest"])
    result, *_ = _build_transaction(cap, life)
    assert result["transaction_outcome"] == "CONSUMPTION_REJECTED_INVALID_CAPABILITY"


def test_rejection_receipt_has_no_artifact_digest():
    cap = _make_capability()
    life = create_lifecycle_entry(cap["capability_digest"], cap["nonce_digest"])
    life["revocation_state"] = "REVOKED"
    result, *_ = _build_transaction(cap, life)
    receipt = result["consumption_receipt"]
    assert receipt["produced_influence_artifact_digest"] is None
    assert receipt["authorized_proposal_digests"] == []
