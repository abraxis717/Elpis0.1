"""G5.2B Canonical authority policy.

Conforms exactly to CapabilityAuthorityPolicyV1 from G5.2A schema.
"""
from .canonical import canonical_digest, sha256_bytes, canonical_json_bytes


# Reason taxonomy from G5.2A
REASON_CODES = [
    "ACTIVATION_AUTHORITY_FORBIDDEN",
    "ADAPTER_SELECTION_FORBIDDEN",
    "ADJUDICATION_BINDING_INVALID",
    "AUTHORITY_CONTEXT_VALID",
    "AUTHORITY_EVIDENCE_CONTRADICTION",
    "AUTHORITY_EVIDENCE_INSUFFICIENT",
    "AUTHORITY_POLICY_BOUND",
    "AUTHORITY_POLICY_CONFLICT",
    "AUTHORITY_POLICY_NOT_SATISFIED",
    "CAPABILITY_CLASS_SUPPORTED",
    "CAPABILITY_CLASS_UNSUPPORTED",
    "CAPABILITY_SCOPE_EXPLICIT",
    "CAPABILITY_SCOPE_INVALID",
    "CAPABILITY_SCOPE_MINIMAL",
    "CAPABILITY_SCOPE_TOO_BROAD",
    "CAPABILITY_TOKEN_FORBIDDEN",
    "CONSUMER_CONTRACT_BOUND",
    "CONSUMER_CONTRACT_UNBOUND",
    "CONSUMPTION_SCOPE_VIOLATION",
    "CONTINUOUS_SCORING_FORBIDDEN",
    "EXECUTION_FIELD_FORBIDDEN",
    "GRANT_REQUIREMENTS_SATISFIED",
    "LOGICAL_VALIDITY_BOUND",
    "LOGICAL_VALIDITY_INVALID",
    "MODEL_SELECTION_FORBIDDEN",
    "NONTRANSFERABILITY_BOUND",
    "NONTRANSFERABILITY_VIOLATION",
    "NO_CAPABILITY_GRANTED",
    "PROPOSAL_SET_BINDING_INVALID",
    "REJECT_INVALID_REQUEST",
    "REPLAY_CONSUMPTION_VIOLATION",
    "REPLAY_PROTECTION_BOUND",
    "REPLAY_PROTECTION_INVALID",
    "REPLAY_PROTECTION_MISSING",
    "REQUEST_BINDING_VERIFIED",
    "REQUEST_DIGEST_INVALID",
    "REQUEST_SET_COMPLETE",
    "REQUEST_SET_EMPTY",
    "REQUEST_SET_INCOMPLETE",
    "REQUEST_STATE_NOT_REVIEW_REQUESTED",
    "REQUEST_STATE_REVIEW_REQUESTED",
    "REVOCATION_POLICY_BOUND",
    "REVOCATION_POLICY_MISSING",
    "REVOKED_CAPABILITY_CONSUMPTION_VIOLATION",
    "RUNTIME_TARGET_FORBIDDEN",
    "SINGLE_USE_ENFORCED",
    "SINGLE_USE_VIOLATION",
    "UPSTREAM_BINDING_VERIFIED",
]

DECISION_OUTCOMES = [
    "GRANT_CAPABILITY",
    "DENY_CAPABILITY",
    "DEFER_AUTHORITY_EVALUATION",
    "ABSTAIN_AUTHORITY_CONFLICT",
    "REJECT_INVALID_REQUEST",
]


def create_canonical_policy() -> dict:
    """Create the canonical authority policy conforming to CapabilityAuthorityPolicyV1."""
    # Compute reason taxonomy digest
    reason_taxonomy = {
        "closed": True,
        "count": len(REASON_CODES),
        "reason_codes": sorted(REASON_CODES),
        "schema_version": "g52a-reason-taxonomy.v1",
        "sorted": True,
        "title": "G5.2A Reason Taxonomy",
        "unique": True,
    }
    reason_taxonomy_digest = canonical_digest(reason_taxonomy)

    # Build policy without self-referential digest
    policy_body = {
        "authority_decision_outcomes": sorted(DECISION_OUTCOMES),
        "logical_validity_required": True,
        "nontransferability_required": True,
        "revocation_policy_required": True,
        "schema_version": "capability-authority-policy.v1",
        "single_use_required": True,
        "supported_capability_classes": ["STRUCTURAL_INFLUENCE_CAPABILITY_V1"],
        "supported_consumer_classes": ["STRUCTURAL_INFLUENCE_COMPILER_V1"],
        "supported_operation_classes": ["PRODUCE_BOUNDED_STRUCTURAL_INFLUENCE_V1"],
    }
    policy_digest = canonical_digest(policy_body)
    policy_body["reason_taxonomy_digest"] = reason_taxonomy_digest
    policy_body["policy_digest"] = policy_digest

    return policy_body


def get_grant_reasons() -> list:
    """Return the required grant reason codes, sorted."""
    return sorted([
        "UPSTREAM_BINDING_VERIFIED",
        "REQUEST_BINDING_VERIFIED",
        "REQUEST_STATE_REVIEW_REQUESTED",
        "REQUEST_SET_NONEMPTY",
        "REQUEST_SET_COMPLETE",
        "AUTHORITY_POLICY_BOUND",
        "AUTHORITY_CONTEXT_VALID",
        "CAPABILITY_SCOPE_EXPLICIT",
        "CAPABILITY_SCOPE_MINIMAL",
        "CAPABILITY_CLASS_SUPPORTED",
        "CONSUMER_CONTRACT_BOUND",
        "SINGLE_USE_ENFORCED",
        "REPLAY_PROTECTION_BOUND",
        "LOGICAL_VALIDITY_BOUND",
        "REVOCATION_POLICY_BOUND",
        "NONTRANSFERABILITY_BOUND",
        "GRANT_REQUIREMENTS_SATISFIED",
    ])
