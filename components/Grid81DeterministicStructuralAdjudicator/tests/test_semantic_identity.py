"""Test semantic identity computation."""

import os
import sys

BASE = os.environ.get("ELPIS_BASE", "/mnt/primesauce/Elpis_Canon")
sys.path.insert(0, os.path.join(BASE, "Grid81DeterministicStructuralAdjudicator", "src"))

from elpis_grid81_adjudication.semantic_identity import compute_semantic_identity


class TestSemanticIdentity:
    def test_order_independence(self):
        d1 = [
            {"disposition": "REFERRED_FOR_CAPABILITY_REVIEW", "group_id": "TRANSITION_EDIT",
             "group_relevant": True, "reason_codes": ["CAPABILITY_REVIEW_REQUIRED"],
             "_sort_key": "a", "proposal_digest": "a" * 64},
            {"disposition": "NOT_REFERRED_NEGATIVE_EVIDENCE", "group_id": "RATIONALE_DIAGNOSTIC",
             "group_relevant": False, "reason_codes": ["NEGATIVE_EVIDENCE_PRESERVED"],
             "_sort_key": "b", "proposal_digest": "b" * 64},
        ]
        d2 = list(reversed(d1))
        conflicts = [{"conflict_kind": "SHARED_SUPPORT"}]
        outcome = "REVIEW_SET_FORMED"
        abstention = {"abstention_kind": "NONE"}
        review_set = ["a" * 64]
        request_state = "REVIEW_REQUESTED"
        reason_codes = ["CAPABILITY_REVIEW_REQUIRED", "NEGATIVE_EVIDENCE_PRESERVED"]

        s1 = compute_semantic_identity(d1, conflicts, outcome, abstention, review_set, request_state, reason_codes)
        s2 = compute_semantic_identity(d2, conflicts, outcome, abstention, review_set, request_state, reason_codes)
        assert s1 == s2

    def test_disposition_sensitivity(self):
        base = [
            {"disposition": "REFERRED_FOR_CAPABILITY_REVIEW", "group_id": "TRANSITION_EDIT",
             "group_relevant": True, "reason_codes": ["CAPABILITY_REVIEW_REQUIRED"],
             "_sort_key": "a", "proposal_digest": "a" * 64},
        ]
        modified = [
            {"disposition": "PRESERVED_ALTERNATIVE", "group_id": "TRANSITION_EDIT",
             "group_relevant": True, "reason_codes": ["RATIONALE_DIAGNOSTIC_ONLY"],
             "_sort_key": "a", "proposal_digest": "a" * 64},
        ]
        conflicts = []
        outcome = "REVIEW_SET_FORMED"
        abstention = {"abstention_kind": "NONE"}
        review_set = ["a" * 64]
        request_state = "REVIEW_REQUESTED"
        reason_codes = ["CAPABILITY_REVIEW_REQUIRED"]

        s1 = compute_semantic_identity(base, conflicts, outcome, abstention, review_set, request_state, reason_codes)
        s2 = compute_semantic_identity(modified, conflicts, outcome, abstention, review_set, request_state, reason_codes)
        assert s1 != s2

    def test_outcome_sensitivity(self):
        d = [{"disposition": "REFERRED_FOR_CAPABILITY_REVIEW", "group_id": "TRANSITION_EDIT",
              "group_relevant": True, "reason_codes": [], "_sort_key": "a", "proposal_digest": "a" * 64}]
        conflicts = []
        abstention = {"abstention_kind": "NONE"}
        review_set = ["a" * 64]
        request_state = "REVIEW_REQUESTED"
        reason_codes = []

        s1 = compute_semantic_identity(d, conflicts, "REVIEW_SET_FORMED", abstention, review_set, request_state, reason_codes)
        s2 = compute_semantic_identity(d, conflicts, "ABSTAIN_LOGICAL_CONTRADICTION", abstention, review_set, request_state, reason_codes)
        assert s1 != s2

    def test_source_row_not_in_semantic(self):
        """Source row digest should not affect semantic identity."""
        # Semantic identity takes dispositions, conflicts, outcome, etc.
        # It does NOT take source_row_digest as input
        # This is verified by the function signature — source_row_digest is not a parameter
        d = [{"disposition": "REFERRED_FOR_CAPABILITY_REVIEW", "group_id": "TRANSITION_EDIT",
              "group_relevant": True, "reason_codes": [], "_sort_key": "a", "proposal_digest": "a" * 64}]
        conflicts = []
        outcome = "REVIEW_SET_FORMED"
        abstention = {"abstention_kind": "NONE"}
        review_set = ["a" * 64]
        request_state = "REVIEW_REQUESTED"
        reason_codes = []

        s = compute_semantic_identity(d, conflicts, outcome, abstention, review_set, request_state, reason_codes)
        assert len(s) == 64  # Valid SHA-256

    def test_conflict_kind_sensitivity(self):
        d = [{"disposition": "REFERRED_FOR_CAPABILITY_REVIEW", "group_id": "TRANSITION_EDIT",
              "group_relevant": True, "reason_codes": [], "_sort_key": "a", "proposal_digest": "a" * 64}]
        outcome = "REVIEW_SET_FORMED"
        abstention = {"abstention_kind": "NONE"}
        review_set = ["a" * 64]
        request_state = "REVIEW_REQUESTED"
        reason_codes = []

        s1 = compute_semantic_identity(d, [{"conflict_kind": "SHARED_SUPPORT"}], outcome, abstention, review_set, request_state, reason_codes)
        s2 = compute_semantic_identity(d, [{"conflict_kind": "SIMULTANEOUS_RELEVANCE"}], outcome, abstention, review_set, request_state, reason_codes)
        assert s1 != s2
