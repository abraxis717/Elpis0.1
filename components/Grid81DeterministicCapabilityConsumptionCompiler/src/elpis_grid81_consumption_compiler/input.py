"""G5.3B Transaction input construction.

Creates CapabilityConsumptionTransactionInputV1 records from capability
and lifecycle data.
"""
from .canonical import canonical_digest


def create_transaction_input(capability: dict, lifecycle: dict,
                             consumer_class: str, consumer_contract_digest: str,
                             requested_operation_class: str,
                             logical_tick: int, consumption_ordinal: int,
                             consumption_policy_digest: str,
                             claims_not_made: list) -> dict:
    """Create a CapabilityConsumptionTransactionInputV1.

    All fields populated from the capability and lifecycle records.
    """
    sorted_proposals = sorted(capability.get("authorized_proposal_digests", []))

    input_record = {
        "schema_version": "capability-consumption-transaction-input.v1",
        "capability_digest": capability["capability_digest"],
        "capability_semantic_digest": capability["capability_semantic_digest"],
        "nonce_digest": capability["nonce_digest"],
        "current_lifecycle_state": lifecycle.get("current_state",
                                                  lifecycle.get("initial_lifecycle_state",
                                                                "GRANTED_UNCONSUMED")),
        "current_consumption_count": lifecycle.get("consumption_count", 0),
        "revocation_state": lifecycle.get("revocation_state", "NOT_REVOKED"),
        "consumer_class": consumer_class,
        "consumer_contract_digest": consumer_contract_digest,
        "requested_operation_class": requested_operation_class,
        "requested_proposal_digests": sorted_proposals,
        "logical_tick": logical_tick,
        "consumption_ordinal": consumption_ordinal,
        "consumption_request_digest": "",
        "consumption_policy_digest": consumption_policy_digest,
        "transaction_input_digest": "",
        "claims_not_made": sorted(claims_not_made),
    }

    # Compute consumption_request_digest from key request fields
    request_payload = {
        "capability_digest": input_record["capability_digest"],
        "consumer_class": input_record["consumer_class"],
        "consumer_contract_digest": input_record["consumer_contract_digest"],
        "logical_tick": input_record["logical_tick"],
        "nonce_digest": input_record["nonce_digest"],
        "requested_operation_class": input_record["requested_operation_class"],
        "requested_proposal_digests": input_record["requested_proposal_digests"],
    }
    input_record["consumption_request_digest"] = canonical_digest(request_payload)

    # Compute transaction_input_digest from the full record (without its own digest)
    input_for_digest = {k: v for k, v in input_record.items()
                        if k not in ("transaction_input_digest",)}
    input_record["transaction_input_digest"] = canonical_digest(input_for_digest)

    return input_record
