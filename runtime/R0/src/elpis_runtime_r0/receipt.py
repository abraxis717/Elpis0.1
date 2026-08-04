"""R0 receipt utilities — serialization, verification, comparison."""

from __future__ import annotations

import hashlib
import json

from .contracts import R0TransactionReceipt, _canonical_bytes, _sha256_hex


def verify_receipt_self_hash(receipt: R0TransactionReceipt) -> bool:
    """Verify that the receipt's self-hash matches a recomputation."""
    payload = {
        "schema": receipt.schema,
        "transaction_id": receipt.transaction_id,
        "request_digest": receipt.request_digest,
        "logical_tick": receipt.logical_tick,
        "p0_projection_digest": receipt.p0_projection_digest,
        "grid81_generation_number": receipt.grid81_generation_number,
        "grid81_canonical_state_digest": receipt.grid81_canonical_state_digest,
        "scope_decision_digest": receipt.scope_decision_digest,
        "structural_oracle_input_digest": receipt.structural_oracle_input_digest,
        "structural_oracle_output_digest": receipt.structural_oracle_output_digest,
        "adjudication_digest": receipt.adjudication_digest,
        "adjudication_verdict": receipt.adjudication_verdict,
        "darwinian_episode_digest": receipt.darwinian_episode_digest,
        "darwinian_verdict": receipt.darwinian_verdict,
        "decoder_control_plan_digest": receipt.decoder_control_plan_digest,
        "decoded_artifact_digest": receipt.decoded_artifact_digest,
        "ast_validation_result": receipt.ast_validation_result,
        "component_manifest_digests": receipt.component_manifest_digests,
        "dependency_resolution_audit": receipt.dependency_resolution_audit,
        "termination_disposition": receipt.termination_disposition,
        "runtime_admission": receipt.runtime_admission,
    }
    expected = _sha256_hex(_canonical_bytes(payload))
    return receipt.receipt_self_hash == expected


def receipts_identical(a: R0TransactionReceipt, b: R0TransactionReceipt) -> bool:
    """Check byte-identical receipts."""
    return a.receipt_bytes() == b.receipt_bytes()


def receipts_identical_from_json(json_a: str, json_b: str) -> bool:
    """Check byte-identical receipts from JSON strings."""
    return json_a.encode("utf-8") == json_b.encode("utf-8")


def receipt_bytes_hash(receipt: R0TransactionReceipt) -> str:
    """SHA-256 of the canonical JSON bytes (what determinism verifies)."""
    return hashlib.sha256(receipt.receipt_bytes()).hexdigest()


def receipt_from_json(json_str: str) -> R0TransactionReceipt:
    """Deserialize a receipt from canonical JSON."""
    data = json.loads(json_str)
    return R0TransactionReceipt(**data)
