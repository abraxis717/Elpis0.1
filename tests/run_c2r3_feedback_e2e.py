from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from DarwinianMatrix.projector.constraints import (
    ClampOperation,
    ClampProposal,
    ClampState,
    ClampTransaction,
    apply_clamp_transaction,
)
from elpis_reference.feedback_refinement import (
    FEEDBACK_REPROPOSED,
    execute_samsung_feedback_step,
)
from elpis_reference.refinement import solve_sudoku
from elpis_reference.semantic_refinement import (
    SEMANTIC_OBJECT,
    TASK_REJECTION,
    ReverseTraceIndex,
    StructuralObservationRecord,
    TaskDiagnosticV1,
)
from elpis_reference.sudoku import parse_puzzle, validate


SOLVED_TEXT = (
    "534678912672195348198342567859761423426853791713924856"
    "961537284287419635345286179"
)
SOLVED = parse_puzzle(SOLVED_TEXT)


def h(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()

    model_path = args.model.resolve()

    one_blank = parse_puzzle("." + SOLVED_TEXT[1:])
    baseline = solve_sudoku(
        one_blank,
        model_path=model_path,
        device=args.device,
        max_steps=16,
    )

    if baseline.status != "SOLVED" or baseline.solution is None:
        raise RuntimeError("public learned baseline did not solve one-blank fixture")

    prior = tuple(int(value) for value in baseline.solution)
    if not validate(one_blank, prior).valid:
        raise RuntimeError("public learned baseline escaped Sudoku validation")

    state = ClampState.empty("c2r3-reference-e2e")
    evidence_digest = h("c2r3-preexisting-structural-support")

    assertions = tuple(
        ClampProposal(
            proposal_id=f"c2r3-support-{cell:02d}",
            operation=ClampOperation.ASSERT,
            slot_id="c2r3-preexisting-structural-support",
            evidence_digest=evidence_digest,
            cell_index=cell,
            value=prior[cell],
        )
        for cell in range(81)
    )

    initial_tx = ClampTransaction(
        transaction_id="c2r3-initial-structural-support",
        episode_id=state.episode_id,
        expected_state_digest=state.digest(),
        proposals=assertions,
    )
    initial_result = apply_clamp_transaction(
        state=state,
        transaction=initial_tx,
    )
    if not initial_result.accepted:
        raise RuntimeError("canonical Projector rejected C2R3 initial support")

    state_0 = initial_result.state
    semantic_digest = h("c2r3-predeclared-semantic-locus-cell-0")

    diagnostic = TaskDiagnosticV1(
        diagnostic_class=TASK_REJECTION,
        task_scope_id=state_0.episode_id,
        frame_index=0,
        subject_digest=h("c2r3-prior-learned-proposal"),
        producer_id="c2r3.generic-task-validator.v1",
        locus_namespace=SEMANTIC_OBJECT,
        locus_identity=semantic_digest,
        reason_codes=("TASK_REQUIREMENT_UNSATISFIED",),
        details_digest=h("c2r3-generic-task-evidence"),
    )

    forbidden = {
        "grid81_cell_index",
        "grid81_digit",
        "grid81_value",
        "sudoku_error",
        "clamp_operation",
        "clamp_value",
    }
    if forbidden.intersection(diagnostic.payload()):
        raise RuntimeError("task diagnostic leaked structural selection")

    observation = StructuralObservationRecord.create(
        source_semantic_object_digest=semantic_digest,
        topology_vertex_digest=h("c2r3-topology-cell-0"),
        P7_capsule_digest=h("c2r3-capsule-cell-0"),
        P7_primary_cell_index=0,
    )

    traversal = execute_samsung_feedback_step(
        run_id="c2r3-reference-e2e",
        refinement_step_index=0,
        prior_proposal=prior,
        diagnostic=diagnostic,
        reverse_trace=ReverseTraceIndex((observation,)),
        clamp_state=state_0,
        model_path=model_path,
        device=args.device,
        max_model_steps=16,
    )

    if traversal.status != FEEDBACK_REPROPOSED:
        raise RuntimeError(f"unexpected feedback status: {traversal.status}")
    if traversal.released_cells != (0,):
        raise RuntimeError("predeclared residual did not release exactly cell 0")
    if traversal.model_input_changed_cells != (0,):
        raise RuntimeError("release changed learned input outside cell 0")
    if traversal.learned_input != one_blank:
        raise RuntimeError("revised support did not reproduce one-blank model input")
    if traversal.learned_status != "SOLVED":
        raise RuntimeError("Samsung TRM re-proposal did not solve revised support")
    if traversal.learned_solution is None:
        raise RuntimeError("solved re-proposal lacks solution")
    if not validate(one_blank, traversal.learned_solution).valid:
        raise RuntimeError("learned re-proposal escaped validation")

    for cell in range(1, 81):
        if traversal.learned_solution[cell] != prior[cell]:
            raise RuntimeError("learned re-proposal violated surviving support")

    report = {
        "schema": "elpis.public-c2r3-bounded-feedback-e2e.v1",
        "status": "PASS",
        "role": "MECHANISM_COMPOSITION_CONTROL",
        "model_path": str(model_path),
        "baseline_status": baseline.status,
        "baseline_steps": len(baseline.steps),
        "task_failure": {
            "producer_id": diagnostic.producer_id,
            "reason_codes": list(diagnostic.reason_codes),
            "diagnostic_digest": diagnostic.digest(),
            "contains_grid81_cell": False,
            "contains_grid81_value": False,
            "contains_sudoku_error": False,
        },
        "feedback": {
            "run_id": traversal.run_id,
            "refinement_step_index": traversal.refinement_step_index,
            "released_cells": list(traversal.released_cells),
            "model_input_changed_cells": list(
                traversal.model_input_changed_cells
            ),
            "release_transaction_digest": traversal.release_transaction_digest,
            "traversal_digest": traversal.traversal_digest,
            "learned_status": traversal.learned_status,
            "learned_iterations": traversal.learned_iteration_count,
            "surviving_clamps_preserved": True,
        },
        "authority": {
            "task_derived_assert": False,
            "task_derived_replace": False,
            "task_derived_release": True,
            "task_semantics_seen_by_model": False,
            "task_diagnostic_seen_by_model": False,
            "semantic_sidecar_seen_by_model": False,
            "learned_model_task_authority": False,
            "learned_model_structural_authority": False,
            "runtime_admission": False,
        },
        "claims": {
            "one_bounded_feedback_traversal_executed": True,
            "real_learned_reproposal_executed": True,
            "generalized_task_improvement_proven": False,
            "production_validator_ingress_proven": False,
            "production_p5_p6_p7_binding_proven": False,
            "generalization_proven": False,
            "runtime_admission": False,
        },
    }

    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
