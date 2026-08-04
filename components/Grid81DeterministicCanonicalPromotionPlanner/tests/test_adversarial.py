"""Tests for adversarial qualification and authority — G5.3E.1 comprehensive matrix."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from elpis_grid81_promotion_planner.verifier import (
    run_adversarial_tests,
    verify_plan_nonexecutable,
    generate_authority_audit,
    verify_three_seed_determinism,
    verify_source_nonmutation,
)
from elpis_grid81_promotion_planner.adversarial_matrix import (
    run_full_adversarial_matrix,
    MUTATION_REGISTRY,
)

CONFIG = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "fixtures", "source_config.json"
)

# Module-level caches to avoid rerunning 30 mutations per test
_CACHE_LEGACY = None
_CACHE_FULL = None


def _load_config():
    with open(CONFIG) as f:
        return json.load(f)


def _get_legacy_results():
    global _CACHE_LEGACY
    if _CACHE_LEGACY is None:
        _CACHE_LEGACY = run_adversarial_tests(_load_config())
    return _CACHE_LEGACY


def _get_full_records():
    global _CACHE_FULL
    if _CACHE_FULL is None:
        _CACHE_FULL = run_full_adversarial_matrix(_load_config())
    return _CACHE_FULL


def _get_record(mutation_id):
    records = _get_full_records()
    for r in records:
        if r["mutation_id"] == mutation_id:
            return r
    raise AssertionError(f"Mutation {mutation_id} not found in records")


# ─── Legacy tests (original 3 missing-phase tests) ───

def test_adversarial_missing_phase_g53b1():
    results = _get_legacy_results()
    missing_b1 = [t for t in results if t["name"] == "missing_phase_g53b1"]
    assert len(missing_b1) == 1
    assert missing_b1[0]["passed"] is True


def test_adversarial_missing_phase_g53c():
    results = _get_legacy_results()
    missing_c = [t for t in results if t["name"] == "missing_phase_g53c"]
    assert len(missing_c) == 1
    assert missing_c[0]["passed"] is True


def test_adversarial_missing_phase_g53d():
    results = _get_legacy_results()
    missing_d = [t for t in results if t["name"] == "missing_phase_g53d"]
    assert len(missing_d) == 1
    assert missing_d[0]["passed"] is True


def test_adversarial_all_rejected():
    results = _get_legacy_results()
    for t in results:
        assert t["passed"] is True, f"Test {t['name']} should reject but passed"


def test_plan_non_executable():
    result = verify_plan_nonexecutable()
    assert result["plan_non_executable"] is True
    assert result["violations_found"] == 0


def test_authority_audit_all_false():
    audit = generate_authority_audit(_load_config())
    assert audit.planner_authoritative_for_application is False
    assert audit.planner_authoritative_for_capability_consumption is False
    assert audit.planner_authoritative_for_canonical_state is False
    assert audit.canonical_write_permitted is False
    assert audit.canonical_capabilities_consumed == 0
    assert audit.qubo_touched is False
    assert audit.darwinian_life_touched is False
    assert audit.production_trm_touched is False
    assert audit.network_used is False


def test_source_nonmutation():
    result = verify_source_nonmutation(_load_config())
    assert result["g53b1_intact"] is True
    assert result["g53c_intact"] is True
    assert result["g53d_intact"] is True
    assert result["files_mismatched"] == 0


def test_three_seed_determinism():
    result = verify_three_seed_determinism(_load_config())
    assert result["all_deterministic"] is True
    assert result["chain_byte_identity"] is True
    assert result["decision_byte_identity"] is True
    assert result["plan_byte_identity"] is True
    assert result["gate_byte_identity"] is True
    assert result["census_byte_identity"] is True


# ─── G5.3E.1 Comprehensive matrix: 30 individual mutation tests ───

# Phase absence mutations (1-4)

def test_mut_01_g53b1_phase_absent():
    r = _get_record("MUT_01")
    assert r["caught"] is True
    assert r["exact_match"] is True
    assert r["actual_rejection_code"] == "SOURCE_MANIFEST_INVALID"
    assert r["plan_emitted"] is False
    assert r["partial_plan_emitted"] is False
    assert r["decision_emitted"] == "NOT_READY_FOR_CANONICAL_REVIEW"


def test_mut_02_g53c_phase_absent():
    r = _get_record("MUT_02")
    assert r["caught"] is True
    assert r["exact_match"] is True
    assert r["actual_rejection_code"] == "SOURCE_MANIFEST_INVALID"
    assert r["plan_emitted"] is False


def test_mut_03_g53d_phase_absent():
    r = _get_record("MUT_03")
    assert r["caught"] is True
    assert r["exact_match"] is True
    assert r["actual_rejection_code"] == "SOURCE_MANIFEST_INVALID"
    assert r["plan_emitted"] is False


def test_mut_04_source_manifest_absent():
    r = _get_record("MUT_04")
    assert r["caught"] is True
    assert r["exact_match"] is True
    assert r["actual_rejection_code"] == "SOURCE_MANIFEST_INVALID"
    assert r["plan_emitted"] is False


# Source evidence mutations (5-8)

def test_mut_05_extra_unbound_evidence():
    r = _get_record("MUT_05")
    assert r["caught"] is True
    assert r["exact_match"] is True
    assert r["actual_rejection_code"] == "SOURCE_HASH_MISMATCH"
    assert r["plan_emitted"] is False


def test_mut_06_source_evidence_byte_corruption():
    r = _get_record("MUT_06")
    assert r["caught"] is True
    assert r["exact_match"] is True
    assert r["actual_rejection_code"] == "SOURCE_HASH_MISMATCH"
    assert r["plan_emitted"] is False


def test_mut_07_source_evidence_size_mismatch():
    r = _get_record("MUT_07")
    assert r["caught"] is True
    assert r["exact_match"] is True
    assert r["plan_emitted"] is False


def test_mut_08_phase_disposition_altered():
    r = _get_record("MUT_08")
    assert r["caught"] is True
    assert r["exact_match"] is True
    assert r["plan_emitted"] is False


# Identity discontinuity mutations (9-11)

def test_mut_09_artifact_digest_discontinuity():
    r = _get_record("MUT_09")
    assert r["caught"] is True
    assert r["exact_match"] is True
    assert r["plan_emitted"] is False


def test_mut_10_capability_digest_discontinuity():
    r = _get_record("MUT_10")
    assert r["caught"] is True
    assert r["exact_match"] is True
    assert r["plan_emitted"] is False


def test_mut_11_compiler_identity_discontinuity():
    r = _get_record("MUT_11")
    assert r["caught"] is True
    assert r["exact_match"] is True
    assert r["plan_emitted"] is False


# Receipt and state mutations (12-14)

def test_mut_12_receipt_digest_altered():
    r = _get_record("MUT_12")
    assert r["caught"] is True
    assert r["exact_match"] is True
    assert r["plan_emitted"] is False


def test_mut_13_shadow_state_result_altered():
    r = _get_record("MUT_13")
    assert r["caught"] is True
    assert r["exact_match"] is True
    assert r["plan_emitted"] is False


def test_mut_14_ledger_head_continuity_broken():
    r = _get_record("MUT_14")
    assert r["caught"] is True
    assert r["exact_match"] is True
    assert r["plan_emitted"] is False


# Qualification falsification mutations (15-19)

def test_mut_15_replay_qualification_falsified():
    r = _get_record("MUT_15")
    assert r["caught"] is True
    assert r["exact_match"] is True
    assert r["plan_emitted"] is False


def test_mut_16_atomicity_qualification_falsified():
    r = _get_record("MUT_16")
    assert r["caught"] is True
    assert r["exact_match"] is True
    assert r["plan_emitted"] is False


def test_mut_17_canonical_nonmutation_falsified():
    r = _get_record("MUT_17")
    assert r["caught"] is True
    assert r["exact_match"] is True
    assert r["plan_emitted"] is False


def test_mut_18_authority_boundary_falsified():
    r = _get_record("MUT_18")
    assert r["caught"] is True
    assert r["exact_match"] is True
    assert r["plan_emitted"] is False


def test_mut_19_three_seed_determinism_falsified():
    r = _get_record("MUT_19")
    assert r["caught"] is True
    assert r["exact_match"] is True
    assert r["plan_emitted"] is False


# Bundle and lifecycle mutations (20-21)

def test_mut_20_g53d_bundle_digest_altered():
    r = _get_record("MUT_20")
    assert r["caught"] is True
    assert r["exact_match"] is True
    assert r["plan_emitted"] is False


def test_mut_21_capability_lifecycle_consumed():
    r = _get_record("MUT_21")
    assert r["caught"] is True
    assert r["exact_match"] is True
    assert r["plan_emitted"] is False


# Executable payload mutations (22-27)

def test_mut_22_plan_executable_true():
    r = _get_record("MUT_22")
    assert r["caught"] is True
    assert r["exact_match"] is True
    assert r["actual_rejection_code"] == "SOURCE_HASH_MISMATCH"
    assert r["plan_emitted"] is False


def test_mut_23_plan_self_applying_true():
    r = _get_record("MUT_23")
    assert r["caught"] is True
    assert r["exact_match"] is True
    assert r["actual_rejection_code"] == "SOURCE_HASH_MISMATCH"
    assert r["plan_emitted"] is False


def test_mut_24_canonical_write_permitted_true():
    r = _get_record("MUT_24")
    assert r["caught"] is True
    assert r["exact_match"] is True
    assert r["actual_rejection_code"] == "SOURCE_HASH_MISMATCH"
    assert r["plan_emitted"] is False


def test_mut_25_shell_command_in_plan():
    r = _get_record("MUT_25")
    assert r["caught"] is True
    assert r["exact_match"] is True
    assert r["actual_rejection_code"] == "SOURCE_HASH_MISMATCH"
    assert r["plan_emitted"] is False


def test_mut_26_python_import_in_plan():
    r = _get_record("MUT_26")
    assert r["caught"] is True
    assert r["exact_match"] is True
    assert r["actual_rejection_code"] == "SOURCE_HASH_MISMATCH"
    assert r["plan_emitted"] is False


def test_mut_27_network_endpoint_in_plan():
    r = _get_record("MUT_27")
    assert r["caught"] is True
    assert r["exact_match"] is True
    assert r["actual_rejection_code"] == "SOURCE_HASH_MISMATCH"
    assert r["plan_emitted"] is False


# Source mutation and collision tests (28-30)

def test_mut_28_source_file_mutated():
    r = _get_record("MUT_28")
    assert r["caught"] is True
    assert r["exact_match"] is True
    assert r["actual_rejection_code"] == "SOURCE_HASH_MISMATCH"
    assert r["plan_emitted"] is False


def test_mut_29_partial_plan_after_rejection():
    r = _get_record("MUT_29")
    assert r["caught"] is True
    assert r["exact_match"] is True
    assert r["partial_plan_emitted"] is False
    assert r["partial_output_detected"] is False
    assert r["decision_emitted"] == "NOT_READY_FOR_CANONICAL_REVIEW"


def test_mut_30_rejection_precedence_collision():
    r = _get_record("MUT_30")
    assert r["caught"] is True
    assert r["exact_match"] is True
    assert r["partial_plan_emitted"] is False


# Aggregate matrix assertions

def test_full_matrix_count():
    records = _get_full_records()
    assert len(records) == 30


def test_full_matrix_all_caught():
    records = _get_full_records()
    for r in records:
        assert r["caught"] is True, f"{r['mutation_id']} not caught"


def test_full_matrix_all_exact():
    records = _get_full_records()
    for r in records:
        assert r["exact_match"] is True, f"{r['mutation_id']} mismatch: {r['expected_rejection_code']} != {r['actual_rejection_code']}"


def test_full_matrix_no_partial_plans():
    records = _get_full_records()
    for r in records:
        assert r["partial_plan_emitted"] is False, f"{r['mutation_id']} emitted partial plan"


def test_full_matrix_all_not_ready():
    records = _get_full_records()
    for r in records:
        assert r["decision_emitted"] == "NOT_READY_FOR_CANONICAL_REVIEW", f"{r['mutation_id']} wrong decision"


def test_full_matrix_no_plan_emitted():
    records = _get_full_records()
    for r in records:
        assert r["plan_emitted"] is False, f"{r['mutation_id']} emitted plan"


def test_full_matrix_mutation_record_digests_present():
    records = _get_full_records()
    for r in records:
        assert len(r["mutation_record_digest"]) == 64, f"{r['mutation_id']} missing digest"


def test_full_matrix_source_digests_present():
    records = _get_full_records()
    for r in records:
        assert len(r["source_before_digest"]) == 64, f"{r['mutation_id']} missing source_before_digest"


def test_full_matrix_executable_payloads_rejected():
    records = _get_full_records()
    exec_ids = {"MUT_22", "MUT_23", "MUT_24", "MUT_25", "MUT_26", "MUT_27"}
    for r in records:
        if r["mutation_id"] in exec_ids:
            assert r["caught"] is True
            assert r["actual_rejection_code"] == "SOURCE_HASH_MISMATCH"


def test_full_matrix_collision_tests_caught():
    records = _get_full_records()
    collision_ids = {"MUT_29", "MUT_30"}
    for r in records:
        if r["mutation_id"] in collision_ids:
            assert r["caught"] is True
            assert r["partial_plan_emitted"] is False
            assert r["partial_output_detected"] is False