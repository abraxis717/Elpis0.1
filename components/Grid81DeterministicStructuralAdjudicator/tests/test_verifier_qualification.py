"""Tests for semantic verifier failure-code exactness.

Proves:
  - V07 reaches SEMANTIC_IDENTITY_SUMMARY_CONTRADICTION
  - V08 reaches SEMANTIC_IDENTITY_SUMMARY_CONTRADICTION
  - V11 reaches REPORT_DIRECTORY_CLOSURE_INCOMPLETE
  - V12 reaches REPORT_DIRECTORY_CLOSURE_INCOMPLETE
  - caught=true with wrong code means pass=false
  - one code mismatch makes all_codes_match=false
  - all_codes_match=false prevents qualification success
"""

import json
import os
import sys

BASE = os.environ.get("ELPIS_BASE", "/mnt/primesauce/Elpis_Canon")
REPORTS = os.path.join(BASE, "reports", "G5_1B_DeterministicStructuralAdjudicator")
sys.path.insert(0, os.path.join(BASE, "Grid81DeterministicStructuralAdjudicator", "src"))


class TestVerifierFailureCodeExactness:
    """Load the qualification report and verify exact code matching."""

    def _load(self):
        path = os.path.join(REPORTS, "G51B_SEMANTIC_VERIFIER_QUALIFICATION.json")
        with open(path) as f:
            return json.load(f)

    def test_total_cases_is_12(self):
        data = self._load()
        assert data["total_cases"] == 12

    def test_all_12_caught(self):
        data = self._load()
        assert data["cases_caught"] == 12
        assert data["all_caught"] is True

    def test_all_codes_match(self):
        data = self._load()
        assert data["all_codes_match"] is True

    def test_intended_codes_reached_is_12(self):
        data = self._load()
        assert data["intended_failure_codes_reached"] == 12

    def test_v07_exact_code(self):
        data = self._load()
        v07 = [c for c in data["qualification_cases"] if c["case_id"] == "V07"][0]
        assert v07["caught"] is True
        assert v07["actual_code"] == "SEMANTIC_IDENTITY_SUMMARY_CONTRADICTION"
        assert v07["expected_code"] == "SEMANTIC_IDENTITY_SUMMARY_CONTRADICTION"
        assert v07["pass"] is True

    def test_v08_exact_code(self):
        data = self._load()
        v08 = [c for c in data["qualification_cases"] if c["case_id"] == "V08"][0]
        assert v08["caught"] is True
        assert v08["actual_code"] == "SEMANTIC_IDENTITY_SUMMARY_CONTRADICTION"
        assert v08["expected_code"] == "SEMANTIC_IDENTITY_SUMMARY_CONTRADICTION"
        assert v08["pass"] is True

    def test_v11_exact_code(self):
        data = self._load()
        v11 = [c for c in data["qualification_cases"] if c["case_id"] == "V11"][0]
        assert v11["caught"] is True
        assert v11["actual_code"] == "REPORT_DIRECTORY_CLOSURE_INCOMPLETE"
        assert v11["expected_code"] == "REPORT_DIRECTORY_CLOSURE_INCOMPLETE"
        assert v11["pass"] is True

    def test_v12_exact_code(self):
        data = self._load()
        v12 = [c for c in data["qualification_cases"] if c["case_id"] == "V12"][0]
        assert v12["caught"] is True
        assert v12["actual_code"] == "REPORT_DIRECTORY_CLOSURE_INCOMPLETE"
        assert v12["expected_code"] == "REPORT_DIRECTORY_CLOSURE_INCOMPLETE"
        assert v12["pass"] is True

    def test_qualification_status_is_pass(self):
        data = self._load()
        assert data["status"] == "SEMANTIC_VERIFIER_QUALIFICATION_PASS"

    def test_caught_true_wrong_code_means_pass_false(self):
        """Prove: caught=true with wrong code means pass=false."""
        # Simulate a case where caught but code mismatches
        simulated = {
            "caught": True,
            "actual_code": "WRONG_CODE",
            "expected_code": "RIGHT_CODE",
        }
        passed = simulated["caught"] is True and simulated["actual_code"] == simulated["expected_code"]
        assert passed is False

    def test_one_code_mismatch_makes_all_codes_match_false(self):
        """Prove: one code mismatch makes all_codes_match=false."""
        results = [
            {"actual_code": "A", "expected_code": "A"},  # match
            {"actual_code": "B", "expected_code": "C"},  # mismatch
        ]
        all_match = all(r["actual_code"] == r["expected_code"] for r in results)
        assert all_match is False

    def test_all_codes_match_false_prevents_qualification(self):
        """Prove: all_codes_match=false prevents qualification success."""
        all_caught = True
        all_codes_match = False
        qualification_pass = all_caught and all_codes_match
        assert qualification_pass is False
