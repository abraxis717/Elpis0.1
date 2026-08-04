"""Test mutation qualification results."""

import os
import sys
import json

BASE = os.environ.get("ELPIS_BASE", "$ELPIS_CANON_ROOT/Elpis_Canon")
sys.path.insert(0, os.path.join(BASE, "Grid81DeterministicStructuralAdjudicator", "src"))


class TestMutationQualification:
    def test_mutation_results_exist(self):
        path = os.path.join(BASE, "reports", "G5_1B_DeterministicStructuralAdjudicator",
                           "G51B_MUTATION_RESULTS.json")
        assert os.path.exists(path)

    def test_mutation_count(self):
        path = os.path.join(BASE, "reports", "G5_1B_DeterministicStructuralAdjudicator",
                           "G51B_MUTATION_RESULTS.json")
        with open(path) as f:
            data = json.load(f)
        assert data["total_mutations"] == 32
        assert len(data["results"]) == 32

    def test_all_caught(self):
        path = os.path.join(BASE, "reports", "G5_1B_DeterministicStructuralAdjudicator",
                           "G51B_MUTATION_RESULTS.json")
        with open(path) as f:
            data = json.load(f)
        assert data["caught"] == 32
        assert data["missed"] == 0
        assert all(r["caught"] for r in data["results"])

    def test_codes_match(self):
        path = os.path.join(BASE, "reports", "G5_1B_DeterministicStructuralAdjudicator",
                           "G51B_MUTATION_RESULTS.json")
        with open(path) as f:
            data = json.load(f)
        assert data["codes_match"] == 32
        for r in data["results"]:
            if r["caught"]:
                assert r["expected_failure_code"] == r["observed_failure_code"], \
                    f"Mutation {r['mutation_id']}: expected {r['expected_failure_code']}, got {r['observed_failure_code']}"

    def test_mutation_ids_complete(self):
        path = os.path.join(BASE, "reports", "G5_1B_DeterministicStructuralAdjudicator",
                           "G51B_MUTATION_RESULTS.json")
        with open(path) as f:
            data = json.load(f)
        ids = [r["mutation_id"] for r in data["results"]]
        expected = [f"{i:02d}" for i in range(1, 33)]
        assert ids == expected

    def test_mutation_ids_unique(self):
        path = os.path.join(BASE, "reports", "G5_1B_DeterministicStructuralAdjudicator",
                           "G51B_MUTATION_RESULTS.json")
        with open(path) as f:
            data = json.load(f)
        ids = [r["mutation_id"] for r in data["results"]]
        assert len(set(ids)) == len(ids)

    def test_canonical_source_unchanged(self):
        path = os.path.join(BASE, "reports", "G5_1B_DeterministicStructuralAdjudicator",
                           "G51B_MUTATION_RESULTS.json")
        with open(path) as f:
            data = json.load(f)
        for r in data["results"]:
            assert r["canonical_source_unchanged"] is True

    def test_status(self):
        path = os.path.join(BASE, "reports", "G5_1B_DeterministicStructuralAdjudicator",
                           "G51B_MUTATION_RESULTS.json")
        with open(path) as f:
            data = json.load(f)
        assert data["status"] == "G51B_MUTATION_QUALIFICATION_PASS"

    def test_name_binding(self):
        path = os.path.join(BASE, "reports", "G5_1B_DeterministicStructuralAdjudicator",
                           "G51B_MUTATION_RESULTS.json")
        with open(path) as f:
            data = json.load(f)
        for r in data["results"]:
            assert len(r["mutation_name"]) > 0
            assert len(r["target_artifact"]) > 0

    def test_determinism_mutation(self):
        path = os.path.join(BASE, "reports", "G5_1B_DeterministicStructuralAdjudicator",
                           "G51B_MUTATION_RESULTS.json")
        with open(path) as f:
            data = json.load(f)
        det = [r for r in data["results"] if r["mutation_id"] == "31"]
        assert len(det) == 1
        assert det[0]["caught"] is True
        assert det[0]["expected_failure_code"] == "DETERMINISM_MISMATCH"

    def test_evidence_contradiction_mutation(self):
        path = os.path.join(BASE, "reports", "G5_1B_DeterministicStructuralAdjudicator",
                           "G51B_MUTATION_RESULTS.json")
        with open(path) as f:
            data = json.load(f)
        ev = [r for r in data["results"] if r["mutation_id"] == "32"]
        assert len(ev) == 1
        assert ev[0]["caught"] is True
        assert ev[0]["expected_failure_code"] == "SUMMARY_EVIDENCE_CONTRADICTION"
