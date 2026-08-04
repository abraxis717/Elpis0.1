"""AdjudicationInputEnvelopeV1 — input envelope construction."""

from .canonical import canonical_digest, canonical_json


def build_input_envelope(source_row_data, source_manifest_sha256):
    """Build an AdjudicationInputEnvelopeV1 for a source row.

    Args:
        source_row_data: dict from source_join with proposals, ordering, conflicts
        source_manifest_sha256: SHA-256 of G5.0B manifest file

    Returns:
        AdjudicationInputEnvelopeV1 dict
    """
    row_index = source_row_data["row_index"]
    proposals = source_row_data["proposals"]
    ordering = source_row_data["ordering"]
    conflicts = source_row_data["conflicts"]

    # Proposal digests — sorted for order independence
    proposal_digests = sorted([p["proposal_digest"] for p in proposals])

    # Proposal-set digest — independent of presentation ordering
    proposal_set_digest = canonical_digest(proposal_digests)

    # Ordering digest
    ordering_digest = ordering["ordering_digest"]

    # Conflict digests — sorted
    conflict_digests = sorted([c["canonical_conflict_digest"] for c in conflicts])

    # Relevant proposal digests
    relevant_digests = sorted([
        p["proposal_digest"] for p in proposals if p["group_relevant"]
    ])

    # Negative-evidence proposal digests (not relevant)
    negative_digests = sorted([
        p["proposal_digest"] for p in proposals if not p["group_relevant"]
    ])

    # Build envelope without input_digest
    envelope = {
        "schema_version": "adjudication-input-envelope.v1",
        "source_gate": "G5.0B",
        "source_manifest_sha256": source_manifest_sha256,
        "source_row_digest": row_index["source_row_digest"],
        "proposal_digests": proposal_digests,
        "proposal_set_digest": proposal_set_digest,
        "ordering_digest": ordering_digest,
        "conflict_digests": conflict_digests,
        "relevant_proposal_digests": relevant_digests,
        "negative_evidence_proposal_digests": negative_digests,
    }

    # Compute input_digest from the envelope without the digest field
    input_digest = canonical_digest(envelope)
    envelope["input_digest"] = input_digest

    return envelope


def verify_input_envelope(envelope):
    """Verify an input envelope against schema constraints."""
    errors = []

    # Must have exactly 5 proposals
    if len(envelope["proposal_digests"]) != 5:
        errors.append(f"Expected 5 proposal digests, got {len(envelope['proposal_digests'])}")

    # All proposal digests must be unique
    if len(set(envelope["proposal_digests"])) != len(envelope["proposal_digests"]):
        errors.append("Duplicate proposal digests in envelope")

    # Verify input_digest
    envelope_copy = dict(envelope)
    del envelope_copy["input_digest"]
    expected_digest = canonical_digest(envelope_copy)
    if envelope["input_digest"] != expected_digest:
        errors.append(f"input_digest mismatch: {envelope['input_digest']} != {expected_digest}")

    # Verify proposal_set_digest
    expected_ps = canonical_digest(sorted(envelope["proposal_digests"]))
    if envelope["proposal_set_digest"] != expected_ps:
        errors.append(f"proposal_set_digest mismatch")

    return len(errors) == 0, errors
