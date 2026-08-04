"""G5.3B Transaction replay verification.

Replays a transaction from original inputs and verifies exact byte identity.
Replaying an already-consumed fixture returns CONSUMPTION_REJECTED_REPLAY.
"""
import json
from .canonical import canonical_json
from .transaction import consume_capability


def replay_transaction(original_result: dict, capability: dict,
                        lifecycle: dict, request: dict, policy: dict,
                        compiler_contract: dict) -> dict:
    """Replay a transaction from original inputs.

    Returns a dict with:
    - replay_match: bool — whether replayed result matches original
    - replayed_result: the new transaction result
    - original_result: the original result for comparison
    """
    replayed = consume_capability(
        capability=capability,
        lifecycle=lifecycle,
        request=request,
        policy=policy,
        compiler_contract=compiler_contract,
    )

    # Compare canonical JSON for exact byte identity
    original_canonical = canonical_json(original_result)
    replayed_canonical = canonical_json(replayed)

    return {
        "replay_match": original_canonical == replayed_canonical,
        "original_digest": original_result.get("transaction_result_digest", ""),
        "replayed_digest": replayed.get("transaction_result_digest", ""),
        "replayed_result": replayed,
    }


def replay_already_consumed(original_result: dict, capability: dict,
                             consumed_lifecycle: dict, request: dict,
                             policy: dict, compiler_contract: dict) -> dict:
    """Replay a transaction with already-consumed lifecycle.

    Must return CONSUMPTION_REJECTED_REPLAY and no artifact.
    """
    replayed = consume_capability(
        capability=capability,
        lifecycle=consumed_lifecycle,
        request=request,
        policy=policy,
        compiler_contract=compiler_contract,
    )

    return {
        "outcome": replayed["transaction_outcome"],
        "is_replay_rejection": replayed["transaction_outcome"] == "CONSUMPTION_REJECTED_REPLAY",
        "no_artifact": replayed["structural_influence_artifact"] is None,
        "replayed_result": replayed,
    }
