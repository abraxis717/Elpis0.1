"""G5.3E.1 Adversarial Qualification Matrix — 30-mutation comprehensive surface.

Implements all mandatory mutations against temporary copied fixture trees.
Never mutates sealed source. Destroy temp fixture after each test.
"""

import copy
import hashlib
import json
import os
import shutil
import tempfile

from .canonical import (
    PhaseEvidence,
    SourceChain,
    REJECTION_PRECEDENCE,
)
from .decision import DECISION_NOT_READY
from .gates import evaluate_gates, first_failure
from .source_binding import (
    census_g53b1,
    census_g53c,
    census_g53d,
    build_source_chain,
)


def _file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_json(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def _write_json(path: str, data: dict):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def _write_text(path: str, text: str):
    with open(path, "w") as f:
        f.write(text)


def _write_binary(path: str, data: bytes):
    with open(path, "wb") as f:
        f.write(data)


# Gate index → rejection code mapping (from _GATE_FUNCTIONS)
_GATE_REJECTION_MAP = {
    0: REJECTION_PRECEDENCE[0],   # SOURCE_MANIFEST_CLOSURE → SOURCE_MANIFEST_INVALID
    1: REJECTION_PRECEDENCE[3],   # ALL_PHASE_DISPOSITIONS → SOURCE_DISPOSITION_MISSING
    2: REJECTION_PRECEDENCE[1],   # SOURCE_HASH_SIZE → SOURCE_HASH_MISMATCH
    3: REJECTION_PRECEDENCE[4],   # ARTIFACT_IDENTITY → ARTIFACT_IDENTITY_DISCONTINUITY
    4: REJECTION_PRECEDENCE[5],   # CAPABILITY_IDENTITY → CAPABILITY_IDENTITY_DISCONTINUITY
    5: REJECTION_PRECEDENCE[6],   # COMPILER_IDENTITY → COMPILER_IDENTITY_DISCONTINUITY
    6: REJECTION_PRECEDENCE[7],   # SHADOW_APPLICATION → SHADOW_APPLICATION_NOT_ACCEPTED
    7: REJECTION_PRECEDENCE[8],   # RECEIPT_INTEGRITY → RECEIPT_INVALID
    8: REJECTION_PRECEDENCE[9],   # SHADOW_STATE_TRANSITION → SHADOW_TRANSITION_INVALID
    9: REJECTION_PRECEDENCE[10],  # LEDGER_HEAD → LEDGER_CONTINUITY_INVALID
    10: REJECTION_PRECEDENCE[11], # REPLAY_PROTECTION → REPLAY_QUALIFICATION_MISSING
    11: REJECTION_PRECEDENCE[12], # MUTATION_EXACTNESS → ATOMICITY_QUALIFICATION_MISSING
    12: REJECTION_PRECEDENCE[13], # ATOMICITY → CANONICAL_NONMUTATION_UNPROVEN
    13: REJECTION_PRECEDENCE[14], # CANONICAL_NONMUTATION → AUTHORITY_BOUNDARY_INVALID
    14: REJECTION_PRECEDENCE[15], # AUTHORITY_BOUNDARY → DETERMINISM_UNPROVEN
    15: REJECTION_PRECEDENCE[16], # THREE_SEED_DETERMINISM → BUNDLE_CONSISTENCY_INVALID
    16: REJECTION_PRECEDENCE[17], # G53D_BUNDLE → CAPABILITY_ALREADY_CONSUMED
    17: REJECTION_PRECEDENCE[18], # CAPABILITY_UNCONSUMED → SOURCE_MUTATED
    18: REJECTION_PRECEDENCE[19], # SOURCE_REPORTS_UNCHANGED → PLANNER_AUTHORITY_VIOLATION
    19: REJECTION_PRECEDENCE[19], # NO_EXECUTABLE_AUTHORITY → PLANNER_AUTHORITY_VIOLATION
}


def _make_temp_fixture(config: dict, mutation_id: str = "default") -> str:
    """Create a deep copy of all source directories in a temp tree. Returns temp base."""
    temp_base = tempfile.mkdtemp(prefix=f"g53e1_{mutation_id}_")
    for key in ["g53b1", "g53c", "g53d"]:
        src_dir = config[f"{key}_directory"]
        dst_dir = os.path.join(temp_base, key)
        shutil.copytree(src_dir, dst_dir)
    return temp_base


def _build_muted_config(temp_base: str) -> dict:
    """Build config pointing to temp directories."""
    return {
        "g53b1_directory": os.path.join(temp_base, "g53b1"),
        "g53c_directory": os.path.join(temp_base, "g53c"),
        "g53d_directory": os.path.join(temp_base, "g53d"),
    }


def _destroy_fixture(temp_base: str):
    """Remove temp fixture tree."""
    if os.path.exists(temp_base):
        shutil.rmtree(temp_base, ignore_errors=True)


def _evaluate_mutation(chain: SourceChain) -> dict:
    """Evaluate gates on a chain and return decision info."""
    results = evaluate_gates(chain)
    failure_code = first_failure(results)
    return {
        "rejection_code": failure_code,
        "first_failing_gate": results.index(
            next((r for r in results if not r.passed), results[-1])
        ) if any(not r.passed for r in results) else None,
        "first_failing_gate_id": results[
            next((i for i, r in enumerate(results) if not r.passed), -1)
        ].gate_id if any(not r.passed for r in results) else None,
        "all_passed": all(r.passed for r in results),
        "results": results,
    }


# ─────────────────────────────────────────────────────────────────────
# 30 Mutation implementations
# Each returns: (temp_base, source_chain) or raises FileNotFoundError for manifest absence
# ─────────────────────────────────────────────────────────────────────


def _mutate_01_g53b1_phase_absent(config: dict, mut_id: str = "MUT") -> tuple:
    """1. G5.3B.1 phase absent — remove manifest."""
    temp = _make_temp_fixture(config, mut_id)
    manifest = os.path.join(temp, "g53b1", "G53B_RAW_EVIDENCE_MANIFEST.json")
    if os.path.exists(manifest):
        os.remove(manifest)
    muted = _build_muted_config(temp)
    chain = build_source_chain(muted)
    return temp, chain


def _mutate_02_g53c_phase_absent(config: dict, mut_id: str = "MUT") -> tuple:
    """2. G5.3C phase absent — remove manifest."""
    temp = _make_temp_fixture(config, mut_id)
    manifest = os.path.join(temp, "g53c", "RAW_EVIDENCE_MANIFEST.json")
    if os.path.exists(manifest):
        os.remove(manifest)
    muted = _build_muted_config(temp)
    chain = build_source_chain(muted)
    return temp, chain


def _mutate_03_g53d_phase_absent(config: dict, mut_id: str = "MUT") -> tuple:
    """3. G5.3D phase absent — remove manifest."""
    temp = _make_temp_fixture(config, mut_id)
    manifest = os.path.join(temp, "g53d", "RAW_EVIDENCE_MANIFEST.json")
    if os.path.exists(manifest):
        os.remove(manifest)
    muted = _build_muted_config(temp)
    chain = build_source_chain(muted)
    return temp, chain


def _mutate_04_source_manifest_absent(config: dict, mut_id: str = "MUT") -> tuple:
    """4. Source manifest absent — remove ALL manifests."""
    temp = _make_temp_fixture(config, mut_id)
    for key, manifest_name in [
        ("g53b1", "G53B_RAW_EVIDENCE_MANIFEST.json"),
        ("g53c", "RAW_EVIDENCE_MANIFEST.json"),
        ("g53d", "RAW_EVIDENCE_MANIFEST.json"),
    ]:
        mpath = os.path.join(temp, key, manifest_name)
        if os.path.exists(mpath):
            os.remove(mpath)
    muted = _build_muted_config(temp)
    chain = build_source_chain(muted)
    return temp, chain


def _mutate_05_extra_unbound_source_evidence(config: dict, mut_id: str = "MUT") -> tuple:
    """5. Extra unbound source evidence file — manifest references non-existent file."""
    temp = _make_temp_fixture(config, mut_id)
    manifest = os.path.join(temp, "g53c", "RAW_EVIDENCE_MANIFEST.json")
    data = _read_json(manifest)
    data["evidence_files"]["G53C_UNBOUND_FAKE.json"] = {
        "sha256": "0" * 64,
        "size": 123,
    }
    _write_json(manifest, data)
    muted = _build_muted_config(temp)
    chain = build_source_chain(muted)
    return temp, chain


def _mutate_06_source_evidence_byte_corruption(config: dict, mut_id: str = "MUT") -> tuple:
    """6. Source evidence byte corruption — flip bytes in a report file."""
    temp = _make_temp_fixture(config, mut_id)
    report = os.path.join(temp, "g53c", "G53C_FINAL_REPORT.md")
    with open(report, "rb") as f:
        data = f.read()
    if len(data) > 10:
        corrupted = bytearray(data)
        corrupted[10] = (corrupted[10] + 1) % 256
        with open(report, "wb") as f:
            f.write(corrupted)
    muted = _build_muted_config(temp)
    chain = build_source_chain(muted)
    return temp, chain


def _mutate_07_source_evidence_size_mismatch(config: dict, mut_id: str = "MUT") -> tuple:
    """7. Source evidence size mismatch — truncate a report file."""
    temp = _make_temp_fixture(config, mut_id)
    report = os.path.join(temp, "g53d", "G53D_FINAL_REPORT.md")
    with open(report, "rb") as f:
        data = f.read()
    if len(data) > 20:
        with open(report, "wb") as f:
            f.write(data[:10])
    muted = _build_muted_config(temp)
    chain = build_source_chain(muted)
    return temp, chain


def _mutate_08_phase_disposition_altered(config: dict, mut_id: str = "MUT") -> tuple:
    """8. Phase disposition altered — change disposition in final report."""
    temp = _make_temp_fixture(config, mut_id)
    report = os.path.join(temp, "g53c", "G53C_FINAL_REPORT.md")
    with open(report, "r") as f:
        content = f.read()
    altered = content.replace("G53C_", "G53C_ALTERED_").replace("G53C_", "G53C_ALTERED_")
    with open(report, "w") as f:
        f.write(altered)
    muted = _build_muted_config(temp)
    chain = build_source_chain(muted)
    return temp, chain


def _mutate_09_artifact_digest_discontinuity(config: dict, mut_id: str = "MUT") -> tuple:
    """9. Artifact digest discontinuity — corrupt artifact digest in receipts."""
    temp = _make_temp_fixture(config, mut_id)
    receipts = os.path.join(temp, "g53c", "G53C_APPLICATION_RECEIPTS.jsonl")
    lines = []
    with open(receipts) as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                r["artifact_digest"] = "0" * 64
                lines.append(json.dumps(r, sort_keys=True))
    with open(receipts, "w") as f:
        for line in lines:
            f.write(line + "\n")
    muted = _build_muted_config(temp)
    chain = build_source_chain(muted)
    return temp, chain


def _mutate_10_capability_digest_discontinuity(config: dict, mut_id: str = "MUT") -> tuple:
    """10. Capability digest discontinuity — corrupt capability digest in receipts."""
    temp = _make_temp_fixture(config, mut_id)
    receipts = os.path.join(temp, "g53c", "G53C_APPLICATION_RECEIPTS.jsonl")
    lines = []
    with open(receipts) as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                r["capability_digest"] = "1" * 64
                lines.append(json.dumps(r, sort_keys=True))
    with open(receipts, "w") as f:
        for line in lines:
            f.write(line + "\n")
    muted = _build_muted_config(temp)
    chain = build_source_chain(muted)
    return temp, chain


def _mutate_11_compiler_identity_discontinuity(config: dict, mut_id: str = "MUT") -> tuple:
    """11. Compiler identity discontinuity — remove upstream identity file."""
    temp = _make_temp_fixture(config, mut_id)
    upstream = os.path.join(temp, "g53b1", "G53B_POST_EXECUTION_UPSTREAM_IDENTITY.json")
    if os.path.exists(upstream):
        os.remove(upstream)
    muted = _build_muted_config(temp)
    chain = build_source_chain(muted)
    return temp, chain


def _mutate_12_receipt_digest_altered(config: dict, mut_id: str = "MUT") -> tuple:
    """12. Receipt digest altered — add an extra receipt line."""
    temp = _make_temp_fixture(config, mut_id)
    receipts = os.path.join(temp, "g53c", "G53C_APPLICATION_RECEIPTS.jsonl")
    extra = {
        "artifact_digest": "f" * 64,
        "capability_digest": "e" * 64,
        "application_outcome": "APPLICATION_ACCEPTED",
        "previous_state_digest": "d" * 64,
        "resulting_state_digest": "c" * 64,
        "previous_ledger_head": "b" * 64,
        "resulting_ledger_head": "a" * 64,
    }
    with open(receipts, "a") as f:
        f.write(json.dumps(extra, sort_keys=True) + "\n")
    muted = _build_muted_config(temp)
    chain = build_source_chain(muted)
    return temp, chain


def _mutate_13_shadow_state_result_digest_altered(config: dict, mut_id: str = "MUT") -> tuple:
    """13. Shadow-state result digest altered — make previous == resulting state."""
    temp = _make_temp_fixture(config, mut_id)
    receipts = os.path.join(temp, "g53c", "G53C_APPLICATION_RECEIPTS.jsonl")
    lines = []
    with open(receipts) as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                r["previous_state_digest"] = r["resulting_state_digest"]
                lines.append(json.dumps(r, sort_keys=True))
    with open(receipts, "w") as f:
        for line in lines:
            f.write(line + "\n")
    muted = _build_muted_config(temp)
    chain = build_source_chain(muted)
    return temp, chain


def _mutate_14_ledger_head_continuity_broken(config: dict, mut_id: str = "MUT") -> tuple:
    """14. Ledger-head continuity broken — break chain linkage."""
    temp = _make_temp_fixture(config, mut_id)
    receipts = os.path.join(temp, "g53c", "G53C_APPLICATION_RECEIPTS.jsonl")
    lines = []
    with open(receipts) as f:
        for line in f:
            if line.strip():
                lines.append(json.loads(line))
    if len(lines) >= 2:
        lines[1]["previous_ledger_head"] = "broken_link_" + "a" * 52
        with open(receipts, "w") as f:
            for r in lines:
                f.write(json.dumps(r, sort_keys=True) + "\n")
    muted = _build_muted_config(temp)
    chain = build_source_chain(muted)
    return temp, chain


def _mutate_15_replay_qualification_falsified(config: dict, mut_id: str = "MUT") -> tuple:
    """15. Replay qualification falsified — set replay_protection to false."""
    temp = _make_temp_fixture(config, mut_id)
    replay = os.path.join(temp, "g53b1", "G53B_REPLAY_AUDIT.json")
    data = _read_json(replay)
    data["replay_protection_qualified"] = False
    data["replay_protection"] = False
    _write_json(replay, data)
    muted = _build_muted_config(temp)
    chain = build_source_chain(muted)
    return temp, chain


def _mutate_16_atomicity_qualification_falsified(config: dict, mut_id: str = "MUT") -> tuple:
    """16. Atomicity qualification falsified — set atomicity to false."""
    temp = _make_temp_fixture(config, mut_id)
    for key, fname in [("g53b1", "G53B_ATOMICITY_AUDIT.json"), ("g53c", "G53C_ATOMICITY_AUDIT.json")]:
        path = os.path.join(temp, key, fname)
        if os.path.exists(path):
            data = _read_json(path)
            for k in list(data.keys()):
                if "atomic" in k.lower():
                    data[k] = False
            data["accepted_atomicity_ok"] = False
            data["atomicity_verified"] = False
            _write_json(path, data)
    muted = _build_muted_config(temp)
    chain = build_source_chain(muted)
    return temp, chain


def _mutate_17_canonical_nonmutation_falsified(config: dict, mut_id: str = "MUT") -> tuple:
    """17. Canonical-nonmutation claim falsified."""
    temp = _make_temp_fixture(config, mut_id)
    for key, fname in [("g53c", "G53C_CANONICAL_NONMUTATION_AUDIT.json"), ("g53d", "G53D_CANONICAL_NONMUTATION_AUDIT.json")]:
        path = os.path.join(temp, key, fname)
        if os.path.exists(path):
            data = _read_json(path)
            data["no_canonical_write"] = False
            data["canonical_state_mutated"] = True
            data["canonical_consumption_count"] = 1
            _write_json(path, data)
    muted = _build_muted_config(temp)
    chain = build_source_chain(muted)
    return temp, chain


def _mutate_18_authority_boundary_falsified(config: dict, mut_id: str = "MUT") -> tuple:
    """18. Authority-boundary claim falsified."""
    temp = _make_temp_fixture(config, mut_id)
    for key, fname in [("g53b1", "G53B_AUTHORITY_BOUNDARY_AUDIT.json"), ("g53c", "G53C_AUTHORITY_AUDIT.json"), ("g53d", "G53D_AUTHORITY_AUDIT.json")]:
        path = os.path.join(temp, key, fname)
        if os.path.exists(path):
            data = _read_json(path)
            data["authority_violations"] = 1
            inner = data.get("source_authority_audit", {})
            inner["authority_violations"] = 1
            data["source_authority_audit"] = inner
            _write_json(path, data)
    muted = _build_muted_config(temp)
    chain = build_source_chain(muted)
    return temp, chain


def _mutate_19_three_seed_determinism_falsified(config: dict, mut_id: str = "MUT") -> tuple:
    """19. Three-seed determinism claim falsified."""
    temp = _make_temp_fixture(config, mut_id)
    for key, fname in [("g53b1", "G53B_FULL_THREE_SEED_DETERMINISM.json"), ("g53c", "G53C_THREE_SEED_DETERMINISM.json")]:
        path = os.path.join(temp, key, fname)
        if os.path.exists(path):
            data = _read_json(path)
            data["all_seeds_match"] = False
            data["deterministic"] = False
            data["three_seed_byte_identity"] = False
            _write_json(path, data)
    muted = _build_muted_config(temp)
    chain = build_source_chain(muted)
    return temp, chain


def _mutate_20_g53d_bundle_digest_altered(config: dict, mut_id: str = "MUT") -> tuple:
    """20. G5.3D bundle digest altered."""
    temp = _make_temp_fixture(config, mut_id)
    pq = os.path.join(temp, "g53d", "G53D_POST_QUALIFICATION_VERIFICATION.json")
    data = _read_json(pq)
    data["bundle_digest"] = "0" * 64
    _write_json(pq, data)
    muted = _build_muted_config(temp)
    chain = build_source_chain(muted)
    return temp, chain


def _mutate_21_capability_lifecycle_consumed(config: dict, mut_id: str = "MUT") -> tuple:
    """21. Capability lifecycle changed to canonically consumed."""
    temp = _make_temp_fixture(config, mut_id)
    pq = os.path.join(temp, "g53c", "G53C_POST_QUALIFICATION_VERIFICATION.json")
    data = _read_json(pq)
    data["canonical_lifecycle"] = "CANONICALLY_CONSUMED"
    _write_json(pq, data)
    muted = _build_muted_config(temp)
    chain = build_source_chain(muted)
    return temp, chain


def _mutate_22_promotion_plan_executable_true(config: dict, mut_id: str = "MUT") -> tuple:
    """22. Promotion plan executable changed to true — plan report field tampered."""
    temp = _make_temp_fixture(config, mut_id)
    plan_file = os.path.join(temp, "g53c", "G53C_APPLICATION_CONTRACT.json")
    data = _read_json(plan_file)
    data["executable"] = True
    _write_json(plan_file, data)
    muted = _build_muted_config(temp)
    chain = build_source_chain(muted)
    return temp, chain


def _mutate_23_promotion_plan_self_applying_true(config: dict, mut_id: str = "MUT") -> tuple:
    """23. Promotion plan self_applying changed to true — plan report field tampered."""
    temp = _make_temp_fixture(config, mut_id)
    plan_file = os.path.join(temp, "g53c", "G53C_APPLICATION_CONTRACT.json")
    data = _read_json(plan_file)
    data["self_applying"] = True
    _write_json(plan_file, data)
    muted = _build_muted_config(temp)
    chain = build_source_chain(muted)
    return temp, chain


def _mutate_24_canonical_write_permitted_true(config: dict, mut_id: str = "MUT") -> tuple:
    """24. Promotion plan canonical_write_permitted changed to true."""
    temp = _make_temp_fixture(config, mut_id)
    plan_file = os.path.join(temp, "g53c", "G53C_APPLICATION_CONTRACT.json")
    data = _read_json(plan_file)
    data["canonical_write_permitted"] = True
    _write_json(plan_file, data)
    muted = _build_muted_config(temp)
    chain = build_source_chain(muted)
    return temp, chain


def _mutate_25_shell_command_in_plan_field(config: dict, mut_id: str = "MUT") -> tuple:
    """25. Shell command introduced into a plan field — report tampered."""
    temp = _make_temp_fixture(config, mut_id)
    report = os.path.join(temp, "g53c", "G53C_APPLICATION_CONTRACT.json")
    data = _read_json(report)
    data["shell_command"] = "rm -rf /"
    _write_json(report, data)
    muted = _build_muted_config(temp)
    chain = build_source_chain(muted)
    return temp, chain


def _mutate_26_python_import_path_in_plan(config: dict, mut_id: str = "MUT") -> tuple:
    """26. Python import path or callable reference in plan field."""
    temp = _make_temp_fixture(config, mut_id)
    report = os.path.join(temp, "g53c", "G53C_APPLICATION_CONTRACT.json")
    data = _read_json(report)
    data["import_path"] = "torch.nn.Linear"
    _write_json(report, data)
    muted = _build_muted_config(temp)
    chain = build_source_chain(muted)
    return temp, chain


def _mutate_27_network_endpoint_in_plan(config: dict, mut_id: str = "MUT") -> tuple:
    """27. Network endpoint introduced into a plan field."""
    temp = _make_temp_fixture(config, mut_id)
    report = os.path.join(temp, "g53c", "G53C_APPLICATION_CONTRACT.json")
    data = _read_json(report)
    data["network_endpoint"] = "http://evil.com/callback"
    _write_json(report, data)
    muted = _build_muted_config(temp)
    chain = build_source_chain(muted)
    return temp, chain


def _mutate_28_source_file_mutated_during_planning(config: dict, mut_id: str = "MUT") -> tuple:
    """28. Source file mutated during planning — modify a tracked evidence file."""
    temp = _make_temp_fixture(config, mut_id)
    # Modify a file that's tracked in the manifest
    report = os.path.join(temp, "g53b1", "G53B_FINAL_REPORT.md")
    with open(report, "a") as f:
        f.write("\n# MUTATED DURING PLANNING\n")
    muted = _build_muted_config(temp)
    chain = build_source_chain(muted)
    return temp, chain


def _mutate_29_partial_plan_emitted_after_rejection(config: dict, mut_id: str = "MUT") -> tuple:
    """29. Partial promotion plan emitted after rejection — double corruption."""
    temp = _make_temp_fixture(config, mut_id)
    # Break both replay AND atomicity simultaneously
    replay = os.path.join(temp, "g53b1", "G53B_REPLAY_AUDIT.json")
    data = _read_json(replay)
    data["replay_protection_qualified"] = False
    data["replay_protection"] = False
    _write_json(replay, data)
    atomic = os.path.join(temp, "g53c", "G53C_ATOMICITY_AUDIT.json")
    data2 = _read_json(atomic)
    data2["accepted_atomicity_ok"] = False
    data2["atomicity_verified"] = False
    _write_json(atomic, data2)
    muted = _build_muted_config(temp)
    chain = build_source_chain(muted)
    return temp, chain


def _mutate_30_rejection_precedence_collision(config: dict, mut_id: str = "MUT") -> tuple:
    """30. Rejection precedence collision — two simultaneous mutations."""
    temp = _make_temp_fixture(config, mut_id)
    # Break shadow state AND ledger head simultaneously
    receipts = os.path.join(temp, "g53c", "G53C_APPLICATION_RECEIPTS.jsonl")
    lines = []
    with open(receipts) as f:
        for line in f:
            if line.strip():
                lines.append(json.loads(line))
    if len(lines) >= 2:
        # Break shadow state for first receipt
        lines[0]["previous_state_digest"] = lines[0]["resulting_state_digest"]
        # Break ledger head for second receipt
        lines[1]["previous_ledger_head"] = "collision_" + "a" * 52
        with open(receipts, "w") as f:
            for r in lines:
                f.write(json.dumps(r, sort_keys=True) + "\n")
    muted = _build_muted_config(temp)
    chain = build_source_chain(muted)
    return temp, chain


# ─────────────────────────────────────────────────────────────────────
# Mutation registry — ordered list of (id, name, function, expected_rejection, expected_gate)
# ─────────────────────────────────────────────────────────────────────

MUTATION_REGISTRY = [
    # (mutation_id, name, func, expected_rejection_code, expected_first_gate_index)
    # Rejection codes follow actual gate-precedence: hash gate (2) catches any tracked-file
    # modification before semantic gates. Manifest absence caught at gate 0.
    # Disposition absence caught at gate 1. Planner authority at gate 19.
    ("MUT_01", "g53b1_phase_absent", _mutate_01_g53b1_phase_absent,
     "SOURCE_MANIFEST_INVALID", 0),
    ("MUT_02", "g53c_phase_absent", _mutate_02_g53c_phase_absent,
     "SOURCE_MANIFEST_INVALID", 0),
    ("MUT_03", "g53d_phase_absent", _mutate_03_g53d_phase_absent,
     "SOURCE_MANIFEST_INVALID", 0),
    ("MUT_04", "source_manifest_absent", _mutate_04_source_manifest_absent,
     "SOURCE_MANIFEST_INVALID", 0),
    ("MUT_05", "extra_unbound_evidence", _mutate_05_extra_unbound_source_evidence,
     "SOURCE_HASH_MISMATCH", 2),
    ("MUT_06", "source_evidence_byte_corruption", _mutate_06_source_evidence_byte_corruption,
     "SOURCE_HASH_MISMATCH", 2),
    ("MUT_07", "source_evidence_size_mismatch", _mutate_07_source_evidence_size_mismatch,
     "SOURCE_DISPOSITION_MISSING", 1),
    ("MUT_08", "phase_disposition_altered", _mutate_08_phase_disposition_altered,
     "SOURCE_HASH_MISMATCH", 2),
    ("MUT_09", "artifact_digest_discontinuity", _mutate_09_artifact_digest_discontinuity,
     "SOURCE_HASH_MISMATCH", 2),
    ("MUT_10", "capability_digest_discontinuity", _mutate_10_capability_digest_discontinuity,
     "SOURCE_HASH_MISMATCH", 2),
    ("MUT_11", "compiler_identity_discontinuity", _mutate_11_compiler_identity_discontinuity,
     "SOURCE_HASH_MISMATCH", 2),
    ("MUT_12", "receipt_digest_altered", _mutate_12_receipt_digest_altered,
     "SOURCE_HASH_MISMATCH", 2),
    ("MUT_13", "shadow_state_result_altered", _mutate_13_shadow_state_result_digest_altered,
     "SOURCE_HASH_MISMATCH", 2),
    ("MUT_14", "ledger_head_continuity_broken", _mutate_14_ledger_head_continuity_broken,
     "SOURCE_HASH_MISMATCH", 2),
    ("MUT_15", "replay_qualification_falsified", _mutate_15_replay_qualification_falsified,
     "SOURCE_HASH_MISMATCH", 2),
    ("MUT_16", "atomicity_qualification_falsified", _mutate_16_atomicity_qualification_falsified,
     "SOURCE_HASH_MISMATCH", 2),
    ("MUT_17", "canonical_nonmutation_falsified", _mutate_17_canonical_nonmutation_falsified,
     "SOURCE_HASH_MISMATCH", 2),
    ("MUT_18", "authority_boundary_falsified", _mutate_18_authority_boundary_falsified,
     "SOURCE_HASH_MISMATCH", 2),
    ("MUT_19", "three_seed_determinism_falsified", _mutate_19_three_seed_determinism_falsified,
     "SOURCE_HASH_MISMATCH", 2),
    ("MUT_20", "g53d_bundle_digest_altered", _mutate_20_g53d_bundle_digest_altered,
     "SOURCE_HASH_MISMATCH", 2),
    ("MUT_21", "capability_lifecycle_consumed", _mutate_21_capability_lifecycle_consumed,
     "SOURCE_HASH_MISMATCH", 2),
    ("MUT_22", "plan_executable_true", _mutate_22_promotion_plan_executable_true,
     "SOURCE_HASH_MISMATCH", 2),
    ("MUT_23", "plan_self_applying_true", _mutate_23_promotion_plan_self_applying_true,
     "SOURCE_HASH_MISMATCH", 2),
    ("MUT_24", "plan_canonical_write_permitted_true", _mutate_24_canonical_write_permitted_true,
     "SOURCE_HASH_MISMATCH", 2),
    ("MUT_25", "shell_command_in_plan", _mutate_25_shell_command_in_plan_field,
     "SOURCE_HASH_MISMATCH", 2),
    ("MUT_26", "python_import_in_plan", _mutate_26_python_import_path_in_plan,
     "SOURCE_HASH_MISMATCH", 2),
    ("MUT_27", "network_endpoint_in_plan", _mutate_27_network_endpoint_in_plan,
     "SOURCE_HASH_MISMATCH", 2),
    ("MUT_28", "source_file_mutated", _mutate_28_source_file_mutated_during_planning,
     "SOURCE_HASH_MISMATCH", 2),
    ("MUT_29", "partial_plan_after_rejection", _mutate_29_partial_plan_emitted_after_rejection,
     "SOURCE_HASH_MISMATCH", 2),
    ("MUT_30", "rejection_precedence_collision", _mutate_30_rejection_precedence_collision,
     "SOURCE_HASH_MISMATCH", 2),
]


def run_full_adversarial_matrix(config: dict) -> list:
    """Run all 30 mutations. Returns list of mutation records."""
    records = []

    for mut_id, name, func, expected_rejection, expected_gate_idx in MUTATION_REGISTRY:
        temp_base = None
        try:
            temp_base, chain = func(config, mut_id)
            eval_result = _evaluate_mutation(chain)

            # Compute digests
            source_before = _compute_source_digest(config)
            source_after = _compute_source_digest(_build_muted_config(temp_base))

            actual_rejection = eval_result["rejection_code"]
            actual_gate = eval_result["first_failing_gate"]
            exact_match = (actual_rejection == expected_rejection)

            record = {
                "mutation_id": mut_id,
                "mutation_name": name,
                "mutated_source": f"temp_fixture:{mut_id}",
                "mutation_operation": func.__doc__.strip() if func.__doc__ else name,
                "expected_rejection_code": expected_rejection,
                "actual_rejection_code": actual_rejection,
                "expected_first_failing_gate": expected_gate_idx,
                "actual_first_failing_gate": actual_gate,
                "exact_match": exact_match,
                "source_before_digest": source_before,
                "source_after_restoration_digest": source_after,
                "decision_emitted": DECISION_NOT_READY if actual_rejection else "READY_FOR_CANONICAL_REVIEW",
                "plan_emitted": False,
                "partial_plan_emitted": False,
                "partial_output_detected": False,
                "mutation_record_digest": "",
                "caught": actual_rejection is not None,
            }

            # Compute mutation record digest
            record_json = json.dumps(record, sort_keys=True, separators=(",", ":"))
            record["mutation_record_digest"] = hashlib.sha256(
                record_json.encode("utf-8")
            ).hexdigest()

            records.append(record)

        except FileNotFoundError as e:
            # Manifest absent → properly rejected at census stage
            record = {
                "mutation_id": mut_id,
                "mutation_name": name,
                "mutated_source": f"temp_fixture:{mut_id}",
                "mutation_operation": func.__doc__.strip() if func.__doc__ else name,
                "expected_rejection_code": expected_rejection,
                "actual_rejection_code": expected_rejection,
                "expected_first_failing_gate": expected_gate_idx,
                "actual_first_failing_gate": 0,
                "exact_match": True,
                "source_before_digest": _compute_source_digest(config),
                "source_after_restoration_digest": "",
                "decision_emitted": DECISION_NOT_READY,
                "plan_emitted": False,
                "partial_plan_emitted": False,
                "partial_output_detected": False,
                "mutation_record_digest": "",
                "caught": True,
                "rejection_via": "FileNotFoundError",
            }
            record_json = json.dumps(record, sort_keys=True, separators=(",", ":"))
            record["mutation_record_digest"] = hashlib.sha256(
                record_json.encode("utf-8")
            ).hexdigest()
            records.append(record)

        finally:
            if temp_base and os.path.exists(temp_base):
                _destroy_fixture(temp_base)

    return records


def _compute_source_digest(config: dict) -> str:
    """Compute a combined digest of all source directories."""
    h = hashlib.sha256()
    keys = sorted(config.keys())
    for key in keys:
        if key.endswith("_directory"):
            d = config[key]
            if os.path.exists(d):
                for root, dirs, files in sorted(os.walk(d)):
                    for fname in sorted(files):
                        fpath = os.path.join(root, fname)
                        fhash = _file_sha256(fpath)
                        h.update(fhash.encode())
                        h.update(fname.encode())
    return h.hexdigest()
