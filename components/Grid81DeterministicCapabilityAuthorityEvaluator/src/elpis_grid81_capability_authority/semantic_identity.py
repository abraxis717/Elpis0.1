"""G5.2B Semantic Identity Verification.

Capability semantic identity includes only semantic dimensions, excludes provenance.
Tests invariance under provenance changes and sensitivity under semantic changes.
"""
import copy

from .canonical import canonical_digest
from .capability import create_capability


def compute_semantic_digest(capability: dict) -> str:
    """Compute the semantic digest of a capability (excludes provenance)."""
    semantic_payload = {
        "authorized_consumer_class": capability["authorized_consumer_class"],
        "authorized_operation_class": capability["authorized_operation_class"],
        "authorized_proposal_digests": capability["authorized_proposal_digests"],
        "authority_policy_digest": capability["authority_policy_digest"],
        "capability_class": capability["capability_class"],
        "capability_limit_digest": capability["capability_limit_digest"],
        "capability_scope_digest": capability["capability_scope_digest"],
        "logical_validity": {
            "valid_from_logical_tick": capability["valid_from_logical_tick"],
            "valid_through_logical_tick": capability["valid_through_logical_tick"],
        },
        "nonce_digest": capability["nonce_digest"],
        "nontransferable": capability["nontransferable"],
        "revocation_policy_digest": capability["revocation_policy_digest"],
        "single_use": True,
    }
    return canonical_digest(semantic_payload)


def run_invariance_checks(capability: dict) -> list:
    """Run semantic identity invariance checks.

    The semantic digest should be unchanged when provenance fields change.
    """
    checks = []
    base_digest = compute_semantic_digest(capability)

    # Check 1: Source request digest change (provenance)
    mutated = copy.deepcopy(capability)
    mutated["source_request_digest"] = "0" * 64
    new_digest = compute_semantic_digest(mutated)
    checks.append({
        "check_id": "INVARIANCE_PROVENANCE_REQUEST",
        "transformation": "source_request_digest_changed",
        "before_digest": base_digest,
        "after_digest": new_digest,
        "pass": base_digest == new_digest,
    })

    # Check 2: Source adjudication digest change (provenance)
    mutated = copy.deepcopy(capability)
    mutated["source_adjudication_record_digest"] = "0" * 64
    new_digest = compute_semantic_digest(mutated)
    checks.append({
        "check_id": "INVARIANCE_PROVENANCE_ADJUDICATION",
        "transformation": "source_adjudication_record_digest_changed",
        "before_digest": base_digest,
        "after_digest": new_digest,
        "pass": base_digest == new_digest,
    })

    # Check 3: Source proposal set digest change (provenance)
    mutated = copy.deepcopy(capability)
    mutated["source_proposal_set_digest"] = "0" * 64
    new_digest = compute_semantic_digest(mutated)
    checks.append({
        "check_id": "INVARIANCE_PROVENANCE_PROPOSAL_SET",
        "transformation": "source_proposal_set_digest_changed",
        "before_digest": base_digest,
        "after_digest": new_digest,
        "pass": base_digest == new_digest,
    })

    # Check 4: Claims-not-made change (provenance)
    mutated = copy.deepcopy(capability)
    mutated["claims_not_made"] = []
    new_digest = compute_semantic_digest(mutated)
    checks.append({
        "check_id": "INVARIANCE_PROVENANCE_CLAIMS",
        "transformation": "claims_not_made_cleared",
        "before_digest": base_digest,
        "after_digest": new_digest,
        "pass": base_digest == new_digest,
    })

    return checks


def run_sensitivity_checks(capability: dict, authority_context: dict) -> list:
    """Run semantic identity sensitivity checks.

    Each semantic dimension mutation must change the semantic digest.
    """
    checks = []
    base_digest = compute_semantic_digest(capability)

    # 1. Authorized proposal change
    mutated = copy.deepcopy(capability)
    mutated["authorized_proposal_digests"] = ["0" * 64]
    new_digest = compute_semantic_digest(mutated)
    checks.append({
        "check_id": "SENSITIVITY_PROPOSAL",
        "semantic_dimension": "authorized_proposal_digests",
        "before_digest": base_digest,
        "after_digest": new_digest,
        "pass": base_digest != new_digest,
    })

    # 2. Operation class change
    mutated = copy.deepcopy(capability)
    mutated["authorized_operation_class"] = "OTHER_OPERATION_V1"
    new_digest = compute_semantic_digest(mutated)
    checks.append({
        "check_id": "SENSITIVITY_OPERATION",
        "semantic_dimension": "authorized_operation_class",
        "before_digest": base_digest,
        "after_digest": new_digest,
        "pass": base_digest != new_digest,
    })

    # 3. Consumer class change
    mutated = copy.deepcopy(capability)
    mutated["authorized_consumer_class"] = "OTHER_CONSUMER_V1"
    new_digest = compute_semantic_digest(mutated)
    checks.append({
        "check_id": "SENSITIVITY_CONSUMER",
        "semantic_dimension": "authorized_consumer_class",
        "before_digest": base_digest,
        "after_digest": new_digest,
        "pass": base_digest != new_digest,
    })

    # 4. Authority policy change
    mutated = copy.deepcopy(capability)
    mutated["authority_policy_digest"] = "1" * 64
    new_digest = compute_semantic_digest(mutated)
    checks.append({
        "check_id": "SENSITIVITY_POLICY",
        "semantic_dimension": "authority_policy_digest",
        "before_digest": base_digest,
        "after_digest": new_digest,
        "pass": base_digest != new_digest,
    })

    # 5. Scope digest change
    mutated = copy.deepcopy(capability)
    mutated["capability_scope_digest"] = "2" * 64
    new_digest = compute_semantic_digest(mutated)
    checks.append({
        "check_id": "SENSITIVITY_SCOPE",
        "semantic_dimension": "capability_scope_digest",
        "before_digest": base_digest,
        "after_digest": new_digest,
        "pass": base_digest != new_digest,
    })

    # 6. Limit digest change (max_consumptions)
    mutated = copy.deepcopy(capability)
    mutated["capability_limit_digest"] = "3" * 64
    new_digest = compute_semantic_digest(mutated)
    checks.append({
        "check_id": "SENSITIVITY_LIMIT",
        "semantic_dimension": "capability_limit_digest",
        "before_digest": base_digest,
        "after_digest": new_digest,
        "pass": base_digest != new_digest,
    })

    # 7. Logical validity change
    mutated = copy.deepcopy(capability)
    mutated["valid_from_logical_tick"] = 1
    mutated["valid_through_logical_tick"] = 2
    new_digest = compute_semantic_digest(mutated)
    checks.append({
        "check_id": "SENSITIVITY_LOGICAL_VALIDITY",
        "semantic_dimension": "logical_validity",
        "before_digest": base_digest,
        "after_digest": new_digest,
        "pass": base_digest != new_digest,
    })

    # 8. Nonce change
    mutated = copy.deepcopy(capability)
    mutated["nonce_digest"] = "4" * 64
    new_digest = compute_semantic_digest(mutated)
    checks.append({
        "check_id": "SENSITIVITY_NONCE",
        "semantic_dimension": "nonce_digest",
        "before_digest": base_digest,
        "after_digest": new_digest,
        "pass": base_digest != new_digest,
    })

    # 9. Revocation policy change
    mutated = copy.deepcopy(capability)
    mutated["revocation_policy_digest"] = "5" * 64
    new_digest = compute_semantic_digest(mutated)
    checks.append({
        "check_id": "SENSITIVITY_REVOCATION",
        "semantic_dimension": "revocation_policy_digest",
        "before_digest": base_digest,
        "after_digest": new_digest,
        "pass": base_digest != new_digest,
    })

    # 10. Nontransferability change
    mutated = copy.deepcopy(capability)
    mutated["nontransferable"] = False
    new_digest = compute_semantic_digest(mutated)
    checks.append({
        "check_id": "SENSITIVITY_NONTRANSFERABILITY",
        "semantic_dimension": "nontransferable",
        "before_digest": base_digest,
        "after_digest": new_digest,
        "pass": base_digest != new_digest,
    })

    return checks
