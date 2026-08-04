"""Test scope preservation and no-winner-selection laws."""
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


def _consume(scope_size=1):
    policy = create_consumption_policy()
    contract = create_compiler_contract()
    cap = _make_capability(scope_size)
    life = create_lifecycle_entry(cap["capability_digest"], cap["nonce_digest"])
    req = create_transaction_input(cap, life, "STRUCTURAL_INFLUENCE_COMPILER_V1",
                                    contract["compiler_contract_digest"],
                                    "PRODUCE_BOUNDED_STRUCTURAL_INFLUENCE_V1",
                                    0, 1, policy["policy_digest"], ["test"])
    return consume_capability(capability=cap, lifecycle=life, request=req,
                               policy=policy, compiler_contract=contract), cap


def test_scope_size_1_complete_preservation():
    result, cap = _consume(scope_size=1)
    artifact = result["structural_influence_artifact"]
    assert sorted(artifact["authorized_proposal_digests"]) == sorted(cap["authorized_proposal_digests"])
    assert len(artifact["proposal_bindings"]) == 1


def test_scope_size_2_complete_preservation():
    result, cap = _consume(scope_size=2)
    artifact = result["structural_influence_artifact"]
    assert sorted(artifact["authorized_proposal_digests"]) == sorted(cap["authorized_proposal_digests"])
    assert len(artifact["proposal_bindings"]) == 2


def test_no_winner_in_artifact():
    result, cap = _consume(scope_size=2)
    artifact = result["structural_influence_artifact"]
    # Check field names, not values (claims_not_made text is exempt)
    field_names = set()
    def collect_names(obj):
        if isinstance(obj, dict):
            field_names.update(obj.keys())
            for v in obj.values():
                collect_names(v)
        elif isinstance(obj, list):
            for item in obj:
                collect_names(item)
    collect_names(artifact)
    forbidden = {"winner", "selected", "rank", "priority", "score", "weight",
                 "confidence", "probability", "model_id", "model_name", "model_path",
                 "adapter_id", "adapter_name", "adapter_path", "runtime_target",
                 "device", "gpu", "port", "endpoint", "command", "process_id",
                 "server", "ecs_entity", "token_commit", "apply", "applied",
                 "activation", "execute", "dispatch"}
    assert field_names.isdisjoint(forbidden), f"Forbidden field names found: {field_names & forbidden}"


def test_no_ranking_in_artifact():
    result, cap = _consume(scope_size=2)
    artifact = result["structural_influence_artifact"]
    field_names = set()
    def collect_names(obj):
        if isinstance(obj, dict):
            field_names.update(obj.keys())
            for v in obj.values():
                collect_names(v)
        elif isinstance(obj, list):
            for item in obj:
                collect_names(item)
    collect_names(artifact)
    assert field_names.isdisjoint({"rank", "score", "priority", "weight"})


def test_no_activation_in_artifact():
    result, cap = _consume(scope_size=2)
    artifact = result["structural_influence_artifact"]
    field_names = set()
    def collect_names(obj):
        if isinstance(obj, dict):
            field_names.update(obj.keys())
            for v in obj.values():
                collect_names(v)
        elif isinstance(obj, list):
            for item in obj:
                collect_names(item)
    collect_names(artifact)
    assert field_names.isdisjoint({"activation", "applied"})


def test_all_bindings_included_unapplied():
    result, cap = _consume(scope_size=2)
    artifact = result["structural_influence_artifact"]
    for binding in artifact["proposal_bindings"]:
        assert binding["binding_state"] == "INCLUDED_UNAPPLIED"


def test_proposal_bindings_match_authorized_set():
    result, cap = _consume(scope_size=3)
    artifact = result["structural_influence_artifact"]
    binding_digests = {b["proposal_digest"] for b in artifact["proposal_bindings"]}
    authorized = set(artifact["authorized_proposal_digests"])
    assert binding_digests == authorized


def test_scope_mismatch_rejects():
    policy = create_consumption_policy()
    contract = create_compiler_contract()
    cap = _make_capability(scope_size=2)
    life = create_lifecycle_entry(cap["capability_digest"], cap["nonce_digest"])
    req = create_transaction_input(cap, life, "STRUCTURAL_INFLUENCE_COMPILER_V1",
                                    contract["compiler_contract_digest"],
                                    "PRODUCE_BOUNDED_STRUCTURAL_INFLUENCE_V1",
                                    0, 1, policy["policy_digest"], ["test"])
    req["requested_proposal_digests"] = [canonical_digest({"wrong": 1})]
    result = consume_capability(capability=cap, lifecycle=life, request=req,
                                 policy=policy, compiler_contract=contract)
    assert result["transaction_outcome"] == "CONSUMPTION_REJECTED_SCOPE_MISMATCH"
