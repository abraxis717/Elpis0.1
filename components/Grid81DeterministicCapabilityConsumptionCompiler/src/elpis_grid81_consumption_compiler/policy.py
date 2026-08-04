"""G5.3B Consumption policy and compiler contract creation.

Creates policy and compiler contract records matching G5.3A schemas.
"""
from .canonical import canonical_digest


def create_consumption_policy() -> dict:
    """Create a CapabilityConsumptionPolicyV1 record."""
    policy = {
        "schema_version": "capability-consumption-policy.v1",
        "supported_capability_classes": [
            "STRUCTURAL_INFLUENCE_CAPABILITY_V1",
        ],
        "supported_consumer_classes": [
            "STRUCTURAL_INFLUENCE_COMPILER_V1",
        ],
        "supported_operation_classes": [
            "PRODUCE_BOUNDED_STRUCTURAL_INFLUENCE_V1",
        ],
        "supported_artifact_classes": [
            "BOUNDED_STRUCTURAL_INFLUENCE_ARTIFACT_V1",
        ],
        "supported_materialization_classes": [
            "MATERIALIZE_AUTHORIZED_STRUCTURAL_INFLUENCE_SET_V1",
        ],
        "supported_target_domains": [
            "GRID81_STRUCTURAL_PROPOSAL_DOMAIN_V1",
        ],
        "single_use_required": True,
        "exact_scope_match_required": True,
        "nonce_match_required": True,
        "logical_validity_required": True,
        "unrevoked_required": True,
        "atomic_artifact_and_receipt_required": True,
        "unapplied_artifact_required": True,
        "transaction_outcomes": [
            "CONSUMPTION_ACCEPTED",
            "CONSUMPTION_REJECTED_REPLAY",
            "CONSUMPTION_REJECTED_REVOKED",
            "CONSUMPTION_REJECTED_EXPIRED",
            "CONSUMPTION_REJECTED_CONSUMER_MISMATCH",
            "CONSUMPTION_REJECTED_SCOPE_MISMATCH",
            "CONSUMPTION_REJECTED_INVALID_CAPABILITY",
        ],
    }
    # Reason taxonomy: sorted tuple of all rejection outcomes
    reason_taxonomy = sorted(policy["transaction_outcomes"])
    policy["reason_taxonomy_digest"] = canonical_digest(reason_taxonomy)
    policy["policy_digest"] = canonical_digest(policy)
    return policy


def create_compiler_contract() -> dict:
    """Create a StructuralInfluenceCompilerContractV1 record."""
    contract = {
        "schema_version": "structural-influence-compiler-contract.v1",
        "compiler_class": "STRUCTURAL_INFLUENCE_COMPILER_V1",
        "accepted_capability_classes": [
            "STRUCTURAL_INFLUENCE_CAPABILITY_V1",
        ],
        "accepted_operation_classes": [
            "PRODUCE_BOUNDED_STRUCTURAL_INFLUENCE_V1",
        ],
        "produced_artifact_classes": [
            "BOUNDED_STRUCTURAL_INFLUENCE_ARTIFACT_V1",
        ],
        "produced_materialization_classes": [
            "MATERIALIZE_AUTHORIZED_STRUCTURAL_INFLUENCE_SET_V1",
        ],
        "target_domain_classes": [
            "GRID81_STRUCTURAL_PROPOSAL_DOMAIN_V1",
        ],
        "exact_scope_preservation": True,
        "single_artifact_per_consumption": True,
        "atomic_receipt_required": True,
        "unapplied_output_required": True,
    }
    contract["compiler_contract_digest"] = canonical_digest(contract)
    return contract
