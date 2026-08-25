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
from elpis_reference.projector_release import (
    ReleaseBindingTableV1,
    ReleaseBindingTargetV1,
    build_release_transaction,
)
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


def _diagnostic(diagnostic_class: str = TASK_REJECTION, *, locus: str | None = None):
    return TaskDiagnosticV1(
        diagnostic_class=diagnostic_class,
        task_scope_id="c2r4-release-episode",
        frame_index=0,
        subject_digest=_h("candidate"),
        producer_id="c2r4.task-validator.v1",
        locus_namespace=SEMANTIC_OBJECT,
        locus_identity=locus or _h("semantic-a"),
        reason_codes=("TASK_REQUIREMENT_UNSATISFIED",),
        details_digest=_h("details"),
    )


def _observation(cell: int, semantic: str = "semantic-a"):
    return StructuralObservationRecord.create(
        source_semantic_object_digest=_h(semantic),
        topology_vertex_digest=_h(f"topology-{cell}"),
        P7_capsule_digest=_h(f"capsule-{cell}"),
        P7_primary_cell_index=cell,
    )


def _tx(state, *proposals, transaction_id="initial"):
    return ClampTransaction(
        transaction_id=transaction_id,
        episode_id=state.episode_id,
        expected_state_digest=state.digest(),
        proposals=tuple(proposals),
    )


def _state(cells=(10, 20, 30)):
    state = ClampState.empty("c2r4-release-episode")
    props = tuple(
        ClampProposal(
            proposal_id=f"assert-{cell}",
            operation=ClampOperation.ASSERT,
            slot_id=f"slot-{cell}",
            evidence_digest=_h(f"evidence-{cell}"),
            cell_index=cell,
            value=(cell % 9) + 1,
        )
        for cell in cells
    )
    result = apply_clamp_transaction(state=state, transaction=_tx(state, *props))
    assert result.accepted
    return result.state


def _binding(state, *, cell=10, owner=None, semantic="semantic-a"):
    return ReleaseBindingTableV1(
        episode_id=state.episode_id,
        clamp_state_digest=state.digest(),
        targets=(
            ReleaseBindingTargetV1(
                cell_index=cell,
                owner=owner or f"slot-{cell}",
                locus_namespace=SEMANTIC_OBJECT,
                locus_identity=_h(semantic),
            ),
        ),
    )


def _resolved(cell=10):
    diagnostic = _diagnostic()
    residual = diagnostic.to_task_residual()
    resolved = ReverseTraceIndex((_observation(cell),)).resolve(residual)
    return diagnostic, residual, resolved


def test_release_uses_precommitted_owner_not_live_owner_copy():
    diagnostic, residual, resolved = _resolved()
    state = _state()
    binding = _binding(state)
    plan, transaction = build_release_transaction(
        residual=residual,
        resolved=resolved,
        clamp_state=state,
        release_bindings=binding,
    )
    assert plan.target_cells == (10,)
    assert plan.target_owners == ("slot-10",)
    assert plan.binding_table_digest == binding.binding_table_digest
    assert transaction is not None
    assert transaction.proposals[0].slot_id == "slot-10"
    assert transaction.proposals[0].evidence_digest == diagnostic.digest()
    assert transaction.proposals[0].operation == ClampOperation.RELEASE


def test_wrong_precommitted_owner_fails_before_projector_mutation():
    _, residual, resolved = _resolved()
    state = _state()
    with pytest.raises(ValueError, match="release binding owner does not match ClampState"):
        build_release_transaction(
            residual=residual,
            resolved=resolved,
            clamp_state=state,
            release_bindings=_binding(state, owner="forged-owner"),
        )


def test_release_binding_is_exact_state_bound():
    _, residual, resolved = _resolved()
    state = _state()
    binding = _binding(state)
    extra = ClampProposal(
        proposal_id="assert-40",
        operation=ClampOperation.ASSERT,
        slot_id="slot-40",
        evidence_digest=_h("evidence-40"),
        cell_index=40,
        value=5,
    )
    changed = apply_clamp_transaction(
        state=state,
        transaction=_tx(state, extra, transaction_id="change"),
    ).state
    with pytest.raises(ValueError, match="not bound to current ClampState"):
        build_release_transaction(
            residual=residual,
            resolved=resolved,
            clamp_state=changed,
            release_bindings=binding,
        )


def test_multi_cell_release_is_rejected_instead_of_truncated():
    diagnostic = _diagnostic()
    residual = diagnostic.to_task_residual()
    resolved = ReverseTraceIndex((_observation(10), _observation(20))).resolve(residual)
    state = _state()
    bindings = ReleaseBindingTableV1(
        episode_id=state.episode_id,
        clamp_state_digest=state.digest(),
        targets=tuple(
            ReleaseBindingTargetV1(
                cell_index=cell,
                owner=f"slot-{cell}",
                locus_namespace=SEMANTIC_OBJECT,
                locus_identity=_h("semantic-a"),
            )
            for cell in (10, 20)
        ),
    )
    with pytest.raises(ValueError, match="cardinality exceeds C2R4 bound of one"):
        build_release_transaction(
            residual=residual,
            resolved=resolved,
            clamp_state=state,
            release_bindings=bindings,
        )


def test_missing_binding_for_active_resolved_support_fails_closed():
    _, residual, resolved = _resolved(cell=20)
    state = _state()
    with pytest.raises(LookupError, match="lacks exactly one precommitted release binding"):
        build_release_transaction(
            residual=residual,
            resolved=resolved,
            clamp_state=state,
            release_bindings=_binding(state, cell=10),
        )


def test_release_preserves_unrelated_clamps():
    _, residual, resolved = _resolved()
    state = _state()
    _, transaction = build_release_transaction(
        residual=residual,
        resolved=resolved,
        clamp_state=state,
        release_bindings=_binding(state),
    )
    assert transaction is not None
    result = apply_clamp_transaction(state=state, transaction=transaction)
    assert result.accepted
    assert not bool(result.state.active_mask[10])
    for cell in (20, 30):
        assert bool(result.state.active_mask[cell])
        assert result.state.owners[cell] == f"slot-{cell}"


def test_inactive_resolved_support_is_deterministic_noop():
    _, residual, resolved = _resolved()
    state = _state()
    _, transaction = build_release_transaction(
        residual=residual,
        resolved=resolved,
        clamp_state=state,
        release_bindings=_binding(state),
    )
    assert transaction is not None
    after = apply_clamp_transaction(state=state, transaction=transaction).state
    rebound = ReleaseBindingTableV1(
        episode_id=after.episode_id,
        clamp_state_digest=after.digest(),
        targets=(
            ReleaseBindingTargetV1(
                cell_index=10,
                owner="slot-10",
                locus_namespace=SEMANTIC_OBJECT,
                locus_identity=_h("semantic-a"),
            ),
        ),
    )
    plan, second = build_release_transaction(
        residual=residual,
        resolved=resolved,
        clamp_state=after,
        release_bindings=rebound,
    )
    assert plan.target_cells == ()
    assert second is None


def test_stale_projector_transaction_still_rejected():
    _, residual, resolved = _resolved()
    state = _state()
    _, transaction = build_release_transaction(
        residual=residual,
        resolved=resolved,
        clamp_state=state,
        release_bindings=_binding(state),
    )
    assert transaction is not None
    extra = ClampProposal(
        proposal_id="assert-40",
        operation=ClampOperation.ASSERT,
        slot_id="slot-40",
        evidence_digest=_h("evidence-40"),
        cell_index=40,
        value=5,
    )
    changed = apply_clamp_transaction(
        state=state, transaction=_tx(state, extra, transaction_id="change")
    ).state
    stale = apply_clamp_transaction(state=changed, transaction=transaction)
    assert not stale.accepted
    assert stale.receipt.reason_codes == ("STALE_CLAMP_STATE",)


def test_structural_rejection_cannot_reach_release_adapter():
    with pytest.raises(ValueError, match="structural rejection cannot become a task residual"):
        _diagnostic(STRUCTURAL_REJECTION).to_task_residual()


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
        name.startswith("elpis_reference.model") or name.startswith("elpis_reference.vendor")
        for name in imported
    )
    assert tuple(inspect.signature(build_release_transaction).parameters) == (
        "residual", "resolved", "clamp_state", "release_bindings"
    )
