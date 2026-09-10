"""Executable representability blocker; no E1/E2 or learned execution."""
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import subprocess
import sys
import json
from pathlib import Path
import struct

import pytest

from elpis_reference.ecs_r0 import (
    Candidate, FrozenTheta, MutationRequest, Opcode, R0Error, Status,
    equivalent, mutate, permute,
)
from elpis_reference.structural_guidance._authority.c2r6p0.contracts import binding_payload
from elpis_reference.structural_guidance._authority.elpis_p0.structural_residual import (
    INVARIANT_KINDS, MAX_SEMANTIC_LANES, StructuralSchemaError, validate_transition,
)
from tools.ecs_r0_e0r2 import (
    PREDICATE, _disable, _evidence_binding, _snapshot_probe,
    adjudicate, capacity_probe, synthetic_candidate, validate_snapshot_evidence,
)

FIXTURE = json.loads(Path(__file__).with_name("ecs_r0_e0r2_blocker.json").read_text())


@pytest.fixture(params=FIXTURE["widths"])
def probe(request):
    candidate = synthetic_candidate(request.param)
    semantic, projection = _snapshot_probe(candidate)
    binding = _evidence_binding(candidate, projection)
    return candidate, semantic, projection, binding


def test_exact_blocker_fixture(probe):
    candidate, request, projection, binding = probe
    assert projection.status == FIXTURE["expected_snapshot_status"]
    request.validate()
    assert len(request.entities) == len(request.quantities) == candidate.width
    assert len(projection.bindings.entity_bindings) == candidate.width
    assert len(projection.bindings.edge_bindings) == candidate.width
    assert {q.payload["subject"] for q in projection.bindings.edge_bindings} == {
        entity.entity_id for entity in request.entities}
    assert all(q.structural_kind == FIXTURE["expected_quantity_structural_kind"]
               and list(q.lanes) == FIXTURE["expected_quantity_lanes"]
               and q.payload["predicate"] == PREDICATE
               and q.payload["value"] == 1 for q in projection.bindings.edge_bindings)
    validate_snapshot_evidence(candidate, projection, binding)
    assert "PARTICIPATION" not in " ".join(INVARIANT_KINDS)
    assert len(projection.grid81) == 81
    assert all(f + w == 1 for f, w in zip(projection.frozen_mask, projection.writable_mask))


def test_no_floats_or_observations_in_grid_or_semantic_request(probe):
    candidate, request, projection, _ = probe
    def walk(value):
        if isinstance(value, dict):
            for k, v in value.items():
                assert k.lower() not in ("s3", "theta", "adjacency", "modules")
                walk(v)
        elif isinstance(value, (tuple, list)):
            for v in value: walk(v)
        else:
            assert not isinstance(value, (float, bytes))
    walk(asdict(request))
    assert all(type(token) is int and 0 <= token <= 9 for token in projection.grid81)
    assert all(candidate.theta.digest in entity.identity for entity in request.entities)
    # The only proposal operation is the R0-authorized abstention. No per-column
    # operation, route, dependency, or module is asserted by the snapshot.
    assert [(op.operation_id, op.operator) for op in request.operations] == [
        ("proposal.abstain", "ABSTAIN")]
    assert not request.relations and not request.dependencies and not request.constraints


def test_single_bit_and_same_count_complete_identity(probe):
    candidate, _, before, _ = probe
    a = _disable(candidate, FIXTURE["same_count_masks"][0][0])
    b = _disable(candidate, FIXTURE["same_count_masks"][1][0])
    _, pa = _snapshot_probe(a)
    _, pb = _snapshot_probe(b)
    assert not equivalent(a, b)
    assert a.mask.count(Status.ACTIVE) == b.mask.count(Status.ACTIVE)
    assert before.grid81 == pa.grid81 == pb.grid81
    assert len({p.structural_input_fingerprint for p in (before, pa, pb)}) == 3
    assert len({p.projection_digest for p in (before, pa, pb)}) == 3
    assert binding_payload(pa.bindings) != binding_payload(pb.bindings)
    assert [q.payload["value"] for q in pa.bindings.edge_bindings] == [
        0 if i == 0 else 1 for i in range(candidate.width)]


def test_every_single_bit_retained_with_no_truncation(probe):
    candidate, _, projection, _ = probe
    identities = {projection.structural_input_fingerprint}
    for slot in range(candidate.width):
        disabled = _disable(candidate, slot)
        _, changed = _snapshot_probe(disabled)
        assert len(changed.bindings.edge_bindings) == candidate.width
        assert [q.payload["value"] for q in changed.bindings.edge_bindings] == [
            int(i != slot) for i in range(candidate.width)]
        identities.add(changed.structural_input_fingerprint)
    assert len(identities) == candidate.width + 1


def test_permutation_and_reverse_addresses(probe):
    candidate, _, _, _ = probe
    candidate = _disable(candidate, 0)
    moved, addresses = permute(candidate, tuple(reversed(range(candidate.width))))
    assert equivalent(candidate, moved)
    assert candidate.equivalence_digest == moved.equivalence_digest
    _, projection = _snapshot_probe(moved)
    validate_snapshot_evidence(moved, projection, _evidence_binding(moved, projection))
    for old, new in enumerate(addresses):
        assert candidate.theta.column(old) == moved.theta.column(new)
        assert candidate.mask[old] == moved.mask[new]
    with pytest.raises(R0Error, match="STALE_ADDRESS"):
        mutate(moved, MutationRequest(Opcode.RESTORE_COLUMN, moved.digest, candidate.address(0)))


@pytest.mark.parametrize("fault", FIXTURE["adversaries"])
def test_adversarial_snapshot_binding(probe, fault):
    candidate, _, projection, binding = probe
    if fault == "stale_theta":
        bad = replace(binding, theta_digest="0" * 64)
    elif fault == "stale_candidate":
        bad = replace(binding, candidate_digest="0" * 64)
    elif fault == "malformed_address":
        bad = replace(binding, addresses=(("slot.-1", -1, True),) + binding.addresses[1:])
    elif fault == "frozen_writable_swap":
        bad = replace(binding, addresses=(("slot.000", 0, False),) + binding.addresses[1:])
    elif fault == "reverse_binding_collision":
        bad = replace(binding, addresses=(binding.addresses[0],) + binding.addresses[:-1])
    else:
        pytest.fail("unknown adversarial fixture")
    with pytest.raises(R0Error): validate_snapshot_evidence(candidate, projection, bad)


def test_true_cross_theta_and_candidate_staleness(probe):
    candidate, _, projection, binding = probe
    changed_theta = Candidate.bind(FrozenTheta(candidate.width,
        struct.pack("<d", -99.0) + candidate.theta.data[8:]))
    with pytest.raises(R0Error, match="STALE_THETA"):
        validate_snapshot_evidence(changed_theta, projection, binding)
    with pytest.raises(R0Error, match="STALE_CANDIDATE"):
        validate_snapshot_evidence(_disable(candidate, 0), projection, binding)


def test_projection_mask_swap_and_stale_digest_rejected(probe):
    candidate, _, projection, binding = probe
    forged = replace(projection, frozen_mask=projection.writable_mask,
                     writable_mask=projection.frozen_mask)
    with pytest.raises(R0Error, match="STALE_OR_FORGED_PROJECTION"):
        validate_snapshot_evidence(candidate, forged, binding)
    with pytest.raises(R0Error, match="STALE_OR_FORGED_PROJECTION"):
        validate_snapshot_evidence(candidate, projection,
                                   replace(binding, projection_digest="0" * 64))


def test_frozen_zero_snapshot_cannot_be_declared_writable(probe):
    candidate, _, _, _ = probe
    raw = bytearray(candidate.theta.data)
    for row in range(6):
        start = row * candidate.width * 8
        raw[start:start + 8] = struct.pack("<d", -0.0)
    candidate = Candidate.bind(FrozenTheta(candidate.width, raw))
    _, projection = _snapshot_probe(candidate)
    binding = _evidence_binding(candidate, projection)
    validate_snapshot_evidence(candidate, projection, binding)
    assert projection.bindings.edge_bindings[0].payload["value"] == 2
    forged = replace(binding, addresses=(("slot.000", 0, True),) + binding.addresses[1:])
    with pytest.raises(R0Error, match="FROZEN_WRITABLE_SWAP"):
        validate_snapshot_evidence(candidate, projection, forged)


def test_cannot_reinterpret_removal_as_participation(probe):
    _, _, projection, _ = probe
    op = projection.bindings.op_bindings[0]
    assert op.frozen and projection.frozen_mask[op.cell] == 1
    after = list(projection.grid81)
    after[op.cell] = 0
    with pytest.raises(StructuralSchemaError):
        validate_transition(projection.grid81, tuple(after), projection.structural_schema)


@pytest.mark.parametrize("count", FIXTURE["generic_operation_capacity_boundary"] + FIXTURE["widths"])
def test_real_projector_capacity_boundary(count):
    result = capacity_probe(count)
    assert result == capacity_probe(count)
    if count <= MAX_SEMANTIC_LANES:
        assert result.status == "PROJECTED"
        assert len(result.bindings.op_bindings) == count
    else:
        assert result.status == "DECOMPOSITION_REQUIRED"
        assert result.error.code == "ERR.DECOMPOSITION_REQUIRED"
        assert result.error.rule == "R15.CAPACITY_LANES"
        assert result.capacity["lanes_required"] == count
        assert not result.bindings.op_bindings
        assert result.structural_schema is None
        assert result.structural_input_fingerprint == ""


def test_terminal_result_and_gates_are_deterministic():
    a = adjudicate()
    assert a == adjudicate()
    assert a["terminal_state"] == FIXTURE["expected_terminal_state"]
    assert a["unresolved_variables"] == 1
    assert not a["E1_executed"] and not a["E2_executed"]
    assert not a["canonical_grid81_written"]
    assert all(item["participation_writable_referents"] == 0 for item in a["widths"])
    assert all(item["single_bit_changes_complete_snapshot_identity"] and
               item["same_active_count_changes_complete_snapshot_identity"] and
               item["permutation_equivalence"] for item in a["widths"])


def test_e0r2_cli_stdout_default_does_not_write_repo(tmp_path):
    root = Path(__file__).resolve().parents[1]
    forbidden = root / "ASTRA_E0R2_RESULT.json"
    assert not forbidden.exists()
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
               PYTHONPATH=str(root / "src"))
    cp = subprocess.run(
        [sys.executable, "-B", str(root / "tools/ecs_r0_e0r2.py")],
        cwd=tmp_path, env=env, text=True, capture_output=True, check=True,
    )
    result = json.loads(cp.stdout)
    assert result["terminal_state"] == "SEMANTIC_IR_INSUFFICIENT"
    assert not forbidden.exists()


def test_e0r2_cli_explicit_output(tmp_path):
    root = Path(__file__).resolve().parents[1]
    target = tmp_path / "result.json"
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
               PYTHONPATH=str(root / "src"))
    cp = subprocess.run(
        [sys.executable, "-B", str(root / "tools/ecs_r0_e0r2.py"),
         "--output", str(target)],
        cwd=tmp_path, env=env, text=True, capture_output=True, check=True,
    )
    assert cp.stdout.strip() == "SEMANTIC_IR_INSUFFICIENT"
    assert json.loads(target.read_text())["terminal_state"] == "SEMANTIC_IR_INSUFFICIENT"
