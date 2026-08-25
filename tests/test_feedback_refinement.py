from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

import elpis_reference.feedback_refinement as feedback
from DarwinianMatrix.projector.constraints import (
    ClampOperation, ClampProposal, ClampState, ClampTransaction, apply_clamp_transaction,
)
from elpis_reference.projector_release import ReleaseBindingTableV1, ReleaseBindingTargetV1
from elpis_reference.refinement import RefinementResult, RefinementStep
from elpis_reference.semantic_refinement import (
    SEMANTIC_OBJECT, STRUCTURAL_REJECTION, TASK_REJECTION,
    ReverseTraceIndex, StructuralObservationRecord, TaskDiagnosticV1,
)

SOLVED = tuple(int(v) for v in (
    "534678912672195348198342567859761423426853791713924856"
    "961537284287419635345286179"
))
IMMUTABLE = (0, SOLVED[1], SOLVED[2]) + (0,) * 78


def _h(text): return hashlib.sha256(text.encode()).hexdigest()


def _state():
    state = ClampState.empty("c2r4-feedback-episode")
    proposals = tuple(
        ClampProposal(
            proposal_id=f"assert-{cell}", operation=ClampOperation.ASSERT,
            slot_id=f"slot-{cell}", evidence_digest=_h(f"evidence-{cell}"),
            cell_index=cell, value=SOLVED[cell],
        ) for cell in (0,1,2)
    )
    tx = ClampTransaction(
        transaction_id="initial", episode_id=state.episode_id,
        expected_state_digest=state.digest(), proposals=proposals,
    )
    result = apply_clamp_transaction(state=state, transaction=tx)
    assert result.accepted
    return result.state


def _diag(locus="semantic-cell-0", cls=TASK_REJECTION, frame=0):
    return TaskDiagnosticV1(
        diagnostic_class=cls, task_scope_id="c2r4-feedback-episode", frame_index=frame,
        subject_digest=feedback.samsung_proposal_digest(SOLVED),
        producer_id="c2r4.task-validator.v1", locus_namespace=SEMANTIC_OBJECT,
        locus_identity=_h(locus), reason_codes=("TASK_REQUIREMENT_UNSATISFIED",),
        details_digest=_h("details"),
    )


def _index(cell=0, semantic="semantic-cell-0"):
    return ReverseTraceIndex((StructuralObservationRecord.create(
        source_semantic_object_digest=_h(semantic),
        topology_vertex_digest=_h(f"topology-{cell}"),
        P7_capsule_digest=_h(f"capsule-{cell}"),
        P7_primary_cell_index=cell,
    ),))


def _bindings(state, cell=0, owner="slot-0", semantic="semantic-cell-0"):
    return ReleaseBindingTableV1(
        episode_id=state.episode_id, clamp_state_digest=state.digest(),
        targets=(ReleaseBindingTargetV1(
            cell_index=cell, owner=owner, locus_namespace=SEMANTIC_OBJECT,
            locus_identity=_h(semantic),
        ),),
    )


def _fake_solved(puzzle, model_path=None, device="auto", max_steps=16):
    del model_path, device, max_steps
    assert puzzle[0] == 0
    return RefinementResult(
        status="SOLVED", solution=SOLVED,
        steps=(RefinementStep(step=1, valid=True, complete=True, conflicts=(), proposal=SOLVED),),
        device="cpu",
    )


def test_release_changes_one_bound_nonimmutable_cell_and_reproposes(monkeypatch):
    state = _state(); captured={}
    def spy(puzzle, model_path=None, device="auto", max_steps=16):
        captured["puzzle"]=puzzle
        return _fake_solved(puzzle, model_path, device, max_steps)
    monkeypatch.setattr(feedback, "solve_sudoku", spy)
    result = feedback.execute_samsung_feedback_step(
        run_id="run-a", refinement_step_index=0, prior_proposal=SOLVED,
        diagnostic=_diag(), reverse_trace=_index(), clamp_state=state,
        release_bindings=_bindings(state), immutable_givens=IMMUTABLE,
        model_path=Path("/tmp/model.safetensors"), device="cpu", max_model_steps=4,
    )
    assert result.status == feedback.FEEDBACK_REPROPOSED
    assert result.released_cells == (0,)
    assert result.model_input_changed_cells == (0,)
    assert result.learned_solution == SOLVED
    assert captured["puzzle"][0] == 0


def test_immutable_given_cannot_be_released(monkeypatch):
    state = _state()
    monkeypatch.setattr(feedback, "solve_sudoku", lambda *a, **k: (_ for _ in ()).throw(AssertionError()))
    with pytest.raises(ValueError, match="cannot RELEASE an immutable Sudoku given"):
        feedback.execute_samsung_feedback_step(
            run_id="run-a", refinement_step_index=0, prior_proposal=SOLVED,
            diagnostic=_diag(locus="semantic-cell-1"), reverse_trace=_index(1, "semantic-cell-1"),
            clamp_state=state, release_bindings=_bindings(state, 1, "slot-1", "semantic-cell-1"),
            immutable_givens=(0, SOLVED[1]) + (0,) * 79,
        )


def test_missing_or_mismatched_hard_given_fails_before_release(monkeypatch):
    state = _state()
    bad = (9,) + (0,) * 80
    monkeypatch.setattr(feedback, "solve_sudoku", lambda *a, **k: (_ for _ in ()).throw(AssertionError()))
    with pytest.raises(ValueError, match="immutable Sudoku given missing or mismatched"):
        feedback.execute_samsung_feedback_step(
            run_id="run-a", refinement_step_index=0, prior_proposal=SOLVED,
            diagnostic=_diag(), reverse_trace=_index(), clamp_state=state,
            release_bindings=_bindings(state), immutable_givens=bad,
        )


def test_structural_rejection_never_reaches_model(monkeypatch):
    state=_state(); monkeypatch.setattr(feedback,"solve_sudoku",lambda *a,**k: (_ for _ in ()).throw(AssertionError()))
    with pytest.raises(ValueError, match="structural rejection cannot become a task residual"):
        feedback.execute_samsung_feedback_step(
            run_id="run-a", refinement_step_index=0, prior_proposal=SOLVED,
            diagnostic=_diag(cls=STRUCTURAL_REJECTION), reverse_trace=_index(), clamp_state=state,
            release_bindings=_bindings(state), immutable_givens=IMMUTABLE,
        )


def test_unknown_semantic_locus_fails_before_model(monkeypatch):
    state=_state(); monkeypatch.setattr(feedback,"solve_sudoku",lambda *a,**k: (_ for _ in ()).throw(AssertionError()))
    with pytest.raises(LookupError, match="semantic locus has no structural trace"):
        feedback.execute_samsung_feedback_step(
            run_id="run-a", refinement_step_index=0, prior_proposal=SOLVED,
            diagnostic=_diag(locus="unknown"), reverse_trace=_index(), clamp_state=state,
            release_bindings=_bindings(state), immutable_givens=IMMUTABLE,
        )


def test_deterministic_traversal_digest(monkeypatch):
    monkeypatch.setattr(feedback, "solve_sudoku", _fake_solved)
    state=_state()
    kwargs=dict(
        run_id="run-deterministic", refinement_step_index=0, prior_proposal=SOLVED,
        diagnostic=_diag(), reverse_trace=_index(), clamp_state=state,
        release_bindings=_bindings(state), immutable_givens=IMMUTABLE,
        device="cpu", max_model_steps=2,
    )
    a=feedback.execute_samsung_feedback_step(**kwargs); b=feedback.execute_samsung_feedback_step(**kwargs)
    assert a.traversal_digest == b.traversal_digest
    assert a.release_binding_table_digest == b.release_binding_table_digest


def test_invalid_learned_solution_against_hard_givens_is_rejected(monkeypatch):
    bad=list(SOLVED); bad[1]=9; bad=tuple(bad)
    def solver(*args, **kwargs):
        return RefinementResult(
            status="SOLVED", solution=bad,
            steps=(RefinementStep(step=1,valid=True,complete=True,conflicts=(),proposal=bad),), device="cpu"
        )
    monkeypatch.setattr(feedback,"solve_sudoku",solver)
    state=_state()
    with pytest.raises(RuntimeError, match="violated immutable Sudoku givens"):
        feedback.execute_samsung_feedback_step(
            run_id="run-a", refinement_step_index=0, prior_proposal=SOLVED,
            diagnostic=_diag(), reverse_trace=_index(), clamp_state=state,
            release_bindings=_bindings(state), immutable_givens=IMMUTABLE,
        )
