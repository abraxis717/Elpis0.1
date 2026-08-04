"""Test review request records."""

import os
import sys

BASE = os.environ.get("ELPIS_BASE", "$ELPIS_CANON_ROOT/Elpis_Canon")
sys.path.insert(0, os.path.join(BASE, "Grid81DeterministicStructuralAdjudicator", "src"))

from elpis_grid81_adjudication.canonical import canonical_digest
from elpis_grid81_adjudication.review_request import build_review_request, verify_review_request


class TestReviewRequest:
    def test_review_requested(self):
        envelope = {"proposal_set_digest": "p" * 64}
        policy = {
            "request_state": "REVIEW_REQUESTED",
            "review_set": ["a" * 64],
            "reason_codes": [],
        }
        request = build_review_request(envelope, policy, "adj" * 21 + "0")
        assert request["request_state"] == "REVIEW_REQUESTED"
        assert request["required_capability_class"] == "STRUCTURAL_INFLUENCE_CAPABILITY_V1"
        assert "claims_not_made" in request

    def test_review_not_requested(self):
        envelope = {"proposal_set_digest": "p" * 64}
        policy = {
            "request_state": "REVIEW_NOT_REQUESTED",
            "review_set": [],
            "reason_codes": ["LOGICAL_CONTRADICTION_PRESENT"],
        }
        request = build_review_request(envelope, policy, "adj" * 21 + "0")
        assert request["request_state"] == "REVIEW_NOT_REQUESTED"
        assert request["referred_proposal_digests"] == []

    def test_no_forbidden_fields(self):
        envelope = {"proposal_set_digest": "p" * 64}
        policy = {
            "request_state": "REVIEW_REQUESTED",
            "review_set": ["a" * 64],
            "reason_codes": [],
        }
        request = build_review_request(envelope, policy, "adj" * 21 + "0")
        forbidden = {"capability_token", "activation", "selected", "model_path", "adapter_path",
                     "device", "port", "command", "runtime"}
        for field in forbidden:
            assert field not in request, f"Forbidden field: {field}"

    def test_request_digest(self):
        envelope = {"proposal_set_digest": "p" * 64}
        policy = {
            "request_state": "REVIEW_REQUESTED",
            "review_set": ["a" * 64],
            "reason_codes": [],
        }
        request = build_review_request(envelope, policy, "adj" * 21 + "0")
        copy = {k: v for k, v in request.items() if k != "request_digest"}
        expected = canonical_digest(copy)
        assert request["request_digest"] == expected

    def test_claims_not_made(self):
        envelope = {"proposal_set_digest": "p" * 64}
        policy = {
            "request_state": "REVIEW_REQUESTED",
            "review_set": ["a" * 64],
            "reason_codes": [],
        }
        request = build_review_request(envelope, policy, "adj" * 21 + "0")
        assert len(request["claims_not_made"]) >= 5
        assert any("capability" in claim.lower() for claim in request["claims_not_made"])
