"""AdjudicationAbstentionV1 — abstention record construction."""

from .canonical import canonical_digest


def build_abstention_record(policy_result):
    """Build an AdjudicationAbstentionV1 record from policy result.

    Returns:
        AdjudicationAbstentionV1 dict
    """
    abst = policy_result["abstention"]

    record = {
        "schema_version": "adjudication-abstention.v1",
        "abstained": abst["abstained"],
        "abstention_kind": abst["abstention_kind"],
        "implicated_proposal_digests": abst["implicated_proposal_digests"],
        "reason_codes": abst["reason_codes"],
    }

    # Compute digest
    abstention_digest = canonical_digest(record)
    record["abstention_digest"] = abstention_digest

    return record


def verify_abstention(abstention, policy_result):
    """Verify abstention record matches policy result."""
    errors = []

    expected = policy_result["abstention"]

    if abstention["abstained"] != expected["abstained"]:
        errors.append(f"abstained mismatch: {abstention['abstained']} != {expected['abstained']}")

    if abstention["abstention_kind"] != expected["abstention_kind"]:
        errors.append(f"abstention_kind mismatch: {abstention['abstention_kind']} != {expected['abstention_kind']}")

    if sorted(abstention["implicated_proposal_digests"]) != sorted(expected["implicated_proposal_digests"]):
        errors.append("implicated_proposal_digests mismatch")

    # Verify digest
    ab_copy = {k: v for k, v in abstention.items() if k != "abstention_digest"}
    expected_digest = canonical_digest(ab_copy)
    if abstention["abstention_digest"] != expected_digest:
        errors.append(f"abstention_digest mismatch")

    return len(errors) == 0, errors
