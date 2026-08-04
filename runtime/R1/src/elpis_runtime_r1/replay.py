"""R1 replay — deterministic replay of receipt from canonical JSON."""

from __future__ import annotations

import json

from .contracts import R1TransactionReceipt, _canonical_bytes, _sha256_hex
from .receipt import verify_receipt_self_hash


def replay_receipt(json_str: str) -> R1TransactionReceipt:
    """Replay an R1 receipt from canonical JSON string.

    Verifies self-hash integrity.

    Returns:
        R1TransactionReceipt with verified self-hash.

    Raises:
        ValueError: if self-hash verification fails.
    """
    data = json.loads(json_str)
    receipt = R1TransactionReceipt(**data)

    if not verify_receipt_self_hash(receipt):
        raise ValueError(
            f"R1 receipt self-hash mismatch: "
            f"stored={receipt.receipt_self_hash}, "
            f"computed={_sha256_hex(_canonical_bytes(data))}"
        )

    return receipt


def diff_receipts(
    a: R1TransactionReceipt,
    b: R1TransactionReceipt,
) -> list[str]:
    """Compare two R1 receipts and return list of differing fields."""
    fields = [
        "schema", "transaction_id", "request_digest",
        "retrieval_contract_version", "query_derivation_digest",
        "retrieval_query_digest", "retrieval_budget_digest",
        "corpus_identity", "corpus_epoch", "vector_index_identity",
        "vector_index_epoch", "retrieval_bundle_schema",
        "retrieval_bundle_digest", "retrieved_chunk_identities",
        "context_expansion_digest", "evidence_envelope_digest",
        "r0_receipt_digest", "final_artifact_digest",
        "termination_disposition", "component_manifest_digests",
        "dependency_resolution_audit_digest", "runtime_admission_receipt",
        "receipt_self_hash",
    ]
    diffs = []
    for field in fields:
        va = getattr(a, field, None)
        vb = getattr(b, field, None)
        if va != vb:
            diffs.append(f"{field}: {va!r} != {vb!r}")
    return diffs
