"""Bounded diagnostic E0R2 harness, not an E1 adapter or E2 materializer.

The snapshot probe asks the existing Projector to preserve explicit R0 facts
as supported state entities/integer quantities alongside an authorized ABSTAIN
operation. It tests whether that preservation supplies writable referents.
Capacity controls are generic independent-operation graphs, NOT a claim that
one operation per microscopic slot is a faithful R0 representation.
No cell or lane is assigned by this harness. All allocation is by project().
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import struct

from elpis_reference.ecs_r0 import (
    Candidate, DEFAULT_ROOT, FrozenTheta, GAUGE, R0Error, Status,
    MutationRequest, Opcode, equivalent, mutate, permute, verify_authority,
)
from elpis_reference.structural_guidance._authority.c2r6p0.contracts import (
    ProjectionInputV1, binding_payload, domain_digest,
)
from elpis_reference.structural_guidance._authority.c2r6p0.projector import project
from elpis_reference.structural_guidance._authority.elpis_p0.semantic_ir import (
    SemanticEntityV1, SemanticOperationV1, SemanticQuantityV1,
    build_semantic_request_v1,
)
from elpis_reference.structural_guidance._authority.elpis_p0.structural_residual import (
    MAX_SEMANTIC_LANES, StructuralSchemaError, validate_transition,
)

PREDICATE = "ecs_r0_participation_status"
MISSING_PRIMITIVE = (
    "A writable binary whole-column participation referent bound to an external "
    "frozen sidecar and operational gauge slot, with deterministic DISABLE/RESTORE "
    "transition and reverse-binding semantics (exact-zero slots remain frozen)."
)


def synthetic_candidate(width: int) -> Candidate:
    """Distinct finite columns, for software fixtures only; no scientific evaluation."""
    raw = b"".join(struct.pack("<d", float(row * width + i + 1))
                   for row in range(6) for i in range(width))
    return Candidate.bind(FrozenTheta(width, raw))


def _slot_id(i: int) -> str:
    return f"slot.{i:03d}"


def _snapshot_probe(candidate: Candidate):
    """Diagnostic snapshot only: quantities have no authorized writable meaning."""
    codes = {Status.DISABLED: 0, Status.ACTIVE: 1, Status.FROZEN_ZERO: 2}
    request = build_semantic_request_v1(
        request_id="ecs.r0.e0r2.snapshot",
        entities=tuple(SemanticEntityV1(
            _slot_id(i), "state",
            f"{GAUGE}:{candidate.theta.digest}:{i}",
        ) for i in range(candidate.width)),
        operations=(SemanticOperationV1("proposal.abstain", "ABSTAIN"),),
        quantities=tuple(SemanticQuantityV1(
            f"participation.{i:03d}", _slot_id(i), PREDICATE, "eq", codes[status],
        ) for i, status in enumerate(candidate.mask)),
    )
    return request, project(ProjectionInputV1.from_signed(request))


def capacity_probe(count: int):
    """Measure actual generic operation capacity; no microscopic semantics claimed."""
    request = build_semantic_request_v1(
        request_id="ecs.r0.e0r2.capacity.control",
        entities=(),
        operations=tuple(SemanticOperationV1(f"abstain.{i:03d}", "ABSTAIN")
                         for i in range(count)),
    )
    return project(ProjectionInputV1.from_signed(request))


@dataclass(frozen=True, slots=True)
class SnapshotEvidenceBinding:
    """Harness evidence binding, deliberately without a Grid81 inverse API."""
    theta_digest: str
    candidate_digest: str
    projection_digest: str
    addresses: tuple[tuple[str, int, bool], ...]


def _evidence_binding(candidate, projection):
    return SnapshotEvidenceBinding(
        candidate.theta.digest, candidate.digest, projection.projection_digest,
        tuple((_slot_id(i), i, status is not Status.FROZEN_ZERO)
              for i, status in enumerate(candidate.mask)),
    )


def validate_snapshot_evidence(candidate, projection, binding) -> None:
    """Fail closed on stale/colliding evidence, without claiming E2 qualification."""
    if type(binding) is not SnapshotEvidenceBinding:
        raise R0Error("EVIDENCE_TYPE")
    if binding.theta_digest != candidate.theta.digest:
        raise R0Error("STALE_THETA")
    if binding.candidate_digest != candidate.digest:
        raise R0Error("STALE_CANDIDATE")
    # Re-run the existing Projector to validate the whole snapshot and its masks.
    _, replay = _snapshot_probe(candidate)
    if (projection != replay or binding.projection_digest != replay.projection_digest):
        raise R0Error("STALE_OR_FORGED_PROJECTION")
    if type(binding.addresses) is not tuple or len(binding.addresses) != candidate.width:
        raise R0Error("REVERSE_BINDING_LENGTH")
    seen_ids, seen_slots = set(), set()
    for item in binding.addresses:
        if type(item) is not tuple or len(item) != 3:
            raise R0Error("OPERATIONAL_ADDRESS")
        semantic_id, slot, writable = item
        if (type(semantic_id) is not str or
                re.fullmatch(r"slot\.[0-9]{3}", semantic_id) is None or
                type(slot) is not int or not 0 <= slot < candidate.width or
                type(writable) is not bool):
            raise R0Error("OPERATIONAL_ADDRESS")
        if semantic_id in seen_ids or slot in seen_slots:
            raise R0Error("REVERSE_BINDING_COLLISION")
        seen_ids.add(semantic_id)
        seen_slots.add(slot)
        if semantic_id != _slot_id(slot):
            raise R0Error("REVERSE_BINDING_MISMATCH")
        if writable != (candidate.mask[slot] is not Status.FROZEN_ZERO):
            raise R0Error("FROZEN_WRITABLE_SWAP")
    if binding.addresses != _evidence_binding(candidate, replay).addresses:
        raise R0Error("REVERSE_BINDING_ORDER")


def _disable(candidate, slot):
    return mutate(candidate, MutationRequest(
        Opcode.DISABLE_COLUMN, candidate.digest, candidate.address(slot))).candidate


def _summary(projection):
    return {
        "status": projection.status,
        "projection_digest": projection.projection_digest,
        "capacity": projection.capacity,
        "error": projection.error.to_dict() if projection.error else None,
        "op_bindings_count": len(projection.bindings.op_bindings),
        "entity_bindings_count": len(projection.bindings.entity_bindings),
        "edge_bindings_count": len(projection.bindings.edge_bindings),
    }


def adjudicate() -> dict:
    widths = []
    for width in (36, 48, 72):
        candidate = synthetic_candidate(width)
        request, snapshot = _snapshot_probe(candidate)
        if snapshot.status != "PROJECTED":
            raise R0Error("UNEXPECTED_SNAPSHOT_REJECTION")
        binding = _evidence_binding(candidate, snapshot)
        validate_snapshot_evidence(candidate, snapshot, binding)
        quantities = snapshot.bindings.edge_bindings
        exact_snapshot = (
            len(snapshot.bindings.entity_bindings) == width and len(quantities) == width and
            all(q.structural_kind == "preserved" and not q.lanes and
                q.payload["predicate"] == PREDICATE and q.payload["value"] == 1
                for q in quantities)
        )
        if not exact_snapshot:
            raise R0Error("SNAPSHOT_BEHAVIOR_CHANGED")
        single = _disable(candidate, 0)
        same_count = _disable(candidate, 1)
        _, one = _snapshot_probe(single)
        _, two = _snapshot_probe(same_count)
        moved, reverse = permute(single, tuple(reversed(range(width))))
        _, permuted = _snapshot_probe(moved)
        moved_binding = _evidence_binding(moved, permuted)
        validate_snapshot_evidence(moved, permuted, moved_binding)
        # Read the allocated operation binding; do not choose a cell or lane.
        op = snapshot.bindings.op_bindings[0]
        after = list(snapshot.grid81)
        after[op.cell] = 0
        try:
            validate_transition(snapshot.grid81, tuple(after), snapshot.structural_schema)
        except StructuralSchemaError as exc:
            transition_rejection = str(exc)
        else:
            raise R0Error("UNEXPECTED_OPERATION_REMOVAL_AUTHORITY")
        control = capacity_probe(width)
        if control.status != "DECOMPOSITION_REQUIRED":
            raise R0Error("UNEXPECTED_CAPACITY_CONTROL")
        widths.append({
            "N": width,
            "r0_editable_slots": width,
            "snapshot_probe": _summary(snapshot),
            "snapshot_facts_preserved": exact_snapshot,
            "participation_writable_referents": 0,
            "reverse_snapshot_binding": "VALIDATED_BUT_NOT_A_WRITABLE_GRID_BINDING",
            "theta_external": True,
            "theta_digest": candidate.theta.digest,
            "candidate_digest": candidate.digest,
            "semantic_request_digest": request.digest,
            "snapshot_binding_digest": domain_digest(
                "elpis.ecs.r0.e0r2.snapshot-evidence.v1", asdict(binding)),
            "single_bit_changes_complete_snapshot_identity":
                snapshot.structural_input_fingerprint != one.structural_input_fingerprint,
            "same_active_count_changes_complete_snapshot_identity":
                one.structural_input_fingerprint != two.structural_input_fingerprint,
            "different_masks_same_grid": snapshot.grid81 == one.grid81 == two.grid81,
            "same_grid_is_not_complete_identity_collision":
                binding_payload(one.bindings) != binding_payload(two.bindings),
            "permutation_equivalence": equivalent(single, moved),
            "permutation_reverse_addressing": all(
                single.theta.column(i) == moved.theta.column(reverse[i]) and
                single.mask[i] is moved.mask[reverse[i]] for i in range(width)),
            "operation_removal_rejection": transition_rejection,
            "generic_operation_capacity_control": _summary(control),
            "capacity_adjudication": (
                "R0_WRITABLE_CAPACITY_UNDEFINED_WITHOUT_MISSING_PRIMITIVE; "
                "snapshot fits; generic one-operation-per-slot control decomposes"
            ),
            "terminal_state": "SEMANTIC_IR_INSUFFICIENT",
        })
    boundary = [dict(operations=count, **_summary(capacity_probe(count)))
                for count in (MAX_SEMANTIC_LANES, MAX_SEMANTIC_LANES + 1)]
    if [item["status"] for item in boundary] != ["PROJECTED", "DECOMPOSITION_REQUIRED"]:
        raise R0Error("CAPACITY_BOUNDARY_CHANGED")
    return {
        "schema": "elpis.ecs.r0.e0r2-result.v1",
        "terminal_state": "SEMANTIC_IR_INSUFFICIENT",
        "unresolved_variables": 1,
        "missing_semantic_primitive": MISSING_PRIMITIVE,
        "unresolved_variable_scope": (
            "One missing executable participation primitive in the existing public "
            "Semantic-IR/Projector contract. Generic Semantic IR can carry its text "
            "and value but grants no writable structural meaning."
        ),
        "authority_digest": verify_authority(),
        "widths": widths,
        "generic_capacity_boundary": boundary,
        "E1_executed": False,
        "E2_executed": False,
        "projector": "elpis_reference.structural_guidance._authority.c2r6p0.projector.project",
        "canonical_grid81_written": False,
        "blocker_fixture": "tests/ecs_r0_e0r2_blocker.json",
        "smallest_next_contract": (
            "Separately adjudicate a sidecar-bound binary participation referent, its "
            "frozen-zero rule, deterministic transition and reverse-binding semantics, "
            "then its actual Grid81 capacity/decomposition. This task changes none of them."
        ),
        "proof_limits": [
            "Snapshot distinction and deterministic evidence binding are proven; E1/E2 round trips are not qualified.",
            "Generic capacity controls do not prove faithful R0 decomposition.",
            "No claim of general ECS equivalence or scientific efficacy.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the bounded ECS R0 E0R2 diagnostic")
    parser.add_argument("--output", type=Path, help="explicit JSON output path")
    args = parser.parse_args()
    result = adjudicate()
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(payload, end="")
    else:
        args.output.write_text(payload, encoding="utf-8")
        print(result["terminal_state"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
