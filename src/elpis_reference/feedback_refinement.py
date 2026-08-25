"""One bounded task-feedback traversal into the pinned Samsung TRM reference.

This module composes already-qualified authority boundaries:

task diagnostic -> task residual -> reverse trace -> canonical Projector RELEASE
-> revised clamp support -> Samsung TRM re-proposal -> Sudoku validation.

The learned model receives only the revised Sudoku support grid. It does not
receive task diagnostics, residuals, reverse-trace records, Projector receipts,
or task prose. Task-derived structural mutation remains RELEASE-only because
the transaction is built by the C2R2 adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from DarwinianMatrix.projector.constraints import (
    ClampState,
    apply_clamp_transaction,
)

from .projector_release import build_release_transaction
from .refinement import solve_sudoku
from .semantic_refinement import (
    EvidenceSlotLike,
    ReverseTraceIndex,
    TaskDiagnosticV1,
    domain_digest,
)
from .sudoku import validate


FEEDBACK_REPROPOSED = "FEEDBACK_REPROPOSED"
FEEDBACK_NO_RELEASE = "FEEDBACK_NO_RELEASE"


def _grid_tuple(values: Sequence[int]) -> tuple[int, ...]:
    result = tuple(int(value) for value in values)
    if len(result) != 81:
        raise ValueError("Grid81 proposal must contain 81 cells")
    if any(value < 1 or value > 9 for value in result):
        raise ValueError("prior proposal must be a complete 1..9 Grid81")
    return result


def sudoku_input_from_clamp_state(
    clamp_state: ClampState,
) -> tuple[int, ...]:
    """Project active canonical clamps into the pinned Sudoku input domain."""
    values, mask = clamp_state.trm_inputs()
    return tuple(
        int(values[index].item())
        if bool(mask[index].item())
        else 0
        for index in range(81)
    )


def samsung_proposal_digest(values: Sequence[int]) -> str:
    proposal = _grid_tuple(values)
    return domain_digest(
        "elpis.samsung-feedback-proposal.c2r3.v1",
        {"values": list(proposal)},
    )


@dataclass(frozen=True)
class SamsungFeedbackTraversalV1:
    run_id: str
    refinement_step_index: int
    status: str
    prior_proposal_digest: str
    diagnostic_digest: str
    residual_digest: str
    resolution_digest: str
    release_plan_digest: str
    release_transaction_digest: str | None
    clamp_state_before_digest: str
    clamp_state_after_digest: str
    released_cells: tuple[int, ...]
    model_input_changed_cells: tuple[int, ...]
    learned_input: tuple[int, ...] | None
    learned_status: str | None
    learned_solution: tuple[int, ...] | None
    learned_iteration_count: int
    traversal_digest: str


def execute_samsung_feedback_step(
    *,
    run_id: str,
    refinement_step_index: int,
    prior_proposal: Sequence[int],
    diagnostic: TaskDiagnosticV1,
    reverse_trace: ReverseTraceIndex,
    clamp_state: ClampState,
    evidence_slots: Sequence[EvidenceSlotLike] = (),
    model_path: Path | None = None,
    device: str = "auto",
    max_model_steps: int = 16,
) -> SamsungFeedbackTraversalV1:
    """Execute exactly one task-feedback traversal and at most one re-proposal."""
    if not run_id:
        raise ValueError("run_id cannot be empty")
    if refinement_step_index < 0:
        raise ValueError("refinement_step_index cannot be negative")
    if diagnostic.task_scope_id != clamp_state.episode_id:
        raise ValueError("task diagnostic episode does not match ClampState")
    if diagnostic.frame_index != refinement_step_index:
        raise ValueError("task diagnostic frame does not match refinement step")

    prior = _grid_tuple(prior_proposal)
    prior_digest = samsung_proposal_digest(prior)

    if diagnostic.subject_digest != prior_digest:
        raise ValueError(
            "task diagnostic subject does not match prior proposal"
        )

    before_input = sudoku_input_from_clamp_state(clamp_state)
    prior_verdict = validate(before_input, prior)

    if not prior_verdict.valid:
        raise ValueError(
            "prior proposal is not structurally valid against active clamps"
        )

    residual = diagnostic.to_task_residual()
    resolved = reverse_trace.resolve(
        residual,
        evidence_slots=evidence_slots,
    )
    release_plan, release_transaction = build_release_transaction(
        residual=residual,
        resolved=resolved,
        clamp_state=clamp_state,
    )

    common = {
        "run_id": run_id,
        "refinement_step_index": refinement_step_index,
        "prior_proposal_digest": samsung_proposal_digest(prior),
        "diagnostic_digest": diagnostic.digest(),
        "residual_digest": residual.digest(),
        "resolution_digest": resolved.resolution_digest,
        "release_plan_digest": release_plan.plan_digest,
        "clamp_state_before_digest": clamp_state.digest(),
    }

    if release_transaction is None:
        payload = {
            **common,
            "status": FEEDBACK_NO_RELEASE,
            "release_transaction_digest": None,
            "clamp_state_after_digest": clamp_state.digest(),
            "released_cells": [],
            "model_input_changed_cells": [],
            "learned_input": None,
            "learned_status": None,
            "learned_solution_digest": None,
            "learned_iteration_count": 0,
        }
        return SamsungFeedbackTraversalV1(
            run_id=run_id,
            refinement_step_index=refinement_step_index,
            status=FEEDBACK_NO_RELEASE,
            prior_proposal_digest=str(common["prior_proposal_digest"]),
            diagnostic_digest=str(common["diagnostic_digest"]),
            residual_digest=str(common["residual_digest"]),
            resolution_digest=str(common["resolution_digest"]),
            release_plan_digest=str(common["release_plan_digest"]),
            release_transaction_digest=None,
            clamp_state_before_digest=clamp_state.digest(),
            clamp_state_after_digest=clamp_state.digest(),
            released_cells=(),
            model_input_changed_cells=(),
            learned_input=None,
            learned_status=None,
            learned_solution=None,
            learned_iteration_count=0,
            traversal_digest=domain_digest(
                "elpis.samsung-feedback-traversal.c2r3.v1",
                payload,
            ),
        )

    release_result = apply_clamp_transaction(
        state=clamp_state,
        transaction=release_transaction,
    )

    if not release_result.accepted:
        raise RuntimeError(
            "canonical Projector rejected C2R3 RELEASE: "
            + ",".join(release_result.receipt.reason_codes)
        )

    revised_state = release_result.state
    learned_input = sudoku_input_from_clamp_state(revised_state)
    changed_cells = tuple(
        index
        for index, (before, after) in enumerate(
            zip(before_input, learned_input)
        )
        if before != after
    )

    if changed_cells != release_plan.target_cells:
        raise RuntimeError(
            "RELEASE changed learned input outside resolved active support"
        )

    if any(learned_input[cell] != 0 for cell in release_plan.target_cells):
        raise RuntimeError(
            "released support did not become writable Sudoku input"
        )

    learned = solve_sudoku(
        learned_input,
        model_path=model_path,
        device=device,
        max_steps=max_model_steps,
    )

    learned_solution = (
        tuple(int(value) for value in learned.solution)
        if learned.solution is not None
        else None
    )

    if learned_solution is not None:
        verdict = validate(
            learned_input,
            learned_solution,
        )
        if not verdict.valid:
            raise RuntimeError(
                "learned re-proposal escaped Sudoku validation"
            )

        values, mask = revised_state.trm_inputs()
        for index in range(81):
            if bool(mask[index].item()):
                if learned_solution[index] != int(values[index].item()):
                    raise RuntimeError(
                        "learned re-proposal violated surviving clamp"
                    )

    learned_solution_digest = (
        samsung_proposal_digest(learned_solution)
        if learned_solution is not None
        else None
    )

    payload = {
        **common,
        "status": FEEDBACK_REPROPOSED,
        "release_transaction_digest": release_transaction.digest(),
        "clamp_state_after_digest": revised_state.digest(),
        "released_cells": list(release_plan.target_cells),
        "model_input_changed_cells": list(changed_cells),
        "learned_input": list(learned_input),
        "learned_status": learned.status,
        "learned_solution_digest": learned_solution_digest,
        "learned_iteration_count": len(learned.steps),
    }

    return SamsungFeedbackTraversalV1(
        run_id=run_id,
        refinement_step_index=refinement_step_index,
        status=FEEDBACK_REPROPOSED,
        prior_proposal_digest=str(common["prior_proposal_digest"]),
        diagnostic_digest=str(common["diagnostic_digest"]),
        residual_digest=str(common["residual_digest"]),
        resolution_digest=str(common["resolution_digest"]),
        release_plan_digest=str(common["release_plan_digest"]),
        release_transaction_digest=release_transaction.digest(),
        clamp_state_before_digest=clamp_state.digest(),
        clamp_state_after_digest=revised_state.digest(),
        released_cells=release_plan.target_cells,
        model_input_changed_cells=changed_cells,
        learned_input=learned_input,
        learned_status=learned.status,
        learned_solution=learned_solution,
        learned_iteration_count=len(learned.steps),
        traversal_digest=domain_digest(
            "elpis.samsung-feedback-traversal.c2r3.v1",
            payload,
        ),
    )
