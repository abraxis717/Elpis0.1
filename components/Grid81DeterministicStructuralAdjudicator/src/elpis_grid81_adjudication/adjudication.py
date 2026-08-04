"""StructuralAdjudicationRecordV1 — adjudication record construction."""

from .canonical import canonical_digest


CLAIMS_NOT_MADE = [
    "adjudication does not authorize activation",
    "adjudication does not issue capability",
    "adjudication does not consume capability",
    "adjudication does not select a model",
    "adjudication does not dispatch runtime work",
    "adjudication does not start recursion",
    "adjudication does not load models",
    "adjudication does not load adapters",
]


def build_adjudication_record(input_envelope, dispositions, policy_result,
                               abstention_record, semantic_digest):
    """Build a StructuralAdjudicationRecordV1.

    Args:
        input_envelope: AdjudicationInputEnvelopeV1
        dispositions: list of ProposalDispositionV1
        policy_result: policy adjudication result
        abstention_record: AdjudicationAbstentionV1
        semantic_digest: semantic adjudication identity digest

    Returns:
        StructuralAdjudicationRecordV1 dict
    """
    record = {
        "schema_version": "structural-adjudication-record.v1",
        "source_gate": "G5.0B",
        "source_manifest_sha256": input_envelope["source_manifest_sha256"],
        "source_row_digest": input_envelope["source_row_digest"],
        "input_digest": input_envelope["input_digest"],
        "proposal_set_digest": input_envelope["proposal_set_digest"],
        "ordering_digest": input_envelope["ordering_digest"],
        "conflict_digests": input_envelope["conflict_digests"],
        "outcome": policy_result["outcome"],
        "proposal_dispositions": dispositions,
        "review_set_proposal_digests": sorted(policy_result["review_set"]),
        "reason_codes": policy_result["reason_codes"],
        "abstention_digest": abstention_record["abstention_digest"],
        "adjudication_semantic_digest": semantic_digest,
        "claims_not_made": CLAIMS_NOT_MADE,
    }

    # Compute record digest
    record_digest = canonical_digest(record)
    record["adjudication_record_digest"] = record_digest

    return record


def verify_adjudication_record(record, input_envelope, policy_result, abstention_record, semantic_digest):
    """Verify adjudication record consistency."""
    errors = []

    # Check bindings
    if record["input_digest"] != input_envelope["input_digest"]:
        errors.append("input_digest mismatch")

    if record["proposal_set_digest"] != input_envelope["proposal_set_digest"]:
        errors.append("proposal_set_digest mismatch")

    if record["ordering_digest"] != input_envelope["ordering_digest"]:
        errors.append("ordering_digest mismatch")

    if record["abstention_digest"] != abstention_record["abstention_digest"]:
        errors.append("abstention_digest mismatch")

    if record["adjudication_semantic_digest"] != semantic_digest:
        errors.append("adjudication_semantic_digest mismatch")

    if record["outcome"] != policy_result["outcome"]:
        errors.append("outcome mismatch")

    # Verify record digest
    r_copy = {k: v for k, v in record.items() if k != "adjudication_record_digest"}
    expected = canonical_digest(r_copy)
    if record["adjudication_record_digest"] != expected:
        errors.append("adjudication_record_digest mismatch")

    return len(errors) == 0, errors
