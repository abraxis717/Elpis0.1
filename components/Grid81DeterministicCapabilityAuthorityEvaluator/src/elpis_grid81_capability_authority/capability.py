"""G5.2B Structural Influence Capability.

StructuralInfluenceCapabilityV1 — bounded structural-influence capability.
Single-use, non-transferable.
"""
from .canonical import canonical_digest, check_hex64
from .scope import create_capability_scope
from .limits import create_capability_limit
from .nonce import compute_nonce_digest
from .revocation_policy import get_revocation_policy_digest


def create_capability(source_request_digest: str,
                      source_adjudication_record_digest: str,
                      source_proposal_set_digest: str,
                      authorized_proposal_digests: list,
                      authority_policy_digest: str,
                      authority_context: dict) -> dict:
    """Create a StructuralInfluenceCapabilityV1 record.

    All required fields per G5.2A schema are populated.
    """
    # Compute sub-records
    scope = create_capability_scope(authorized_proposal_digests)
    limits = create_capability_limit(valid_from=0, valid_through=0)
    nonce = compute_nonce_digest(
        source_request_digest,
        authority_policy_digest,
        authority_context.get("authority_context_digest", ""),
    )
    revocation_digest = get_revocation_policy_digest()

    sorted_proposals = sorted(set(authorized_proposal_digests))

    capability_body = {
        "authority_policy_digest": authority_policy_digest,
        "authorized_consumer_class": "STRUCTURAL_INFLUENCE_COMPILER_V1",
        "authorized_operation_class": "PRODUCE_BOUNDED_STRUCTURAL_INFLUENCE_V1",
        "authorized_proposal_digests": sorted_proposals,
        "capability_class": "STRUCTURAL_INFLUENCE_CAPABILITY_V1",
        "claims_not_made": sorted([
            "capability does not authorize activation",
            "capability does not consume capability",
            "capability does not dispatch runtime work",
            "capability does not load a model",
            "capability does not load an adapter",
            "capability does not mutate ECS state",
            "capability does not produce structural influence",
            "capability does not select a model",
            "capability does not select an adapter",
        ]),
        "max_consumptions": 1,
        "nonce_digest": nonce,
        "nontransferable": True,
        "revocation_policy_digest": revocation_digest,
        "schema_version": "structural-influence-capability.v1",
        "source_adjudication_record_digest": source_adjudication_record_digest,
        "source_proposal_set_digest": source_proposal_set_digest,
        "source_request_digest": source_request_digest,
        "valid_from_logical_tick": 0,
        "valid_through_logical_tick": 0,
        "capability_scope_digest": scope["scope_digest"],
        "capability_limit_digest": limits["limit_digest"],
    }

    # Compute semantic digest
    semantic_payload = {
        "authorized_consumer_class": capability_body["authorized_consumer_class"],
        "authorized_operation_class": capability_body["authorized_operation_class"],
        "authorized_proposal_digests": capability_body["authorized_proposal_digests"],
        "authority_policy_digest": capability_body["authority_policy_digest"],
        "capability_class": capability_body["capability_class"],
        "capability_limit_digest": capability_body["capability_limit_digest"],
        "capability_scope_digest": capability_body["capability_scope_digest"],
        "logical_validity": {
            "valid_from_logical_tick": capability_body["valid_from_logical_tick"],
            "valid_through_logical_tick": capability_body["valid_through_logical_tick"],
        },
        "nonce_digest": capability_body["nonce_digest"],
        "nontransferable": capability_body["nontransferable"],
        "revocation_policy_digest": capability_body["revocation_policy_digest"],
        "single_use": True,
    }
    capability_body["capability_semantic_digest"] = canonical_digest(semantic_payload)

    # Compute record digest
    capability_body["capability_digest"] = canonical_digest(capability_body)

    return capability_body


def validate_capability(capability: dict) -> bool:
    """Validate a StructuralInfluenceCapabilityV1 record against G5.2A schema."""
    required_fields = [
        "schema_version", "capability_class", "source_request_digest",
        "source_adjudication_record_digest", "source_proposal_set_digest",
        "authorized_proposal_digests", "authorized_operation_class",
        "authorized_consumer_class", "authority_policy_digest",
        "capability_scope_digest", "capability_limit_digest",
        "nonce_digest", "valid_from_logical_tick", "valid_through_logical_tick",
        "max_consumptions", "revocation_policy_digest", "nontransferable",
        "capability_semantic_digest", "capability_digest", "claims_not_made",
    ]

    for field in required_fields:
        if field not in capability:
            return False

    # Check constant values
    if capability.get("capability_class") != "STRUCTURAL_INFLUENCE_CAPABILITY_V1":
        return False
    if capability.get("authorized_operation_class") != "PRODUCE_BOUNDED_STRUCTURAL_INFLUENCE_V1":
        return False
    if capability.get("authorized_consumer_class") != "STRUCTURAL_INFLUENCE_COMPILER_V1":
        return False
    if capability.get("max_consumptions") != 1:
        return False
    if capability.get("nontransferable") is not True:
        return False

    # Check hex digests
    digest_fields = [
        "source_request_digest", "source_adjudication_record_digest",
        "source_proposal_set_digest", "authority_policy_digest",
        "capability_scope_digest", "capability_limit_digest", "nonce_digest",
        "revocation_policy_digest", "capability_semantic_digest", "capability_digest",
    ]
    for field in digest_fields:
        if not check_hex64(capability.get(field, "")):
            return False

    # Check authorized proposals
    proposals = capability.get("authorized_proposal_digests", [])
    if len(proposals) == 0:
        return False
    if proposals != sorted(set(proposals)):
        return False

    # Verify no forbidden fields (additionalProperties: false)
    allowed_fields = set(required_fields + ["schema_version"])
    actual_fields = set(capability.keys())
    if not actual_fields.issubset(allowed_fields):
        return False

    return True
