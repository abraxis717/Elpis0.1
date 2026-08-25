from __future__ import annotations

import ast
import hashlib
import inspect

import pytest

import elpis_reference.projector_release as adapter_module
from DarwinianMatrix.projector.constraints import (
    ClampOperation,
    ClampProposal,
    ClampState,
    ClampTransaction,
    apply_clamp_transaction,
)
from elpis_reference.projector_release import build_release_transaction
from elpis_reference.semantic_refinement import (
    SEMANTIC_OBJECT,
    STRUCTURAL_REJECTION,
    TASK_REJECTION,
    ReverseTraceIndex,
    StructuralObservationRecord,
    TaskDiagnosticV1,
)


def _h(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _diagnostic(
    diagnostic_class: str = TASK_REJECTION,
    *,
    frame_index: int = 0,
    subject: str = "candidate",
    details: str = "details",
) -> TaskDiagnosticV1:
    return TaskDiagnosticV1(
        diagnostic_class=diagnostic_class,
        task_scope_id="c2r2-episode",
        frame_index=frame_index,
        subject_digest=_h(subject),
        producer_id="c2r2.task-validator.v1",
        locus_namespace=SEMANTIC_OBJECT,
        locus_identity=_h("semantic-a"),
        reason_codes=("TASK_REQUIREMENT_UNSATISFIED",),
        details_digest=_h(details),
    )


def _observations():
    return (
        StructuralObservationRecord.create(
            source_semantic_object_digest=_h("semantic-a"),
            topology_vertex_digest=_h("topology-a"),
            P7_capsule_digest=_h("capsule-a"),
            P7_primary_cell_index=10,
        ),
        StructuralObservationRecord.create(
            source_semantic_object_digest=_h("semantic-a"),
            topology_vertex_digest=_h("topology-b"),
            P7_capsule_digest=_h("capsule-b"),
            P7_primary_cell_index=20,
        ),
    )


def _transaction(
    state: ClampState,
    *proposals: ClampProposal,
    transaction_id: str,
) -> ClampTransaction:
    return ClampTransaction(
        transaction_id=transaction_id,
        episode_id=state.episode_id,
        expected_state_digest=state.digest(),
        proposals=tuple(proposals),
    )


def _clamped_state() -> ClampState:
    state = ClampState.empty("c2r2-episode")
    proposals = (
        ClampProposal(
            proposal_id="assert-10",
            operation=ClampOperation.ASSERT,
            slot_id="slot-a",
            evidence_digest=_h("original-evidence-a"),
            cell_index=10,
            value=1,
        ),
        ClampProposal(
            proposal_id="assert-20",
            operation=ClampOperation.ASSERT,
            slot_id="slot-b",
            evidence_digest=_h("original-evidence-b"),
            cell_index=20,
            value=2,
        ),
        ClampProposal(
            proposal_id="assert-30",
            operation=ClampOperation.ASSERT,
            slot_id="slot-c",
            evidence_digest=_h("original-evidence-c"),
            cell_index=30,
            value=3,
        ),
    )
    result = apply_clamp_transaction(
        state=state,
        transaction=_transaction(state, *proposals, transaction_id="initial-support"),
    )
    assert result.accepted
    return result.state


def _resolved():
    diagnostic = _diagnostic()
    residual = diagnostic.to_task_residual()
    resolved = ReverseTraceIndex(_observations()).resolve(residual)
    return diagnostic, residual, resolved


def test_semantic_resolution_builds_release_only_transaction():
    diagnostic, residual, resolved = _resolved()
    state = _clamped_state()
    plan, transaction = build_release_transaction(
        residual=residual,
        resolved=resolved,
        clamp_state=state,
    )
    assert plan.target_cells == (10, 20)
    assert plan.target_owners == ("slot-a", "slot-b")
    assert transaction is not None
    assert transaction.expected_state_digest == state.digest()
    assert all(
        proposal.operation == ClampOperation.RELEASE and proposal.value is None
        for proposal in transaction.proposals
    )
    assert all(
        proposal.evidence_digest == diagnostic.digest()
        for proposal in transaction.proposals
    )
    assert {proposal.operation for proposal in transaction.proposals} == {
        ClampOperation.RELEASE,
    }


def test_canonical_projector_release_preserves_unrelated_clamp():
    _, residual, resolved = _resolved()
    state = _clamped_state()
    plan, transaction = build_release_transaction(
        residual=residual,
        resolved=resolved,
        clamp_state=state,
    )
    assert transaction is not None
    result = apply_clamp_transaction(state=state, transaction=transaction)
    assert result.accepted
    assert result.state.active_count == state.active_count - 2
    for cell in (10, 20):
        assert not bool(result.state.active_mask[cell])
        assert int(result.state.values[cell]) == 0
        assert result.state.owners[cell] is None
    assert bool(result.state.active_mask[30])
    assert int(result.state.values[30]) == 3
    assert result.state.owners[30] == "slot-c"
    assert plan.target_cells == (10, 20)


def test_inactive_resolved_support_is_deterministic_noop():
    _, residual, resolved = _resolved()
    state = _clamped_state()
    _, transaction = build_release_transaction(
        residual=residual,
        resolved=resolved,
        clamp_state=state,
    )
    assert transaction is not None
    after = apply_clamp_transaction(state=state, transaction=transaction).state
    plan, second = build_release_transaction(
        residual=residual,
        resolved=resolved,
        clamp_state=after,
    )
    assert plan.target_cells == ()
    assert plan.target_owners == ()
    assert second is None


def test_projector_rejects_intentionally_wrong_owner():
    _, residual, resolved = _resolved()
    state = _clamped_state()
    _, transaction = build_release_transaction(
        residual=residual,
        resolved=resolved,
        clamp_state=state,
    )
    assert transaction is not None
    original = transaction.proposals[0]
    tampered = ClampProposal(
        proposal_id=original.proposal_id,
        operation=ClampOperation.RELEASE,
        slot_id="wrong-owner",
        evidence_digest=original.evidence_digest,
        cell_index=original.cell_index,
        value=None,
    )
    wrong_owner = ClampTransaction(
        transaction_id=transaction.transaction_id + "-wrong-owner",
        episode_id=transaction.episode_id,
        expected_state_digest=transaction.expected_state_digest,
        proposals=(tampered, *transaction.proposals[1:]),
    )
    result = apply_clamp_transaction(state=state, transaction=wrong_owner)
    assert not result.accepted
    assert result.receipt.reason_codes == ("CLAMP_OWNER_MISMATCH",)
    assert result.state.digest() == state.digest()


def test_stale_release_transaction_is_rejected():
    _, residual, resolved = _resolved()
    state = _clamped_state()
    _, transaction = build_release_transaction(
        residual=residual,
        resolved=resolved,
        clamp_state=state,
    )
    assert transaction is not None
    unrelated = ClampProposal(
        proposal_id="assert-40",
        operation=ClampOperation.ASSERT,
        slot_id="slot-d",
        evidence_digest=_h("original-evidence-d"),
        cell_index=40,
        value=4,
    )
    changed = apply_clamp_transaction(
        state=state,
        transaction=_transaction(state, unrelated, transaction_id="unrelated-change"),
    )
    assert changed.accepted
    stale = apply_clamp_transaction(state=changed.state, transaction=transaction)
    assert not stale.accepted
    assert stale.receipt.reason_codes == ("STALE_CLAMP_STATE",)
    assert stale.state.digest() == changed.state.digest()


def test_release_builder_rejects_residual_resolution_mismatch():
    _, residual, resolved = _resolved()
    other = _diagnostic(
        frame_index=1,
        subject="other-candidate",
        details="other-details",
    ).to_task_residual()
    with pytest.raises(
        ValueError,
        match="Resolved residual is bound to another task residual",
    ):
        build_release_transaction(
            residual=other,
            resolved=resolved,
            clamp_state=_clamped_state(),
        )
    assert residual.digest() != other.digest()


def test_structural_rejection_cannot_reach_release_adapter():
    structural = _diagnostic(STRUCTURAL_REJECTION)
    with pytest.raises(
        ValueError,
        match="structural rejection cannot become a task residual",
    ):
        structural.to_task_residual()


def test_release_planning_is_order_independent():
    _, residual, resolved_a = _resolved()
    resolved_b = ReverseTraceIndex(reversed(_observations())).resolve(residual)
    state = _clamped_state()
    plan_a, transaction_a = build_release_transaction(
        residual=residual,
        resolved=resolved_a,
        clamp_state=state,
    )
    plan_b, transaction_b = build_release_transaction(
        residual=residual,
        resolved=resolved_b,
        clamp_state=state,
    )
    assert transaction_a is not None
    assert transaction_b is not None
    assert resolved_a.resolution_digest == resolved_b.resolution_digest
    assert plan_a.plan_digest == plan_b.plan_digest
    assert transaction_a.digest() == transaction_b.digest()


def test_adapter_has_no_learned_model_dependency():
    source = inspect.getsource(adapter_module)
    tree = ast.parse(source)
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
    assert not any(
        name.startswith("elpis_reference.model")
        or name.startswith("elpis_reference.vendor")
        for name in imported
    )
    signature = inspect.signature(build_release_transaction)
    assert tuple(signature.parameters) == (
        "residual",
        "resolved",
        "clamp_state",
    )
