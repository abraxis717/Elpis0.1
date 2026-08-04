"""Test disposition records."""

import os
import sys

BASE = os.environ.get("ELPIS_BASE", "$ELPIS_CANON_ROOT/Elpis_Canon")
sys.path.insert(0, os.path.join(BASE, "Grid81DeterministicStructuralAdjudicator", "src"))

from elpis_grid81_adjudication.canonical import canonical_digest
from elpis_grid81_adjudication.dispositions import build_disposition_record, build_dispositions_for_row, verify_dispositions
from elpis_grid81_adjudication.policy import adjudicate_row, REFERRED_FOR_CAPABILITY_REVIEW, NOT_REFERRED_NEGATIVE_EVIDENCE


class TestDispositions:
    def test_build_disposition(self):
        p = {"proposal_digest": "a" * 64, "group_id": "TRANSITION_EDIT", "group_relevant": True}
        pd = {"group_id": "TRANSITION_EDIT", "group_relevant": True, "disposition": REFERRED_FOR_CAPABILITY_REVIEW,
              "reason_codes": ["CAPABILITY_REVIEW_REQUIRED"], "proposal_digest": "a" * 64}
        record = build_disposition_record(p, pd)
        assert record["disposition"] == REFERRED_FOR_CAPABILITY_REVIEW
        assert record["preserved_in_record"] is True
        assert len(record["disposition_digest"]) == 64

    def test_disposition_digest(self):
        p = {"proposal_digest": "b" * 64, "group_id": "QUIESCENCE", "group_relevant": True}
        pd = {"group_id": "QUIESCENCE", "group_relevant": True, "disposition": REFERRED_FOR_CAPABILITY_REVIEW,
              "reason_codes": ["CAPABILITY_REVIEW_REQUIRED"], "proposal_digest": "b" * 64}
        record = build_disposition_record(p, pd)
        # Recompute
        copy_record = {k: v for k, v in record.items() if k != "disposition_digest"}
        expected = canonical_digest(copy_record)
        assert record["disposition_digest"] == expected

    def test_verify_dispositions_complete(self):
        proposals = [
            {"proposal_digest": f"d{i}{'0'*58}", "group_id": "TRANSITION_EDIT", "group_relevant": True,
             "admissible_for_adjudication": True}
            for i in range(5)
        ]
        row_data = {"proposals": proposals, "conflicts": [], "ordering": {}, "evidence": []}
        result = adjudicate_row(row_data, {})
        dispositions = build_dispositions_for_row(proposals, result)

        ok, errors = verify_dispositions(dispositions, proposals)
        assert ok, f"Disposition verification failed: {errors}"

    def test_negative_evidence_preserved(self):
        proposals = [
            {"proposal_digest": f"d0{'0'*63}", "group_id": "TRANSITION_EDIT", "group_relevant": True,
             "admissible_for_adjudication": True},
        ]
        for i in range(1, 5):
            proposals.append({
                "proposal_digest": f"d{i}{'0'*58}",
                "group_id": "RATIONALE_DIAGNOSTIC",
                "group_relevant": False,
                "admissible_for_adjudication": True,
            })
        row_data = {"proposals": proposals, "conflicts": [], "ordering": {}, "evidence": []}
        result = adjudicate_row(row_data, {})
        dispositions = build_dispositions_for_row(proposals, result)

        for d in dispositions:
            if not d["group_relevant"]:
                assert d["disposition"] == NOT_REFERRED_NEGATIVE_EVIDENCE

    def test_all_preserved(self):
        proposals = [
            {"proposal_digest": f"d{i}{'0'*58}", "group_id": "TRANSITION_EDIT", "group_relevant": True,
             "admissible_for_adjudication": True}
            for i in range(5)
        ]
        row_data = {"proposals": proposals, "conflicts": [], "ordering": {}, "evidence": []}
        result = adjudicate_row(row_data, {})
        dispositions = build_dispositions_for_row(proposals, result)

        assert all(d["preserved_in_record"] is True for d in dispositions)


class TestBoundary:
    def test_no_forbidden_imports(self):
        package_dir = os.path.join(BASE, "Grid81DeterministicStructuralAdjudicator", "src")
        forbidden = ["torch", "transformers", "subprocess", "CUDA"]
        for root, dirs, files in os.walk(package_dir):
            for fname in files:
                if fname.endswith(".py"):
                    fpath = os.path.join(root, fname)
                    with open(fpath) as f:
                        content = f.read()
                    for imp in forbidden:
                        assert f"import {imp}" not in content, f"Forbidden import in {fpath}"

    def test_no_activation_fields(self):
        reports = os.path.join(BASE, "reports", "G5_1B_DeterministicStructuralAdjudicator")
        if os.path.exists(os.path.join(reports, "G51B_CAPABILITY_REVIEW_REQUEST_INVENTORY.jsonl")):
            with open(os.path.join(reports, "G51B_CAPABILITY_REVIEW_REQUEST_INVENTORY.jsonl")) as f:
                for line in f:
                    if not line.strip():
                        continue
                    import json
                    record = json.loads(line)
                    assert "capability_token" not in record
                    assert "activation" not in record
                    assert "selected" not in record
                    assert "model_path" not in record
                    assert "adapter_path" not in record


class TestCanonical:
    def test_canonical_json_deterministic(self):
        from elpis_grid81_adjudication.canonical import canonical_json, canonical_digest
        obj = {"b": 2, "a": 1, "c": [3, 1, 2]}
        j1 = canonical_json(obj)
        j2 = canonical_json(obj)
        assert j1 == j2
        assert "a" in j1
        assert j1.index('"a"') < j1.index('"b"')

    def test_canonical_digest_64_chars(self):
        from elpis_grid81_adjudication.canonical import canonical_digest
        digest = canonical_digest({"test": "value"})
        assert len(digest) == 64
        assert all(c in "0123456789abcdef" for c in digest)

    def test_semantic_identity_order_independence(self):
        """Same semantic content, different presentation order -> same digest."""
        from elpis_grid81_adjudication.semantic_identity import compute_semantic_identity

        dispositions1 = [
            {"disposition": "REFERRED_FOR_CAPABILITY_REVIEW", "group_id": "TRANSITION_EDIT",
             "group_relevant": True, "reason_codes": ["CAPABILITY_REVIEW_REQUIRED"],
             "_sort_key": "a", "proposal_digest": "a" * 64},
            {"disposition": "NOT_REFERRED_NEGATIVE_EVIDENCE", "group_id": "RATIONALE_DIAGNOSTIC",
             "group_relevant": False, "reason_codes": ["NEGATIVE_EVIDENCE_PRESERVED"],
             "_sort_key": "b", "proposal_digest": "b" * 64},
        ]
        dispositions2 = list(reversed(dispositions1))
        conflicts = [{"conflict_kind": "SHARED_SUPPORT"}]
        outcome = "REVIEW_SET_FORMED"
        abstention = {"abstention_kind": "NONE"}
        review_set = ["a" * 64]
        request_state = "REVIEW_REQUESTED"
        reason_codes = ["CAPABILITY_REVIEW_REQUIRED", "NEGATIVE_EVIDENCE_PRESERVED"]

        d1 = compute_semantic_identity(dispositions1, conflicts, outcome, abstention, review_set, request_state, reason_codes)
        d2 = compute_semantic_identity(dispositions2, conflicts, outcome, abstention, review_set, request_state, reason_codes)
        assert d1 == d2

    def test_semantic_identity_sensitivity(self):
        """Changing disposition should change semantic digest."""
        from elpis_grid81_adjudication.semantic_identity import compute_semantic_identity

        base_dispositions = [
            {"disposition": "REFERRED_FOR_CAPABILITY_REVIEW", "group_id": "TRANSITION_EDIT",
             "group_relevant": True, "reason_codes": ["CAPABILITY_REVIEW_REQUIRED"],
             "_sort_key": "a", "proposal_digest": "a" * 64},
        ]
        modified_dispositions = [
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

        d1 = compute_semantic_identity(base_dispositions, conflicts, outcome, abstention, review_set, request_state, reason_codes)
        d2 = compute_semantic_identity(modified_dispositions, conflicts, outcome, abstention, review_set, request_state, reason_codes)
        assert d1 != d2


class TestMutations:
    def test_mutation_results_exist(self):
        reports = os.path.join(BASE, "reports", "G5_1B_DeterministicStructuralAdjudicator")
        mutation_path = os.path.join(reports, "G51B_MUTATION_RESULTS.json")
        if os.path.exists(mutation_path):
            import json
            with open(mutation_path) as f:
                data = json.load(f)
            assert data["caught"] == 32
            assert data["status"] == "G51B_MUTATION_QUALIFICATION_PASS"
