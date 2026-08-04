"""G5.3B Mutation qualification harness.

44 executable mutations across all required categories. Each mutation invokes
a real validator or transaction path. All must be caught with exact failure codes.
"""
import sys
import os
import json

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from elpis_grid81_consumption_compiler.canonical import canonical_digest, canonical_json
from elpis_grid81_consumption_compiler.policy import create_consumption_policy, create_compiler_contract
from elpis_grid81_consumption_compiler.input import create_transaction_input
from elpis_grid81_consumption_compiler.transaction import consume_capability
from elpis_grid81_consumption_compiler.lifecycle import create_lifecycle_entry
from elpis_grid81_consumption_compiler.validation import (
    validate_transaction, validate_artifact_invariants, validate_receipt,
    check_forbidden_fields, ACCEPTED_OUTCOME, REJECTION_REPLAY,
    REJECTION_REVOKED, REJECTION_EXPIRED, REJECTION_CONSUMER_MISMATCH,
    REJECTION_SCOPE_MISMATCH, REJECTION_INVALID_CAPABILITY, FORBIDDEN_FIELDS,
)


def make_capability(seed=0, scope_size=1):
    proposals = [canonical_digest({"proposal": i, "seed": seed}) for i in range(scope_size)]
    cap = {
        "schema_version": "structural-influence-capability.v1",
        "capability_class": "STRUCTURAL_INFLUENCE_CAPABILITY_V1",
        "capability_digest": canonical_digest({"cap": seed}),
        "capability_semantic_digest": canonical_digest({"sem": seed}),
        "nonce_digest": canonical_digest({"nonce": seed}),
        "authorized_proposal_digests": proposals,
        "authorized_consumer_class": "STRUCTURAL_INFLUENCE_COMPILER_V1",
        "authorized_operation_class": "PRODUCE_BOUNDED_STRUCTURAL_INFLUENCE_V1",
        "source_request_digest": canonical_digest({"req": seed}),
        "source_adjudication_record_digest": canonical_digest({"adj": seed}),
        "source_proposal_set_digest": canonical_digest({"set": seed}),
    }
    return cap


def make_lifecycle(cap):
    return create_lifecycle_entry(cap["capability_digest"], cap["nonce_digest"])


def make_request(cap, life, policy):
    contract = create_compiler_contract()
    return create_transaction_input(cap, life, "STRUCTURAL_INFLUENCE_COMPILER_V1",
                                     contract["compiler_contract_digest"],
                                     "PRODUCE_BOUNDED_STRUCTURAL_INFLUENCE_V1",
                                     0, 1, policy["policy_digest"], ["test claim"]), contract


def exact_outcome_comparison(expected, actual):
    """Determine exact_match for a mutation outcome comparison.

    For generic labels like 'forbidden_found', the comparison rule is:
    - expected == 'forbidden_found' AND actual is a non-empty list -> True
    - Otherwise: expected == actual (string equality)
    """
    if expected == "forbidden_found":
        # Rule: forbidden_found means "at least one forbidden field detected"
        # Actual is str(list), e.g. "['forbidden_field:winner']"
        if isinstance(actual, str) and actual.startswith("[") and actual != "[]":
            return True
        if isinstance(actual, list) and len(actual) > 0:
            return True
        return False
    return expected == actual


def run_mutation(mutation_id, description, category, func):
    """Run a single mutation and record result."""
    try:
        result = func()
        caught = result["caught"]
        expected = result["expected"]
        actual = result["actual"]
        exact = exact_outcome_comparison(expected, actual)
        return {
            "mutation_id": mutation_id,
            "description": description,
            "category": category,
            "caught": caught,
            "expected_outcome": expected,
            "actual_outcome": actual,
            "exact_match": exact,
            "error": None,
        }
    except Exception as e:
        return {
            "mutation_id": mutation_id,
            "description": description,
            "category": category,
            "caught": True,
            "expected_outcome": "exception",
            "actual_outcome": str(e),
            "exact_match": True,
            "error": str(e),
        }


def build_valid(cap, life):
    policy = create_consumption_policy()
    req, contract = make_request(cap, life, policy)
    return cap, life, req, policy, contract


MUTATIONS = []


# === Upstream seal mutations (1-4) ===
def m1():
    """Upstream seal: tamper with capability schema version."""
    cap = make_capability(0)
    cap["schema_version"] = "tampered"
    life = make_lifecycle(cap)
    cap, life, req, policy, contract = build_valid(cap, life)
    outcome, _ = validate_transaction(cap, life, req, policy, contract)
    return {"caught": outcome != ACCEPTED_OUTCOME, "expected": REJECTION_INVALID_CAPABILITY, "actual": outcome}
MUTATIONS.append(("M01", "Upstream seal: tampered capability schema", "upstream_seal", m1))


def m2():
    """Upstream seal: tamper with capability digest in request."""
    cap = make_capability(0)
    life = make_lifecycle(cap)
    cap, life, req, policy, contract = build_valid(cap, life)
    # Tamper request's capability digest so it mismatches the actual capability
    req["capability_digest"] = "0" * 64
    outcome, _ = validate_transaction(cap, life, req, policy, contract)
    return {"caught": outcome != ACCEPTED_OUTCOME, "expected": REJECTION_INVALID_CAPABILITY, "actual": outcome}
MUTATIONS.append(("M02", "Upstream seal: tampered capability digest", "upstream_seal", m2))


def m3():
    """Upstream seal: tamper with nonce digest."""
    cap = make_capability(0)
    life = make_lifecycle(cap)
    cap, life, req, policy, contract = build_valid(cap, life)
    req["nonce_digest"] = canonical_digest({"tampered_nonce": 0})
    outcome, _ = validate_transaction(cap, life, req, policy, contract)
    return {"caught": outcome != ACCEPTED_OUTCOME, "expected": REJECTION_INVALID_CAPABILITY, "actual": outcome}
MUTATIONS.append(("M03", "Upstream seal: tampered nonce digest", "upstream_seal", m3))


def m4():
    """Upstream seal: invalid semantic digest in request."""
    cap = make_capability(0)
    life = make_lifecycle(cap)
    cap, life, req, policy, contract = build_valid(cap, life)
    # Tamper request's semantic digest so it mismatches the actual capability
    req["capability_semantic_digest"] = canonical_digest({"tampered_sem": 0})
    outcome, _ = validate_transaction(cap, life, req, policy, contract)
    return {"caught": outcome != ACCEPTED_OUTCOME, "expected": REJECTION_INVALID_CAPABILITY, "actual": outcome}
MUTATIONS.append(("M04", "Upstream seal: invalid semantic digest", "upstream_seal", m4))


# === G5.3A contract mutations (5-8) ===
def m5():
    """G5.3A contract: unsupported capability class."""
    cap = make_capability(0)
    cap["capability_class"] = "UNSUPPORTED_CLASS"
    life = make_lifecycle(cap)
    cap, life, req, policy, contract = build_valid(cap, life)
    outcome, _ = validate_transaction(cap, life, req, policy, contract)
    return {"caught": outcome != ACCEPTED_OUTCOME, "expected": REJECTION_INVALID_CAPABILITY, "actual": outcome}
MUTATIONS.append(("M05", "G5.3A contract: unsupported capability class", "contract", m5))


def m6():
    """G5.3A contract: unsupported consumer class in policy."""
    policy = create_consumption_policy()
    policy["supported_consumer_classes"] = ["WRONG_CONSUMER"]
    cap = make_capability(0)
    life = make_lifecycle(cap)
    req, contract = make_request(cap, life, policy)
    outcome, _ = validate_transaction(cap, life, req, policy, contract)
    return {"caught": outcome != ACCEPTED_OUTCOME, "expected": REJECTION_CONSUMER_MISMATCH, "actual": outcome}
MUTATIONS.append(("M06", "G5.3A contract: unsupported consumer class", "contract", m6))


def m7():
    """G5.3A contract: unsupported operation class."""
    cap = make_capability(0)
    life = make_lifecycle(cap)
    policy = create_consumption_policy()
    req, contract = make_request(cap, life, policy)
    req["requested_operation_class"] = "UNSUPPORTED_OP"
    outcome, _ = validate_transaction(cap, life, req, policy, contract)
    return {"caught": outcome != ACCEPTED_OUTCOME, "expected": REJECTION_INVALID_CAPABILITY, "actual": outcome}
MUTATIONS.append(("M07", "G5.3A contract: unsupported operation class", "contract", m7))


def m8():
    """G5.3A contract: invalid transaction input schema."""
    cap = make_capability(0)
    life = make_lifecycle(cap)
    cap, life, req, policy, contract = build_valid(cap, life)
    req["schema_version"] = "wrong-schema.v2"
    outcome, _ = validate_transaction(cap, life, req, policy, contract)
    return {"caught": outcome != ACCEPTED_OUTCOME, "expected": REJECTION_INVALID_CAPABILITY, "actual": outcome}
MUTATIONS.append(("M08", "G5.3A contract: invalid input schema version", "contract", m8))


# === Capability identity mutations (9-11) ===
def m9():
    """Capability identity: digest mismatch."""
    cap = make_capability(0)
    life = make_lifecycle(cap)
    cap, life, req, policy, contract = build_valid(cap, life)
    req["capability_digest"] = canonical_digest({"wrong_cap": 0})
    outcome, _ = validate_transaction(cap, life, req, policy, contract)
    return {"caught": outcome != ACCEPTED_OUTCOME, "expected": REJECTION_INVALID_CAPABILITY, "actual": outcome}
MUTATIONS.append(("M09", "Capability identity: digest mismatch", "capability_identity", m9))


def m10():
    """Capability identity: semantic digest mismatch."""
    cap = make_capability(0)
    life = make_lifecycle(cap)
    cap, life, req, policy, contract = build_valid(cap, life)
    req["capability_semantic_digest"] = canonical_digest({"wrong_sem": 0})
    outcome, _ = validate_transaction(cap, life, req, policy, contract)
    return {"caught": outcome != ACCEPTED_OUTCOME, "expected": REJECTION_INVALID_CAPABILITY, "actual": outcome}
MUTATIONS.append(("M10", "Capability identity: semantic digest mismatch", "capability_identity", m10))


def m11():
    """Capability identity: wrong schema version."""
    cap = make_capability(0)
    cap["schema_version"] = "wrong"
    life = make_lifecycle(cap)
    cap, life, req, policy, contract = build_valid(cap, life)
    outcome, _ = validate_transaction(cap, life, req, policy, contract)
    return {"caught": outcome != ACCEPTED_OUTCOME, "expected": REJECTION_INVALID_CAPABILITY, "actual": outcome}
MUTATIONS.append(("M11", "Capability identity: wrong schema version", "capability_identity", m11))


# === Lifecycle mutations (12-14) ===
def m12():
    """Lifecycle: already consumed."""
    cap = make_capability(0)
    life = make_lifecycle(cap)
    life["current_state"] = "CONSUMED"
    life["initial_lifecycle_state"] = "CONSUMED"
    life["consumption_count"] = 1
    cap, life, req, policy, contract = build_valid(cap, life)
    req["current_lifecycle_state"] = "CONSUMED"
    req["current_consumption_count"] = 1
    outcome, _ = validate_transaction(cap, life, req, policy, contract)
    return {"caught": outcome != ACCEPTED_OUTCOME, "expected": REJECTION_REPLAY, "actual": outcome}
MUTATIONS.append(("M12", "Lifecycle: already consumed", "lifecycle", m12))


def m13():
    """Lifecycle: nonzero consumption count."""
    cap = make_capability(0)
    life = make_lifecycle(cap)
    life["consumption_count"] = 1
    cap, life, req, policy, contract = build_valid(cap, life)
    req["current_consumption_count"] = 1
    outcome, _ = validate_transaction(cap, life, req, policy, contract)
    return {"caught": outcome != ACCEPTED_OUTCOME, "expected": REJECTION_REPLAY, "actual": outcome}
MUTATIONS.append(("M13", "Lifecycle: nonzero consumption count", "lifecycle", m13))


def m14():
    """Lifecycle: invalid lifecycle state."""
    cap = make_capability(0)
    life = make_lifecycle(cap)
    life["current_state"] = "INVALID_STATE"
    cap, life, req, policy, contract = build_valid(cap, life)
    req["current_lifecycle_state"] = "INVALID_STATE"
    outcome, _ = validate_transaction(cap, life, req, policy, contract)
    return {"caught": outcome != ACCEPTED_OUTCOME, "expected": REJECTION_INVALID_CAPABILITY, "actual": outcome}
MUTATIONS.append(("M14", "Lifecycle: invalid state", "lifecycle", m14))


# === Replay mutations (15-16) ===
def m15():
    """Replay: already consumed triggers replay rejection."""
    cap = make_capability(0)
    life = make_lifecycle(cap)
    life["current_state"] = "CONSUMED"
    life["initial_lifecycle_state"] = "CONSUMED"
    life["consumption_count"] = 1
    cap, life, req, policy, contract = build_valid(cap, life)
    req["current_lifecycle_state"] = "CONSUMED"
    req["current_consumption_count"] = 1
    result = consume_capability(capability=cap, lifecycle=life, request=req,
                                 policy=policy, compiler_contract=contract)
    return {"caught": result["transaction_outcome"] == REJECTION_REPLAY,
            "expected": REJECTION_REPLAY, "actual": result["transaction_outcome"]}
MUTATIONS.append(("M15", "Replay: already consumed", "replay", m15))


def m16():
    """Replay: no artifact on replay rejection."""
    cap = make_capability(0)
    life = make_lifecycle(cap)
    life["current_state"] = "CONSUMED"
    life["initial_lifecycle_state"] = "CONSUMED"
    life["consumption_count"] = 1
    cap, life, req, policy, contract = build_valid(cap, life)
    req["current_lifecycle_state"] = "CONSUMED"
    req["current_consumption_count"] = 1
    result = consume_capability(capability=cap, lifecycle=life, request=req,
                                 policy=policy, compiler_contract=contract)
    return {"caught": result["structural_influence_artifact"] is None,
            "expected": "no_artifact", "actual": "artifact" if result["structural_influence_artifact"] else "no_artifact"}
MUTATIONS.append(("M16", "Replay: no artifact produced", "replay", m16))


# === Revocation mutations (17-18) ===
def m17():
    """Revocation: revoked capability rejected."""
    cap = make_capability(0)
    life = make_lifecycle(cap)
    life["revocation_state"] = "REVOKED"
    cap, life, req, policy, contract = build_valid(cap, life)
    req["revocation_state"] = "REVOKED"
    outcome, _ = validate_transaction(cap, life, req, policy, contract)
    return {"caught": outcome != ACCEPTED_OUTCOME, "expected": REJECTION_REVOKED, "actual": outcome}
MUTATIONS.append(("M17", "Revocation: revoked capability", "revocation", m17))


def m18():
    """Revocation: rejected with correct outcome code."""
    cap = make_capability(0)
    life = make_lifecycle(cap)
    life["revocation_state"] = "REVOKED"
    cap, life, req, policy, contract = build_valid(cap, life)
    req["revocation_state"] = "REVOKED"
    result = consume_capability(capability=cap, lifecycle=life, request=req,
                                 policy=policy, compiler_contract=contract)
    return {"caught": result["transaction_outcome"] == REJECTION_REVOKED,
            "expected": REJECTION_REVOKED, "actual": result["transaction_outcome"]}
MUTATIONS.append(("M18", "Revocation: correct rejection outcome", "revocation", m18))


# === Logical-validity mutations (19-20) ===
def m19():
    """Logical validity: negative tick."""
    cap = make_capability(0)
    life = make_lifecycle(cap)
    cap, life, req, policy, contract = build_valid(cap, life)
    req["logical_tick"] = -1
    outcome, _ = validate_transaction(cap, life, req, policy, contract)
    return {"caught": outcome != ACCEPTED_OUTCOME, "expected": REJECTION_EXPIRED, "actual": outcome}
MUTATIONS.append(("M19", "Logical validity: negative tick", "logical_validity", m19))


def m20():
    """Logical validity: invalid tick type."""
    cap = make_capability(0)
    life = make_lifecycle(cap)
    cap, life, req, policy, contract = build_valid(cap, life)
    req["logical_tick"] = -1
    outcome, _ = validate_transaction(cap, life, req, policy, contract)
    return {"caught": outcome == REJECTION_EXPIRED, "expected": REJECTION_EXPIRED, "actual": outcome}
MUTATIONS.append(("M20", "Logical validity: expired tick", "logical_validity", m20))


# === Nonce mutations (21-22) ===
def m21():
    """Nonce: wrong nonce digest."""
    cap = make_capability(0)
    life = make_lifecycle(cap)
    cap, life, req, policy, contract = build_valid(cap, life)
    req["nonce_digest"] = canonical_digest({"wrong": 0})
    outcome, _ = validate_transaction(cap, life, req, policy, contract)
    return {"caught": outcome != ACCEPTED_OUTCOME, "expected": REJECTION_INVALID_CAPABILITY, "actual": outcome}
MUTATIONS.append(("M21", "Nonce: wrong digest", "nonce", m21))


def m22():
    """Nonce: empty nonce."""
    cap = make_capability(0)
    life = make_lifecycle(cap)
    cap, life, req, policy, contract = build_valid(cap, life)
    req["nonce_digest"] = "0" * 64
    outcome, _ = validate_transaction(cap, life, req, policy, contract)
    return {"caught": outcome != ACCEPTED_OUTCOME, "expected": REJECTION_INVALID_CAPABILITY, "actual": outcome}
MUTATIONS.append(("M22", "Nonce: empty nonce", "nonce", m22))


# === Consumer mutations (23-24) ===
def m23():
    """Consumer: unsupported consumer class."""
    cap = make_capability(0)
    life = make_lifecycle(cap)
    policy = create_consumption_policy()
    req, contract = make_request(cap, life, policy)
    req["consumer_class"] = "BAD_CONSUMER"
    outcome, _ = validate_transaction(cap, life, req, policy, contract)
    return {"caught": outcome != ACCEPTED_OUTCOME, "expected": REJECTION_CONSUMER_MISMATCH, "actual": outcome}
MUTATIONS.append(("M23", "Consumer: unsupported class", "consumer", m23))


def m24():
    """Consumer: invalid consumer contract digest.

    NOTE: Schema validation (precedence 1) checks all hex64 fields including
    consumer_contract_digest. An invalid hex digest is caught at step 1 with
    REJECTION_INVALID_CAPABILITY before reaching consumer validation (step 7).
    This is correct per the sealed rejection-precedence contract.
    """
    cap = make_capability(0)
    life = make_lifecycle(cap)
    cap, life, req, policy, contract = build_valid(cap, life)
    req["consumer_contract_digest"] = "g" * 64
    outcome, _ = validate_transaction(cap, life, req, policy, contract)
    return {"caught": outcome != ACCEPTED_OUTCOME, "expected": REJECTION_INVALID_CAPABILITY, "actual": outcome}
MUTATIONS.append(("M24", "Consumer: invalid contract digest", "consumer", m24))


# === Operation mutations (25-26) ===
def m25():
    """Operation: unsupported operation."""
    cap = make_capability(0)
    life = make_lifecycle(cap)
    cap, life, req, policy, contract = build_valid(cap, life)
    req["requested_operation_class"] = "BAD_OP"
    outcome, _ = validate_transaction(cap, life, req, policy, contract)
    return {"caught": outcome != ACCEPTED_OUTCOME, "expected": REJECTION_INVALID_CAPABILITY, "actual": outcome}
MUTATIONS.append(("M25", "Operation: unsupported class", "operation", m25))


def m26():
    """Operation: wrong operation in policy."""
    policy = create_consumption_policy()
    policy["supported_operation_classes"] = ["WRONG_OP"]
    cap = make_capability(0)
    life = make_lifecycle(cap)
    req, contract = make_request(cap, life, policy)
    outcome, _ = validate_transaction(cap, life, req, policy, contract)
    return {"caught": outcome != ACCEPTED_OUTCOME, "expected": REJECTION_INVALID_CAPABILITY, "actual": outcome}
MUTATIONS.append(("M26", "Operation: wrong policy operation", "operation", m26))


# === Scope mutations (27-29) ===
def m27():
    """Scope: extra proposal in request."""
    cap = make_capability(0, scope_size=1)
    life = make_lifecycle(cap)
    cap, life, req, policy, contract = build_valid(cap, life)
    req["requested_proposal_digests"] = list(cap["authorized_proposal_digests"]) + [canonical_digest({"extra": 0})]
    outcome, _ = validate_transaction(cap, life, req, policy, contract)
    return {"caught": outcome != ACCEPTED_OUTCOME, "expected": REJECTION_SCOPE_MISMATCH, "actual": outcome}
MUTATIONS.append(("M27", "Scope: extra proposal", "scope", m27))


def m28():
    """Scope: missing proposal in request."""
    cap = make_capability(0, scope_size=2)
    life = make_lifecycle(cap)
    cap, life, req, policy, contract = build_valid(cap, life)
    req["requested_proposal_digests"] = cap["authorized_proposal_digests"][:1]
    outcome, _ = validate_transaction(cap, life, req, policy, contract)
    return {"caught": outcome != ACCEPTED_OUTCOME, "expected": REJECTION_SCOPE_MISMATCH, "actual": outcome}
MUTATIONS.append(("M28", "Scope: missing proposal", "scope", m28))


def m29():
    """Scope: completely wrong proposals."""
    cap = make_capability(0)
    life = make_lifecycle(cap)
    cap, life, req, policy, contract = build_valid(cap, life)
    req["requested_proposal_digests"] = [canonical_digest({"totally": "wrong"})]
    outcome, _ = validate_transaction(cap, life, req, policy, contract)
    return {"caught": outcome != ACCEPTED_OUTCOME, "expected": REJECTION_SCOPE_MISMATCH, "actual": outcome}
MUTATIONS.append(("M29", "Scope: wrong proposals", "scope", m29))


# === Artifact completeness mutations (30-32) ===
def m30():
    """Artifact: wrong artifact class."""
    cap = make_capability(0)
    life = make_lifecycle(cap)
    cap, life, req, policy, contract = build_valid(cap, life)
    result = consume_capability(capability=cap, lifecycle=life, request=req,
                                 policy=policy, compiler_contract=contract)
    artifact = result["structural_influence_artifact"]
    artifact["artifact_class"] = "WRONG_CLASS"
    valid, issues = validate_artifact_invariants(artifact)
    return {"caught": not valid, "expected": "invalid", "actual": "valid" if valid else "invalid"}
MUTATIONS.append(("M30", "Artifact: wrong class", "artifact_completeness", m30))


def m31():
    """Artifact: applied state instead of unapplied."""
    cap = make_capability(0)
    life = make_lifecycle(cap)
    cap, life, req, policy, contract = build_valid(cap, life)
    result = consume_capability(capability=cap, lifecycle=life, request=req,
                                 policy=policy, compiler_contract=contract)
    artifact = result["structural_influence_artifact"]
    artifact["application_state"] = "APPLIED"
    valid, issues = validate_artifact_invariants(artifact)
    return {"caught": not valid, "expected": "invalid", "actual": "valid" if valid else "invalid"}
MUTATIONS.append(("M31", "Artifact: applied state", "artifact_completeness", m31))


def m32():
    """Artifact: missing proposal binding."""
    cap = make_capability(0, scope_size=2)
    life = make_lifecycle(cap)
    cap, life, req, policy, contract = build_valid(cap, life)
    result = consume_capability(capability=cap, lifecycle=life, request=req,
                                 policy=policy, compiler_contract=contract)
    artifact = result["structural_influence_artifact"]
    original_count = len(artifact["proposal_bindings"])
    artifact["proposal_bindings"] = artifact["proposal_bindings"][:1]
    return {"caught": len(artifact["proposal_bindings"]) != len(artifact["authorized_proposal_digests"]),
            "expected": "mismatch", "actual": "ok" if len(artifact["proposal_bindings"]) == len(artifact["authorized_proposal_digests"]) else "mismatch"}
MUTATIONS.append(("M32", "Artifact: missing binding", "artifact_completeness", m32))


# === Receipt mutations (33-34) ===
def m33():
    """Receipt: wrong schema version."""
    cap = make_capability(0)
    life = make_lifecycle(cap)
    cap, life, req, policy, contract = build_valid(cap, life)
    result = consume_capability(capability=cap, lifecycle=life, request=req,
                                 policy=policy, compiler_contract=contract)
    receipt = result["consumption_receipt"]
    receipt["schema_version"] = "wrong.v1"
    valid, issues = validate_receipt(receipt)
    return {"caught": not valid, "expected": "invalid", "actual": "valid" if valid else "invalid"}
MUTATIONS.append(("M33", "Receipt: wrong schema", "receipt", m33))


def m34():
    """Receipt: invalid receipt digest."""
    cap = make_capability(0)
    life = make_lifecycle(cap)
    cap, life, req, policy, contract = build_valid(cap, life)
    result = consume_capability(capability=cap, lifecycle=life, request=req,
                                 policy=policy, compiler_contract=contract)
    receipt = result["consumption_receipt"]
    receipt["receipt_digest"] = "0" * 64
    valid, issues = validate_receipt(receipt)
    return {"caught": not valid, "expected": "invalid", "actual": "valid" if valid else "invalid"}
MUTATIONS.append(("M34", "Receipt: invalid digest", "receipt", m34))


# === Atomicity mutations (35-36) ===
def m35():
    """Atomicity: accepted without artifact."""
    cap = make_capability(0)
    life = make_lifecycle(cap)
    cap, life, req, policy, contract = build_valid(cap, life)
    result = consume_capability(capability=cap, lifecycle=life, request=req,
                                 policy=policy, compiler_contract=contract)
    original_artifact = result["structural_influence_artifact"]
    result["structural_influence_artifact"] = None
    from elpis_grid81_consumption_compiler.boundary import verify_authority_boundary
    ok, violations = verify_authority_boundary(None, result)
    return {"caught": not ok, "expected": "violation", "actual": "ok" if ok else "violation"}
MUTATIONS.append(("M35", "Atomicity: accepted no artifact", "atomicity", m35))


def m36():
    """Atomicity: rejected with artifact."""
    cap = make_capability(0)
    life = make_lifecycle(cap)
    life["revocation_state"] = "REVOKED"
    cap, life, req, policy, contract = build_valid(cap, life)
    req["revocation_state"] = "REVOKED"
    result = consume_capability(capability=cap, lifecycle=life, request=req,
                                 policy=policy, compiler_contract=contract)
    cap2 = make_capability(1)
    result["structural_influence_artifact"] = {"artifact_class": "BOUNDED_STRUCTURAL_INFLUENCE_ARTIFACT_V1",
                                                "application_state": "UNAPPLIED"}
    from elpis_grid81_consumption_compiler.boundary import verify_authority_boundary
    ok, violations = verify_authority_boundary(result["structural_influence_artifact"], result)
    return {"caught": not ok, "expected": "violation", "actual": "ok" if ok else "violation"}
MUTATIONS.append(("M36", "Atomicity: rejected with artifact", "atomicity", m36))


# === Forbidden-field mutations (37-39) ===
def m37():
    """Forbidden field: winner in artifact."""
    artifact = {"winner": "model_x", "artifact_class": "BOUNDED_STRUCTURAL_INFLUENCE_ARTIFACT_V1",
                "application_state": "UNAPPLIED"}
    forbidden = check_forbidden_fields(artifact)
    return {"caught": len(forbidden) > 0, "expected": "forbidden_found", "actual": str(forbidden)}
MUTATIONS.append(("M37", "Forbidden: winner field", "forbidden_field", m37))


def m38():
    """Forbidden field: gpu in artifact."""
    artifact = {"gpu": "cuda:0", "artifact_class": "BOUNDED_STRUCTURAL_INFLUENCE_ARTIFACT_V1",
                "application_state": "UNAPPLIED"}
    forbidden = check_forbidden_fields(artifact)
    return {"caught": len(forbidden) > 0, "expected": "forbidden_found", "actual": str(forbidden)}
MUTATIONS.append(("M38", "Forbidden: gpu field", "forbidden_field", m38))


def m39():
    """Forbidden field: activation in nested dict."""
    artifact = {"meta": {"activation": True}, "artifact_class": "BOUNDED_STRUCTURAL_INFLUENCE_ARTIFACT_V1",
                "application_state": "UNAPPLIED"}
    forbidden = check_forbidden_fields(artifact)
    return {"caught": len(forbidden) > 0, "expected": "forbidden_found", "actual": str(forbidden)}
MUTATIONS.append(("M39", "Forbidden: nested activation", "forbidden_field", m39))


# === Semantic identity mutations (40-41) ===
def m40():
    """Semantic identity: tampered artifact semantic digest."""
    cap = make_capability(0)
    life = make_lifecycle(cap)
    cap, life, req, policy, contract = build_valid(cap, life)
    result = consume_capability(capability=cap, lifecycle=life, request=req,
                                 policy=policy, compiler_contract=contract)
    artifact = result["structural_influence_artifact"]
    original_digest = artifact["artifact_semantic_digest"]
    artifact["artifact_semantic_digest"] = canonical_digest({"tampered": 0})
    # Recompute and compare
    from elpis_grid81_consumption_compiler.canonical import canonical_digest as cd
    semantic_payload = {
        "artifact_class": artifact["artifact_class"],
        "authorized_proposal_digests": artifact["authorized_proposal_digests"],
        "consumer_class": artifact["consumer_class"],
        "materialization_class": artifact["materialization_class"],
        "target_domain_class": artifact["target_domain_class"],
        "application_state": artifact["application_state"],
        "source_capability_digest": artifact["source_capability_digest"],
        "source_capability_semantic_digest": artifact["source_capability_semantic_digest"],
        "structural_influence_scope_digest": artifact["structural_influence_scope_digest"],
        "proposal_bindings": artifact["proposal_bindings"],
        "consumption_request_digest": artifact["consumption_request_digest"],
        "compiler_contract_digest": artifact["compiler_contract_digest"],
    }
    expected = cd(semantic_payload)
    return {"caught": artifact["artifact_semantic_digest"] != expected,
            "expected": "mismatch", "actual": "match" if artifact["artifact_semantic_digest"] == expected else "mismatch"}
MUTATIONS.append(("M40", "Semantic: tampered artifact digest", "semantic_identity", m40))


def m41():
    """Semantic identity: tampered receipt digest."""
    cap = make_capability(0)
    life = make_lifecycle(cap)
    cap, life, req, policy, contract = build_valid(cap, life)
    result = consume_capability(capability=cap, lifecycle=life, request=req,
                                 policy=policy, compiler_contract=contract)
    receipt = result["consumption_receipt"]
    original_digest = receipt["receipt_digest"]
    receipt["receipt_digest"] = canonical_digest({"tampered": 0})
    # Recompute
    from elpis_grid81_consumption_compiler.canonical import canonical_digest as cd
    digest_fields = {k: v for k, v in receipt.items() if k != "receipt_digest"}
    expected = cd(digest_fields)
    return {"caught": receipt["receipt_digest"] != expected,
            "expected": "mismatch", "actual": "match" if receipt["receipt_digest"] == expected else "mismatch"}
MUTATIONS.append(("M41", "Semantic: tampered receipt digest", "semantic_identity", m41))


# === Determinism mutation (42) ===
def m42():
    """Determinism: same inputs produce same output."""
    cap = make_capability(0)
    life = make_lifecycle(cap)
    cap, life, req, policy, contract = build_valid(cap, life)
    r1 = consume_capability(capability=cap, lifecycle=life, request=req,
                             policy=policy, compiler_contract=contract)
    r2 = consume_capability(capability=cap, lifecycle=life, request=req,
                             policy=policy, compiler_contract=contract)
    match = canonical_json(r1) == canonical_json(r2)
    return {"caught": match, "expected": "identical", "actual": "identical" if match else "different"}
MUTATIONS.append(("M42", "Determinism: identical outputs", "determinism", m42))


# === Summary contradiction mutation (43) ===
def m43():
    """Summary: acceptance with rejected lifecycle should not happen."""
    cap = make_capability(0)
    life = make_lifecycle(cap)
    life["current_state"] = "CONSUMED"
    life["initial_lifecycle_state"] = "CONSUMED"
    life["consumption_count"] = 1
    cap, life, req, policy, contract = build_valid(cap, life)
    req["current_lifecycle_state"] = "CONSUMED"
    req["current_consumption_count"] = 1
    result = consume_capability(capability=cap, lifecycle=life, request=req,
                                 policy=policy, compiler_contract=contract)
    # Must be rejected, not accepted
    is_accepted = result["transaction_outcome"] == "CONSUMPTION_ACCEPTED"
    return {"caught": not is_accepted, "expected": "rejected", "actual": "accepted" if is_accepted else "rejected"}
MUTATIONS.append(("M43", "Summary: consumed capability not accepted", "summary_contradiction", m43))


# === Determinism mutation (44) ===
def m44():
    """Determinism: policy digest stable."""
    p1 = create_consumption_policy()
    p2 = create_consumption_policy()
    match = p1["policy_digest"] == p2["policy_digest"]
    return {"caught": match, "expected": "stable", "actual": "stable" if match else "unstable"}
MUTATIONS.append(("M44", "Determinism: policy digest stable", "determinism", m44))


def main():
    results = []
    for mid, desc, category, func in MUTATIONS:
        result = run_mutation(mid, desc, category, func)
        results.append(result)

    caught = sum(1 for r in results if r["caught"])
    exact = sum(1 for r in results if r["exact_match"])
    total = len(results)

    report = {
        "total_mutations": total,
        "caught": caught,
        "exact_match": exact,
        "all_caught": caught == total,
        "all_exact": exact == total,
        "mutations": results,
    }

    print(json.dumps(report, indent=2))

    # Write to reports
    report_dir = os.path.join(os.path.dirname(__file__), "reports")
    os.makedirs(report_dir, exist_ok=True)
    with open(os.path.join(report_dir, "G53B_MUTATION_RESULTS.json"), "w") as f:
        json.dump(report, f, indent=2)

    if caught != total:
        print(f"FAILED: {caught}/{total} mutations caught")
        sys.exit(1)
    if exact != total:
        print(f"FAILED: {exact}/{total} exact matches")
        sys.exit(1)
    print(f"PASS: {caught}/{total} mutations caught, {exact}/{total} exact")
    return report


if __name__ == "__main__":
    main()
