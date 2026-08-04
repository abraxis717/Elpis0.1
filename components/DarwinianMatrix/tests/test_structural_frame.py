from __future__ import annotations

import torch

from DarwinianMatrix.climate.state import (
    ClimateDynamicsState,
)
from DarwinianMatrix.controller.structural_frame import (
    STRUCTURAL_FRAME_COMMITTED,
    STRUCTURAL_REFINEMENT_REJECTED,
    advance_structural_frame_transaction,
    replay_structural_frame_transaction,
    verify_structural_attempt_chain,
)
from DarwinianMatrix.controller.verdict import (
    MetaEpisodeState,
)
from DarwinianMatrix.ecology.engine import (
    PRODUCER,
    EcologyState,
)
from DarwinianMatrix.ecology.transaction import (
    EcologyTransactionConfig,
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


def clamp_state(value: int = 6) -> ClampState:
    state = ClampState.empty("structural-frame")

    proposal = ClampProposal(
        proposal_id=f"proposal-{value}",
        operation=ClampOperation.ASSERT,
        slot_id="slot-a",
        evidence_digest="a" * 64,
        cell_index=0,
        value=value,
    )

    transaction = ClampTransaction(
        transaction_id=f"transaction-{value}",
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


def ecology_state() -> EcologyState:
    state = EcologyState()
    state.ctype[3280] = PRODUCER
    state.genome[3280] = 0.5
    state.energy[3280] = 1.0
    state.lineage[3280] = 3280
    state.validate()
    return state


def inputs():
    return (
        clamp_state(),
        ClimateDynamicsState.empty(),
        ecology_state(),
        MetaEpisodeState(
            meta_id="structural-frame",
            attempt_budget=3,
        ),
        build_neighbor_table(),
        EcologyTransactionConfig(),
    )


def accepted_first():
    clamps, climate, ecology, meta, neighbors, config = (
        inputs()
    )

    result = advance_structural_frame_transaction(
        episode_id="structural-frame",
        structural_attempt_index=0,
        random_seed=717,
        previous_grid=GRID,
        clamp_state=clamps,
        adapter=DeterministicSudokuReferenceAdapter(),
        climate_state=climate,
        ecology_state=ecology,
        meta_state=meta,
        target_viability=1_000_000.0,
        neighbors=neighbors,
        config=config,
    )

    return (
        result,
        clamps,
        climate,
        ecology,
        meta,
        neighbors,
        config,
    )


def rejected_first():
    clamps, climate, ecology, meta, neighbors, config = (
        inputs()
    )

    result = advance_structural_frame_transaction(
        episode_id="structural-frame",
        structural_attempt_index=0,
        random_seed=717,
        previous_grid=GRID,
        clamp_state=clamps,
        adapter=DeterministicSudokuReferenceAdapter(
            max_search_nodes=0
        ),
        climate_state=climate,
        ecology_state=ecology,
        meta_state=meta,
        target_viability=1_000_000.0,
        neighbors=neighbors,
        config=config,
    )

    return (
        result,
        clamps,
        climate,
        ecology,
        meta,
        neighbors,
        config,
    )


def test_accepted_structural_frame_composes_layers() -> None:
    result, _, _, _, _, _, _ = accepted_first()

    assert result.committed
    assert result.outcome == STRUCTURAL_FRAME_COMMITTED
    assert result.frame_result is not None
    assert result.meta_state.attempt_index == 1
    assert result.climate_state.initialized
    assert result.attempt_record.validate_digest()


def test_refinement_output_satisfies_clamp_and_drives_climate() -> None:
    result, _, _, _, _, _, _ = accepted_first()

    output = result.refinement_result.output_grid()

    assert output is not None
    assert int(output[0]) == 6
    assert int(result.climate_state.current[0]) == 6

    assert (
        result.attempt_record.output_grid_digest
        == result.frame_result.commit_record.grid_digest
    )


def test_accepted_attempt_record_binds_inner_commit() -> None:
    result, _, _, _, _, _, _ = accepted_first()

    assert result.frame_result is not None

    assert (
        result.attempt_record.frame_commit_digest
        == result.frame_result.commit_record.commit_digest
    )
    assert (
        result.attempt_record.ecology_record_digest
        == result.frame_result.ecology_record.record_digest
    )
    assert (
        result.attempt_record.refinement_result_digest
        == result.refinement_result.result_digest
    )


def test_rejected_refinement_preserves_all_states() -> None:
    (
        result,
        clamps,
        climate,
        ecology,
        meta,
        _,
        _,
    ) = rejected_first()

    assert not result.committed
    assert (
        result.outcome
        == STRUCTURAL_REFINEMENT_REJECTED
    )
    assert result.frame_result is None

    assert result.climate_state is climate
    assert result.ecology_state is ecology
    assert result.meta_state is meta

    assert result.climate_state.digest() == climate.digest()
    assert result.ecology_state.digest() == ecology.digest()
    assert result.meta_state.digest() == meta.digest()
    assert result.meta_state.attempt_index == 0
    assert result.refinement_request.episode_id == (
        clamps.episode_id
    )


def test_rejected_attempt_record_is_valid() -> None:
    result, _, _, _, _, _, _ = rejected_first()

    record = result.attempt_record

    assert record.validate_digest()
    assert record.output_grid_digest is None
    assert record.ecology_record_digest is None
    assert record.frame_commit_digest is None
    assert (
        record.climate_before_digest
        == record.climate_after_digest
    )
    assert (
        record.ecology_before_digest
        == record.ecology_after_digest
    )
    assert (
        record.meta_before_digest
        == record.meta_after_digest
    )


def test_exact_accepted_replay() -> None:
    (
        expected,
        clamps,
        climate,
        ecology,
        meta,
        neighbors,
        config,
    ) = accepted_first()

    observed, replay = (
        replay_structural_frame_transaction(
            expected_result=expected,
            episode_id="structural-frame",
            structural_attempt_index=0,
            random_seed=717,
            previous_grid=GRID,
            clamp_state=clamps,
            adapter=DeterministicSudokuReferenceAdapter(),
            climate_state=climate,
            ecology_state=ecology,
            meta_state=meta,
            target_viability=1_000_000.0,
            neighbors=neighbors,
            config=config,
        )
    )

    assert replay.passed
    assert (
        observed.attempt_record.attempt_digest
        == expected.attempt_record.attempt_digest
    )


def test_exact_rejected_replay() -> None:
    (
        expected,
        clamps,
        climate,
        ecology,
        meta,
        neighbors,
        config,
    ) = rejected_first()

    _, replay = replay_structural_frame_transaction(
        expected_result=expected,
        episode_id="structural-frame",
        structural_attempt_index=0,
        random_seed=717,
        previous_grid=GRID,
        clamp_state=clamps,
        adapter=DeterministicSudokuReferenceAdapter(
            max_search_nodes=0
        ),
        climate_state=climate,
        ecology_state=ecology,
        meta_state=meta,
        target_viability=1_000_000.0,
        neighbors=neighbors,
        config=config,
    )

    assert replay.passed


def test_replay_detects_changed_clamp_state() -> None:
    (
        expected,
        _,
        climate,
        ecology,
        meta,
        neighbors,
        config,
    ) = accepted_first()

    _, replay = replay_structural_frame_transaction(
        expected_result=expected,
        episode_id="structural-frame",
        structural_attempt_index=0,
        random_seed=717,
        previous_grid=GRID,
        clamp_state=clamp_state(value=7),
        adapter=DeterministicSudokuReferenceAdapter(),
        climate_state=climate,
        ecology_state=ecology,
        meta_state=meta,
        target_viability=1_000_000.0,
        neighbors=neighbors,
        config=config,
    )

    assert not replay.passed
    assert (
        replay.expected_attempt_digest
        != replay.observed_attempt_digest
    )


def test_two_accepted_attempts_form_valid_chain() -> None:
    first, clamps, _, _, _, neighbors, config = (
        accepted_first()
    )

    output = first.refinement_result.output_grid()
    assert output is not None
    assert first.frame_result is not None

    second = advance_structural_frame_transaction(
        episode_id="structural-frame",
        structural_attempt_index=1,
        random_seed=717,
        previous_grid=output,
        clamp_state=clamps,
        adapter=DeterministicSudokuReferenceAdapter(),
        climate_state=first.climate_state,
        ecology_state=first.ecology_state,
        meta_state=first.meta_state,
        target_viability=1_000_000.0,
        neighbors=neighbors,
        config=config,
        previous_ecology_record_digest=(
            first.frame_result.ecology_record.record_digest
        ),
        previous_frame_commit_digest=(
            first.frame_result.commit_record.commit_digest
        ),
        previous_structural_attempt_digest=(
            first.attempt_record.attempt_digest
        ),
    )

    assert verify_structural_attempt_chain(
        (
            first.attempt_record,
            second.attempt_record,
        )
    )
    assert second.meta_state.attempt_index == 2


def test_episode_identity_mismatch_rejected() -> None:
    clamps, climate, ecology, meta, neighbors, config = (
        inputs()
    )

    try:
        advance_structural_frame_transaction(
            episode_id="wrong-episode",
            structural_attempt_index=0,
            random_seed=717,
            previous_grid=GRID,
            clamp_state=clamps,
            adapter=DeterministicSudokuReferenceAdapter(),
            climate_state=climate,
            ecology_state=ecology,
            meta_state=meta,
            target_viability=1_000_000.0,
            neighbors=neighbors,
            config=config,
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Mismatched episode identity was accepted."
        )


def test_closed_clamp_state_rejected() -> None:
    clamps = ClampState.empty("structural-frame")

    closing = ClampTransaction(
        transaction_id="close",
        episode_id=clamps.episode_id,
        expected_state_digest=clamps.digest(),
        close_episode=True,
    )

    closed = apply_clamp_transaction(
        state=clamps,
        transaction=closing,
    ).state

    try:
        advance_structural_frame_transaction(
            episode_id="structural-frame",
            structural_attempt_index=0,
            random_seed=717,
            previous_grid=GRID,
            clamp_state=closed,
            adapter=DeterministicSudokuReferenceAdapter(),
            climate_state=ClimateDynamicsState.empty(),
            ecology_state=ecology_state(),
            meta_state=MetaEpisodeState(
                meta_id="structural-frame",
                attempt_budget=3,
            ),
            target_viability=1_000_000.0,
            neighbors=build_neighbor_table(),
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Closed clamp state entered the adapter."
        )


def test_repeated_structural_frames_bit_identical() -> None:
    first = accepted_first()[0]
    second = accepted_first()[0]

    assert (
        first.refinement_request.digest()
        == second.refinement_request.digest()
    )
    assert (
        first.refinement_result.result_digest
        == second.refinement_result.result_digest
    )
    assert (
        first.attempt_record.attempt_digest
        == second.attempt_record.attempt_digest
    )
    assert (
        first.climate_state.digest()
        == second.climate_state.digest()
    )
    assert (
        first.ecology_state.digest()
        == second.ecology_state.digest()
    )
    assert (
        first.meta_state.digest()
        == second.meta_state.digest()
    )
