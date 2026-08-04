"""Test three-seed determinism for fixture generation."""
import pytest
from elpis_grid81_consumption_compiler.canonical import canonical_digest, canonical_json
from elpis_grid81_consumption_compiler.policy import create_consumption_policy, create_compiler_contract
from elpis_grid81_consumption_compiler.input import create_transaction_input
from elpis_grid81_consumption_compiler.transaction import consume_capability
from elpis_grid81_consumption_compiler.lifecycle import create_lifecycle_entry


def _make_capability(seed_index=0, scope_size=1):
    proposals = [canonical_digest({"proposal": i, "seed": seed_index}) for i in range(scope_size)]
    cap = {
        "schema_version": "structural-influence-capability.v1",
        "capability_class": "STRUCTURAL_INFLUENCE_CAPABILITY_V1",
        "capability_digest": canonical_digest({"cap": seed_index}),
        "capability_semantic_digest": canonical_digest({"sem": seed_index}),
        "nonce_digest": canonical_digest({"nonce": seed_index}),
        "authorized_proposal_digests": proposals,
        "authorized_consumer_class": "STRUCTURAL_INFLUENCE_COMPILER_V1",
        "authorized_operation_class": "PRODUCE_BOUNDED_STRUCTURAL_INFLUENCE_V1",
        "source_request_digest": canonical_digest({"req": seed_index}),
        "source_adjudication_record_digest": canonical_digest({"adj": seed_index}),
        "source_proposal_set_digest": canonical_digest({"set": seed_index}),
    }
    return cap


def test_canonical_digest_deterministic():
    for _ in range(100):
        cap = _make_capability(42)
        d1 = canonical_digest(cap)
        d2 = canonical_digest(cap)
        assert d1 == d2


def test_policy_deterministic():
    p1 = create_consumption_policy()
    p2 = create_consumption_policy()
    assert canonical_json(p1) == canonical_json(p2)
    assert p1["policy_digest"] == p2["policy_digest"]


def test_contract_deterministic():
    c1 = create_compiler_contract()
    c2 = create_compiler_contract()
    assert canonical_json(c1) == canonical_json(c2)
    assert c1["compiler_contract_digest"] == c2["compiler_contract_digest"]


def test_transaction_result_deterministic():
    policy = create_consumption_policy()
    contract = create_compiler_contract()
    cap = _make_capability(0)
    life = create_lifecycle_entry(cap["capability_digest"], cap["nonce_digest"])
    req = create_transaction_input(cap, life, "STRUCTURAL_INFLUENCE_COMPILER_V1",
                                    contract["compiler_contract_digest"],
                                    "PRODUCE_BOUNDED_STRUCTURAL_INFLUENCE_V1",
                                    0, 1, policy["policy_digest"], ["test"])

    r1 = consume_capability(capability=cap, lifecycle=life, request=req,
                             policy=policy, compiler_contract=contract)
    r2 = consume_capability(capability=cap, lifecycle=life, request=req,
                             policy=policy, compiler_contract=contract)
    assert canonical_json(r1) == canonical_json(r2)
    assert r1["transaction_result_digest"] == r2["transaction_result_digest"]


def test_artifact_deterministic():
    policy = create_consumption_policy()
    contract = create_compiler_contract()
    cap = _make_capability(0)
    life = create_lifecycle_entry(cap["capability_digest"], cap["nonce_digest"])
    req = create_transaction_input(cap, life, "STRUCTURAL_INFLUENCE_COMPILER_V1",
                                    contract["compiler_contract_digest"],
                                    "PRODUCE_BOUNDED_STRUCTURAL_INFLUENCE_V1",
                                    0, 1, policy["policy_digest"], ["test"])

    r1 = consume_capability(capability=cap, lifecycle=life, request=req,
                             policy=policy, compiler_contract=contract)
    r2 = consume_capability(capability=cap, lifecycle=life, request=req,
                             policy=policy, compiler_contract=contract)
    a1 = r1["structural_influence_artifact"]
    a2 = r2["structural_influence_artifact"]
    assert canonical_json(a1) == canonical_json(a2)


def test_rejection_deterministic():
    policy = create_consumption_policy()
    contract = create_compiler_contract()
    cap = _make_capability(0)
    life = create_lifecycle_entry(cap["capability_digest"], cap["nonce_digest"])
    life["revocation_state"] = "REVOKED"
    req = create_transaction_input(cap, life, "STRUCTURAL_INFLUENCE_COMPILER_V1",
                                    contract["compiler_contract_digest"],
                                    "PRODUCE_BOUNDED_STRUCTURAL_INFLUENCE_V1",
                                    0, 1, policy["policy_digest"], ["test"])

    r1 = consume_capability(capability=cap, lifecycle=life, request=req,
                             policy=policy, compiler_contract=contract)
    r2 = consume_capability(capability=cap, lifecycle=life, request=req,
                             policy=policy, compiler_contract=contract)
    assert canonical_json(r1) == canonical_json(r2)


def test_fixture_corpus_deterministic():
    """Generate a small corpus twice and verify byte identity."""
    results_a = []
    results_b = []
    for i in range(10):
        cap = _make_capability(i)
        life = create_lifecycle_entry(cap["capability_digest"], cap["nonce_digest"])
        policy = create_consumption_policy()
        contract = create_compiler_contract()
        req = create_transaction_input(cap, life, "STRUCTURAL_INFLUENCE_COMPILER_V1",
                                        contract["compiler_contract_digest"],
                                        "PRODUCE_BOUNDED_STRUCTURAL_INFLUENCE_V1",
                                        0, 1, policy["policy_digest"], ["test"])
        r1 = consume_capability(capability=cap, lifecycle=life, request=req,
                                 policy=policy, compiler_contract=contract)
        r2 = consume_capability(capability=cap, lifecycle=life, request=req,
                                 policy=policy, compiler_contract=contract)
        results_a.append(canonical_json(r1))
        results_b.append(canonical_json(r2))
    assert results_a == results_b
