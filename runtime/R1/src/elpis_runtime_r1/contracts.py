"""R1 contracts — canonical types, digests, and receipt schema."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Canonical JSON helpers
# ---------------------------------------------------------------------------

def _canonical_bytes(obj: Any) -> bytes:
    """Minimal canonical JSON: sorted keys, compact separators, no NaN."""
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha256_hex(data: bytes) -> str:
    """Lowercase SHA-256 hex digest."""
    return hashlib.sha256(data).hexdigest()


def _digest(obj: Any) -> str:
    """Canonical digest of any JSON-serializable object."""
    return _sha256_hex(_canonical_bytes(obj))


# ---------------------------------------------------------------------------
# Retrieval query contract
# ---------------------------------------------------------------------------

RETRIEVAL_CONTRACT_VERSION = "elpis.retrieval_contract.v1"


@dataclass(frozen=True)
class RetrievalQuery:
    """Canonical retrieval query derived from RequestContext."""
    query_text: str
    query_digest: str
    source_request_digest: str
    selected_fields: tuple[str, ...]
    normalization_schema: str
    budget_parameters: str

    def to_canonical_dict(self) -> dict:
        return {
            "query_text": self.query_text,
            "query_digest": self.query_digest,
            "source_request_digest": self.source_request_digest,
            "selected_fields": list(self.selected_fields),
            "normalization_schema": self.normalization_schema,
            "budget_parameters": self.budget_parameters,
        }


# ---------------------------------------------------------------------------
# Retrieval bundle contract (Python mirror of HACF C struct)
# ---------------------------------------------------------------------------

RETRIEVAL_BUNDLE_SCHEMA = "elpis.retrieval_bundle.v1"


@dataclass(frozen=True)
class RetrievalItem:
    """Single item in a validated RetrievalBundle."""
    chunk_digest: str
    doc_digest: str
    namespace: str
    authority: str
    graph_parent_digest: str  # all-zero hex for primary
    text_digest: str
    fusion_score_key: int
    dense_score_key: int
    lexical_rank: int  # 1-based; 0 = absent
    dense_rank: int    # 1-based; 0 = absent
    final_rank: int    # 0-based bundle order
    source_mask: int
    item_kind: int     # 1=primary, 2=context
    graph_hop: int     # 0 or 1
    edge_type: int
    edge_authority: int
    text: str
    text_bytes: int


@dataclass(frozen=True)
class RetrievalBundle:
    """Validated retrieval bundle from HACF."""
    schema: str = RETRIEVAL_BUNDLE_SCHEMA
    query_digest: str = ""
    corpus_manifest_digest: str = ""
    vector_index_manifest_digest: str = ""
    graph_snapshot_digest: str = ""
    fusion_policy_digest: str = ""
    bundle_digest: str = ""
    hacf_package_digest: str = ""
    corpus_epoch: int = 0
    vector_index_epoch: int = 0
    items: tuple[RetrievalItem, ...] = ()

    def to_canonical_dict(self) -> dict:
        return {
            "schema": self.schema,
            "query_digest": self.query_digest,
            "corpus_manifest_digest": self.corpus_manifest_digest,
            "vector_index_manifest_digest": self.vector_index_manifest_digest,
            "graph_snapshot_digest": self.graph_snapshot_digest,
            "fusion_policy_digest": self.fusion_policy_digest,
            "bundle_digest": self.bundle_digest,
            "hacf_package_digest": self.hacf_package_digest,
            "corpus_epoch": self.corpus_epoch,
            "vector_index_epoch": self.vector_index_epoch,
            "items": [item.__dict__ for item in self.items],
        }


# ---------------------------------------------------------------------------
# Evidence envelope contract
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EvidenceEnvelope:
    """Immutable evidence envelope wrapping RetrievalBundle for P0 input."""
    original_request_digest: str
    retrieval_query_digest: str
    retrieval_bundle_digest: str
    evidence_references: tuple[str, ...]  # chunk digests in rank order
    evidence_texts: tuple[str, ...]       # frozen chunk text in rank order
    retrieval_budget_decision: str
    corpus_epoch: int
    vector_index_epoch: int

    def to_canonical_dict(self) -> dict:
        return {
            "original_request_digest": self.original_request_digest,
            "retrieval_query_digest": self.retrieval_query_digest,
            "retrieval_bundle_digest": self.retrieval_bundle_digest,
            "evidence_references": list(self.evidence_references),
            "evidence_texts": list(self.evidence_texts),
            "retrieval_budget_decision": self.retrieval_budget_decision,
            "corpus_epoch": self.corpus_epoch,
            "vector_index_epoch": self.vector_index_epoch,
        }


# ---------------------------------------------------------------------------
# R1 Receipt
# ---------------------------------------------------------------------------

RECEIPT_SCHEMA = "elpis.runtime.r1.receipt.v1"


@dataclass(frozen=True)
class R1TransactionReceipt:
    """Canonical R1 composite receipt with self-hash."""

    schema: str = RECEIPT_SCHEMA
    transaction_id: str = ""
    request_digest: str = ""
    retrieval_contract_version: str = ""
    query_derivation_digest: str = ""
    retrieval_query_digest: str = ""
    retrieval_budget_digest: str = ""
    corpus_identity: str = ""
    corpus_epoch: int = 0
    vector_index_identity: str = ""
    vector_index_epoch: int = 0
    retrieval_bundle_schema: str = ""
    retrieval_bundle_digest: str = ""
    retrieved_chunk_identities: str = ""
    context_expansion_digest: str = ""
    evidence_envelope_digest: str = ""
    r0_receipt_digest: str = ""
    final_artifact_digest: str = ""
    termination_disposition: str = ""
    component_manifest_digests: str = ""
    dependency_resolution_audit_digest: str = ""
    runtime_admission_receipt: bool = False
    receipt_self_hash: str = ""

    def __post_init__(self) -> None:
        payload = {
            "schema": self.schema,
            "transaction_id": self.transaction_id,
            "request_digest": self.request_digest,
            "retrieval_contract_version": self.retrieval_contract_version,
            "query_derivation_digest": self.query_derivation_digest,
            "retrieval_query_digest": self.retrieval_query_digest,
            "retrieval_budget_digest": self.retrieval_budget_digest,
            "corpus_identity": self.corpus_identity,
            "corpus_epoch": self.corpus_epoch,
            "vector_index_identity": self.vector_index_identity,
            "vector_index_epoch": self.vector_index_epoch,
            "retrieval_bundle_schema": self.retrieval_bundle_schema,
            "retrieval_bundle_digest": self.retrieval_bundle_digest,
            "retrieved_chunk_identities": self.retrieved_chunk_identities,
            "context_expansion_digest": self.context_expansion_digest,
            "evidence_envelope_digest": self.evidence_envelope_digest,
            "r0_receipt_digest": self.r0_receipt_digest,
            "final_artifact_digest": self.final_artifact_digest,
            "termination_disposition": self.termination_disposition,
            "component_manifest_digests": self.component_manifest_digests,
            "dependency_resolution_audit_digest": self.dependency_resolution_audit_digest,
            "runtime_admission_receipt": self.runtime_admission_receipt,
        }
        self_hash = _sha256_hex(_canonical_bytes(payload))
        object.__setattr__(self, "receipt_self_hash", self_hash)

    def to_canonical_json(self) -> str:
        payload = {
            "schema": self.schema,
            "transaction_id": self.transaction_id,
            "request_digest": self.request_digest,
            "retrieval_contract_version": self.retrieval_contract_version,
            "query_derivation_digest": self.query_derivation_digest,
            "retrieval_query_digest": self.retrieval_query_digest,
            "retrieval_budget_digest": self.retrieval_budget_digest,
            "corpus_identity": self.corpus_identity,
            "corpus_epoch": self.corpus_epoch,
            "vector_index_identity": self.vector_index_identity,
            "vector_index_epoch": self.vector_index_epoch,
            "retrieval_bundle_schema": self.retrieval_bundle_schema,
            "retrieval_bundle_digest": self.retrieval_bundle_digest,
            "retrieved_chunk_identities": self.retrieved_chunk_identities,
            "context_expansion_digest": self.context_expansion_digest,
            "evidence_envelope_digest": self.evidence_envelope_digest,
            "r0_receipt_digest": self.r0_receipt_digest,
            "final_artifact_digest": self.final_artifact_digest,
            "termination_disposition": self.termination_disposition,
            "component_manifest_digests": self.component_manifest_digests,
            "dependency_resolution_audit_digest": self.dependency_resolution_audit_digest,
            "runtime_admission_receipt": self.runtime_admission_receipt,
            "receipt_self_hash": self.receipt_self_hash,
        }
        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )

    def receipt_bytes(self) -> bytes:
        return self.to_canonical_json().encode("utf-8")
