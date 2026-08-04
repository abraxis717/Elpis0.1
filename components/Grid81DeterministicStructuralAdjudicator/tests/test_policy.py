"""Test deterministic adjudication policy."""

import os
import sys

BASE = os.environ.get("ELPIS_BASE", "$ELPIS_CANON_ROOT/Elpis_Canon")
sys.path.insert(0, os.path.join(BASE, "Grid81DeterministicStructuralAdjudicator", "src"))

from elpis_grid81_adjudication.policy import (
    REVIEWABLE_STRUCTURAL_GROUPS,
    DIAGNOSTIC_ONLY_GROUPS,
    adjudicate_row,
    REFERRED_FOR_CAPABILITY_REVIEW,
    PRESERVED_ALTERNATIVE,
    DEFERRED_PENDING_EVIDENCE,
    NOT_REFERRED_NEGATIVE_EVIDENCE,
    REVIEW_SET_FORMED,
    REVIEW_REQUESTED,
    REVIEW_NOT_REQUESTED,
    ABSTAIN_LOGICAL_CONTRADICTION,
    ABSTAIN_INSUFFICIENT_EVIDENCE,
)


class TestPolicy:
    def test_reviewable_groups(self):
        assert "TRANSITION_EDIT" in REVIEWABLE_STRUCTURAL_GROUPS
        assert "TRANSITION_NOOP" in REVIEWABLE_STRUCTURAL_GROUPS
        assert "EXPANSION_DECOMPOSITION" in REVIEWABLE_STRUCTURAL_GROUPS
        assert "QUIESCENCE" in REVIEWABLE_STRUCTURAL_GROUPS
        assert "RATIONALE_DIAGNOSTIC" not in REVIEWABLE_STRUCTURAL_GROUPS

    def test_diagnostic_groups(self):
        assert "RATIONALE_DIAGNOSTIC" in DIAGNOSTIC_ONLY_GROUPS

    def test_normal_adjudication(self):
        """Normal row with transition + expansion + rationale."""
        proposals = [
            {"proposal_digest": f"d{i}{'0'*58}", "group_id": "TRANSITION_EDIT", "group_relevant": i == 0,
             "admissible_for_adjudication": True, "evidence_digest": f"e{i}{'0'*58}"}
            for i in range(5)
        ]
        proposals[0]["group_relevant"] = True
        proposals[1]["group_relevant"] = True
        proposals[1]["group_id"] = "EXPANSION_DECOMPOSITION"

        conflicts = [{"conflict_kind": "SHARED_SUPPORT", "canonical_conflict_digest": "c0" * 32}]

        row_data = {"proposals": proposals, "conflicts": conflicts, "ordering": {}, "evidence": []}
        result = adjudicate_row(row_data, {})

        assert result["outcome"] == REVIEW_SET_FORMED
        assert result["request_state"] == REVIEW_REQUESTED
        assert len(result["review_set"]) > 0

    def test_quiescence_non_veto(self):
        """Quiescence should be referred, not defer others."""
        proposals = [
            {"proposal_digest": f"d{i}{'0'*58}", "group_id": "QUIESCENCE", "group_relevant": True,
             "admissible_for_adjudication": True, "evidence_digest": f"e{i}{'0'*58}"}
            for i in range(1)
        ]
        # Add negative proposals
        for i in range(4):
            proposals.append({
                "proposal_digest": f"n{i}{'0'*58}",
                "group_id": "RATIONALE_DIAGNOSTIC",
                "group_relevant": False,
                "admissible_for_adjudication": True,
                "evidence_digest": f"ne{i}{'0'*58}",
            })

        row_data = {"proposals": proposals, "conflicts": [], "ordering": {}, "evidence": []}
        result = adjudicate_row(row_data, {})

        assert result["outcome"] == REVIEW_SET_FORMED
        quiescence_disp = [d for d in result["dispositions"] if d["group_id"] == "QUIESCENCE"]
        assert all(d["disposition"] == REFERRED_FOR_CAPABILITY_REVIEW for d in quiescence_disp)

    def test_rationale_not_referred(self):
        """RATIONALE_DIAGNOSTIC should be PRESERVED_ALTERNATIVE, never REFERRED."""
        proposals = [
            {"proposal_digest": f"d{i}{'0'*58}", "group_id": "TRANSITION_EDIT", "group_relevant": True,
             "admissible_for_adjudication": True, "evidence_digest": f"e{i}{'0'*58}"}
            for i in range(1)
        ]
        proposals.append({
            "proposal_digest": "r0" + "0" * 58,
            "group_id": "RATIONALE_DIAGNOSTIC",
            "group_relevant": True,
            "admissible_for_adjudication": True,
            "evidence_digest": "re" + "0" * 58,
        })
        # Fill to 5
        for i in range(3):
            proposals.append({
                "proposal_digest": f"n{i}{'0'*58}",
                "group_id": "RATIONALE_DIAGNOSTIC",
                "group_relevant": False,
                "admissible_for_adjudication": True,
                "evidence_digest": f"ne{i}{'0'*58}",
            })

        row_data = {"proposals": proposals, "conflicts": [], "ordering": {}, "evidence": []}
        result = adjudicate_row(row_data, {})

        rationale_disp = [d for d in result["dispositions"] if d["group_id"] == "RATIONALE_DIAGNOSTIC" and d["group_relevant"]]
        assert all(d["disposition"] == PRESERVED_ALTERNATIVE for d in rationale_disp)
        assert all(d["disposition"] != REFERRED_FOR_CAPABILITY_REVIEW for d in rationale_disp)

    def test_logical_contradiction_abstention(self):
        """Logical contradiction should cause abstention."""
        proposals = [
            {"proposal_digest": f"d{i}{'0'*58}", "group_id": "TRANSITION_EDIT", "group_relevant": True,
             "admissible_for_adjudication": True, "evidence_digest": f"e{i}{'0'*58}"}
            for i in range(5)
        ]
        conflicts = [{"conflict_kind": "LOGICAL_CONTRADICTION", "canonical_conflict_digest": "c0" * 32}]

        row_data = {"proposals": proposals, "conflicts": conflicts, "ordering": {}, "evidence": []}
        result = adjudicate_row(row_data, {})

        assert result["outcome"] == ABSTAIN_LOGICAL_CONTRADICTION
        assert result["request_state"] == REVIEW_NOT_REQUESTED
        assert len(result["review_set"]) == 0
        assert all(d["disposition"] == DEFERRED_PENDING_EVIDENCE for d in result["dispositions"] if d["group_relevant"])

    def test_insufficient_evidence_abstention(self):
        """Only rationale diagnostic should cause insufficient evidence abstention."""
        proposals = [
            {"proposal_digest": f"d{i}{'0'*58}", "group_id": "RATIONALE_DIAGNOSTIC", "group_relevant": True,
             "admissible_for_adjudication": True, "evidence_digest": f"e{i}{'0'*58}"}
            for i in range(5)
        ]

        row_data = {"proposals": proposals, "conflicts": [], "ordering": {}, "evidence": []}
        result = adjudicate_row(row_data, {})

        assert result["outcome"] == ABSTAIN_INSUFFICIENT_EVIDENCE
        assert result["request_state"] == REVIEW_NOT_REQUESTED
        assert len(result["review_set"]) == 0

    def test_negative_evidence_disposition(self):
        """Negative evidence proposals get NOT_REFERRED_NEGATIVE_EVIDENCE."""
        proposals = [
            {"proposal_digest": f"d{i}{'0'*58}", "group_id": "TRANSITION_EDIT", "group_relevant": True,
             "admissible_for_adjudication": True, "evidence_digest": f"e{i}{'0'*58}"}
            for i in range(1)
        ]
        for i in range(4):
            proposals.append({
                "proposal_digest": f"n{i}{'0'*58}",
                "group_id": "RATIONALE_DIAGNOSTIC",
                "group_relevant": False,
                "admissible_for_adjudication": True,
                "evidence_digest": f"ne{i}{'0'*58}",
            })

        row_data = {"proposals": proposals, "conflicts": [], "ordering": {}, "evidence": []}
        result = adjudicate_row(row_data, {})

        negative = [d for d in result["dispositions"] if not d["group_relevant"]]
        assert all(d["disposition"] == NOT_REFERRED_NEGATIVE_EVIDENCE for d in negative)

    def test_ordering_not_used(self):
        """Policy result must not reference ordering position."""
        proposals = [
            {"proposal_digest": f"d{i}{'0'*58}", "group_id": "TRANSITION_EDIT", "group_relevant": True,
             "admissible_for_adjudication": True, "evidence_digest": f"e{i}{'0'*58}"}
            for i in range(5)
        ]

        row_data = {"proposals": proposals, "conflicts": [], "ordering": {}, "evidence": []}
        result = adjudicate_row(row_data, {})

        # No ordering position should influence the result
        assert "ordering_position" not in result
