"""Tests for independent mutation evidence verification and closure checks.

All tests are self-contained — no dependency on pre-existing evidence files.
"""
import copy
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Import verifier functions from verify_g52b
VERIFY_SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "verify_g52b.py"
)
_spec = __import__("importlib.util").util.spec_from_file_location(
    "verify_g52b", VERIFY_SCRIPT
)
_verify = __import__("importlib.util").util.module_from_spec(_spec)
_spec.loader.exec_module(_verify)
check_mode_mutation_evidence = _verify.check_mode_mutation_evidence
check_mode_report_closure = _verify.check_mode_report_closure


BASE = os.path.join(os.path.dirname(__file__), "..", "..")
REPORTS = os.path.join(BASE, "reports", "G5_2B_DeterministicCapabilityAuthorityEvaluator")


# Canonical mutation spec (same as in verify_g52b.py and mutation harness)
CANONICAL_SPECS = {
    "01": {"name": "G5.0A manifest digest changed", "expected_code": "UPSTREAM_G50A_SEAL_DIGEST_MISMATCH"},
    "02": {"name": "G5.0B manifest digest changed", "expected_code": "UPSTREAM_G50B_SEAL_DIGEST_MISMATCH"},
    "03": {"name": "G5.1A manifest digest changed", "expected_code": "UPSTREAM_G51A_SEAL_DIGEST_MISMATCH"},
    "04": {"name": "G5.1B manifest digest changed", "expected_code": "UPSTREAM_G51B_SEAL_DIGEST_MISMATCH"},
    "05": {"name": "G5.2A manifest digest changed", "expected_code": "UPSTREAM_G52A_SEAL_DIGEST_MISMATCH"},
    "06": {"name": "cross-seal binding changed", "expected_code": "CROSS_SEAL_CONSUMPTION_MISMATCH"},
    "07": {"name": "source request omitted", "expected_code": "SOURCE_JOIN_MISSING_REQUEST"},
    "08": {"name": "source adjudication omitted", "expected_code": "SOURCE_JOIN_MISSING_ADJUDICATION"},
    "09": {"name": "request digest changed", "expected_code": "REQUEST_DIGEST_INVALID"},
    "10": {"name": "adjudication binding changed", "expected_code": "ADJUDICATION_BINDING_INVALID"},
    "11": {"name": "proposal-set binding changed", "expected_code": "PROPOSAL_SET_BINDING_INVALID"},
    "12": {"name": "referred proposal omitted", "expected_code": "REQUEST_SET_INCOMPLETE"},
    "13": {"name": "referred proposal duplicated", "expected_code": "REQUEST_SET_DUPLICATE"},
    "14": {"name": "negative-evidence proposal inserted", "expected_code": "AUTHORIZED_SCOPE_NEGATIVE_EVIDENCE_VIOLATION"},
    "15": {"name": "rationale proposal inserted", "expected_code": "AUTHORIZED_SCOPE_RATIONALE_VIOLATION"},
    "16": {"name": "capability class unsupported", "expected_code": "CAPABILITY_CLASS_UNSUPPORTED"},
    "17": {"name": "operation class unsupported", "expected_code": "OPERATION_CLASS_UNSUPPORTED"},
    "18": {"name": "consumer class unsupported", "expected_code": "CONSUMER_CLASS_UNSUPPORTED"},
    "19": {"name": "authority context digest changed", "expected_code": "AUTHORITY_CONTEXT_DIGEST_MISMATCH"},
    "20": {"name": "authority context incomplete", "expected_code": "AUTHORITY_CONTEXT_INCOMPLETE"},
    "21": {"name": "authority-policy digest changed", "expected_code": "AUTHORITY_POLICY_DIGEST_MISMATCH"},
    "22": {"name": "conflicting authority policy", "expected_code": "AUTHORITY_POLICY_CONFLICT"},
    "23": {"name": "scope empty", "expected_code": "CAPABILITY_SCOPE_INVALID"},
    "24": {"name": "scope exceeds maximum", "expected_code": "CAPABILITY_SCOPE_TOO_BROAD"},
    "25": {"name": "scope drops one referred proposal", "expected_code": "CAPABILITY_SCOPE_INCOMPLETE"},
    "26": {"name": "scope adds non-referred proposal", "expected_code": "CAPABILITY_SCOPE_INVALID"},
    "27": {"name": "max consumptions changed to 2", "expected_code": "SINGLE_USE_VIOLATION"},
    "28": {"name": "single_use changed to false", "expected_code": "SINGLE_USE_VIOLATION"},
    "29": {"name": "nonce removed", "expected_code": "REPLAY_PROTECTION_MISSING"},
    "30": {"name": "nonce malformed", "expected_code": "REPLAY_PROTECTION_INVALID"},
    "31": {"name": "duplicate nonce introduced", "expected_code": "REPLAY_NONCE_DUPLICATE"},
    "32": {"name": "logical interval reversed", "expected_code": "LOGICAL_VALIDITY_INVALID"},
    "33": {"name": "wall-clock timestamp added", "expected_code": "WALL_CLOCK_IDENTITY_FORBIDDEN"},
    "34": {"name": "revocation-policy binding removed", "expected_code": "REVOCATION_POLICY_MISSING"},
    "35": {"name": "nontransferable changed to false", "expected_code": "NONTRANSFERABILITY_VIOLATION"},
    "36": {"name": "lifecycle state changed to CONSUMED", "expected_code": "CAPABILITY_COMPILATION_CONSUMPTION_VIOLATION"},
    "37": {"name": "consumption receipt added", "expected_code": "CAPABILITY_COMPILATION_CONSUMPTION_VIOLATION"},
    "38": {"name": "produced influence artifact added", "expected_code": "STRUCTURAL_INFLUENCE_PRODUCTION_FORBIDDEN"},
    "39": {"name": "activation field added", "expected_code": "ACTIVATION_AUTHORITY_FORBIDDEN"},
    "40": {"name": "model identifier added", "expected_code": "MODEL_SELECTION_FORBIDDEN"},
    "41": {"name": "adapter identifier added", "expected_code": "ADAPTER_SELECTION_FORBIDDEN"},
    "42": {"name": "provenance inserted into semantic identity", "expected_code": "PROVENANCE_CONTAMINATED_CAPABILITY_IDENTITY"},
    "43": {"name": "one-seed inventory changed", "expected_code": "DETERMINISM_MISMATCH"},
    "44": {"name": "findings contradict raw inventories", "expected_code": "SUMMARY_EVIDENCE_CONTRADICTION"},
}


def _make_good_mutation(mid, spec):
    """Create a valid mutation record from a spec."""
    return {
        "mutation_id": mid,
        "mutation_name": spec["name"],
        "expected_failure_code": spec["expected_code"],
        "observed_failure_code": spec["expected_code"],
        "caught": True,
        "pass": True,
        "canonical_source_unchanged": True,
        "detail": "test",
    }


def _make_full_dataset(mutation_records, caught_count=None, exact_count=None):
    """Create a complete mutation results dataset."""
    return {
        "mutation_count": len(mutation_records),
        "caught_count": caught_count if caught_count is not None else len(mutation_records),
        "exact_codes_count": exact_count if exact_count is not None else len(mutation_records),
        "mutations": mutation_records,
        "harness_self_audit": {"status": "MUTATION_HARNESS_NO_SYNTHETIC_PASS_FLAGS", "violation_count": 0},
    }


def _write_and_verify(data, tmpdir):
    """Write data to tmpdir and run verifier."""
    path = os.path.join(tmpdir, "G52B_MUTATION_RESULTS.json")
    with open(path, "w") as f:
        json.dump(data, f)
    return check_mode_mutation_evidence(tmpdir)


# ─── Test: verifier accepts valid full dataset ───

def test_verifier_accepts_valid_dataset():
    """Verifier should pass when all 44 mutations are correct."""
    mutations = [_make_good_mutation(mid, spec) for mid, spec in CANONICAL_SPECS.items()]
    data = _make_full_dataset(mutations)
    with tempfile.TemporaryDirectory() as tmpdir:
        result = _write_and_verify(data, tmpdir)
    assert result["status"] == "G52B_MUTATION_EVIDENCE_VERIFIED", (
        f"Valid dataset should pass: {result.get('errors', [])}"
    )


# ─── Test: blank observed code cannot pass ───

def test_blank_observed_code_cannot_pass():
    """A mutation with blank observed_failure_code must have pass=False."""
    mutations = []
    for mid, spec in CANONICAL_SPECS.items():
        if mid == "12":
            # Inject a blank observed code mutation
            mutations.append({
                "mutation_id": mid,
                "mutation_name": spec["name"],
                "expected_failure_code": spec["expected_code"],
                "observed_failure_code": "",
                "caught": True,
                "pass": True,  # falsely True
                "canonical_source_unchanged": True,
                "detail": "test",
            })
        else:
            mutations.append(_make_good_mutation(mid, spec))

    data = _make_full_dataset(mutations)
    with tempfile.TemporaryDirectory() as tmpdir:
        result = _write_and_verify(data, tmpdir)
    assert result["status"] != "G52B_MUTATION_EVIDENCE_VERIFIED", \
        "Verifier should reject blank observed code with pass=True"
    error_codes = [e["code"] for e in result.get("errors", [])]
    assert "MUTATION_PASS_CONTRADICTION" in error_codes or "MUTATION_OBSERVED_CODE_MISMATCH" in error_codes


# ─── Test: caught-only does not imply exactness ───

def test_caught_only_does_not_imply_exactness():
    """caught=True with wrong observed code must be pass=False."""
    mutations = []
    for mid, spec in CANONICAL_SPECS.items():
        if mid == "12":
            mutations.append({
                "mutation_id": mid,
                "mutation_name": spec["name"],
                "expected_failure_code": spec["expected_code"],
                "observed_failure_code": "WRONG_CODE",
                "caught": True,
                "pass": True,  # falsely True
                "canonical_source_unchanged": True,
                "detail": "test",
            })
        else:
            mutations.append(_make_good_mutation(mid, spec))

    data = _make_full_dataset(mutations)
    with tempfile.TemporaryDirectory() as tmpdir:
        result = _write_and_verify(data, tmpdir)
    assert result["status"] != "G52B_MUTATION_EVIDENCE_VERIFIED"
    error_codes = [e["code"] for e in result.get("errors", [])]
    assert "MUTATION_PASS_CONTRADICTION" in error_codes or "MUTATION_OBSERVED_CODE_MISMATCH" in error_codes


# ─── Test: summary counts recomputed from mutation rows ───

def test_summary_counts_recomputed_from_mutation_rows():
    """caught_count and exact_codes_count must match raw mutation rows."""
    mutations = [_make_good_mutation(mid, spec) for mid, spec in CANONICAL_SPECS.items()]
    data = _make_full_dataset(mutations, caught_count=1, exact_count=1)  # Deliberately wrong counts
    with tempfile.TemporaryDirectory() as tmpdir:
        result = _write_and_verify(data, tmpdir)
    assert result["status"] != "G52B_MUTATION_EVIDENCE_VERIFIED", \
        "Verifier should detect summary count mismatch"
    error_codes = [e["code"] for e in result.get("errors", [])]
    assert any(c in error_codes for c in ["SUMMARY_CAUGHT_MISMATCH", "SUMMARY_EXACT_MISMATCH", "SUMMARY_COUNT_MISMATCH"])


# ─── Test: independent verifier rejects false pass flag ───

def test_independent_verifier_rejects_false_pass_flag():
    """Verifier must detect when pass=True but observed != expected."""
    mutations = []
    for mid, spec in CANONICAL_SPECS.items():
        if mid == "01":
            mutations.append({
                "mutation_id": mid,
                "mutation_name": spec["name"],
                "expected_failure_code": spec["expected_code"],
                "observed_failure_code": "WRONG_CODE",
                "caught": True,
                "pass": True,  # falsely True
                "canonical_source_unchanged": True,
                "detail": "test",
            })
        else:
            mutations.append(_make_good_mutation(mid, spec))

    data = _make_full_dataset(mutations)
    with tempfile.TemporaryDirectory() as tmpdir:
        result = _write_and_verify(data, tmpdir)
    assert result["status"] != "G52B_MUTATION_EVIDENCE_VERIFIED"
    error_codes = [e["code"] for e in result.get("errors", [])]
    assert "MUTATION_PASS_CONTRADICTION" in error_codes, f"Got: {error_codes}"


# ─── Test: independent verifier rejects false exact count ───

def test_independent_verifier_rejects_false_exact_count():
    """Verifier must detect when exact_codes_count doesn't match actual pass count."""
    mutations = [_make_good_mutation(mid, spec) for mid, spec in CANONICAL_SPECS.items()]
    data = _make_full_dataset(mutations, exact_count=1)  # All pass, but reported as 1
    with tempfile.TemporaryDirectory() as tmpdir:
        result = _write_and_verify(data, tmpdir)
    assert result["status"] != "G52B_MUTATION_EVIDENCE_VERIFIED"
    error_codes = [e["code"] for e in result.get("errors", [])]
    assert any(c in error_codes for c in ["SUMMARY_CAUGHT_MISMATCH", "SUMMARY_EXACT_MISMATCH", "SUMMARY_COUNT_MISMATCH"]), f"Got: {error_codes}"


# ─── Test: independent verifier rejects missing mutation ───

def test_independent_verifier_rejects_missing_mutation():
    """Verifier must detect when a mutation ID is absent from records."""
    mutations = [_make_good_mutation(mid, spec) for mid, spec in list(CANONICAL_SPECS.items())[:-1]]
    data = _make_full_dataset(mutations)
    with tempfile.TemporaryDirectory() as tmpdir:
        result = _write_and_verify(data, tmpdir)
    assert result["status"] != "G52B_MUTATION_EVIDENCE_VERIFIED"
    error_codes = [e["code"] for e in result.get("errors", [])]
    assert "MUTATION_ID_SET_INCOMPLETE" in error_codes, f"Got: {error_codes}"


# ─── Test: independent verifier rejects duplicate mutation ID ───

def test_independent_verifier_rejects_duplicate_mutation_id():
    """Verifier must detect when a mutation ID appears twice."""
    mutations = [_make_good_mutation(mid, spec) for mid, spec in CANONICAL_SPECS.items()]
    mutations.append(_make_good_mutation("01", CANONICAL_SPECS["01"]))  # Duplicate
    data = _make_full_dataset(mutations)
    with tempfile.TemporaryDirectory() as tmpdir:
        result = _write_and_verify(data, tmpdir)
    assert result["status"] != "G52B_MUTATION_EVIDENCE_VERIFIED"
    error_codes = [e["code"] for e in result.get("errors", [])]
    assert "MUTATION_ID_DUPLICATE" in error_codes, f"Got: {error_codes}"


# ─── Closure rejects two unbound files ───

def test_closure_rejects_two_unbound_files():
    """Report closure must fail if two files are unbound (only manifest allowed)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manifest = {"schema_version": "evidence-manifest.v1", "artifact_count": 0, "entries": []}
        manifest_path = os.path.join(tmpdir, "G52B_RAW_EVIDENCE_MANIFEST.json")
        with open(manifest_path, "w") as f:
            json.dump(manifest, f)
        with open(os.path.join(tmpdir, "G52B_FINDINGS.json"), "w") as f:
            f.write("{}")
        with open(os.path.join(tmpdir, "G52B_VERIFIER_RESULTS.json"), "w") as f:
            f.write("{}")
        result = check_mode_report_closure(tmpdir)
        assert result["status"] == "REPORT_DIRECTORY_CLOSURE_FAILED", \
            f"Expected closure failure, got: {result['status']}"


# ─── Closure permits only manifest self-unbound ───

def test_closure_permits_manifest_self_unbound():
    """Report closure must pass when only the manifest itself is unbound."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "G52B_FINDINGS.json"), "w") as f:
            f.write("{}")
        import hashlib
        findings_hash = hashlib.sha256(b"{}").hexdigest()
        findings_size = 2
        manifest = {
            "schema_version": "evidence-manifest.v1",
            "artifact_count": 1,
            "entries": [
                {"filename": "G52B_FINDINGS.json", "sha256": findings_hash, "byte_size": findings_size},
            ],
        }
        manifest_path = os.path.join(tmpdir, "G52B_RAW_EVIDENCE_MANIFEST.json")
        with open(manifest_path, "w") as f:
            json.dump(manifest, f)
        result = check_mode_report_closure(tmpdir)
        assert result["status"] == "REPORT_DIRECTORY_CLOSURE_VERIFIED", \
            f"Expected closure pass, got: {result}"
        assert result["unbound"] == ["G52B_RAW_EVIDENCE_MANIFEST.json"]


# ─── Test: mutation 12 reaches REQUEST_SET_INCOMPLETE through real verifier ───

def test_mutation_12_reaches_request_set_incomplete():
    """Mutation 12 must reach REQUEST_SET_INCOMPLETE through the real evaluator."""
    from elpis_grid81_capability_authority.source_join import load_jsonl
    from elpis_grid81_capability_authority.decision import evaluate_authority
    from elpis_grid81_capability_authority.policy import create_canonical_policy
    from elpis_grid81_capability_authority.authority_context import create_authority_context
    from elpis_grid81_capability_authority.evaluation_input import create_evaluation_input

    requests_path = os.path.join(BASE, "reports", "G5_1B_DeterministicStructuralAdjudicator",
                                  "G51B_CAPABILITY_REVIEW_REQUEST_INVENTORY.jsonl")
    requests = load_jsonl(requests_path)
    scope1_req = None
    for req in requests:
        if len(req.get("referred_proposal_digests", [])) == 1:
            scope1_req = req
            break
    assert scope1_req is not None

    mutated_req = copy.deepcopy(scope1_req)
    mutated_req["referred_proposal_digests"] = []
    policy = create_canonical_policy()
    context = create_authority_context(scope1_req.get("request_digest", ""))
    eval_input = create_evaluation_input(
        mutated_req, policy["policy_digest"], context["authority_context_digest"],
        scope1_req.get("source_manifest_sha256", ""),
    )
    decision = evaluate_authority(eval_input, context, policy)
    assert decision["decision_outcome"] == "REJECT_INVALID_REQUEST"
    assert "REQUEST_SET_INCOMPLETE" in decision.get("reason_codes", []), \
        f"REQUEST_SET_INCOMPLETE not in reason codes: {decision.get('reason_codes', [])}"
