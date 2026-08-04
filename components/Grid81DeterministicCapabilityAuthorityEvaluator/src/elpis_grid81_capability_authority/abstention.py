"""G5.2B Capability Abstention.

CapabilityAbstentionV1 — explicit authority abstention record.
Null or omitted abstention is forbidden.
"""
from .canonical import canonical_digest


def create_abstention(abstained: bool, abstention_kind: str,
                     implicated_request_digests: list = None,
                     reason_codes: list = None) -> dict:
    """Create an explicit capability abstention record."""
    if implicated_request_digests is None:
        implicated_request_digests = []
    if reason_codes is None:
        reason_codes = []

    abstention_body = {
        "abstained": abstained,
        "abstention_kind": abstention_kind,
        "implicated_request_digests": implicated_request_digests,
        "reason_codes": sorted(set(reason_codes)),
        "schema_version": "capability-abstention.v1",
    }
    abstention_body["abstention_digest"] = canonical_digest(abstention_body)
    return abstention_body


def create_grant_abstention() -> dict:
    """Create the standard abstention record for a canonical grant.

    abstained=false, kind=NONE, empty implicated list, empty reasons.
    """
    return create_abstention(
        abstained=False,
        abstention_kind="NONE",
        implicated_request_digests=[],
        reason_codes=[],
    )


def validate_abstention(abstention: dict) -> bool:
    """Validate an abstention record."""
    required = ["schema_version", "abstained", "abstention_kind",
                "implicated_request_digests", "reason_codes", "abstention_digest"]
    for field in required:
        if field not in abstention:
            return False

    valid_kinds = ["NONE", "AUTHORITY_POLICY_CONFLICT",
                   "AUTHORITY_EVIDENCE_CONTRADICTION", "INVALID_AUTHORITY_CONTEXT"]
    if abstention.get("abstention_kind") not in valid_kinds:
        return False

    # Verify digest
    expected = canonical_digest({k: v for k, v in abstention.items() if k != "abstention_digest"})
    if expected != abstention.get("abstention_digest"):
        return False

    return True
