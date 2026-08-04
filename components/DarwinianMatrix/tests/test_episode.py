from __future__ import annotations

import torch

from DarwinianMatrix.controller.episode import (
    DarwinianEpisodeState,
    EpisodeDisposition,
    advance_episode,
    replay_episode_advance,
)
from DarwinianMatrix.ecology.engine import (
    PRODUCER,
    EcologyState,
)
from DarwinianMatrix.geometry import (
    build_neighbor_table,
)
from DarwinianMatrix.projector.constraints import (
    ClampOperation,
    ClampProposal,
    ClampState,
    ClampTransaction,
    apply_clamp_transaction,
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


def ecology_state() -> EcologyState:
    state = EcologyState()
    state.ctype[3280] = PRODUCER
    state.genome[3280] = 0.5
    state.energy[3280] = 1.0
    state.lineage[3280] = 3280
    state.validate()
    return state


def forced_clamps() -> ClampState:
    state = ClampState.empty("episode-owner")

    proposal = ClampProposal(
        proposal_id="force-six",
        operation=ClampOperation.ASSERT,
        slot_id="slot-a",
        evidence_digest="a" * 64,
        cell_index=0,
        value=6,
    )

    transaction = ClampTransaction(
        transaction_id="assert-six",
        episode_id=state.episode_id,
        expected_state_digest=state.digest(),
        proposals=(proposal,),
    )

    result = apply_clamp_transaction(
        state=state,
        transaction=transaction,
    )

    assert result.accepted
    return result.state


def initial_state(
    *,
    meta_budget: int = 3,
    structural_budget: int = 4,
) -> DarwinianEpisodeState:
    return DarwinianEpisodeState.initial(
        episode_id="episode-owner",
        previous_grid=GRID,
        ecology_state=ecology_state(),
        meta_attempt_budget=meta_budget,
        structural_attempt_budget=(
            structural_budget
        ),
        clamp_state=forced_clamps(),
    )


def accepted_adapter():
    return DeterministicSudokuReferenceAdapter()


def rejected_adapter():
    return DeterministicSudokuReferenceAdapter(
        max_search_nodes=0
    )


def test_initial_episode_owns_genesis_heads() -> None:
    state = initial_state()

    assert state.structural_attempt_index == 0
    assert state.meta_state.attempt_index == 0
    assert state.disposition == EpisodeDisposition.RUNNING
    assert not state.closed
    assert state.previous_ecology_record_digest == "0" * 64
    assert state.previous_frame_commit_digest == "0" * 64
    assert state.previous_structural_attempt_digest == "0" * 64


def test_accepted_attempt_advances_all_owned_heads() -> None:
    state = initial_state()

    result = advance_episode(
        state=state,
        random_seed=717,
        adapter=accepted_adapter(),
        target_viability=1_000_000.0,
        neighbors=build_neighbor_table(),
    )

    next_state = result.state

    assert result.structural_result.committed
    assert next_state.structural_attempt_index == 1
    assert next_state.meta_state.attempt_index == 1
    assert int(next_state.previous_grid[0]) == 6
    assert next_state.previous_ecology_record_digest != "0" * 64
    assert next_state.previous_frame_commit_digest != "0" * 64
    assert next_state.previous_structural_attempt_digest != "0" * 64
    assert not next_state.closed


def test_rejected_attempt_advances_only_structural_ownership() -> None:
    state = initial_state()

    result = advance_episode(
        state=state,
        random_seed=717,
        adapter=rejected_adapter(),
        target_viability=1_000_000.0,
        neighbors=build_neighbor_table(),
    )

    next_state = result.state

    assert not result.structural_result.committed
    assert next_state.structural_attempt_index == 1
    assert next_state.meta_state.attempt_index == 0
    assert torch.equal(
        next_state.previous_grid,
        state.previous_grid,
    )
    assert (
        next_state.climate_state.digest()
        == state.climate_state.digest()
    )
    assert (
        next_state.ecology_state.digest()
        == state.ecology_state.digest()
    )
    assert next_state.previous_ecology_record_digest == "0" * 64
    assert next_state.previous_frame_commit_digest == "0" * 64
    assert next_state.previous_structural_attempt_digest != "0" * 64


def test_rejection_then_acceptance_uses_distinct_indices() -> None:
    state = initial_state()

    rejected = advance_episode(
        state=state,
        random_seed=717,
        adapter=rejected_adapter(),
        target_viability=1_000_000.0,
        neighbors=build_neighbor_table(),
    )

    accepted = advance_episode(
        state=rejected.state,
        random_seed=717,
        adapter=accepted_adapter(),
        target_viability=1_000_000.0,
        neighbors=build_neighbor_table(),
    )

    assert (
        rejected.structural_result.attempt_record
        .structural_attempt_index
        == 0
    )
    assert (
        rejected.structural_result.attempt_record
        .frame_index
        == 0
    )

    assert (
        accepted.structural_result.attempt_record
        .structural_attempt_index
        == 1
    )
    assert (
        accepted.structural_result.attempt_record
        .frame_index
        == 0
    )

    assert accepted.state.structural_attempt_index == 2
    assert accepted.state.meta_state.attempt_index == 1


def test_structural_budget_exhaustion_closes_clamps() -> None:
    state = initial_state(
        structural_budget=1
    )

    result = advance_episode(
        state=state,
        random_seed=717,
        adapter=rejected_adapter(),
        target_viability=1_000_000.0,
        neighbors=build_neighbor_table(),
    )

    assert result.state.closed
    assert (
        result.state.disposition
        == EpisodeDisposition
        .STRUCTURAL_ATTEMPT_BUDGET_EXHAUSTED
    )
    assert result.state.clamp_state.closed
    assert result.state.clamp_state.active_count == 0
    assert result.clamp_close_receipt is not None
    assert result.clamp_close_receipt.validate_digest()


def test_meta_terminal_closes_clamps() -> None:
    state = initial_state(
        meta_budget=1,
        structural_budget=4,
    )

    result = advance_episode(
        state=state,
        random_seed=717,
        adapter=accepted_adapter(),
        target_viability=1_000_000.0,
        neighbors=build_neighbor_table(),
    )

    assert result.state.closed
    assert (
        result.state.disposition
        == EpisodeDisposition.META_EPISODE_TERMINAL
    )
    assert result.state.meta_state.closed
    assert result.state.clamp_state.closed
    assert result.state.clamp_state.active_count == 0
    assert result.clamp_close_receipt is not None


def test_closed_episode_rejects_further_advance() -> None:
    state = initial_state(
        structural_budget=1
    )

    closed = advance_episode(
        state=state,
        random_seed=717,
        adapter=rejected_adapter(),
        target_viability=1_000_000.0,
        neighbors=build_neighbor_table(),
    ).state

    try:
        advance_episode(
            state=closed,
            random_seed=717,
            adapter=accepted_adapter(),
            target_viability=1_000_000.0,
            neighbors=build_neighbor_table(),
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError(
            "Closed episode accepted another attempt."
        )


def test_episode_state_is_immutable_by_interface() -> None:
    state = initial_state()
    before = state.digest()

    grid = state.previous_grid
    clamp = state.clamp_state
    climate = state.climate_state
    ecology = state.ecology_state

    grid[0] = 9

    clamp_values = clamp.values
    clamp_values[0] = 9

    climate_current = climate.current
    climate_current[0] = 9

    ecology.energy[3280] = 717.0

    assert state.digest() == before
    assert int(state.previous_grid[0]) == 5
    assert int(state.clamp_state.values[0]) == 6
    assert not state.climate_state.initialized
    assert float(state.ecology_state.energy[3280]) == 1.0


def test_exact_accepted_episode_replay() -> None:
    state = initial_state()

    expected = advance_episode(
        state=state,
        random_seed=717,
        adapter=accepted_adapter(),
        target_viability=1_000_000.0,
        neighbors=build_neighbor_table(),
    )

    observed, replay = replay_episode_advance(
        expected_result=expected,
        state=state,
        random_seed=717,
        adapter=accepted_adapter(),
        target_viability=1_000_000.0,
        neighbors=build_neighbor_table(),
    )

    assert replay.passed
    assert observed.state.digest() == expected.state.digest()


def test_exact_rejected_episode_replay() -> None:
    state = initial_state()

    expected = advance_episode(
        state=state,
        random_seed=717,
        adapter=rejected_adapter(),
        target_viability=1_000_000.0,
        neighbors=build_neighbor_table(),
    )

    _, replay = replay_episode_advance(
        expected_result=expected,
        state=state,
        random_seed=717,
        adapter=rejected_adapter(),
        target_viability=1_000_000.0,
        neighbors=build_neighbor_table(),
    )

    assert replay.passed


def test_exact_terminal_episode_replay_binds_close_receipt() -> None:
    state = initial_state(
        structural_budget=1
    )

    expected = advance_episode(
        state=state,
        random_seed=717,
        adapter=rejected_adapter(),
        target_viability=1_000_000.0,
        neighbors=build_neighbor_table(),
    )

    observed, replay = replay_episode_advance(
        expected_result=expected,
        state=state,
        random_seed=717,
        adapter=rejected_adapter(),
        target_viability=1_000_000.0,
        neighbors=build_neighbor_table(),
    )

    assert replay.passed
    assert (
        replay.expected_close_receipt_digest
        == replay.observed_close_receipt_digest
    )
    assert observed.state.closed


def test_repeated_episode_advances_are_bit_identical() -> None:
    first_state = initial_state()
    second_state = initial_state()

    first = advance_episode(
        state=first_state,
        random_seed=717,
        adapter=accepted_adapter(),
        target_viability=1_000_000.0,
        neighbors=build_neighbor_table(),
    )

    second = advance_episode(
        state=second_state,
        random_seed=717,
        adapter=accepted_adapter(),
        target_viability=1_000_000.0,
        neighbors=build_neighbor_table(),
    )

    assert first.state.digest() == second.state.digest()
    assert (
        first.structural_result.attempt_record
        .attempt_digest
        == second.structural_result.attempt_record
        .attempt_digest
    )
