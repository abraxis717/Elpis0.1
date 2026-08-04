"""Test acceptance outcomes for capability consumption transactions."""
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


def _build_and_consume(scope_size=1):
    policy = create_consumption_policy()
    contract = create_compiler_contract()
    cap = _make_capability(scope_size)
    life = create_lifecycle_entry(cap["capability_digest"], cap["nonce_digest"])
    req = create_transaction_input(
        capability=cap, lifecycle=life,
        consumer_class="STRUCTURAL_INFLUENCE_COMPILER_V1",
        consumer_contract_digest=contract["compiler_contract_digest"],
        requested_operation_class="PRODUCE_BOUNDED_STRUCTURAL_INFLUENCE_V1",
        logical_tick=0, consumption_ordinal=1,
        consumption_policy_digest=policy["policy_digest"],
        claims_not_made=["test claim"],
    )
    result = consume_capability(
        capability=cap, lifecycle=life, request=req,
        policy=policy, compiler_contract=contract,
    )
    return result, cap, life, req, policy, contract


def test_acceptance_scope_size_1():
    result, *_ = _build_and_consume(scope_size=1)
    assert result["transaction_outcome"] == "CONSUMPTION_ACCEPTED"
    assert result["structural_influence_artifact"] is not None
    assert result["consumption_receipt"] is not None
    assert result["rejection_record"] is None


def test_acceptance_scope_size_2():
    result, *_ = _build_and_consume(scope_size=2)
    assert result["transaction_outcome"] == "CONSUMPTION_ACCEPTED"
    assert result["structural_influence_artifact"] is not None


def test_acceptance_produces_artifact():
    result, cap, *_ = _build_and_consume(scope_size=1)
    artifact = result["structural_influence_artifact"]
    assert artifact["artifact_class"] == "BOUNDED_STRUCTURAL_INFLUENCE_ARTIFACT_V1"
    assert artifact["application_state"] == "UNAPPLIED"
    assert artifact["materialization_class"] == "MATERIALIZE_AUTHORIZED_STRUCTURAL_INFLUENCE_SET_V1"
    assert artifact["target_domain_class"] == "GRID81_STRUCTURAL_PROPOSAL_DOMAIN_V1"
    assert artifact["consumer_class"] == "STRUCTURAL_INFLUENCE_COMPILER_V1"


def test_acceptance_produces_receipt():
    result, *_ = _build_and_consume(scope_size=1)
    receipt = result["consumption_receipt"]
    assert receipt["schema_version"] == "capability-consumption-receipt.v1"
    assert receipt["consumption_outcome"] == "CONSUMPTION_ACCEPTED"
    assert receipt["resulting_lifecycle_state"] == "CONSUMED"
    assert receipt["produced_influence_artifact_digest"] is not None


def test_acceptance_lifecycle_transition():
    result, *_ = _build_and_consume(scope_size=1)
    lt = result["lifecycle_transition"]
    assert lt["previous_lifecycle_state"] == "GRANTED_UNCONSUMED"
    assert lt["resulting_lifecycle_state"] == "CONSUMED"
    assert lt["previous_consumption_count"] == 0
    assert lt["resulting_consumption_count"] == 1


def test_acceptance_scope_size_1_preserves_all_proposals():
    result, cap, *_ = _build_and_consume(scope_size=1)
    artifact = result["structural_influence_artifact"]
    assert artifact["authorized_proposal_digests"] == cap["authorized_proposal_digests"]


def test_acceptance_scope_size_2_preserves_all_proposals():
    result, cap, *_ = _build_and_consume(scope_size=2)
    artifact = result["structural_influence_artifact"]
    assert sorted(artifact["authorized_proposal_digests"]) == sorted(cap["authorized_proposal_digests"])


def test_acceptance_complete_proposal_bindings():
    result, cap, *_ = _build_and_consume(scope_size=2)
    artifact = result["structural_influence_artifact"]
    assert len(artifact["proposal_bindings"]) == len(cap["authorized_proposal_digests"])
    for binding in artifact["proposal_bindings"]:
        assert binding["binding_state"] == "INCLUDED_UNAPPLIED"
        assert binding["proposal_digest"] in artifact["authorized_proposal_digests"]


def test_acceptance_no_winner_selection():
    result, *_ = _build_and_consume(scope_size=2)
    artifact = result["structural_influence_artifact"]
    # All proposals are present, none selected as winner
    for key in artifact:
        assert "winner" not in key.lower()
    for binding in artifact["proposal_bindings"]:
        assert binding["binding_state"] == "INCLUDED_UNAPPLIED"


def test_acceptance_result_digest():
    result, *_ = _build_and_consume(scope_size=1)
    assert len(result["transaction_result_digest"]) == 64


def test_acceptance_reason_codes_empty():
    result, *_ = _build_and_consume(scope_size=1)
    assert result["reason_codes"] == []
