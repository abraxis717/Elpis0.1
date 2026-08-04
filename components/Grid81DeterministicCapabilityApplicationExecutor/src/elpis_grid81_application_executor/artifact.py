"""G5.3C Application receipt construction and validation.

Produces ApplicationReceiptV1 for accepted or rejected applications.
"""
from .canonical import canonical_digest


def create_application_receipt(
    artifact_digest: str,
    capability_digest: str,
    application_outcome: str,
    previous_state_digest: str,
    resulting_state_digest: str,
    previous_ledger_head: str,
    resulting_ledger_head: str,
    consumer_class: str,
) -> dict:
    """Create an ApplicationReceiptV1."""
    receipt = {
        "schema_version": "application-receipt.v1",
        "artifact_digest": artifact_digest,
        "capability_digest": capability_digest,
        "application_outcome": application_outcome,
        "previous_state_digest": previous_state_digest,
        "resulting_state_digest": resulting_state_digest,
        "previous_ledger_head": previous_ledger_head,
        "resulting_ledger_head": resulting_ledger_head,
        "consumer_class": consumer_class,
        "timestamp": "deterministic",
        "receipt_digest": "",
    }

    # Compute self-digest (excluding receipt_digest field)
    digest_payload = {k: v for k, v in receipt.items() if k != "receipt_digest"}
    receipt["receipt_digest"] = canonical_digest(digest_payload)

    return receipt


def validate_receipt(receipt: dict) -> tuple[bool, list[str]]:
    """Validate application receipt structure and digest integrity."""
    issues = []

    if receipt.get("schema_version") != "application-receipt.v1":
        issues.append("invalid_schema_version")

    if not receipt.get("receipt_digest"):
        issues.append("missing_receipt_digest")
    else:
        # Verify self-digest
        digest_fields = {k: v for k, v in receipt.items() if k != "receipt_digest"}
        expected = canonical_digest(digest_fields)
        if receipt["receipt_digest"] != expected:
            issues.append("receipt_digest_mismatch")

    required_fields = [
        "artifact_digest", "capability_digest", "application_outcome",
        "previous_state_digest", "resulting_state_digest",
        "previous_ledger_head", "resulting_ledger_head",
        "consumer_class",
    ]
    for field in required_fields:
        if not receipt.get(field):
            issues.append(f"missing_field:{field}")

    return len(issues) == 0, issues
