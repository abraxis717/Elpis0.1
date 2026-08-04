"""Test validation predicates and rejection precedence."""
import pytest
from elpis_grid81_consumption_compiler.validation import (
    validate_transaction, validate_artifact_invariants, validate_receipt,
    validate_schema_and_identity, validate_capability_identity,
    validate_lifecycle, validate_revocation, validate_logical_validity,
    validate_nonce, validate_consumer, validate_operation, validate_scope,
    check_forbidden_fields, FORBIDDEN_FIELDS,
    ACCEPTED_OUTCOME, REJECTION_REPLAY, REJECTION_REVOKED,
    REJECTION_EXPIRED, REJECTION_CONSUMER_MISMATCH,
    REJECTION_SCOPE_MISMATCH, REJECTION_INVALID_CAPABILITY,
)
from elpis_grid81_consumption_compiler.canonical import canonical_digest
from elpis_grid81_consumption_compiler.policy import create_consumption_policy
from elpis_grid81_consumption_compiler.policy import create_compiler_contract


def _make_capability(scope_size=1):
    proposals = [canonical_digest({"proposal": i}) for i in range(scope_size)]
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


def _make_lifecycle(cap, state="GRANTED_UNCONSUMED", count=0, revoked=False):
    return {
        "capability_digest": cap["capability_digest"],
        "nonce_digest": cap["nonce_digest"],
        "current_state": state,
        "initial_lifecycle_state": state,
        "consumption_count": count,
        "revocation_state": "REVOKED" if revoked else "NOT_REVOKED",
        "logical_interval": {"valid_from_logical_tick": 0, "valid_through_logical_tick": 0},
        "max_consumptions": 1,
    }


def _make_request(cap, lifecycle, policy):
    return {
        "schema_version": "capability-consumption-transaction-input.v1",
        "capability_digest": cap["capability_digest"],
        "capability_semantic_digest": cap["capability_semantic_digest"],
        "nonce_digest": cap["nonce_digest"],
        "current_lifecycle_state": lifecycle["current_state"],
        "current_consumption_count": lifecycle["consumption_count"],
        "revocation_state": lifecycle["revocation_state"],
        "consumer_class": "STRUCTURAL_INFLUENCE_COMPILER_V1",
        "consumer_contract_digest": canonical_digest({"contract": "test"}),
        "requested_operation_class": "PRODUCE_BOUNDED_STRUCTURAL_INFLUENCE_V1",
        "requested_proposal_digests": list(cap["authorized_proposal_digests"]),
        "logical_tick": 0,
        "consumption_ordinal": 1,
        "consumption_request_digest": canonical_digest({"req": "input"}),
        "consumption_policy_digest": policy["policy_digest"],
        "transaction_input_digest": canonical_digest({"txn": "input"}),
        "claims_not_made": ["test claim"],
    }


@pytest.fixture
def policy():
    return create_consumption_policy()


@pytest.fixture
def contract():
    return create_compiler_contract()


def test_schema_rejection(policy, contract):
    cap = _make_capability()
    life = _make_lifecycle(cap)
    req = _make_request(cap, life, policy)
    req["schema_version"] = "invalid-version"
    outcome, _ = validate_transaction(cap, life, req, policy, contract)
    assert outcome == REJECTION_INVALID_CAPABILITY


def test_valid_schema_accepts(capability_policy_contract):
    cap, life, policy, contract = capability_policy_contract
    req = _make_request(cap, life, policy)
    outcome, reasons = validate_transaction(cap, life, req, policy, contract)
    assert outcome == ACCEPTED_OUTCOME
    assert len(reasons) == 0


@pytest.fixture
def capability_policy_contract(policy, contract):
    cap = _make_capability()
    life = _make_lifecycle(cap)
    return cap, life, policy, contract


def test_lifecycle_replay_rejection(policy, contract):
    cap = _make_capability()
    life = _make_lifecycle(cap, state="CONSUMED", count=1)
    req = _make_request(cap, life, policy)
    req["current_lifecycle_state"] = "CONSUMED"
    req["current_consumption_count"] = 1
    outcome, _ = validate_transaction(cap, life, req, policy, contract)
    assert outcome == REJECTION_REPLAY


def test_revocation_rejection(policy, contract):
    cap = _make_capability()
    life = _make_lifecycle(cap, revoked=True)
    req = _make_request(cap, life, policy)
    req["revocation_state"] = "REVOKED"
    outcome, _ = validate_transaction(cap, life, req, policy, contract)
    assert outcome == REJECTION_REVOKED


def test_consumer_mismatch(policy, contract):
    cap = _make_capability()
    life = _make_lifecycle(cap)
    req = _make_request(cap, life, policy)
    req["consumer_class"] = "UNAUTHORIZED_CONSUMER"
    outcome, _ = validate_transaction(cap, life, req, policy, contract)
    assert outcome == REJECTION_CONSUMER_MISMATCH


def test_scope_mismatch(policy, contract):
    cap = _make_capability()
    life = _make_lifecycle(cap)
    req = _make_request(cap, life, policy)
    req["requested_proposal_digests"] = [canonical_digest({"wrong": 1})]
    outcome, _ = validate_transaction(cap, life, req, policy, contract)
    assert outcome == REJECTION_SCOPE_MISMATCH


def test_nonce_mismatch(policy, contract):
    cap = _make_capability()
    life = _make_lifecycle(cap)
    req = _make_request(cap, life, policy)
    req["nonce_digest"] = canonical_digest({"wrong_nonce": 1})
    outcome, _ = validate_transaction(cap, life, req, policy, contract)
    assert outcome == REJECTION_INVALID_CAPABILITY


def test_forbidden_field_detection():
    obj = {"winner": "model_x"}
    found = check_forbidden_fields(obj)
    assert any("forbidden_field" in f for f in found)


def test_no_forbidden_in_clean_artifact():
    artifact = {
        "artifact_class": "BOUNDED_STRUCTURAL_INFLUENCE_ARTIFACT_V1",
        "application_state": "UNAPPLIED",
        "authorized_proposal_digests": ["abc123"],
    }
    found = check_forbidden_fields(artifact)
    assert len(found) == 0


def test_scope_size_1(policy, contract):
    cap = _make_capability(scope_size=1)
    life = _make_lifecycle(cap)
    req = _make_request(cap, life, policy)
    outcome, _ = validate_transaction(cap, life, req, policy, contract)
    assert outcome == ACCEPTED_OUTCOME


def test_scope_size_2(policy, contract):
    cap = _make_capability(scope_size=2)
    life = _make_lifecycle(cap)
    req = _make_request(cap, life, policy)
    outcome, _ = validate_transaction(cap, life, req, policy, contract)
    assert outcome == ACCEPTED_OUTCOME


def test_rejection_precedence_schema_before_lifecycle(policy, contract):
    """Schema check (precedence 1) fires before lifecycle check (precedence 3)."""
    cap = _make_capability()
    life = _make_lifecycle(cap, count=1)
    req = _make_request(cap, life, policy)
    req["schema_version"] = "bad"
    req["current_consumption_count"] = 1
    outcome, _ = validate_transaction(cap, life, req, policy, contract)
    # Should be INVALID_CAPABILITY (schema), not REPLAY (lifecycle)
    assert outcome == REJECTION_INVALID_CAPABILITY


def test_rejection_precedence_lifecycle_before_revocation(policy, contract):
    """Lifecycle check (precedence 3) fires before revocation (precedence 4)."""
    cap = _make_capability()
    life = _make_lifecycle(cap, state="CONSUMED", count=1, revoked=True)
    req = _make_request(cap, life, policy)
    req["current_lifecycle_state"] = "CONSUMED"
    req["current_consumption_count"] = 1
    req["revocation_state"] = "REVOKED"
    outcome, _ = validate_transaction(cap, life, req, policy, contract)
    # Should be REPLAY (lifecycle), not REVOKED (revocation)
    assert outcome == REJECTION_REPLAY


def test_logical_validity_accepts_valid_tick(policy, contract):
    cap = _make_capability()
    life = _make_lifecycle(cap)
    req = _make_request(cap, life, policy)
    req["logical_tick"] = 0
    outcome, _ = validate_transaction(cap, life, req, policy, contract)
    assert outcome == ACCEPTED_OUTCOME


def test_artifact_invariants_valid(policy, contract):
    from elpis_grid81_consumption_compiler.artifact import create_structural_influence_artifact
    cap = _make_capability()
    life = _make_lifecycle(cap)
    req = _make_request(cap, life, policy)
    artifact = create_structural_influence_artifact(cap, life, req, contract)
    valid, issues = validate_artifact_invariants(artifact)
    assert valid is True
    assert len(issues) == 0
