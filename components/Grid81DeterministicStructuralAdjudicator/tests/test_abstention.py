"""Test abstention records."""

import os
import sys

BASE = os.environ.get("ELPIS_BASE", "/mnt/primesauce/Elpis_Canon")
sys.path.insert(0, os.path.join(BASE, "Grid81DeterministicStructuralAdjudicator", "src"))

from elpis_grid81_adjudication.policy import adjudicate_row
from elpis_grid81_adjudication.abstention import build_abstention_record, verify_abstention
from elpis_grid81_adjudication.canonical import canonical_digest


class TestAbstention:
    def test_normal_abstention(self):
        proposals = [
            {"proposal_digest": f"d{i}{'0'*58}", "group_id": "TRANSITION_EDIT", "group_relevant": True,
             "admissible_for_adjudication": True}
            for i in range(5)
        ]
        row_data = {"proposals": proposals, "conflicts": [], "ordering": {}, "evidence": []}
        result = adjudicate_row(row_data, {})
        abstention = build_abstention_record(result)

        assert abstention["abstained"] is False
        assert abstention["abstention_kind"] == "NONE"
        assert abstention["implicated_proposal_digests"] == []

    def test_abstention_digest(self):
        proposals = [
            {"proposal_digest": f"d{i}{'0'*58}", "group_id": "TRANSITION_EDIT", "group_relevant": True,
             "admissible_for_adjudication": True}
            for i in range(5)
        ]
        row_data = {"proposals": proposals, "conflicts": [], "ordering": {}, "evidence": []}
        result = adjudicate_row(row_data, {})
        abstention = build_abstention_record(result)

        copy = {k: v for k, v in abstention.items() if k != "abstention_digest"}
        expected = canonical_digest(copy)
        assert abstention["abstention_digest"] == expected

    def test_logical_contradiction_abstention(self):
        proposals = [
            {"proposal_digest": f"d{i}{'0'*58}", "group_id": "TRANSITION_EDIT", "group_relevant": True,
             "admissible_for_adjudication": True}
            for i in range(5)
        ]
        conflicts = [{"conflict_kind": "LOGICAL_CONTRADICTION", "canonical_conflict_digest": "c0" * 32}]
        row_data = {"proposals": proposals, "conflicts": conflicts, "ordering": {}, "evidence": []}
        result = adjudicate_row(row_data, {})
        abstention = build_abstention_record(result)

        assert abstention["abstained"] is True
        assert abstention["abstention_kind"] == "LOGICAL_CONTRADICTION"
        assert len(abstention["implicated_proposal_digests"]) == 5

    def test_verify_abstention(self):
        proposals = [
            {"proposal_digest": f"d{i}{'0'*58}", "group_id": "TRANSITION_EDIT", "group_relevant": True,
             "admissible_for_adjudication": True}
            for i in range(5)
        ]
        row_data = {"proposals": proposals, "conflicts": [], "ordering": {}, "evidence": []}
        result = adjudicate_row(row_data, {})
        abstention = build_abstention_record(result)

        ok, errors = verify_abstention(abstention, result)
        assert ok, f"Abstention verification failed: {errors}"

    def test_insufficient_evidence_abstention(self):
        proposals = [
            {"proposal_digest": f"d{i}{'0'*58}", "group_id": "RATIONALE_DIAGNOSTIC", "group_relevant": True,
             "admissible_for_adjudication": True}
            for i in range(5)
        ]
        row_data = {"proposals": proposals, "conflicts": [], "ordering": {}, "evidence": []}
        result = adjudicate_row(row_data, {})
        abstention = build_abstention_record(result)

        assert abstention["abstained"] is True
        assert abstention["abstention_kind"] == "INSUFFICIENT_EVIDENCE"


class TestReviewRequest:
    def test_review_request_structure(self):
        from elpis_grid81_adjudication.review_request import build_review_request

        envelope = {
            "proposal_set_digest": "p" * 64,
            "source_manifest_sha256": "m" * 64,
            "source_row_digest": "r" * 64,
        }
        policy_result = {
            "request_state": "REVIEW_REQUESTED",
            "review_set": ["a" * 64, "b" * 64],
            "reason_codes": [],
        }

        request = build_review_request(envelope, policy_result, "adj" * 21 + "0")
        assert request["request_state"] == "REVIEW_REQUESTED"
        assert request["required_capability_class"] == "STRUCTURAL_INFLUENCE_CAPABILITY_V1"
        assert len(request["referred_proposal_digests"]) == 2
        assert len(request["claims_not_made"]) > 0

    def test_review_not_requested(self):
        from elpis_grid81_adjudication.review_request import build_review_request

        envelope = {"proposal_set_digest": "p" * 64}
        policy_result = {
            "request_state": "REVIEW_NOT_REQUESTED",
            "review_set": [],
            "reason_codes": ["LOGICAL_CONTRADICTION_PRESENT"],
        }

        request = build_review_request(envelope, policy_result, "adj" * 21 + "0")
        assert request["request_state"] == "REVIEW_NOT_REQUESTED"
        assert request["referred_proposal_digests"] == []
        assert len(request["non_request_reason_codes"]) > 0
