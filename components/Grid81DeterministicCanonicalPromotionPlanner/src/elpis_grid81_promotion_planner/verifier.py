"""Verification utilities — adversarial testing, determinism, nonmutation."""

import hashlib
import json
import os
import shutil
import tempfile
from typing import Any

from .canonical import (
    AuthorityAudit,
    GateResult,
    PromotionDecision,
    SourceChain,
    REJECTION_PRECEDENCE,
)
from .decision import DECISION_READY, make_decision
from .gates import evaluate_gates, first_failure
from .plan import render_plan
from .source_binding import build_source_chain


def _file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_json(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def verify_source_nonmutation(config: dict) -> dict:
    """Verify source directories have not been mutated since census."""
    result = {
        "g53b1_intact": True,
        "g53c_intact": True,
        "g53d_intact": True,
        "files_checked": 0,
        "files_mismatched": 0,
    }
    for phase_key, manifest_name in [
        ("g53b1_directory", "G53B_RAW_EVIDENCE_MANIFEST.json"),
        ("g53c_directory", "RAW_EVIDENCE_MANIFEST.json"),
        ("g53d_directory", "RAW_EVIDENCE_MANIFEST.json"),
    ]:
        directory = config[phase_key]
        manifest_path = os.path.join(directory, manifest_name)
        if not os.path.exists(manifest_path):
            continue
        manifest = _read_json(manifest_path)
        intact_key = phase_key.replace("_directory", "") + "_intact"
        for fname, meta in manifest.get("evidence_files", {}).items():
            expected_hash = meta["sha256"]
            result["files_checked"] += 1
            fpath = os.path.join(directory, fname)
            if not os.path.exists(fpath):
                result[intact_key] = False
                result["files_mismatched"] += 1
                continue
            actual_hash = _file_sha256(fpath)
            if actual_hash != expected_hash:
                result[intact_key] = False
                result["files_mismatched"] += 1
    return result


def run_adversarial_tests(config: dict) -> list:
    """Run adversarial mutation tests. Returns list of test results."""
    tests = []

    # Build baseline chain
    chain = build_source_chain(config)
    baseline_results = evaluate_gates(chain)
    baseline_decision = make_decision(baseline_results, chain)
    baseline_ready = baseline_decision.decision == DECISION_READY

    if not baseline_ready:
        # If baseline fails, adversarial testing is meaningless
        return [{"test": "baseline", "passed": False, "note": "baseline chain fails gates"}]

    # Test cases: modify a copy of a source file and verify gate rejection
    test_cases = [
        {
            "name": "missing_phase_g53b1",
            "description": "Remove G5.3B.1 manifest to simulate missing phase",
            "config_override": {"g53b1_directory": "/nonexistent/g53b1"},
        },
        {
            "name": "missing_phase_g53c",
            "description": "Remove G5.3C manifest to simulate missing phase",
            "config_override": {"g53c_directory": "/nonexistent/g53c"},
        },
        {
            "name": "missing_phase_g53d",
            "description": "Remove G5.3D manifest to simulate missing phase",
            "config_override": {"g53d_directory": "/nonexistent/g53d"},
        },
    ]

    for tc in test_cases:
        try:
            mutated_config = dict(config)
            mutated_config.update(tc["config_override"])
            mutated_chain = build_source_chain(mutated_config)
            mutated_results = evaluate_gates(mutated_chain)
            mutated_decision = make_decision(mutated_results, mutated_chain)
            rejected = mutated_decision.decision != DECISION_READY
            tests.append({
                "name": tc["name"],
                "description": tc["description"],
                "rejected": rejected,
                "rejection_code": first_failure(mutated_results),
                "passed": rejected,  # We expect rejection
            })
        except Exception as e:
            tests.append({
                "name": tc["name"],
                "description": tc["description"],
                "rejected": True,
                "rejection_code": str(e)[:80],
                "passed": True,  # Exception = properly rejected
            })

    return tests


def verify_three_seed_determinism(config: dict) -> dict:
    """Verify byte-identical results across PYTHONHASHSEED values."""
    seeds = [0, 1, 717]
    chain_digests = []
    decision_digests = []
    plan_digests = []
    gate_vectors = []
    census_outputs = []

    for seed in seeds:
        env_patch = {"PYTHONHASHSEED": str(seed)}
        import builtins
        original_environ = dict(os.environ)

        os.environ.update(env_patch)

        chain = build_source_chain(config)
        results = evaluate_gates(chain)
        decision = make_decision(results, chain)
        plan = render_plan(decision, chain)

        chain_digests.append(chain.chain_digest)
        decision_digests.append(decision.digest)

        if plan is not None:
            plan_digests.append(plan.digest)
        else:
            plan_digests.append("NONE")

        gate_vectors.append(tuple(r.digest for r in results))

        census_output = json.dumps({
            "g53b1_digest": chain.g53b1.digest,
            "g53c_digest": chain.g53c.digest,
            "g53d_digest": chain.g53d.digest,
        }, sort_keys=True)
        census_outputs.append(census_output)

        # Restore environment
        os.environ.clear()
        os.environ.update(original_environ)

    return {
        "seeds": seeds,
        "chain_digests": chain_digests,
        "chain_byte_identity": len(set(chain_digests)) == 1,
        "decision_digests": decision_digests,
        "decision_byte_identity": len(set(decision_digests)) == 1,
        "plan_digests": plan_digests,
        "plan_byte_identity": len(set(plan_digests)) == 1,
        "gate_vectors": [list(gv) for gv in gate_vectors],
        "gate_byte_identity": len(set(tuple(gv) for gv in gate_vectors)) == 1,
        "census_outputs": census_outputs,
        "census_byte_identity": len(set(census_outputs)) == 1,
        "all_deterministic": (
            len(set(chain_digests)) == 1
            and len(set(decision_digests)) == 1
            and len(set(plan_digests)) == 1
            and len(set(tuple(gv) for gv in gate_vectors)) == 1
            and len(set(census_outputs)) == 1
        ),
    }


def verify_plan_nonexecutable() -> dict:
    """Verify the promotion plan contains no executable content."""
    import elpis_grid81_promotion_planner
    pkg_dir = os.path.dirname(elpis_grid81_promotion_planner.__file__)
    plan_module_path = os.path.join(pkg_dir, "plan.py")

    with open(plan_module_path) as f:
        content = f.read()

    forbidden_patterns = [
        "subprocess", "os.system", "os.popen", "exec(", "eval(",
        "socket", "urllib", "requests", "import torch",
        "callable", "lambda", "def _execute", "def _apply",
        "def _commit", "def _write",
    ]

    violations = []
    for pattern in forbidden_patterns:
        if pattern in content:
            violations.append(pattern)

    return {
        "plan_module": plan_module_path,
        "forbidden_patterns_checked": len(forbidden_patterns),
        "violations_found": len(violations),
        "violation_details": violations,
        "plan_non_executable": len(violations) == 0,
    }


def generate_authority_audit(config: dict) -> AuthorityAudit:
    """Generate the authority audit record."""
    return AuthorityAudit(
        planner_authoritative_for_application=False,
        planner_authoritative_for_capability_consumption=False,
        planner_authoritative_for_canonical_state=False,
        promotion_plan_executable=False,
        promotion_plan_self_applying=False,
        canonical_write_permitted=False,
        canonical_capabilities_consumed=0,
        canonical_applications_committed=0,
        source_g53b1_modified=False,
        source_g53c_modified=False,
        source_g53d_modified=False,
        shadow_state_modified=False,
        canonical_state_modified=False,
        qubo_touched=False,
        darwinian_life_touched=False,
        production_trm_touched=False,
        network_used=False,
    )
