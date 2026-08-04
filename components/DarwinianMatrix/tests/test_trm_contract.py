from __future__ import annotations

import json

import torch

from DarwinianMatrix.projector.constraints import (
    ClampOperation,
    ClampProposal,
    ClampState,
    ClampTransaction,
    apply_clamp_transaction,
)
from DarwinianMatrix.trm.contract import (
    REFINEMENT_ACCEPTED,
    StructuralAdapterManifest,
    StructuralRefinementRequest,
    build_refinement_result,
    execute_refinement,
)
from DarwinianMatrix.trm.reference_solver import (
    DeterministicSudokuReferenceAdapter,
)


GRID = torch.tensor([
    5,3,4,6,7,8,9,1,2,
    6,7,2,1,9,5,3,4,8,
    1,9,8,3,4,2,5,6,7,
    8,5,9,7,6,1,4,2,3,
    4,2,6,8,5,3,7,9,1,
    7,1,3,9,2,4,8,5,6,
    9,6,1,5,3,7,2,8,4,
    2,8,7,4,1,9,6,3,5,
    3,4,5,2,8,6,1,7,9,
])


def alternate_grid() -> torch.Tensor:
    matrix = GRID.reshape(9, 9)
    order = torch.tensor(
        [1, 0, 2, 3, 4, 5, 6, 7, 8]
    )
    return matrix[order].reshape(-1).clone()


def empty_request() -> StructuralRefinementRequest:
    return StructuralRefinementRequest(
        episode_id="trm-contract",
        frame_index=0,
        previous_grid=GRID,
        clamp_values=torch.zeros(
            81,
            dtype=torch.int64,
        ),
        clamp_mask=torch.zeros(
            81,
            dtype=torch.bool,
        ),
    )


def forced_request() -> StructuralRefinementRequest:
    values = torch.zeros(81, dtype=torch.int64)
    mask = torch.zeros(81, dtype=torch.bool)

    values[0] = 6
    mask[0] = True

    return StructuralRefinementRequest(
        episode_id="trm-contract",
        frame_index=0,
        previous_grid=GRID,
        clamp_values=values,
        clamp_mask=mask,
    )


def test_manifest_requires_frozen_adapter() -> None:
    try:
        StructuralAdapterManifest(
            adapter_id="bad",
            adapter_version="1",
            solver_family="bad",
            implementation_digest="a" * 64,
            frozen=False,
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Mutable structural adapter was accepted."
        )


def test_request_contains_only_structural_fields() -> None:
    request = empty_request()
    payload = request.canonical_payload()

    assert set(payload) == {
        "clamp_mask",
        "clamp_values",
        "episode_id",
        "frame_index",
        "previous_grid",
        "schema_version",
    }

    encoded = json.dumps(
        payload,
        sort_keys=True,
    ).lower()

    for forbidden in (
        "ecology",
        "energy",
        "viability",
        "verdict",
        "cascade",
        "resource",
        "lineage",
    ):
        assert forbidden not in encoded


def test_request_rejects_nonzero_inactive_values() -> None:
    values = torch.zeros(81, dtype=torch.int64)
    mask = torch.zeros(81, dtype=torch.bool)
    values[0] = 5

    try:
        StructuralRefinementRequest(
            episode_id="trm-contract",
            frame_index=0,
            previous_grid=GRID,
            clamp_values=values,
            clamp_mask=mask,
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Nonzero inactive clamp was accepted."
        )


def test_request_rejects_local_contradiction() -> None:
    values = torch.zeros(81, dtype=torch.int64)
    mask = torch.zeros(81, dtype=torch.bool)

    values[0] = 5
    values[1] = 5
    mask[0] = True
    mask[1] = True

    try:
        StructuralRefinementRequest(
            episode_id="trm-contract",
            frame_index=0,
            previous_grid=GRID,
            clamp_values=values,
            clamp_mask=mask,
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Contradictory clamp constellation was accepted."
        )


def test_previous_grid_may_differ_from_new_clamp() -> None:
    request = forced_request()

    assert int(request.previous_grid[0]) == 5
    assert int(request.clamp_values[0]) == 6
    assert bool(request.clamp_mask[0])


def test_reference_adapter_preserves_satisfied_grid() -> None:
    adapter = DeterministicSudokuReferenceAdapter()

    result = execute_refinement(
        adapter=adapter,
        request=empty_request(),
    )

    assert result.outcome == REFINEMENT_ACCEPTED
    assert result.iteration_count == 0
    assert torch.equal(result.output_grid(), GRID)


def test_reference_adapter_satisfies_new_clamp() -> None:
    adapter = DeterministicSudokuReferenceAdapter()

    result = execute_refinement(
        adapter=adapter,
        request=forced_request(),
    )

    assert result.outcome == REFINEMENT_ACCEPTED

    output = result.output_grid()

    assert output is not None
    assert int(output[0]) == 6
    assert not torch.equal(output, GRID)


def test_reference_adapter_budget_exhaustion() -> None:
    adapter = DeterministicSudokuReferenceAdapter(
        max_search_nodes=0
    )

    result = execute_refinement(
        adapter=adapter,
        request=forced_request(),
    )

    assert result.outcome == "REFINEMENT_REJECTED"
    assert result.reason_codes == (
        "SEARCH_BUDGET_EXHAUSTED",
    )


def test_execute_refinement_does_not_mutate_request() -> None:
    request = forced_request()
    before = request.digest()

    execute_refinement(
        adapter=DeterministicSudokuReferenceAdapter(),
        request=request,
    )

    assert request.digest() == before
    assert int(request.previous_grid[0]) == 5
    assert int(request.clamp_values[0]) == 6


def test_result_digest_is_sensitive_to_output() -> None:
    request = empty_request()
    adapter = DeterministicSudokuReferenceAdapter()

    first = build_refinement_result(
        request=request,
        manifest=adapter.manifest,
        outcome=REFINEMENT_ACCEPTED,
        reason_codes=("ACCEPTED",),
        iteration_count=0,
        output_grid=GRID,
    )

    second = build_refinement_result(
        request=request,
        manifest=adapter.manifest,
        outcome=REFINEMENT_ACCEPTED,
        reason_codes=("ACCEPTED",),
        iteration_count=0,
        output_grid=alternate_grid(),
    )

    assert first.validate_digest()
    assert second.validate_digest()
    assert first.result_digest != second.result_digest


def test_wrong_request_binding_is_rejected() -> None:
    request = empty_request()
    other = forced_request()
    reference = DeterministicSudokuReferenceAdapter()

    wrong_result = reference.refine(other)

    class WrongAdapter:
        @property
        def manifest(self):
            return reference.manifest

        def refine(self, supplied_request):
            return wrong_result

    try:
        execute_refinement(
            adapter=WrongAdapter(),
            request=request,
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError(
            "Wrong request binding was accepted."
        )


def test_request_can_be_built_from_clamp_state() -> None:
    state = ClampState.empty("trm-contract")

    proposal = ClampProposal(
        proposal_id="proposal-1",
        operation=ClampOperation.ASSERT,
        slot_id="slot-a",
        evidence_digest="a" * 64,
        cell_index=0,
        value=6,
    )

    transaction = ClampTransaction(
        transaction_id="transaction-1",
        episode_id=state.episode_id,
        expected_state_digest=state.digest(),
        proposals=(proposal,),
    )

    state = apply_clamp_transaction(
        state=state,
        transaction=transaction,
    ).state

    request = StructuralRefinementRequest.from_clamp_state(
        previous_grid=GRID,
        clamp_state=state,
        frame_index=0,
    )

    assert request.episode_id == state.episode_id
    assert request.active_clamp_count == 1
    assert int(request.clamp_values[0]) == 6


def test_closed_clamp_state_cannot_create_request() -> None:
    state = ClampState.empty("trm-contract")

    closing = ClampTransaction(
        transaction_id="close",
        episode_id=state.episode_id,
        expected_state_digest=state.digest(),
        close_episode=True,
    )

    closed = apply_clamp_transaction(
        state=state,
        transaction=closing,
    ).state

    try:
        StructuralRefinementRequest.from_clamp_state(
            previous_grid=GRID,
            clamp_state=closed,
            frame_index=0,
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Closed clamp state created a TRM request."
        )
