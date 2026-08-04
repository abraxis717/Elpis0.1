"""R1 receipt utilities — serialization, verification, comparison."""

from __future__ import annotations

import hashlib
import json

from .contracts import (
    R1TransactionReceipt,
    _canonical_bytes,
    _sha256_hex,
)


def verify_receipt_self_hash(receipt: R1TransactionReceipt) -> bool:
    """Verify that the R1 receipt self-hash matches recomputation."""
    payload = {
        "schema": receipt.schema,
        "transaction_id": receipt.transaction_id,
        "request_digest": receipt.request_digest,
        "retrieval_contract_version": receipt.retrieval_contract_version,
        "query_derivation_digest": receipt.query_derivation_digest,
        "retrieval_query_digest": receipt.retrieval_query_digest,
        "retrieval_budget_digest": receipt.retrieval_budget_digest,
        "corpus_identity": receipt.corpus_identity,
        "corpus_epoch": receipt.corpus_epoch,
        "vector_index_identity": receipt.vector_index_identity,
        "vector_index_epoch": receipt.vector_index_epoch,
        "retrieval_bundle_schema": receipt.retrieval_bundle_schema,
        "retrieval_bundle_digest": receipt.retrieval_bundle_digest,
        "retrieved_chunk_identities": receipt.retrieved_chunk_identities,
        "context_expansion_digest": receipt.context_expansion_digest,
        "evidence_envelope_digest": receipt.evidence_envelope_digest,
        "r0_receipt_digest": receipt.r0_receipt_digest,
        "final_artifact_digest": receipt.final_artifact_digest,
        "termination_disposition": receipt.termination_disposition,
        "component_manifest_digests": receipt.component_manifest_digests,
        "dependency_resolution_audit_digest": receipt.dependency_resolution_audit_digest,
        "runtime_admission_receipt": receipt.runtime_admission_receipt,
    }
    expected = _sha256_hex(_canonical_bytes(payload))
    return receipt.receipt_self_hash == expected


def receipts_identical(a: R1TransactionReceipt, b: R1TransactionReceipt) -> bool:
    """Check byte-identical R1 receipts."""
    return a.receipt_bytes() == b.receipt_bytes()


def receipts_identical_from_json(json_a: str, json_b: str) -> bool:
    """Check byte-identical R1 receipts from JSON strings."""
    return json_a.encode("utf-8") == json_b.encode("utf-8")


def receipt_bytes_hash(receipt: R1TransactionReceipt) -> str:
    """SHA-256 of the R1 canonical receipt bytes."""
    return hashlib.sha256(receipt.receipt_bytes()).hexdigest()


def receipt_from_json(json_str: str) -> R1TransactionReceipt:
    """Deserialize an R1 receipt from canonical JSON."""
    data = json.loads(json_str)
    return R1TransactionReceipt(**data)
