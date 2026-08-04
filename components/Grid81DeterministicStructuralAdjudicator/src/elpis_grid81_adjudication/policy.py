"""Deterministic adjudication policy — G5.1A contract implementation.

Policy precedence:
  1. input-contract validation
  2. logical-contradiction handling
  3. insufficient structural basis
  4. normal review-set formation

Ordering position must never participate.
"""

# Group class definitions
REVIEWABLE_STRUCTURAL_GROUPS = frozenset({
    "TRANSITION_EDIT",
    "TRANSITION_NOOP",
    "EXPANSION_DECOMPOSITION",
    "QUIESCENCE",
})

DIAGNOSTIC_ONLY_GROUPS = frozenset({
    "RATIONALE_DIAGNOSTIC",
})

ALL_GROUPS = REVIEWABLE_STRUCTURAL_GROUPS | DIAGNOSTIC_ONLY_GROUPS

# Disposition values
REFERRED_FOR_CAPABILITY_REVIEW = "REFERRED_FOR_CAPABILITY_REVIEW"
PRESERVED_ALTERNATIVE = "PRESERVED_ALTERNATIVE"
DEFERRED_PENDING_EVIDENCE = "DEFERRED_PENDING_EVIDENCE"
NOT_REFERRED_NEGATIVE_EVIDENCE = "NOT_REFERRED_NEGATIVE_EVIDENCE"
REJECTED_CONTRACT_INVALID = "REJECTED_CONTRACT_INVALID"

# Outcome values
REVIEW_SET_FORMED = "REVIEW_SET_FORMED"
PRESERVE_ALL = "PRESERVE_ALL"
DEFER_ALL = "DEFER_ALL"
ABSTAIN_LOGICAL_CONTRADICTION = "ABSTAIN_LOGICAL_CONTRADICTION"
ABSTAIN_INSUFFICIENT_EVIDENCE = "ABSTAIN_INSUFFICIENT_EVIDENCE"
REJECT_INVALID_INPUT = "REJECT_INVALID_INPUT"

# Request states
REVIEW_REQUESTED = "REVIEW_REQUESTED"
REVIEW_NOT_REQUESTED = "REVIEW_NOT_REQUESTED"

# Abstention kinds
ABSTENTION_NONE = "NONE"
ABSTENTION_LOGICAL_CONTRADICTION = "LOGICAL_CONTRADICTION"
ABSTENTION_INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
ABSTENTION_INVALID_INPUT = "INVALID_INPUT"


def adjudicate_row(source_row_data, input_envelope):
    """Apply deterministic adjudication policy to a single row.

    Returns:
        dict with outcome, dispositions, review_set, reason_codes, abstention, request_state
    """
    proposals = source_row_data["proposals"]
    conflicts = source_row_data["conflicts"]

    # Step 1: Input-contract validation
    # Check that all proposals are admissible
    for p in proposals:
        if not p.get("admissible_for_adjudication", False):
            return _reject_invalid_input(proposals, "CONTRACT_VALIDATION_FAILED")

    # Verify proposal set completeness
    if len(proposals) != 5:
        return _reject_invalid_input(proposals, "PROPOSAL_SET_INCOMPLETE")

    # Step 2: Logical-contradiction handling
    has_logical_contradiction = any(
        c["conflict_kind"] == "LOGICAL_CONTRADICTION"
        for c in conflicts
    )

    if has_logical_contradiction:
        return _abstain_logical_contradiction(proposals)

    # Step 3: Insufficient structural basis
    relevant_proposals = [p for p in proposals if p["group_relevant"]]
    relevant_reviewable = [
        p for p in relevant_proposals
        if p["group_id"] in REVIEWABLE_STRUCTURAL_GROUPS
    ]

    if not relevant_reviewable:
        return _abstain_insufficient_evidence(proposals)

    # Step 4: Normal review-set formation
    return _normal_adjudication(proposals, conflicts)


def _reject_invalid_input(proposals, reason):
    """Handle invalid input — REJECT_INVALID_INPUT."""
    dispositions = []
    for p in proposals:
        dispositions.append({
            "proposal_digest": p["proposal_digest"],
            "group_id": p["group_id"],
            "group_relevant": p["group_relevant"],
            "disposition": REJECTED_CONTRACT_INVALID,
            "reason_codes": sorted(["CONTRACT_VALIDATION_FAILED", reason]),
        })

    return {
        "outcome": REJECT_INVALID_INPUT,
        "dispositions": dispositions,
        "review_set": [],
        "reason_codes": sorted(["CONTRACT_VALIDATION_FAILED", reason]),
        "abstention": {
            "abstained": True,
            "abstention_kind": ABSTENTION_INVALID_INPUT,
            "implicated_proposal_digests": sorted([p["proposal_digest"] for p in proposals]),
            "reason_codes": sorted(["CONTRACT_VALIDATION_FAILED", reason]),
        },
        "request_state": REVIEW_NOT_REQUESTED,
    }


def _abstain_logical_contradiction(proposals):
    """Handle logical contradiction — ABSTAIN_LOGICAL_CONTRADICTION."""
    relevant = [p for p in proposals if p["group_relevant"]]
    negative = [p for p in proposals if not p["group_relevant"]]

    dispositions = []
    for p in relevant:
        dispositions.append({
            "proposal_digest": p["proposal_digest"],
            "group_id": p["group_id"],
            "group_relevant": True,
            "disposition": DEFERRED_PENDING_EVIDENCE,
            "reason_codes": sorted(["DEFERRED_FOR_ADDITIONAL_EVIDENCE", "LOGICAL_CONTRADICTION_PRESENT"]),
        })
    for p in negative:
        dispositions.append({
            "proposal_digest": p["proposal_digest"],
            "group_id": p["group_id"],
            "group_relevant": False,
            "disposition": NOT_REFERRED_NEGATIVE_EVIDENCE,
            "reason_codes": sorted(["LOGICAL_CONTRADICTION_PRESENT", "NEGATIVE_EVIDENCE_PRESERVED"]),
        })

    implicated = sorted([p["proposal_digest"] for p in relevant])

    return {
        "outcome": ABSTAIN_LOGICAL_CONTRADICTION,
        "dispositions": dispositions,
        "review_set": [],
        "reason_codes": sorted(["DEFERRED_FOR_ADDITIONAL_EVIDENCE", "LOGICAL_CONTRADICTION_PRESENT", "NEGATIVE_EVIDENCE_PRESERVED"]),
        "abstention": {
            "abstained": True,
            "abstention_kind": ABSTENTION_LOGICAL_CONTRADICTION,
            "implicated_proposal_digests": implicated,
            "reason_codes": sorted(["LOGICAL_CONTRADICTION_PRESENT"]),
        },
        "request_state": REVIEW_NOT_REQUESTED,
    }


def _abstain_insufficient_evidence(proposals):
    """Handle insufficient structural basis — ABSTAIN_INSUFFICIENT_EVIDENCE."""
    relevant = [p for p in proposals if p["group_relevant"]]
    negative = [p for p in proposals if not p["group_relevant"]]

    dispositions = []
    for p in relevant:
        dispositions.append({
            "proposal_digest": p["proposal_digest"],
            "group_id": p["group_id"],
            "group_relevant": True,
            "disposition": DEFERRED_PENDING_EVIDENCE,
            "reason_codes": sorted(["DEFERRED_FOR_ADDITIONAL_EVIDENCE", "INSUFFICIENT_STRUCTURAL_BASIS"]),
        })
    for p in negative:
        dispositions.append({
            "proposal_digest": p["proposal_digest"],
            "group_id": p["group_id"],
            "group_relevant": False,
            "disposition": NOT_REFERRED_NEGATIVE_EVIDENCE,
            "reason_codes": sorted(["INSUFFICIENT_STRUCTURAL_BASIS", "NEGATIVE_EVIDENCE_PRESERVED"]),
        })

    implicated = sorted([p["proposal_digest"] for p in relevant])

    return {
        "outcome": ABSTAIN_INSUFFICIENT_EVIDENCE,
        "dispositions": dispositions,
        "review_set": [],
        "reason_codes": sorted(["DEFERRED_FOR_ADDITIONAL_EVIDENCE", "INSUFFICIENT_STRUCTURAL_BASIS", "NEGATIVE_EVIDENCE_PRESERVED"]),
        "abstention": {
            "abstained": True,
            "abstention_kind": ABSTENTION_INSUFFICIENT_EVIDENCE,
            "implicated_proposal_digests": implicated,
            "reason_codes": sorted(["INSUFFICIENT_STRUCTURAL_BASIS"]),
        },
        "request_state": REVIEW_NOT_REQUESTED,
    }


def _normal_adjudication(proposals, conflicts):
    """Normal canonical adjudication — REVIEW_SET_FORMED."""
    relevant = [p for p in proposals if p["group_relevant"]]
    negative = [p for p in proposals if not p["group_relevant"]]

    # Determine conflict-based reason codes
    conflict_reasons = set()
    for c in conflicts:
        if c["conflict_kind"] == "SHARED_SUPPORT":
            conflict_reasons.add("SHARED_SUPPORT_PRESENT")
        elif c["conflict_kind"] == "SIMULTANEOUS_RELEVANCE":
            conflict_reasons.add("SIMULTANEOUS_RELEVANCE_PRESENT")

    # Determine quiescence coexistence
    has_quiescence = any(
        p["group_relevant"] and p["group_id"] == "QUIESCENCE"
        for p in proposals
    )
    has_other_reviewable = any(
        p["group_relevant"] and p["group_id"] in {"TRANSITION_EDIT", "TRANSITION_NOOP", "EXPANSION_DECOMPOSITION"}
        for p in proposals
    )
    quiescence_coexists = has_quiescence and has_other_reviewable

    if quiescence_coexists:
        conflict_reasons.add("QUIESCENCE_COEXISTS_WITH_OTHER_RELEVANCE")
    if has_quiescence:
        conflict_reasons.add("QUIESCENCE_PRESENT")

    # Multiple vs single relevant
    reviewable_relevant = [p for p in relevant if p["group_id"] in REVIEWABLE_STRUCTURAL_GROUPS]
    has_rationale = any(p["group_id"] == "RATIONALE_DIAGNOSTIC" for p in relevant)

    if len(reviewable_relevant) + (1 if has_rationale else 0) > 1:
        conflict_reasons.add("MULTIPLE_RELEVANT_PROPOSALS")
    else:
        conflict_reasons.add("SINGLE_RELEVANT_PROPOSAL")

    # Build dispositions
    dispositions = []
    review_set = []

    for p in relevant:
        if p["group_id"] in REVIEWABLE_STRUCTURAL_GROUPS:
            # Relevant reviewable structural proposal -> REFERRED
            prop_reasons = set(["CAPABILITY_REVIEW_REQUIRED", "UPSTREAM_BINDING_VERIFIED"])
            if quiescence_coexists and p["group_id"] == "QUIESCENCE":
                prop_reasons.add("QUIESCENCE_COEXISTS_WITH_OTHER_RELEVANCE")
            if p["group_id"] == "QUIESCENCE":
                prop_reasons.add("QUIESCENCE_PRESENT")
            prop_reasons.update(conflict_reasons)
            dispositions.append({
                "proposal_digest": p["proposal_digest"],
                "group_id": p["group_id"],
                "group_relevant": True,
                "disposition": REFERRED_FOR_CAPABILITY_REVIEW,
                "reason_codes": sorted(prop_reasons),
            })
            review_set.append(p["proposal_digest"])
        elif p["group_id"] == "RATIONALE_DIAGNOSTIC":
            # Rationale diagnostic -> PRESERVED_ALTERNATIVE
            prop_reasons = set(["RATIONALE_DIAGNOSTIC_ONLY", "UPSTREAM_BINDING_VERIFIED"])
            prop_reasons.update(conflict_reasons)
            dispositions.append({
                "proposal_digest": p["proposal_digest"],
                "group_id": p["group_id"],
                "group_relevant": True,
                "disposition": PRESERVED_ALTERNATIVE,
                "reason_codes": sorted(prop_reasons),
            })

    for p in negative:
        # Negative evidence -> NOT_REFERRED
        prop_reasons = set(["NEGATIVE_EVIDENCE_PRESERVED"])
        prop_reasons.update(conflict_reasons)
        dispositions.append({
            "proposal_digest": p["proposal_digest"],
            "group_id": p["group_id"],
            "group_relevant": False,
            "disposition": NOT_REFERRED_NEGATIVE_EVIDENCE,
            "reason_codes": sorted(prop_reasons),
        })

    # Ordering is never used for selection
    all_reasons = set(["ORDERING_BOUND_NOT_AUTHORITATIVE", "PROPOSAL_SET_COMPLETE"])
    all_reasons.update(conflict_reasons)

    # Add rationale reason if relevant
    if has_rationale:
        all_reasons.add("RATIONALE_DIAGNOSTIC_ONLY")

    # Build abstention (non-abstaining)
    abstention_reasons = set()
    if conflict_reasons:
        abstention_reasons.update(conflict_reasons)

    return {
        "outcome": REVIEW_SET_FORMED,
        "dispositions": dispositions,
        "review_set": sorted(review_set),
        "reason_codes": sorted(all_reasons),
        "abstention": {
            "abstained": False,
            "abstention_kind": ABSTENTION_NONE,
            "implicated_proposal_digests": [],
            "reason_codes": sorted(abstention_reasons),
        },
        "request_state": REVIEW_REQUESTED,
    }
