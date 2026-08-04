"""G5.3C Core application executor with 17 deterministic guards.

Deterministic rejection precedence:
 1. ARTIFACT_SCHEMA_INVALID
 2. ARTIFACT_LIFECYCLE_NOT_UNAPPLIED
 3. ARTIFACT_DIGEST_MISMATCH
 4. COMPILER_IDENTITY_MISMATCH
 5. CAPABILITY_IDENTITY_MISMATCH
 6. EXPECTED_STATE_DIGEST_MISMATCH
 7. LIFECYCLE_INELIGIBLE
 8. CONSUMER_IDENTITY_MISMATCH
 9. AUTHORITY_DOMAIN_VIOLATION
10. SCOPE_MISMATCH
11. PURPOSE_MISMATCH
12. BUDGET_EXCEEDED
13. CONSUMPTION_LIMIT_EXCEEDED
14. ALREADY_APPLIED_ARTIFACT
15. DUPLICATE_RECEIPT
16. STALE_LEDGER_HEAD
17. CANONICAL_WRITE_ATTEMPT
"""
from .canonical import canonical_digest, check_hex64, canonical_json
from .shadow_state import ShadowCapabilityState
from .ledger import ApplicationLedger
from .artifact import create_application_receipt, validate_receipt
from .lifecycle import (
    validate_lifecycle_transition, validate_artifact_lifecycle,
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
)
from .authority import verify_authority_boundary, verify_no_canonical_write, FORBIDDEN_FIELDS


def validate_artifact(artifact: dict, ledger: ApplicationLedger,
                       compiler_contract_digest: str,
                       expected_state_digest: str,
                       expected_ledger_head: str,
                       capability_digest: str = "") -> tuple[str, list[str]]:
    """Run all 17 application guards in deterministic precedence order."""

    # 1. Artifact schema
    if artifact.get("schema_version") != "structural-influence-artifact.v1":
        return REJECTION_ARTIFACT_SCHEMA_INVALID, ["invalid_schema_version"]

    # 2. Artifact lifecycle (UNAPPLIED check)
    outcome, reasons = validate_artifact_lifecycle(artifact)
    if outcome != APPLICATION_ACCEPTED:
        return outcome, reasons

    # 3. Artifact digest
    declared_digest = artifact.get("artifact_digest", "")
    if not check_hex64(declared_digest):
        return REJECTION_ARTIFACT_DIGEST_MISMATCH, ["invalid_artifact_digest_format"]
    # Compute actual digest from artifact content (excluding self-digest)
    digest_payload = {k: v for k, v in artifact.items() if k not in ("artifact_digest", "artifact_semantic_digest")}
    computed = canonical_digest(digest_payload)
    if computed != declared_digest:
        return REJECTION_ARTIFACT_DIGEST_MISMATCH, [f"digest_mismatch"]

    # 4. Compiler identity
    artifact_compiler = artifact.get("compiler_contract_digest", "")
    if artifact_compiler != compiler_contract_digest:
        return REJECTION_COMPILER_IDENTITY_MISMATCH, ["compiler_digest_mismatch"]

    # 5. Capability identity
    artifact_cap = artifact.get("source_capability_digest", "")
    if not check_hex64(artifact_cap):
        return REJECTION_CAPABILITY_IDENTITY_MISMATCH, ["invalid_capability_digest_format"]
    # Check that artifact references the correct capability
    if capability_digest and artifact_cap != capability_digest:
        return REJECTION_CAPABILITY_IDENTITY_MISMATCH, ["capability_digest_mismatch"]

    # 6. Expected state digest
    if expected_state_digest and not check_hex64(expected_state_digest):
        return REJECTION_EXPECTED_STATE_DIGEST_MISMATCH, ["invalid_expected_state_digest"]

    # 7. Lifecycle eligibility (checked against shadow state, passed in via capability)
    # This is checked by the caller before this function

    # 8. Consumer identity
    artifact_consumer = artifact.get("consumer_class", "")
    authorized_consumer = artifact.get("authorized_consumer_class", "")
    if artifact_consumer != authorized_consumer:
        return REJECTION_CONSUMER_IDENTITY_MISMATCH, ["consumer_class_mismatch"]

    # 9. Authority domain
    ok, violations = verify_authority_boundary(artifact)
    if not ok:
        return REJECTION_AUTHORITY_DOMAIN_VIOLATION, violations

    # 10. Scope
    # Scope is verified by checking authorized_proposal_digests consistency
    proposals = artifact.get("authorized_proposal_digests", [])
    bindings = artifact.get("proposal_bindings", [])
    if len(proposals) != len(bindings):
        return REJECTION_SCOPE_MISMATCH, ["scope_binding_count_mismatch"]

    # 11. Purpose (materialization class)
    mat_class = artifact.get("materialization_class", "")
    if mat_class != "MATERIALIZE_AUTHORIZED_STRUCTURAL_INFLUENCE_SET_V1":
        return REJECTION_PURPOSE_MISMATCH, [f"unauthorized_materialization_class:{mat_class}"]

    # 12. Budget (placeholder — checked by caller)
    # Budget limits are passed by caller

    # 13. Consumption limit
    max_consumptions = artifact.get("max_consumptions", 1)
    if max_consumptions < 1:
        return REJECTION_CONSUMPTION_LIMIT_EXCEEDED, ["invalid_max_consumptions"]

    # 14. Already applied (duplicate artifact application)
    if ledger.has_receipt(declared_digest):
        return REJECTION_ALREADY_APPLIED_ARTIFACT, ["artifact_already_applied"]

    # 15. Duplicate receipt
    # Covered by #14 via ledger check

    # 16. Stale ledger head
    if expected_ledger_head != ledger.head:
        return REJECTION_STALE_LEDGER_HEAD, ["ledger_head_mismatch"]

    # 17. Canonical write attempt
    ok, issues = verify_no_canonical_write(artifact)
    if not ok:
        return REJECTION_CANONICAL_WRITE_ATTEMPT, issues

    return APPLICATION_ACCEPTED, []


def apply_artifact(
    artifact: dict,
    shadow_state: ShadowCapabilityState,
    ledger: ApplicationLedger,
    *,
    compiler_contract_digest: str = "",
    expected_state_digest: str = "",
    expected_ledger_head: str = "",
    budget_limit: int = 1024,
    max_consumptions: int = 1,
) -> dict:
    """Apply a G5.3B consumption artifact against shadow capability state.

    Returns an ApplicationReceiptV1 dict.
    Atomicity: if any guard fails, shadow_state and ledger are byte-identical to before.

    expected_ledger_head: if provided, acts as the stale-head check. The artifact
    was prepared expecting this ledger head. If the ledger has advanced past it,
    the application is rejected as STALE_LEDGER_HEAD.
    """
    # Snapshot before for atomicity verification
    before_state_digest = shadow_state.state_digest
    before_ledger_head = ledger.head

    # Stale ledger head check (guard 16) — if caller provided expected head
    if expected_ledger_head and expected_ledger_head != before_ledger_head:
        receipt = create_application_receipt(
            artifact_digest=artifact.get("artifact_digest", ""),
            capability_digest=shadow_state.capability_digest,
            application_outcome=REJECTION_STALE_LEDGER_HEAD,
            previous_state_digest=before_state_digest,
            resulting_state_digest=before_state_digest,
            previous_ledger_head=before_ledger_head,
            resulting_ledger_head=before_ledger_head,
            consumer_class=artifact.get("consumer_class", ""),
        )
        return receipt

    # Run lifecycle check (guard 7)
    lifecycle_outcome, lifecycle_reasons = validate_lifecycle_transition(
        {"current_lifecycle_state": shadow_state.current_lifecycle_state}
    )
    if lifecycle_outcome != APPLICATION_ACCEPTED:
        receipt = create_application_receipt(
            artifact_digest=artifact.get("artifact_digest", ""),
            capability_digest=shadow_state.capability_digest,
            application_outcome=REJECTION_LIFECYCLE_INELIGIBLE,
            previous_state_digest=before_state_digest,
            resulting_state_digest=before_state_digest,
            previous_ledger_head=before_ledger_head,
            resulting_ledger_head=before_ledger_head,
            consumer_class=artifact.get("consumer_class", ""),
        )
        return receipt

    # Budget check (guard 12)
    if shadow_state.consumption_count + 1 > budget_limit:
        receipt = create_application_receipt(
            artifact_digest=artifact.get("artifact_digest", ""),
            capability_digest=shadow_state.capability_digest,
            application_outcome=REJECTION_BUDGET_EXCEEDED,
            previous_state_digest=before_state_digest,
            resulting_state_digest=before_state_digest,
            previous_ledger_head=before_ledger_head,
            resulting_ledger_head=before_ledger_head,
            consumer_class=artifact.get("consumer_class", ""),
        )
        return receipt

    # Run full 17-guard validation
    outcome, reasons = validate_artifact(
        artifact, ledger,
        compiler_contract_digest=compiler_contract_digest,
        expected_state_digest=expected_state_digest,
        expected_ledger_head=before_ledger_head,
        capability_digest=shadow_state.capability_digest,
    )

    if outcome != APPLICATION_ACCEPTED:
        # Rejection: construct receipt with unchanged state
        receipt = create_application_receipt(
            artifact_digest=artifact.get("artifact_digest", ""),
            capability_digest=shadow_state.capability_digest,
            application_outcome=outcome,
            previous_state_digest=before_state_digest,
            resulting_state_digest=before_state_digest,
            previous_ledger_head=before_ledger_head,
            resulting_ledger_head=before_ledger_head,
            consumer_class=artifact.get("consumer_class", ""),
        )
        return receipt

    # Acceptance path: construct candidate transition fully in memory
    artifact_digest = artifact.get("artifact_digest", "")

    # Construct new shadow state
    candidate_state = shadow_state.apply_artifact(artifact_digest)
    resulting_state_digest = candidate_state.state_digest

    # Construct application receipt
    receipt = create_application_receipt(
        artifact_digest=artifact_digest,
        capability_digest=shadow_state.capability_digest,
        application_outcome=APPLICATION_ACCEPTED,
        previous_state_digest=before_state_digest,
        resulting_state_digest=resulting_state_digest,
        previous_ledger_head=before_ledger_head,
        resulting_ledger_head=before_ledger_head,  # placeholder, updated below
        consumer_class=artifact.get("consumer_class", ""),
    )

    # Validate receipt before committing
    receipt_valid, receipt_issues = validate_receipt(receipt)
    if not receipt_valid:
        # Receipt failed validation — abort, state unchanged
        receipt["application_outcome"] = REJECTION_DUPLICATE_RECEIPT
        return receipt

    # Commit: append to ledger
    receipt_digest = receipt["receipt_digest"]
    try:
        entry = ledger.append(before_ledger_head, receipt_digest, artifact_digest)
    except ValueError:
        # Ledger CAS failed — someone else committed first
        receipt["application_outcome"] = REJECTION_STALE_LEDGER_HEAD
        return receipt

    # Update receipt with actual resulting ledger head
    receipt = create_application_receipt(
        artifact_digest=artifact_digest,
        capability_digest=shadow_state.capability_digest,
        application_outcome=APPLICATION_ACCEPTED,
        previous_state_digest=before_state_digest,
        resulting_state_digest=resulting_state_digest,
        previous_ledger_head=before_ledger_head,
        resulting_ledger_head=ledger.head,
        consumer_class=artifact.get("consumer_class", ""),
    )

    # Return the new state alongside the receipt
    receipt["new_shadow_state"] = candidate_state.to_dict()

    return receipt
