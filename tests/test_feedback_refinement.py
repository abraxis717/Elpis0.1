from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

import elpis_reference.feedback_refinement as feedback
from DarwinianMatrix.projector.constraints import (
    ClampOperation,
    ClampProposal,
    ClampState,
    ClampTransaction,
    apply_clamp_transaction,
)
from elpis_reference.projector_release import build_release_transaction
from elpis_reference.refinement import RefinementResult, RefinementStep
from elpis_reference.semantic_refinement import (
    SEMANTIC_OBJECT,
    STRUCTURAL_REJECTION,
    TASK_REJECTION,
    ReverseTraceIndex,
    StructuralObservationRecord,
    TaskDiagnosticV1,
)


SOLVED = tuple(
    int(value)
    for value in (
        "534678912672195348198342567859761423426853791713924856"
        "961537284287419635345286179"
    )
)


def _h(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _state() -> ClampState:
    state = ClampState.empty("c2r3-episode")
    proposals = tuple(
        ClampProposal(
            proposal_id=f"assert-{cell}",
            operation=ClampOperation.ASSERT,
            slot_id=f"slot-{cell}",
            evidence_digest=_h(f"evidence-{cell}"),
            cell_index=cell,
            value=SOLVED[cell],
        )
        for cell in (0, 1, 2)
    )
    tx = ClampTransaction(
        transaction_id="c2r3-initial",
        episode_id=state.episode_id,
        expected_state_digest=state.digest(),
        proposals=proposals,
    )
    result = apply_clamp_transaction(
        state=state,
        transaction=tx,
    )
    assert result.accepted
    return result.state


def _diagnostic(
    diagnostic_class: str = TASK_REJECTION,
    *,
    frame_index: int = 0,
    locus: str | None = None,
) -> TaskDiagnosticV1:
    return TaskDiagnosticV1(
        diagnostic_class=diagnostic_class,
        task_scope_id="c2r3-episode",
        frame_index=frame_index,
        subject_digest=_h("prior-proposal"),
        producer_id="c2r3.generic-task-validator.v1",
        locus_namespace=SEMANTIC_OBJECT,
        locus_identity=locus or _h("semantic-cell-0"),
        reason_codes=("TASK_REQUIREMENT_UNSATISFIED",),
        details_digest=_h("generic-task-evidence"),
    )


def _index() -> ReverseTraceIndex:
    return ReverseTraceIndex(
        (
            StructuralObservationRecord.create(
                source_semantic_object_digest=_h("semantic-cell-0"),
                topology_vertex_digest=_h("topology-cell-0"),
                P7_capsule_digest=_h("capsule-cell-0"),
                P7_primary_cell_index=0,
            ),
        )
    )


def _fake_solved(
    puzzle,
    model_path=None,
    device="auto",
    max_steps=16,
):
    del model_path, device, max_steps
    assert puzzle[0] == 0
    return RefinementResult(
        status="SOLVED",
        solution=SOLVED,
        steps=(
            RefinementStep(
                step=1,
                valid=True,
                complete=True,
                conflicts=(),
                proposal=SOLVED,
            ),
        ),
        device="cpu",
    )


def _released_state(state: ClampState) -> ClampState:
    diagnostic = _diagnostic()
    residual = diagnostic.to_task_residual()
    resolved = _index().resolve(residual)
    _, transaction = build_release_transaction(
        residual=residual,
        resolved=resolved,
        clamp_state=state,
    )
    assert transaction is not None
    result = apply_clamp_transaction(
        state=state,
        transaction=transaction,
    )
    assert result.accepted
    return result.state


def test_release_changes_only_resolved_support_and_reproposes(monkeypatch):
    state = _state()
    diagnostic = _diagnostic()
    captured = {}

    def spy(
        puzzle,
        model_path=None,
        device="auto",
        max_steps=16,
    ):
        captured["puzzle"] = puzzle
        captured["model_path"] = model_path
        captured["device"] = device
        captured["max_steps"] = max_steps
        return _fake_solved(
            puzzle,
            model_path=model_path,
            device=device,
            max_steps=max_steps,
        )

    monkeypatch.setattr(
        feedback,
        "solve_sudoku",
        spy,
    )

    result = feedback.execute_samsung_feedback_step(
        run_id="run-a",
        refinement_step_index=0,
        prior_proposal=SOLVED,
        diagnostic=diagnostic,
        reverse_trace=_index(),
        clamp_state=state,
        model_path=Path("/tmp/model.safetensors"),
        device="cpu",
        max_model_steps=4,
    )

    assert result.status == feedback.FEEDBACK_REPROPOSED
    assert result.released_cells == (0,)
    assert result.model_input_changed_cells == (0,)
    assert result.learned_input is not None
    assert result.learned_input[0] == 0
    assert result.learned_input[1] == SOLVED[1]
    assert result.learned_input[2] == SOLVED[2]
    assert result.learned_status == "SOLVED"
    assert result.learned_solution == SOLVED
    assert captured == {
        "puzzle": result.learned_input,
        "model_path": Path("/tmp/model.safetensors"),
        "device": "cpu",
        "max_steps": 4,
    }

    payload = diagnostic.payload()
    assert "grid81_cell_index" not in payload
    assert "grid81_value" not in payload
    assert "clamp_operation" not in payload


def test_inactive_resolved_support_is_noop_and_skips_model(monkeypatch):
    released_state = _released_state(_state())

    def forbidden(*args, **kwargs):
        raise AssertionError("learned model must not run on NO_RELEASE")

    monkeypatch.setattr(
        feedback,
        "solve_sudoku",
        forbidden,
    )

    second = feedback.execute_samsung_feedback_step(
        run_id="run-a",
        refinement_step_index=0,
        prior_proposal=SOLVED,
        diagnostic=_diagnostic(),
        reverse_trace=_index(),
        clamp_state=released_state,
    )

    assert second.status == feedback.FEEDBACK_NO_RELEASE
    assert second.released_cells == ()
    assert second.model_input_changed_cells == ()
    assert second.learned_input is None
    assert second.learned_status is None
    assert second.clamp_state_before_digest == second.clamp_state_after_digest


def test_structural_rejection_never_reaches_learned_model(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("learned model must not receive structural rejection")

    monkeypatch.setattr(
        feedback,
        "solve_sudoku",
        forbidden,
    )

    with pytest.raises(
        ValueError,
        match="structural rejection cannot become a task residual",
    ):
        feedback.execute_samsung_feedback_step(
            run_id="run-a",
            refinement_step_index=0,
            prior_proposal=SOLVED,
            diagnostic=_diagnostic(STRUCTURAL_REJECTION),
            reverse_trace=_index(),
            clamp_state=_state(),
        )


def test_unknown_semantic_locus_fails_before_model_call(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("learned model must not run for unknown trace")

    monkeypatch.setattr(
        feedback,
        "solve_sudoku",
        forbidden,
    )

    with pytest.raises(
        LookupError,
        match="semantic locus has no structural trace",
    ):
        feedback.execute_samsung_feedback_step(
            run_id="run-a",
            refinement_step_index=0,
            prior_proposal=SOLVED,
            diagnostic=_diagnostic(locus=_h("unknown-semantic")),
            reverse_trace=_index(),
            clamp_state=_state(),
        )


def test_prior_proposal_must_be_structurally_valid(monkeypatch):
    invalid = list(SOLVED)
    invalid[1] = 9

    def forbidden(*args, **kwargs):
        raise AssertionError("learned model must not run for invalid prior proposal")

    monkeypatch.setattr(
        feedback,
        "solve_sudoku",
        forbidden,
    )

    with pytest.raises(
        ValueError,
        match="prior proposal is not structurally valid against active clamps",
    ):
        feedback.execute_samsung_feedback_step(
            run_id="run-a",
            refinement_step_index=0,
            prior_proposal=tuple(invalid),
            diagnostic=_diagnostic(),
            reverse_trace=_index(),
            clamp_state=_state(),
        )


def test_episode_and_step_binding_fail_closed(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("learned model must not run for binding mismatch")

    monkeypatch.setattr(
        feedback,
        "solve_sudoku",
        forbidden,
    )

    original = _diagnostic()
    other = TaskDiagnosticV1(
        diagnostic_class=original.diagnostic_class,
        task_scope_id="other-episode",
        frame_index=original.frame_index,
        subject_digest=original.subject_digest,
        producer_id=original.producer_id,
        locus_namespace=original.locus_namespace,
        locus_identity=original.locus_identity,
        reason_codes=original.reason_codes,
        details_digest=original.details_digest,
    )

    with pytest.raises(
        ValueError,
        match="episode does not match",
    ):
        feedback.execute_samsung_feedback_step(
            run_id="run-a",
            refinement_step_index=0,
            prior_proposal=SOLVED,
            diagnostic=other,
            reverse_trace=_index(),
            clamp_state=_state(),
        )

    with pytest.raises(
        ValueError,
        match="frame does not match",
    ):
        feedback.execute_samsung_feedback_step(
            run_id="run-a",
            refinement_step_index=1,
            prior_proposal=SOLVED,
            diagnostic=_diagnostic(frame_index=0),
            reverse_trace=_index(),
            clamp_state=_state(),
        )


def test_deterministic_traversal_digest(monkeypatch):
    monkeypatch.setattr(
        feedback,
        "solve_sudoku",
        _fake_solved,
    )

    kwargs = dict(
        run_id="run-deterministic",
        refinement_step_index=0,
        prior_proposal=SOLVED,
        diagnostic=_diagnostic(),
        reverse_trace=_index(),
        clamp_state=_state(),
        device="cpu",
        max_model_steps=2,
    )

    first = feedback.execute_samsung_feedback_step(**kwargs)
    second = feedback.execute_samsung_feedback_step(**kwargs)

    assert first.traversal_digest == second.traversal_digest
    assert first.release_transaction_digest == second.release_transaction_digest
    assert first.clamp_state_after_digest == second.clamp_state_after_digest


def test_controller_rejects_invalid_learned_solution(monkeypatch):
    bad = list(SOLVED)
    bad[1] = 9
    bad = tuple(bad)

    def invalid_solver(
        puzzle,
        model_path=None,
        device="auto",
        max_steps=16,
    ):
        del puzzle, model_path, device, max_steps
        return RefinementResult(
            status="SOLVED",
            solution=bad,
            steps=(
                RefinementStep(
                    step=1,
                    valid=True,
                    complete=True,
                    conflicts=(),
                    proposal=bad,
                ),
            ),
            device="cpu",
        )

    monkeypatch.setattr(
        feedback,
        "solve_sudoku",
        invalid_solver,
    )

    with pytest.raises(
        RuntimeError,
        match="escaped Sudoku validation",
    ):
        feedback.execute_samsung_feedback_step(
            run_id="run-a",
            refinement_step_index=0,
            prior_proposal=SOLVED,
            diagnostic=_diagnostic(),
            reverse_trace=_index(),
            clamp_state=_state(),
        )
