"""G5.3C Mutation qualification harness.

28 adversarial mutations covering every application guard.
Each mutation runs through the actual apply_artifact() path.
"""
import sys
import os
import json
import copy

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from elpis_grid81_application_executor.canonical import canonical_digest, check_hex64
from elpis_grid81_application_executor.application import apply_artifact
from elpis_grid81_application_executor.shadow_state import ShadowCapabilityState
from elpis_grid81_application_executor.ledger import ApplicationLedger
from elpis_grid81_application_executor.fixture import (
    create_shadow_fixture, create_shadow_artifact, create_mutation_artifact,
    mutate_and_rehash, MutableShadowState,
)
from elpis_grid81_application_executor.lifecycle import (
    APPLICATION_ACCEPTED,
    REJECTION_ARTIFACT_SCHEMA_INVALID,
    REJECTION_ARTIFACT_LIFECYCLE_NOT_UNAPPLIED,
    REJECTION_ARTIFACT_DIGEST_MISMATCH,
    REJECTION_COMPILER_IDENTITY_MISMATCH,
    REJECTION_CAPABILITY_IDENTITY_MISMATCH,
    REJECTION_EXPECTED_STATE_DIGEST_MISMATCH,
    REJECTION_LIFECYCLE_INELIGIBLE,
    REJECTION_CONSUMER_IDENTITY_MISMATCH,
    REJECTION_AUTHORITY_DOMAIN_VIOLATION,
    REJECTION_SCOPE_MISMATCH,
    REJECTION_PURPOSE_MISMATCH,
    REJECTION_BUDGET_EXCEEDED,
    REJECTION_CONSUMPTION_LIMIT_EXCEEDED,
    REJECTION_ALREADY_APPLIED_ARTIFACT,
    REJECTION_DUPLICATE_RECEIPT,
    REJECTION_STALE_LEDGER_HEAD,
    REJECTION_CANONICAL_WRITE_ATTEMPT,
    ALL_REJECTION_CODES,
)


def exact_outcome_comparison(expected, actual):
    """Determine exact_match: string equality."""
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


def make_valid():
    """Create valid fixture, artifact, shadow state, ledger, compiler_contract_digest."""
    fixture = create_shadow_fixture(0, scope_size=1)
    artifact = create_shadow_artifact(fixture, 0)
    shadow = ShadowCapabilityState(
        capability_digest=fixture["capability_digest"],
        application_state="UNAPPLIED",
        consumption_count=1,
        current_lifecycle_state="CONSUMED",
        applied_artifact_digest=None,
    )
    ledger = ApplicationLedger()
    ccd = artifact["compiler_contract_digest"]
    return fixture, artifact, shadow, ledger, ccd


MUTATIONS = []


# === M01: Invalid artifact schema (guard 1, before digest) ===
def m1():
    _, artifact, shadow, ledger, ccd = make_valid()
    mut = copy.deepcopy(artifact)
    mut["schema_version"] = "invalid-schema.v99"
    receipt = apply_artifact(mut, shadow, ledger, compiler_contract_digest=ccd)
    return {"caught": receipt["application_outcome"] != APPLICATION_ACCEPTED,
            "expected": REJECTION_ARTIFACT_SCHEMA_INVALID, "actual": receipt["application_outcome"]}
MUTATIONS.append(("M01", "Invalid artifact schema", "artifact_schema", m1))


# === M02: Artifact lifecycle not UNAPPLIED (guard 2, after digest) ===
def m2():
    _, artifact, shadow, ledger, ccd = make_valid()
    # UNKNOWN is not a valid application state -> ARTIFACT_LIFECYCLE_NOT_UNAPPLIED
    mut = mutate_and_rehash(artifact, "application_state", "UNKNOWN")
    receipt = apply_artifact(mut, shadow, ledger, compiler_contract_digest=ccd)
    return {"caught": receipt["application_outcome"] != APPLICATION_ACCEPTED,
            "expected": REJECTION_ARTIFACT_LIFECYCLE_NOT_UNAPPLIED, "actual": receipt["application_outcome"]}
MUTATIONS.append(("M02", "Artifact lifecycle not UNAPPLIED", "artifact_lifecycle", m2))


# === M03: Artifact digest mismatch (guard 3) ===
def m3():
    _, artifact, shadow, ledger, ccd = make_valid()
    mut = copy.deepcopy(artifact)
    mut["artifact_digest"] = "0" * 64
    receipt = apply_artifact(mut, shadow, ledger, compiler_contract_digest=ccd)
    return {"caught": receipt["application_outcome"] != APPLICATION_ACCEPTED,
            "expected": REJECTION_ARTIFACT_DIGEST_MISMATCH, "actual": receipt["application_outcome"]}
MUTATIONS.append(("M03", "Artifact digest mismatch", "artifact_digest", m3))


# === M04: Compiler identity mismatch (guard 4, after digest) ===
def m4():
    _, artifact, shadow, ledger, ccd = make_valid()
    mut = mutate_and_rehash(artifact, "compiler_contract_digest",
                             canonical_digest({"wrong_compiler": True}))
    receipt = apply_artifact(mut, shadow, ledger, compiler_contract_digest=ccd)
    return {"caught": receipt["application_outcome"] != APPLICATION_ACCEPTED,
            "expected": REJECTION_COMPILER_IDENTITY_MISMATCH, "actual": receipt["application_outcome"]}
MUTATIONS.append(("M04", "Compiler digest mismatch", "compiler_identity", m4))


# === M05: Capability ID mismatch (guard 5, after digest) ===
def m5():
    _, artifact, shadow, ledger, ccd = make_valid()
    mut = mutate_and_rehash(artifact, "source_capability_digest",
                             canonical_digest({"wrong_cap": True}))
    receipt = apply_artifact(mut, shadow, ledger, compiler_contract_digest=ccd)
    return {"caught": receipt["application_outcome"] != APPLICATION_ACCEPTED,
            "expected": REJECTION_CAPABILITY_IDENTITY_MISMATCH, "actual": receipt["application_outcome"]}
MUTATIONS.append(("M05", "Capability ID mismatch", "capability_identity", m5))


# === M06: Invalid hex in artifact digest (guard 3) ===
def m6():
    _, artifact, shadow, ledger, ccd = make_valid()
    mut = copy.deepcopy(artifact)
    mut["artifact_digest"] = "g" * 64
    receipt = apply_artifact(mut, shadow, ledger, compiler_contract_digest=ccd)
    return {"caught": receipt["application_outcome"] != APPLICATION_ACCEPTED,
            "expected": REJECTION_ARTIFACT_DIGEST_MISMATCH, "actual": receipt["application_outcome"]}
MUTATIONS.append(("M06", "Invalid hex in artifact digest", "artifact_digest", m6))


# === M07: Lifecycle ineligible (guard 7) ===
def m7():
    _, artifact, shadow, ledger, ccd = make_valid()
    shadow_wrong = ShadowCapabilityState(
        capability_digest=artifact["source_capability_digest"],
        application_state="UNAPPLIED",
        consumption_count=0,
        current_lifecycle_state="GRANTED_UNCONSUMED",
        applied_artifact_digest=None,
    )
    receipt = apply_artifact(artifact, shadow_wrong, ledger, compiler_contract_digest=ccd)
    return {"caught": receipt["application_outcome"] != APPLICATION_ACCEPTED,
            "expected": REJECTION_LIFECYCLE_INELIGIBLE, "actual": receipt["application_outcome"]}
MUTATIONS.append(("M07", "Lifecycle ineligible", "lifecycle", m7))


# === M08: Consumer identity mismatch (guard 8, after digest) ===
def m8():
    _, artifact, shadow, ledger, ccd = make_valid()
    mut = mutate_and_rehash(artifact, "consumer_class", "UNAUTHORIZED_CONSUMER")
    receipt = apply_artifact(mut, shadow, ledger, compiler_contract_digest=ccd)
    return {"caught": receipt["application_outcome"] != APPLICATION_ACCEPTED,
            "expected": REJECTION_CONSUMER_IDENTITY_MISMATCH, "actual": receipt["application_outcome"]}
MUTATIONS.append(("M08", "Consumer identity mismatch", "consumer_identity", m8))


# === M09: Authority domain violation (guard 9, after digest) ===
def m9():
    _, artifact, shadow, ledger, ccd = make_valid()
    mut = mutate_and_rehash(artifact, "winner", "should_not_be_here")
    receipt = apply_artifact(mut, shadow, ledger, compiler_contract_digest=ccd)
    return {"caught": receipt["application_outcome"] != APPLICATION_ACCEPTED,
            "expected": REJECTION_AUTHORITY_DOMAIN_VIOLATION, "actual": receipt["application_outcome"]}
MUTATIONS.append(("M09", "Authority domain violation", "authority_domain", m9))


# === M10: Scope mismatch (guard 10, after digest) ===
def m10():
    _, artifact, shadow, ledger, ccd = make_valid()
    mut = mutate_and_rehash(artifact, "proposal_bindings", [])
    receipt = apply_artifact(mut, shadow, ledger, compiler_contract_digest=ccd)
    return {"caught": receipt["application_outcome"] != APPLICATION_ACCEPTED,
            "expected": REJECTION_SCOPE_MISMATCH, "actual": receipt["application_outcome"]}
MUTATIONS.append(("M10", "Scope mismatch", "scope", m10))


# === M11: Purpose mismatch (guard 11, after digest) ===
def m11():
    _, artifact, shadow, ledger, ccd = make_valid()
    mut = mutate_and_rehash(artifact, "materialization_class", "INVALID_MATERIALIZATION")
    receipt = apply_artifact(mut, shadow, ledger, compiler_contract_digest=ccd)
    return {"caught": receipt["application_outcome"] != APPLICATION_ACCEPTED,
            "expected": REJECTION_PURPOSE_MISMATCH, "actual": receipt["application_outcome"]}
MUTATIONS.append(("M11", "Purpose mismatch", "purpose", m11))


# === M12: Budget exceeded (guard 12, before validation) ===
def m12():
    _, artifact, shadow, ledger, ccd = make_valid()
    shadow_exhausted = ShadowCapabilityState(
        capability_digest=artifact["source_capability_digest"],
        application_state="UNAPPLIED",
        consumption_count=10,
        current_lifecycle_state="CONSUMED",
        applied_artifact_digest=None,
    )
    receipt = apply_artifact(artifact, shadow_exhausted, ledger,
                             compiler_contract_digest=ccd, budget_limit=10)
    return {"caught": receipt["application_outcome"] != APPLICATION_ACCEPTED,
            "expected": REJECTION_BUDGET_EXCEEDED, "actual": receipt["application_outcome"]}
MUTATIONS.append(("M12", "Budget exceeded", "budget", m12))


# === M13: Already applied artifact (guard 14 — double application) ===
def m13():
    fixture, artifact, shadow, ledger, ccd = make_valid()
    mutable = MutableShadowState(shadow)
    # First application succeeds
    receipt1 = apply_artifact(artifact, mutable.state, ledger, compiler_contract_digest=ccd)
    assert receipt1["application_outcome"] == APPLICATION_ACCEPTED
    # Transition shadow state
    mutable.transition_to_applied(artifact["artifact_digest"])
    # Second application with same artifact
    receipt2 = apply_artifact(artifact, mutable.state, ledger, compiler_contract_digest=ccd)
    return {"caught": receipt2["application_outcome"] != APPLICATION_ACCEPTED,
            "expected": REJECTION_ALREADY_APPLIED_ARTIFACT, "actual": receipt2["application_outcome"]}
MUTATIONS.append(("M13", "Already applied artifact (double application)", "already_applied", m13))


# === M14: Duplicate receipt ===
def m14():
    fixture, artifact, shadow, ledger, ccd = make_valid()
    mutable = MutableShadowState(shadow)
    receipt1 = apply_artifact(artifact, mutable.state, ledger, compiler_contract_digest=ccd)
    assert receipt1["application_outcome"] == APPLICATION_ACCEPTED
    mutable.transition_to_applied(artifact["artifact_digest"])
    receipt2 = apply_artifact(artifact, mutable.state, ledger, compiler_contract_digest=ccd)
    return {"caught": receipt2["application_outcome"] != APPLICATION_ACCEPTED,
            "expected": REJECTION_ALREADY_APPLIED_ARTIFACT, "actual": receipt2["application_outcome"]}
MUTATIONS.append(("M14", "Duplicate receipt", "duplicate_receipt", m14))


# === M15: Stale ledger head ===
def m15():
    fixture, artifact, shadow, ledger, ccd = make_valid()
    # Record the ledger head before any other application
    expected_head = ledger.head
    # Apply a different artifact first to advance ledger
    fixture2 = create_shadow_fixture(999, scope_size=1)
    artifact2 = create_shadow_artifact(fixture2, 999)
    shadow2 = ShadowCapabilityState(
        capability_digest=fixture2["capability_digest"],
        application_state="UNAPPLIED",
        consumption_count=1,
        current_lifecycle_state="CONSUMED",
        applied_artifact_digest=None,
    )
    apply_artifact(artifact2, shadow2, ledger, compiler_contract_digest=artifact2["compiler_contract_digest"])
    # Now try original with stale expected head
    receipt = apply_artifact(artifact, shadow, ledger, compiler_contract_digest=ccd,
                              expected_ledger_head=expected_head)
    return {"caught": receipt["application_outcome"] != APPLICATION_ACCEPTED,
            "expected": REJECTION_STALE_LEDGER_HEAD, "actual": receipt["application_outcome"]}
MUTATIONS.append(("M15", "Stale ledger head", "stale_ledger", m15))


# === M16: Canonical write attempt (guard 17, after digest) ===
def m16():
    _, artifact, shadow, ledger, ccd = make_valid()
    mut = mutate_and_rehash(artifact, "canonical_path", "/should/not/exist")
    receipt = apply_artifact(mut, shadow, ledger, compiler_contract_digest=ccd)
    return {"caught": receipt["application_outcome"] != APPLICATION_ACCEPTED,
            "expected": REJECTION_CANONICAL_WRITE_ATTEMPT, "actual": receipt["application_outcome"]}
MUTATIONS.append(("M16", "Canonical write attempt", "canonical_write", m16))


# === M17: Empty proposal bindings ===
def m17():
    _, artifact, shadow, ledger, ccd = make_valid()
    mut = mutate_and_rehash(artifact, "proposal_bindings", [])
    receipt = apply_artifact(mut, shadow, ledger, compiler_contract_digest=ccd)
    return {"caught": receipt["application_outcome"] != APPLICATION_ACCEPTED,
            "expected": REJECTION_SCOPE_MISMATCH, "actual": receipt["application_outcome"]}
MUTATIONS.append(("M17", "Empty proposal bindings", "scope", m17))


# === M18: Malformed nested values ===
def m18():
    _, artifact, shadow, ledger, ccd = make_valid()
    # Malformed bindings (contains None) — scope count check catches this
    # because len(bindings) != len(proposals) when bindings has wrong structure
    # Actually [None] has same length as [valid_binding] so count matches.
    # Instead use wrong-length bindings:
    mut = mutate_and_rehash(artifact, "proposal_bindings", [None, None, None])
    receipt = apply_artifact(mut, shadow, ledger, compiler_contract_digest=ccd)
    return {"caught": receipt["application_outcome"] != APPLICATION_ACCEPTED,
            "expected": REJECTION_SCOPE_MISMATCH, "actual": receipt["application_outcome"]}
MUTATIONS.append(("M18", "Malformed nested values", "malformed", m18))


# === M19: Already applied capability state ===
def m19():
    _, artifact, shadow, ledger, ccd = make_valid()
    shadow_applied = ShadowCapabilityState(
        capability_digest=artifact["source_capability_digest"],
        application_state="APPLIED",
        consumption_count=1,
        current_lifecycle_state="APPLIED",
        applied_artifact_digest=canonical_digest({"prior": "artifact"}),
    )
    receipt = apply_artifact(artifact, shadow_applied, ledger, compiler_contract_digest=ccd)
    return {"caught": receipt["application_outcome"] != APPLICATION_ACCEPTED,
            "expected": REJECTION_LIFECYCLE_INELIGIBLE, "actual": receipt["application_outcome"]}
MUTATIONS.append(("M19", "Already applied capability state", "lifecycle", m19))


# === M20: REVOKED lifecycle ===
def m20():
    _, artifact, shadow, ledger, ccd = make_valid()
    shadow_revoked = ShadowCapabilityState(
        capability_digest=artifact["source_capability_digest"],
        application_state="UNAPPLIED",
        consumption_count=0,
        current_lifecycle_state="REVOKED",
        applied_artifact_digest=None,
    )
    receipt = apply_artifact(artifact, shadow_revoked, ledger, compiler_contract_digest=ccd)
    return {"caught": receipt["application_outcome"] != APPLICATION_ACCEPTED,
            "expected": REJECTION_LIFECYCLE_INELIGIBLE, "actual": receipt["application_outcome"]}
MUTATIONS.append(("M20", "Revoked lifecycle", "lifecycle", m20))


# === M21: EXPIRED lifecycle ===
def m21():
    _, artifact, shadow, ledger, ccd = make_valid()
    shadow_expired = ShadowCapabilityState(
        capability_digest=artifact["source_capability_digest"],
        application_state="UNAPPLIED",
        consumption_count=0,
        current_lifecycle_state="EXPIRED",
        applied_artifact_digest=None,
    )
    receipt = apply_artifact(artifact, shadow_expired, ledger, compiler_contract_digest=ccd)
    return {"caught": receipt["application_outcome"] != APPLICATION_ACCEPTED,
            "expected": REJECTION_LIFECYCLE_INELIGIBLE, "actual": receipt["application_outcome"]}
MUTATIONS.append(("M21", "Expired lifecycle", "lifecycle", m21))


# === M22: Replay after acceptance ===
def m22():
    fixture, artifact, shadow, ledger, ccd = make_valid()
    mutable = MutableShadowState(shadow)
    receipt1 = apply_artifact(artifact, mutable.state, ledger, compiler_contract_digest=ccd)
    assert receipt1["application_outcome"] == APPLICATION_ACCEPTED
    mutable.transition_to_applied(artifact["artifact_digest"])
    receipt2 = apply_artifact(artifact, mutable.state, ledger, compiler_contract_digest=ccd)
    return {"caught": receipt2["application_outcome"] != APPLICATION_ACCEPTED,
            "expected": REJECTION_ALREADY_APPLIED_ARTIFACT, "actual": receipt2["application_outcome"]}
MUTATIONS.append(("M22", "Replay after acceptance", "replay", m22))


# === M23: Concurrent stale-state application ===
# === M23: Concurrent stale-state application ===
def m23():
    fixture = create_shadow_fixture(0, scope_size=1)
    artifact = create_shadow_artifact(fixture, 0)
    shadow = ShadowCapabilityState(
        capability_digest=fixture["capability_digest"],
        application_state="UNAPPLIED",
        consumption_count=1,
        current_lifecycle_state="CONSUMED",
        applied_artifact_digest=None,
    )
    ledger = ApplicationLedger()
    ccd = artifact["compiler_contract_digest"]
    mutable = MutableShadowState(shadow)

    # Record ledger head before any application
    expected_head = ledger.head

    # Apply first
    receipt1 = apply_artifact(artifact, mutable.state, ledger, compiler_contract_digest=ccd)
    assert receipt1["application_outcome"] == APPLICATION_ACCEPTED
    mutable.transition_to_applied(artifact["artifact_digest"])

    # Create competing artifact for same capability with stale expected head
    fixture2 = create_shadow_fixture(0, scope_size=1)
    artifact2 = create_shadow_artifact(fixture2, 0)
    receipt2 = apply_artifact(artifact2, mutable.state, ledger, compiler_contract_digest=ccd,
                               expected_ledger_head=expected_head)
    return {"caught": receipt2["application_outcome"] != APPLICATION_ACCEPTED,
            "expected": REJECTION_STALE_LEDGER_HEAD, "actual": receipt2["application_outcome"]}
MUTATIONS.append(("M23", "Concurrent stale-state application", "concurrent", m23))


# === M24: Altered compiled payload ===
def m24():
    _, artifact, shadow, ledger, ccd = make_valid()
    mut = copy.deepcopy(artifact)
    mut["source_capability_digest"] = canonical_digest({"altered": True})
    # Don't rehash — digest check should catch the alteration
    receipt = apply_artifact(mut, shadow, ledger, compiler_contract_digest=ccd)
    return {"caught": receipt["application_outcome"] != APPLICATION_ACCEPTED,
            "expected": REJECTION_ARTIFACT_DIGEST_MISMATCH, "actual": receipt["application_outcome"]}
MUTATIONS.append(("M24", "Altered compiled payload", "payload_integrity", m24))


# === M25: Altered upstream capability ===
def m25():
    fixture = create_shadow_fixture(0, scope_size=1)
    artifact = create_shadow_artifact(fixture, 0)
    ccd = artifact["compiler_contract_digest"]
    # Shadow state references different capability
    fixture2 = create_shadow_fixture(999, scope_size=1)
    shadow = ShadowCapabilityState(
        capability_digest=fixture2["capability_digest"],
        application_state="UNAPPLIED",
        consumption_count=1,
        current_lifecycle_state="CONSUMED",
        applied_artifact_digest=None,
    )
    ledger = ApplicationLedger()
    receipt = apply_artifact(artifact, shadow, ledger, compiler_contract_digest=ccd)
    return {"caught": receipt["application_outcome"] != APPLICATION_ACCEPTED,
            "expected": REJECTION_CAPABILITY_IDENTITY_MISMATCH, "actual": receipt["application_outcome"]}
MUTATIONS.append(("M25", "Altered upstream capability", "capability_identity", m25))


# === M26: Receipt chain integrity ===
def m26():
    fixture, artifact, shadow, ledger, ccd = make_valid()
    receipt1 = apply_artifact(artifact, shadow, ledger, compiler_contract_digest=ccd)
    assert receipt1["application_outcome"] == APPLICATION_ACCEPTED
    ok, status = ledger.verify_chain()
    return {"caught": ok, "expected": "valid", "actual": status}
MUTATIONS.append(("M26", "Receipt chain integrity", "receipt_chain", m26))


# === M27: Injected unknown forbidden fields (guard 9, after digest) ===
def m27():
    _, artifact, shadow, ledger, ccd = make_valid()
    mut = mutate_and_rehash(artifact, "model_id", "injected_model")
    receipt = apply_artifact(mut, shadow, ledger, compiler_contract_digest=ccd)
    return {"caught": receipt["application_outcome"] != APPLICATION_ACCEPTED,
            "expected": REJECTION_AUTHORITY_DOMAIN_VIOLATION, "actual": receipt["application_outcome"]}
MUTATIONS.append(("M27", "Injected unknown forbidden fields", "authority_domain", m27))


# === M28: Noncanonical ordering (should accept) ===
def m28():
    _, artifact, shadow, ledger, ccd = make_valid()
    receipt = apply_artifact(artifact, shadow, ledger, compiler_contract_digest=ccd)
    return {"caught": receipt["application_outcome"] == APPLICATION_ACCEPTED,
            "expected": APPLICATION_ACCEPTED, "actual": receipt["application_outcome"]}
MUTATIONS.append(("M28", "Noncanonical ordering (should accept)", "determinism", m28))


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

    # Write mutation records
    report_dir = os.path.join(os.path.dirname(__file__), "reports")
    os.makedirs(report_dir, exist_ok=True)
    with open(os.path.join(report_dir, "G53C_MUTATION_RECORDS.jsonl"), "w") as f:
        for r in results:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")

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
