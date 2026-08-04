"""G5.2B Revocation Policy Binding.

Deterministic revocation-policy record compatible with G5.2A contract.
Every capability must bind the revocation-policy digest.
"""
from .canonical import canonical_digest


def create_revocation_policy() -> dict:
    """Create the canonical revocation policy record.

    Revocation allowed before consumption, prohibited after consumption in v1.
    G5.2B does not revoke any canonical capability.
    """
    policy_body = {
        "revocation_allowed_before_consumption": True,
        "revocation_prohibited_after_consumption": True,
        "revocation_history_preserved": True,
        "revoked_cannot_be_consumed": True,
        "revocation_does_not_activate": True,
        "schema_version": "capability-revocation-policy.v1",
    }
    policy_body["revocation_policy_digest"] = canonical_digest(policy_body)
    return policy_body


def get_revocation_policy_digest() -> str:
    """Get the canonical revocation policy digest."""
    return create_revocation_policy()["revocation_policy_digest"]


def validate_revocation_policy(policy: dict) -> bool:
    """Validate a revocation policy record."""
    required = ["schema_version", "revocation_policy_digest"]
    for field in required:
        if field not in policy:
            return False

    expected = canonical_digest({k: v for k, v in policy.items() if k != "revocation_policy_digest"})
    if expected != policy.get("revocation_policy_digest"):
        return False

    return True
