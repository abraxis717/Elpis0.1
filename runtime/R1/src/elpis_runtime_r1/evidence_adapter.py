"""Evidence-bound request adapter — construct immutable evidence envelope.

Wraps a validated RetrievalBundle into an EvidenceEnvelope suitable for
consumption by downstream P0 projection. Does not claim semantic truth;
only states retrieval provenance.
"""

from __future__ import annotations

from .contracts import (
    EvidenceEnvelope,
    RetrievalBundle,
    _digest,
)
from .errors import R1EvidenceAdapterError


def build_evidence_envelope(
    original_request_digest: str,
    retrieval_query_digest: str,
    bundle: RetrievalBundle,
    budget_decision_digest: str,
) -> EvidenceEnvelope:
    """Construct an immutable evidence envelope from a validated bundle.

    Args:
        original_request_digest: Digest of the original RequestContext.
        retrieval_query_digest: Digest of the derived retrieval query.
        bundle: Validated RetrievalBundle.
        budget_decision_digest: Digest of the budget decision record.

    Returns:
        EvidenceEnvelope with frozen evidence references and texts.

    Raises:
        R1EvidenceAdapterError: on construction failure.
    """
    if not bundle.items:
        raise R1EvidenceAdapterError(
            "EMPTY_BUNDLE",
            "Cannot build evidence envelope from empty bundle",
        )

    # Extract evidence references (chunk digests in rank order)
    evidence_refs = tuple(item.chunk_digest for item in bundle.items)

    # Extract frozen evidence texts (in rank order)
    evidence_texts = tuple(item.text for item in bundle.items)

    # Compute bundle digest from canonical representation
    bundle_digest = _digest(bundle.to_canonical_dict())

    envelope = EvidenceEnvelope(
        original_request_digest=original_request_digest,
        retrieval_query_digest=retrieval_query_digest,
        retrieval_bundle_digest=bundle_digest,
        evidence_references=evidence_refs,
        evidence_texts=evidence_texts,
        retrieval_budget_decision=budget_decision_digest,
        corpus_epoch=bundle.corpus_epoch,
        vector_index_epoch=bundle.vector_index_epoch,
    )

    return envelope


def evidence_envelope_digest(envelope: EvidenceEnvelope) -> str:
    """Compute canonical digest of an EvidenceEnvelope."""
    return _digest(envelope.to_canonical_dict())


def evidence_envelope_to_p0_input(
    envelope: EvidenceEnvelope,
) -> dict:
    """Convert evidence envelope to a deterministic dict for P0 consumption.

    Returns a dict containing:
        - evidence_references: ordered chunk digests
        - evidence_texts: frozen text strings
        - retrieval_metadata: provenance-only fields

    Does NOT claim truth — only states retrieval provenance.
    """
    return {
        "evidence_references": list(envelope.evidence_references),
        "evidence_texts": list(envelope.evidence_texts),
        "retrieval_metadata": {
            "original_request_digest": envelope.original_request_digest,
            "retrieval_query_digest": envelope.retrieval_query_digest,
            "retrieval_bundle_digest": envelope.retrieval_bundle_digest,
            "retrieval_budget_decision": envelope.retrieval_budget_decision,
            "corpus_epoch": envelope.corpus_epoch,
            "vector_index_epoch": envelope.vector_index_epoch,
        },
    }
