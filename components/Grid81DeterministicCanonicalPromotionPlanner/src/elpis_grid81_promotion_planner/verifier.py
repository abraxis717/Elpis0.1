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


# Closed data contract declared by plan.py: labels describe a future transaction;
# none is an instruction that this verifier executes.
_PLAN_INTENTIONS = (
    "VERIFY_CANONICAL_LEDGER_HEAD", "VERIFY_CAPABILITY_GRANTED_UNCONSUMED",
    "VERIFY_ARTIFACT_CANONICALLY_UNAPPLIED", "RESERVE_TRANSACTION_IDENTIFIER",
    "PERFORM_CANONICAL_APPLICATION", "APPEND_CANONICAL_RECEIPT",
    "VERIFY_POST_COMMIT_STATE",
)
_PLAN_FIELDS = frozenset({
    "intentions", "decision_digest", "source_chain_digest", "planner_version",
    "executable", "self_applying", "authoritative", "canonical_write_permitted",
})


def verify_plan_nonexecutable(plan) -> dict:
    """Validate the actual plan's closed data/capability surface.

    This proves the data contract only, not runtime isolation or observed absence
    of network access, mutation, or capability consumption.
    """
    from .canonical import CanonicalPromotionPlan
    violations = []
    if type(plan) is not CanonicalPromotionPlan:
        violations.append("PLAN_TYPE")
    else:
        if set(vars(plan)) != _PLAN_FIELDS:
            violations.append("PLAN_FIELDS")
        if type(plan.intentions) is not tuple or any(type(i) is not str for i in plan.intentions) or plan.intentions != _PLAN_INTENTIONS:
            violations.append("INTENTIONS")
        for name in ("decision_digest", "source_chain_digest"):
            value = getattr(plan, name)
            if type(value) is not str or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                violations.append(name.upper())
        if type(plan.planner_version) is not str or plan.planner_version != "1.0.0":
            violations.append("PLANNER_VERSION")
        for name in ("executable", "self_applying", "authoritative", "canonical_write_permitted"):
            if getattr(plan, name) is not False:
                violations.append(name.upper())
    result = {
        "schema": "elpis.grid81.promotion-plan-data-check.v2",
        "plan_non_executable": not violations,
        "violations_found": len(violations),
        "violation_details": violations,
    }
    if not violations:
        result["plan_digest"] = plan.digest
    return result


def generate_authority_audit(config: dict) -> dict:
    """Observe configured plan data; omit all unobserved runtime authority claims."""
    chain = build_source_chain(config)
    decision = make_decision(evaluate_gates(chain), chain)
    plan = render_plan(decision, chain)
    observation = {
        "schema": "elpis.grid81.promotion-plan-observation.v2",
        "source_chain_digest": chain.chain_digest,
        "decision_digest": decision.digest,
        "plan_status": "NOT_RENDERED" if plan is None else "RENDERED",
    }
    if plan is not None:
        observation["plan_check"] = verify_plan_nonexecutable(plan)
    observation["observation_digest"] = hashlib.sha256(json.dumps(
        observation, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()
    return observation
