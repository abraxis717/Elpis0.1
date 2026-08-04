"""CapabilityReviewRequestV1 — capability review request construction.

This is an inert request. It does NOT issue, consume, or authorize capabilities.
"""

from .canonical import canonical_digest
from .policy import (
    REVIEW_REQUESTED, REVIEW_NOT_REQUESTED, REFERRED_FOR_CAPABILITY_REVIEW,
)


CLAIMS_NOT_MADE = [
    "request does not issue capability",
    "request does not consume capability",
    "request does not authorize activation",
    "request does not select a model",
    "request does not select an adapter",
    "request does not load a model",
    "request does not load an adapter",
    "request does not dispatch runtime work",
    "request does not mutate ECS state",
    "request does not start recursion",
]


def build_review_request(input_envelope, policy_result, adjudication_record_digest):
    """Build a CapabilityReviewRequestV1 record.

    Args:
        input_envelope: AdjudicationInputEnvelopeV1
        policy_result: adjudication policy result
        adjudication_record_digest: digest of the parent adjudication record

    Returns:
        CapabilityReviewRequestV1 dict
    """
    request_state = policy_result["request_state"]
    review_set = policy_result["review_set"]

    # Build non-request reason codes
    if request_state == REVIEW_NOT_REQUESTED:
        non_request_reasons = policy_result["reason_codes"]
    else:
        non_request_reasons = []

    record = {
        "schema_version": "capability-review-request.v1",
        "adjudication_record_digest": adjudication_record_digest,
        "proposal_set_digest": input_envelope["proposal_set_digest"],
        "request_state": request_state,
        "referred_proposal_digests": sorted(review_set),
        "required_capability_class": "STRUCTURAL_INFLUENCE_CAPABILITY_V1",
        "non_request_reason_codes": sorted(non_request_reasons),
        "claims_not_made": CLAIMS_NOT_MADE,
    }

    # Compute request digest
    request_digest = canonical_digest(record)
    record["request_digest"] = request_digest

    return record


def verify_review_request(request, policy_result, input_envelope):
    """Verify review request matches policy and input."""
    errors = []

    # Check request state matches policy
    if request["request_state"] != policy_result["request_state"]:
        errors.append(f"request_state mismatch: {request['request_state']} != {policy_result['request_state']}")

    # Check referred proposals match review set
    if sorted(request["referred_proposal_digests"]) != sorted(policy_result["review_set"]):
        errors.append("referred_proposal_digests != review_set")

    # Check proposal_set_digest matches input
    if request["proposal_set_digest"] != input_envelope["proposal_set_digest"]:
        errors.append("proposal_set_digest mismatch")

    # Check required_capability_class
    if request["required_capability_class"] != "STRUCTURAL_INFLUENCE_CAPABILITY_V1":
        errors.append("required_capability_class wrong")

    # Verify digest
    r_copy = {k: v for k, v in request.items() if k != "request_digest"}
    expected = canonical_digest(r_copy)
    if request["request_digest"] != expected:
        errors.append("request_digest mismatch")

    # Verify no forbidden fields
    forbidden = {"capability_token", "authority_token", "model_path", "adapter_path",
                 "device", "port", "command", "runtime", "selected", "activation"}
    for field in forbidden:
        if field in request:
            errors.append(f"Forbidden field present: {field}")

    return len(errors) == 0, errors
