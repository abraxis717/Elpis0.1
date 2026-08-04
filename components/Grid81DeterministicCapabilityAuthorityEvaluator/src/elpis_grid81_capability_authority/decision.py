"""G5.2B Authority Decision.

Produces CapabilityAuthorityDecisionV1 records via explicit predicate evaluation.
"""
from .canonical import canonical_digest, check_hex64


def create_decision(outcome: str, evaluation_input_digest: str,
                   reason_codes: list, abstention_digest: str,
                   capability_digest: str = None,
                   denial_or_deferral_digest: str = None,
                   claims_not_made: list = None) -> dict:
    """Create an authority decision record."""
    if claims_not_made is None:
        claims_not_made = []

    decision_body = {
        "abstention_digest": abstention_digest,
        "capability_digest": capability_digest,
        "claims_not_made": claims_not_made,
        "decision_outcome": outcome,
        "denial_or_deferral_record_digest": denial_or_deferral_digest,
        "evaluation_input_digest": evaluation_input_digest,
        "reason_codes": sorted(set(reason_codes)),
        "schema_version": "capability-authority-decision.v1",
    }

    # Compute semantic digest (excludes decision-level identity)
    decision_body["authority_semantic_digest"] = canonical_digest({
        k: v for k, v in decision_body.items()
        if k not in ("authority_semantic_digest", "authority_decision_digest")
    })

    # Compute decision record digest
    decision_body["authority_decision_digest"] = canonical_digest(decision_body)

    return decision_body


def create_denial_deferral_record(outcome: str, reason_codes: list,
                                  evaluation_input_digest: str) -> dict:
    """Create a denial or deferral detail record."""
    record = {
        "decision_outcome": outcome,
        "evaluation_input_digest": evaluation_input_digest,
        "reason_codes": sorted(set(reason_codes)),
        "schema_version": "authority-denial-deferral.v1",
    }
    record["denial_or_deferral_digest"] = canonical_digest(record)
    return record


def evaluate_authority(evaluation_input: dict, authority_context: dict,
                       policy: dict) -> dict:
    """
    Evaluate authority using deterministic precedence:
    1. Input/schema validation
    2. Source-binding validation
    3. Authority-context validation
    4. Policy conflict / evidence contradiction
    5. Evidence sufficiency
    6. Definitive policy denial
    7. Capability grant
    """
    from .policy import get_grant_reasons

    # Step 1: Input validation
    if not validate_evaluation_input(evaluation_input):
        return create_decision(
            "REJECT_INVALID_REQUEST",
            evaluation_input.get("evaluation_input_digest", ""),
            ["REQUEST_DIGEST_INVALID"],
            "",
        )

    # Step 2: Source binding validation
    source_request_digest = evaluation_input.get("source_request_digest", "")
    if not check_hex64(source_request_digest):
        return create_decision(
            "REJECT_INVALID_REQUEST",
            evaluation_input.get("evaluation_input_digest", ""),
            ["REQUEST_DIGEST_INVALID"],
            "",
        )

    if not evaluation_input.get("referred_proposal_digests"):
        return create_decision(
            "REJECT_INVALID_REQUEST",
            evaluation_input.get("evaluation_input_digest", ""),
            ["REQUEST_SET_EMPTY", "REQUEST_SET_INCOMPLETE"],
            "",
        )

    # Step 3: Authority context validation
    if not validate_authority_context(authority_context):
        return create_decision(
            "DEFER_AUTHORITY_EVALUATION",
            evaluation_input.get("evaluation_input_digest", ""),
            ["AUTHORITY_EVIDENCE_INSUFFICIENT"],
            "",
        )

    # Step 4: Policy conflict check
    if not is_policy_valid(policy):
        return create_decision(
            "ABSTAIN_AUTHORITY_CONFLICT",
            evaluation_input.get("evaluation_input_digest", ""),
            ["AUTHORITY_POLICY_CONFLICT"],
            "",
        )

    # Step 5: Evidence sufficiency
    capability_class = evaluation_input.get("requested_capability_class", "")
    if capability_class not in policy.get("supported_capability_classes", []):
        return create_decision(
            "DENY_CAPABILITY",
            evaluation_input.get("evaluation_input_digest", ""),
            ["CAPABILITY_CLASS_UNSUPPORTED"],
            "",
        )

    # Step 6: Definitive policy denial checks
    referred = evaluation_input.get("referred_proposal_digests", [])
    if len(referred) > authority_context.get("maximum_scope_size", 2):
        denial_record = create_denial_deferral_record(
            "DENY_CAPABILITY", ["CAPABILITY_SCOPE_TOO_BROAD"],
            evaluation_input.get("evaluation_input_digest", "")
        )
        return create_decision(
            "DENY_CAPABILITY",
            evaluation_input.get("evaluation_input_digest", ""),
            ["CAPABILITY_SCOPE_TOO_BROAD"],
            "",
            denial_or_deferral_digest=denial_record.get("denial_or_deferral_digest"),
        )

    # Step 7: Grant - all predicates pass
    grant_reasons = get_grant_reasons()
    return create_decision(
        "GRANT_CAPABILITY",
        evaluation_input.get("evaluation_input_digest", ""),
        grant_reasons,
        "",  # abstention digest (filled later)
        capability_digest="",  # filled later
        claims_not_made=get_grant_claims_not_made(),
    )


def validate_evaluation_input(input_record: dict) -> bool:
    """Validate evaluation input structure."""
    required = ["evaluation_input_digest", "source_request_digest",
                "referred_proposal_digests", "requested_capability_class"]
    for field in required:
        if field not in input_record:
            return False
    return True


def validate_authority_context(context: dict) -> bool:
    """Validate authority context is present and has required fields."""
    if not context:
        return False
    required = ["authority_domain", "evaluation_logical_tick",
                "authority_context_digest"]
    for field in required:
        if field not in context:
            return False
    return True


def is_policy_valid(policy: dict) -> bool:
    """Check if policy has required structure."""
    if not policy:
        return False
    return ("supported_capability_classes" in policy and
            "single_use_required" in policy and
            "policy_digest" in policy)


def get_grant_claims_not_made() -> list:
    """Return the claims-not-made for granted capabilities."""
    return sorted([
        "capability does not authorize activation",
        "capability does not consume capability",
        "capability does not dispatch runtime work",
        "capability does not load a model",
        "capability does not load an adapter",
        "capability does not mutate ECS state",
        "capability does not produce structural influence",
        "capability does not select a model",
        "capability does not select an adapter",
    ])
