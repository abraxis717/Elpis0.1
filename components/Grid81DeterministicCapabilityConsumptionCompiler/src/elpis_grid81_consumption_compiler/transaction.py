"""G5.3B Transaction execution.

Core operation: consume_capability()
Pure function — no input dict may be mutated.
Returns ConsumptionTransactionResult (dict-based).
"""
from dataclasses import dataclass
import copy

from .canonical import canonical_digest, check_hex64
from .validation import (
    validate_transaction, validate_artifact_invariants, validate_receipt,
    FORBIDDEN_FIELDS, ACCEPTED_OUTCOME, REJECTION_REPLAY,
    REJECTION_REVOKED, REJECTION_EXPIRED, REJECTION_CONSUMER_MISMATCH,
    REJECTION_SCOPE_MISMATCH, REJECTION_INVALID_CAPABILITY,
)
from .artifact import create_structural_influence_artifact
from .receipt import create_consumption_receipt, create_rejection_record
from .lifecycle import create_lifecycle_transition
from .errors import ValidationFailed


@dataclass
class ConsumptionTransactionResult:
    """Immutable result record for a capability consumption transaction."""
    transaction_outcome: str
    reason_codes: tuple
    artifact: dict | None
    receipt: dict
    previous_lifecycle_state: str
    resulting_lifecycle_state: str
    previous_consumption_count: int
    resulting_consumption_count: int
    transaction_result_digest: str


def deep_copy(obj):
    """Deep copy to ensure input immutability."""
    return copy.deepcopy(obj)


def consume_capability(*, capability: dict, lifecycle: dict,
                       request: dict, policy: dict,
                       compiler_contract: dict) -> dict:
    """Execute a capability consumption transaction.

    Returns a CapabilityConsumptionTransactionResultV1 dict.
    Pure with respect to inputs — no input is mutated.
    """
    # Deep-copy inputs to ensure immutability
    cap = deep_copy(capability)
    life = deep_copy(lifecycle)
    req = deep_copy(request)
    pol = deep_copy(policy)
    contract = deep_copy(compiler_contract)

    # Run validation chain
    outcome, reasons = validate_transaction(cap, life, req, pol, contract)

    previous_state = life.get("current_state", life.get("initial_lifecycle_state", "GRANTED_UNCONSUMED"))
    previous_count = life.get("consumption_count", 0)

    if outcome == ACCEPTED_OUTCOME:
        # Produce artifact
        artifact = create_structural_influence_artifact(
            capability=cap,
            lifecycle=life,
            request=req,
            compiler_contract=contract,
        )

        # Validate artifact
        artifact_valid, artifact_issues = validate_artifact_invariants(artifact)
        if not artifact_valid:
            return _build_rejection_result(
                cap=cap, req=req, life=life,
                outcome=REJECTION_INVALID_CAPABILITY,
                reasons=["artifact_validation_failed:" + ";".join(artifact_issues)],
            )

        # Produce receipt
        receipt = create_consumption_receipt(
            capability=cap,
            request=req,
            artifact=artifact,
            outcome=ACCEPTED_OUTCOME,
            previous_state=previous_state,
            resulting_state="CONSUMED",
        )

        # Validate receipt
        receipt_valid, receipt_issues = validate_receipt(receipt)
        if not receipt_valid:
            return _build_rejection_result(
                cap=cap, req=req, life=life,
                outcome=REJECTION_INVALID_CAPABILITY,
                reasons=["receipt_validation_failed:" + ";".join(receipt_issues)],
            )

        # Lifecycle transition
        lifecycle_record = create_lifecycle_transition(
            previous_lifecycle_state=previous_state,
            resulting_lifecycle_state="CONSUMED",
            previous_consumption_count=previous_count,
            resulting_consumption_count=previous_count + 1,
        )

        return _build_acceptance_result(
            artifact=artifact,
            receipt=receipt,
            lifecycle=lifecycle_record,
            reasons=[],
        )

    else:
        # Rejection: produce receipt-only, no artifact
        return _build_rejection_result(
            cap=cap, req=req, life=life,
            outcome=outcome, reasons=reasons,
        )


def _build_acceptance_result(artifact: dict, receipt: dict,
                              lifecycle: dict, reasons: list) -> dict:
    """Build an accepted transaction result."""
    result = {
        "schema_version": "capability-consumption-transaction-result.v1",
        "transaction_outcome": ACCEPTED_OUTCOME,
        "consumption_receipt": receipt,
        "lifecycle_transition": lifecycle,
        "structural_influence_artifact": artifact,
        "rejection_record": None,
        "reason_codes": reasons,
        "transaction_result_digest": "",
    }
    # Compute result digest
    digest_payload = {k: v for k, v in result.items()
                      if k != "transaction_result_digest"}
    result["transaction_result_digest"] = canonical_digest(digest_payload)
    return result


def _build_rejection_result(cap: dict, req: dict, life: dict,
                             outcome: str, reasons: list) -> dict:
    """Build a rejected transaction result."""
    previous_state = life.get("current_state", life.get("initial_lifecycle_state", "GRANTED_UNCONSUMED"))
    previous_count = life.get("consumption_count", 0)

    rejection_record = create_rejection_record(
        capability_digest=cap.get("capability_digest", ""),
        consumption_request_digest=req.get("consumption_request_digest", ""),
        rejection_outcome=outcome,
        failure_details=";".join(reasons),
    )

    receipt = create_consumption_receipt(
        capability=cap,
        request=req,
        artifact=None,
        outcome=outcome,
        previous_state=previous_state,
        resulting_state=previous_state,
    )

    lifecycle_record = create_lifecycle_transition(
        previous_lifecycle_state=previous_state,
        resulting_lifecycle_state=previous_state,
        previous_consumption_count=previous_count,
        resulting_consumption_count=previous_count,
    )

    result = {
        "schema_version": "capability-consumption-transaction-result.v1",
        "transaction_outcome": outcome,
        "consumption_receipt": receipt,
        "lifecycle_transition": lifecycle_record,
        "structural_influence_artifact": None,
        "rejection_record": rejection_record,
        "reason_codes": reasons,
        "transaction_result_digest": "",
    }
    digest_payload = {k: v for k, v in result.items()
                      if k != "transaction_result_digest"}
    result["transaction_result_digest"] = canonical_digest(digest_payload)
    return result
