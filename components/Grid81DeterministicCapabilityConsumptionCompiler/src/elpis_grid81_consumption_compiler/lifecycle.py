"""G5.3B Lifecycle transition record construction.

Creates LifecycleTransitionRecordV1 for capability consumption transactions.
"""
from .canonical import canonical_digest


def create_lifecycle_transition(previous_lifecycle_state: str,
                                 resulting_lifecycle_state: str,
                                 previous_consumption_count: int,
                                 resulting_consumption_count: int) -> dict:
    """Create a LifecycleTransitionRecordV1."""
    record = {
        "schema_version": "lifecycle-transition-record.v1",
        "previous_lifecycle_state": previous_lifecycle_state,
        "resulting_lifecycle_state": resulting_lifecycle_state,
        "previous_consumption_count": previous_consumption_count,
        "resulting_consumption_count": resulting_consumption_count,
        "transition_digest": "",
    }

    # Compute transition digest
    digest_fields = {k: v for k, v in record.items() if k != "transition_digest"}
    record["transition_digest"] = canonical_digest(digest_fields)

    return record


def create_lifecycle_entry(capability_digest: str, nonce_digest: str,
                           valid_from: int = 0, valid_through: int = 0) -> dict:
    """Create an isolated fixture lifecycle entry (not canonical)."""
    entry = {
        "capability_digest": capability_digest,
        "current_state": "GRANTED_UNCONSUMED",
        "initial_lifecycle_state": "GRANTED_UNCONSUMED",
        "consumption_count": 0,
        "revocation_state": "NOT_REVOKED",
        "nonce_digest": nonce_digest,
        "logical_interval": {
            "valid_from_logical_tick": valid_from,
            "valid_through_logical_tick": valid_through,
        },
        "max_consumptions": 1,
        "schema_version": "capability-lifecycle.v1",
        "fixture_domain": True,
        "lifecycle_record_digest": "",
    }
    digest_fields = {k: v for k, v in entry.items() if k != "lifecycle_record_digest"}
    entry["lifecycle_record_digest"] = canonical_digest(digest_fields)
    return entry


def transition_lifecycle(lifecycle: dict, to_state: str, to_count: int) -> dict:
    """Transition a fixture lifecycle entry (pure — returns new dict)."""
    import copy
    new = copy.deepcopy(lifecycle)
    new["current_state"] = to_state
    new["consumption_count"] = to_count
    return new
