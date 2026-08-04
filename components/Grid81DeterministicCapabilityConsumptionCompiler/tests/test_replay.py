"""Test replay verification and single-use protection."""
import pytest
from elpis_grid81_consumption_compiler.canonical import canonical_digest, canonical_json
from elpis_grid81_consumption_compiler.policy import create_consumption_policy, create_compiler_contract
from elpis_grid81_consumption_compiler.input import create_transaction_input
from elpis_grid81_consumption_compiler.transaction import consume_capability
from elpis_grid81_consumption_compiler.lifecycle import create_lifecycle_entry, transition_lifecycle
from elpis_grid81_consumption_compiler.replay import replay_transaction, replay_already_consumed


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


def _build_accepted(scope_size=1):
    policy = create_consumption_policy()
    contract = create_compiler_contract()
    cap = _make_capability(scope_size)
    life = create_lifecycle_entry(cap["capability_digest"], cap["nonce_digest"])
    req = create_transaction_input(cap, life, "STRUCTURAL_INFLUENCE_COMPILER_V1",
                                    contract["compiler_contract_digest"],
                                    "PRODUCE_BOUNDED_STRUCTURAL_INFLUENCE_V1",
                                    0, 1, policy["policy_digest"], ["test"])
    result = consume_capability(capability=cap, lifecycle=life, request=req,
                                 policy=policy, compiler_contract=contract)
    return result, cap, life, req, policy, contract


def test_replay_exact_match():
    result, cap, life, req, policy, contract = _build_accepted()
    replay = replay_transaction(result, cap, life, req, policy, contract)
    assert replay["replay_match"] is True
    assert replay["original_digest"] == replay["replayed_digest"]


def test_replay_scope_size_2():
    result, cap, life, req, policy, contract = _build_accepted(scope_size=2)
    replay = replay_transaction(result, cap, life, req, policy, contract)
    assert replay["replay_match"] is True


def test_replay_already_consumed_rejected():
    result, cap, life, req, policy, contract = _build_accepted()
    consumed_lifecycle = transition_lifecycle(life, "CONSUMED", 1)
    replay_result = replay_already_consumed(result, cap, consumed_lifecycle, req, policy, contract)
    assert replay_result["is_replay_rejection"] is True
    assert replay_result["no_artifact"] is True


def test_single_use_no_second_artifact():
    result, cap, life, req, policy, contract = _build_accepted()
    consumed_lifecycle = transition_lifecycle(life, "CONSUMED", 1)
    second = consume_capability(capability=cap, lifecycle=consumed_lifecycle,
                                 request=req, policy=policy, compiler_contract=contract)
    assert second["transaction_outcome"] == "CONSUMPTION_REJECTED_REPLAY"
    assert second["structural_influence_artifact"] is None


def test_replay_all_semantic_digests_match():
    result, cap, life, req, policy, contract = _build_accepted()
    replay = replay_transaction(result, cap, life, req, policy, contract)
    replayed = replay["replayed_result"]
    original = result
    assert replayed["transaction_result_digest"] == original["transaction_result_digest"]
    assert replayed["consumption_receipt"]["receipt_digest"] == original["consumption_receipt"]["receipt_digest"]
    assert replayed["lifecycle_transition"]["transition_digest"] == original["lifecycle_transition"]["transition_digest"]
    o_art = original["structural_influence_artifact"]
    r_art = replayed["structural_influence_artifact"]
    assert r_art["artifact_digest"] == o_art["artifact_digest"]
    assert r_art["artifact_semantic_digest"] == o_art["artifact_semantic_digest"]
