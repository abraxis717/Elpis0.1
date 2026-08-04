"""Canonical semantic identity — G5.1A digest law.

Semantic identity MUST be invariant under presentation order, source split,
case ID, filesystem paths, timestamps, and provenance changes.

Semantic identity MUST change when disposition, outcome, review set, conflict
kind, reason code, or request state changes.
"""

from .canonical import canonical_digest


def compute_semantic_identity(dispositions, conflicts, outcome, abstention,
                                review_set, request_state, reason_codes):
    """Compute the semantic adjudication identity.

    Excludes: source_row_digest, source_manifest_digest, proposal record digests,
              ordering_digest, source split, case ID, filesystem paths, timestamps.

    Includes: group IDs, group relevance, structural orbit identities, dispositions,
              reason codes, conflict kinds, outcome, abstention kind,
              review-set structural identities, request state.
    """
    # Build semantic payload from semantic fields only
    semantic_dispositions = []
    for d in dispositions:
        semantic_dispositions.append({
            "disposition": d["disposition"],
            "group_id": d["group_id"],
            "group_relevant": d["group_relevant"],
            "proposal_semantic_id": f"{d['group_id']}:{d['group_relevant']}",
            "reason_codes": d["reason_codes"],
        })
    # Sort for determinism
    semantic_dispositions.sort(key=lambda d: (d["group_id"], d["disposition"], d["proposal_semantic_id"]))

    # Conflict kinds (not digests)
    conflict_kinds = sorted(set(c["conflict_kind"] for c in conflicts))

    # Review-set structural identities (group IDs of referred proposals)
    review_set_groups = []
    for d in dispositions:
        if d["disposition"] == "REFERRED_FOR_CAPABILITY_REVIEW":
            review_set_groups.append(d["group_id"])
    review_set_groups.sort()

    semantic_payload = {
        "adjudication_kind": outcome,
        "abstention_kind": abstention["abstention_kind"],
        "conflict_kinds": conflict_kinds,
        "dispositions": semantic_dispositions,
        "reason_codes": sorted(reason_codes),
        "request_state": request_state,
        "review_set_structural": review_set_groups,
    }

    return canonical_digest(semantic_payload)


def verify_semantic_invariance(original_record, modified_records, label):
    """Verify semantic identity is invariant under specific transformation.

    Args:
        original_record: original adjudication record
        modified_records: list of records after transformation
        label: description of the transformation

    Returns:
        (bool, str): (invariant, message)
    """
    original_semantic = original_record.get("adjudication_semantic_digest", "")

    for i, modified in enumerate(modified_records):
        modified_semantic = modified.get("adjudication_semantic_digest", "")
        if original_semantic != modified_semantic:
            return False, f"{label}: semantic digest changed at index {i}"

    return True, f"{label}: semantic identity invariant"


def verify_semantic_sensitivity(original_semantic, modified_semantics, label):
    """Verify semantic identity is sensitive to semantic changes.

    Args:
        original_semantic: original semantic digest
        modified_semantics: list of modified semantic digests
        label: description of the semantic change

    Returns:
        (bool, str): (sensitive, message)
    """
    for i, modified in enumerate(modified_semantics):
        if original_semantic == modified:
            return False, f"{label}: semantic digest unchanged at index {i}"

    return True, f"{label}: semantic identity sensitive"
