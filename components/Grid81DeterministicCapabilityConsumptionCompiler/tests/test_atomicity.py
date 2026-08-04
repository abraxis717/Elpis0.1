"""Test atomicity: accepted produces artifact+receipt, rejected produces receipt-only."""
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


def test_accepted_has_artifact_and_receipt():
    policy = create_consumption_policy()
    contract = create_compiler_contract()
    cap = _make_capability()
    life = create_lifecycle_entry(cap["capability_digest"], cap["nonce_digest"])
    req = create_transaction_input(cap, life, "STRUCTURAL_INFLUENCE_COMPILER_V1",
                                    contract["compiler_contract_digest"],
                                    "PRODUCE_BOUNDED_STRUCTURAL_INFLUENCE_V1",
                                    0, 1, policy["policy_digest"], ["test"])
    result = consume_capability(capability=cap, lifecycle=life, request=req,
                                 policy=policy, compiler_contract=contract)
    assert result["structural_influence_artifact"] is not None
    assert result["consumption_receipt"] is not None
    assert result["rejection_record"] is None


def test_rejected_has_no_artifact_has_receipt():
    policy = create_consumption_policy()
    contract = create_compiler_contract()
    cap = _make_capability()
    life = create_lifecycle_entry(cap["capability_digest"], cap["nonce_digest"])
    life["revocation_state"] = "REVOKED"
    req = create_transaction_input(cap, life, "STRUCTURAL_INFLUENCE_COMPILER_V1",
                                    contract["compiler_contract_digest"],
                                    "PRODUCE_BOUNDED_STRUCTURAL_INFLUENCE_V1",
                                    0, 1, policy["policy_digest"], ["test"])
    result = consume_capability(capability=cap, lifecycle=life, request=req,
                                 policy=policy, compiler_contract=contract)
    assert result["structural_influence_artifact"] is None
    assert result["consumption_receipt"] is not None
    assert result["rejection_record"] is not None


def test_atomicity_artifact_digest_in_receipt():
    policy = create_consumption_policy()
    contract = create_compiler_contract()
    cap = _make_capability()
    life = create_lifecycle_entry(cap["capability_digest"], cap["nonce_digest"])
    req = create_transaction_input(cap, life, "STRUCTURAL_INFLUENCE_COMPILER_V1",
                                    contract["compiler_contract_digest"],
                                    "PRODUCE_BOUNDED_STRUCTURAL_INFLUENCE_V1",
                                    0, 1, policy["policy_digest"], ["test"])
    result = consume_capability(capability=cap, lifecycle=life, request=req,
                                 policy=policy, compiler_contract=contract)
    artifact = result["structural_influence_artifact"]
    receipt = result["consumption_receipt"]
    assert receipt["produced_influence_artifact_digest"] == artifact["artifact_digest"]


def test_input_immutability_capability():
    import copy
    policy = create_consumption_policy()
    contract = create_compiler_contract()
    cap = _make_capability()
    life = create_lifecycle_entry(cap["capability_digest"], cap["nonce_digest"])
    req = create_transaction_input(cap, life, "STRUCTURAL_INFLUENCE_COMPILER_V1",
                                    contract["compiler_contract_digest"],
                                    "PRODUCE_BOUNDED_STRUCTURAL_INFLUENCE_V1",
                                    0, 1, policy["policy_digest"], ["test"])
    cap_copy = copy.deepcopy(cap)
    life_copy = copy.deepcopy(life)
    req_copy = copy.deepcopy(req)
    consume_capability(capability=cap, lifecycle=life, request=req,
                       policy=policy, compiler_contract=contract)
    assert cap == cap_copy
    assert life == life_copy
    assert req == req_copy


def test_input_immutability_rejection_path():
    import copy
    policy = create_consumption_policy()
    contract = create_compiler_contract()
    cap = _make_capability()
    life = create_lifecycle_entry(cap["capability_digest"], cap["nonce_digest"])
    life["revocation_state"] = "REVOKED"
    req = create_transaction_input(cap, life, "STRUCTURAL_INFLUENCE_COMPILER_V1",
                                    contract["compiler_contract_digest"],
                                    "PRODUCE_BOUNDED_STRUCTURAL_INFLUENCE_V1",
                                    0, 1, policy["policy_digest"], ["test"])
    cap_copy = copy.deepcopy(cap)
    life_copy = copy.deepcopy(life)
    req_copy = copy.deepcopy(req)
    consume_capability(capability=cap, lifecycle=life, request=req,
                       policy=policy, compiler_contract=contract)
    assert cap == cap_copy
    assert life == life_copy
    assert req == req_copy
