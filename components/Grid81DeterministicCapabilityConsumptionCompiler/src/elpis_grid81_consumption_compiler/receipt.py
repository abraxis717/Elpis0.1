"""G5.3B Receipt and rejection record construction.

Produces CapabilityConsumptionReceiptV1 and ConsumptionRejectionRecordV1.
"""
from .canonical import canonical_digest


def create_consumption_receipt(capability: dict, request: dict,
                                artifact: dict | None, outcome: str,
                                previous_state: str, resulting_state: str) -> dict:
    """Create a CapabilityConsumptionReceiptV1.

    On acceptance: includes artifact digest and proposal digests.
    On rejection: no artifact digest, preserved lifecycle state.
    """
    authorized_proposals = sorted(capability.get("authorized_proposal_digests", []))

    claims = sorted([
        "receipt does not authorize activation",
        "receipt does not enforce structural influence",
        "receipt does not dispatch runtime work",
    ])

    receipt = {
        "schema_version": "capability-consumption-receipt.v1",
        "capability_digest": capability["capability_digest"],
        "consumption_request_digest": request["consumption_request_digest"],
        "consumption_outcome": outcome,
        "consumer_contract_digest": request["consumer_contract_digest"],
        "authorized_proposal_digests": authorized_proposals if artifact else [],
        "consumption_ordinal": request.get("consumption_ordinal", 1),
        "logical_tick": request["logical_tick"],
        "previous_lifecycle_state": previous_state,
        "resulting_lifecycle_state": resulting_state,
        "produced_influence_artifact_digest": artifact.get("artifact_digest", "") if artifact else None,
        "receipt_digest": "",
        "claims_not_made": claims,
    }

    # Compute receipt digest (excluding receipt_digest itself)
    digest_fields = {k: v for k, v in receipt.items() if k != "receipt_digest"}
    receipt["receipt_digest"] = canonical_digest(digest_fields)

    return receipt


def create_rejection_record(capability_digest: str, consumption_request_digest: str,
                             rejection_outcome: str, failure_details: str) -> dict:
    """Create a ConsumptionRejectionRecordV1."""
    record = {
        "schema_version": "consumption-rejection-record.v1",
        "capability_digest": capability_digest,
        "consumption_request_digest": consumption_request_digest,
        "rejection_outcome": rejection_outcome,
        "failure_details": failure_details,
        "rejection_digest": "",
    }

    # Compute rejection digest
    digest_fields = {k: v for k, v in record.items() if k != "rejection_digest"}
    record["rejection_digest"] = canonical_digest(digest_fields)

    return record
