"""G5.2B Capability Authority Evaluation Input.

Constructs CapabilityAuthorityEvaluationInputV1 records from G5.1B source data.
"""
from .canonical import canonical_digest, check_hex64


def create_evaluation_input(source_request: dict, policy_digest: str,
                           context_digest: str, manifest_sha256: str) -> dict:
    """Create an evaluation input record from a source G5.1B request."""
    input_body = {
        "authority_context_digest": context_digest,
        "authority_policy_digest": policy_digest,
        "requested_capability_class": source_request.get("required_capability_class", "STRUCTURAL_INFLUENCE_CAPABILITY_V1"),
        "referred_proposal_digests": sorted(source_request.get("referred_proposal_digests", [])),
        "schema_version": "capability-authority-evaluation-input.v1",
        "source_adjudication_record_digest": source_request.get("adjudication_record_digest", ""),
        "source_gate": "G5.1B",
        "source_manifest_sha256": manifest_sha256,
        "source_proposal_set_digest": source_request.get("proposal_set_digest", ""),
        "source_request_digest": source_request.get("request_digest", ""),
    }
    input_body["evaluation_input_digest"] = canonical_digest(input_body)
    return input_body


def validate_evaluation_input(evaluation_input: dict) -> bool:
    """Validate an evaluation input record."""
    required_fields = [
        "schema_version", "source_gate", "source_manifest_sha256",
        "source_request_digest", "source_adjudication_record_digest",
        "source_proposal_set_digest", "requested_capability_class",
        "referred_proposal_digests", "authority_policy_digest",
        "authority_context_digest", "evaluation_input_digest",
    ]
    for field in required_fields:
        if field not in evaluation_input:
            return False

    # Verify digest
    expected = canonical_digest({
        k: v for k, v in evaluation_input.items() if k != "evaluation_input_digest"
    })
    if expected != evaluation_input.get("evaluation_input_digest"):
        return False

    return True
