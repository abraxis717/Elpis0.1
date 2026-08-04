"""G5.2B Capability Lifecycle Index.

Lifecycle records track the state of each capability.
Canonical state: GRANTED_UNCONSUMED, consumption_count=0, NOT_REVOKED.
"""
from .canonical import canonical_digest


LIFECYCLE_STATES = [
    "GRANTED_UNCONSUMED",
    "CONSUMED",
    "REVOKED",
    "EXPIRED",
]


def create_lifecycle_entry(capability_digest: str, nonce_digest: str,
                          max_consumptions: int = 1,
                          valid_from: int = 0, valid_through: int = 0) -> dict:
    """Create a lifecycle index entry for a capability."""
    entry = {
        "capability_digest": capability_digest,
        "consumption_count": 0,
        "initial_lifecycle_state": "GRANTED_UNCONSUMED",
        "logical_interval": {
            "valid_from_logical_tick": valid_from,
            "valid_through_logical_tick": valid_through,
        },
        "max_consumptions": max_consumptions,
        "nonce_digest": nonce_digest,
        "revocation_state": "NOT_REVOKED",
        "schema_version": "capability-lifecycle.v1",
    }
    entry["lifecycle_record_digest"] = canonical_digest(entry)
    return entry


def validate_lifecycle_entry(entry: dict) -> bool:
    """Validate a lifecycle entry."""
    required = ["capability_digest", "nonce_digest", "initial_lifecycle_state",
                "max_consumptions", "consumption_count", "revocation_state",
                "logical_interval", "lifecycle_record_digest"]
    for field in required:
        if field not in entry:
            return False

    if entry.get("initial_lifecycle_state") not in LIFECYCLE_STATES:
        return False
    if entry.get("consumption_count") != 0:
        return False

    return True
