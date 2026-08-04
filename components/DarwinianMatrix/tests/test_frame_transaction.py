from __future__ import annotations

import torch

from DarwinianMatrix.climate.state import (
    ClimateDynamicsState,
)
from DarwinianMatrix.controller.frame import (
    FrameCommitRecord,
    advance_frame_transaction,
    replay_frame_transaction,
    verify_frame_commit_chain,
)
from DarwinianMatrix.controller.verdict import (
    FrameVerdict,
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
from DarwinianMatrix.ledger.records import (
    verify_record_chain,
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


def changed_grid() -> torch.Tensor:
    matrix = GRID.reshape(9, 9)
    order = torch.tensor(
        [1, 0, 2, 3, 4, 5, 6, 7, 8]
    )
    return matrix[order].reshape(-1).clone()


def initial_ecology() -> EcologyState:
    state = EcologyState()

    state.ctype[3280] = PRODUCER
    state.genome[3280] = 0.5
    state.energy[3280] = 1.0
    state.lineage[3280] = 3280
    state.validate()

    return state


def initial_inputs(*, budget: int = 3):
    return (
        ClimateDynamicsState.empty(),
        initial_ecology(),
        MetaEpisodeState(
            meta_id="episode-frame",
            attempt_budget=budget,
        ),
        build_neighbor_table(),
        EcologyTransactionConfig(),
    )


def run_first(*, budget: int = 3):
    climate, ecology, meta, neighbors, config = (
        initial_inputs(budget=budget)
    )

    result = advance_frame_transaction(
        episode_id="episode-frame",
        random_seed=717,
        grid=GRID,
        climate_state=climate,
        ecology_state=ecology,
        meta_state=meta,
        target_viability=1_000_000.0,
        neighbors=neighbors,
        config=config,
    )

    return (
        result,
        climate,
        ecology,
        meta,
        neighbors,
        config,
    )


def test_first_frame_composes_all_layers() -> None:
    result, _, _, _, _, _ = run_first()

    assert result.climate_state.initialized
    assert result.meta_state.attempt_index == 1
    assert not result.meta_state.closed

    assert (
        result.assessment.verdict
        == FrameVerdict.IMPROVING
    )

    assert result.ecology_record.validate_digest()
    assert result.commit_record.validate_digest()

    assert result.commit_record.frame_index == 0
    assert (
        result.commit_record.ecology_record_digest
        == result.ecology_record.record_digest
    )


def test_frame_transaction_does_not_mutate_inputs() -> None:
    (
        _,
        climate,
        ecology,
        meta,
        _,
        _,
    ) = run_first()

    assert not climate.initialized
    assert climate.current.eq(0).all()
    assert ecology.population == 1
    assert meta.attempt_index == 0
    assert meta.viability_history == ()


def test_second_unchanged_frame_increments_climate_age() -> None:
    first, _, _, _, neighbors, config = run_first()

    second = advance_frame_transaction(
        episode_id="episode-frame",
        random_seed=717,
        grid=GRID,
        climate_state=first.climate_state,
        ecology_state=first.ecology_state,
        meta_state=first.meta_state,
        target_viability=1_000_000.0,
        neighbors=neighbors,
        config=config,
        previous_ecology_record_digest=(
            first.ecology_record.record_digest
        ),
        previous_commit_digest=(
            first.commit_record.commit_digest
        ),
    )

    assert torch.all(
        second.climate_state.transition_age == 1
    )
    assert second.meta_state.attempt_index == 2


def test_changed_frame_resets_exact_changed_regions() -> None:
    first, _, _, _, neighbors, config = run_first()

    second = advance_frame_transaction(
        episode_id="episode-frame",
        random_seed=717,
        grid=changed_grid(),
        climate_state=first.climate_state,
        ecology_state=first.ecology_state,
        meta_state=first.meta_state,
        target_viability=1_000_000.0,
        neighbors=neighbors,
        config=config,
        previous_ecology_record_digest=(
            first.ecology_record.record_digest
        ),
        previous_commit_digest=(
            first.commit_record.commit_digest
        ),
    )

    changed = second.climate_state.changed

    assert int(changed.sum()) == 18
    assert torch.all(
        second.climate_state.transition_age[changed]
        == 0
    )
    assert torch.all(
        second.climate_state.transition_age[~changed]
        == 1
    )


def test_two_frame_ledger_chains_are_valid() -> None:
    first, _, _, _, neighbors, config = run_first()

    second = advance_frame_transaction(
        episode_id="episode-frame",
        random_seed=717,
        grid=GRID,
        climate_state=first.climate_state,
        ecology_state=first.ecology_state,
        meta_state=first.meta_state,
        target_viability=1_000_000.0,
        neighbors=neighbors,
        config=config,
        previous_ecology_record_digest=(
            first.ecology_record.record_digest
        ),
        previous_commit_digest=(
            first.commit_record.commit_digest
        ),
    )

    assert verify_record_chain(
        (
            first.ecology_record,
            second.ecology_record,
        )
    )

    assert verify_frame_commit_chain(
        (
            first.commit_record,
            second.commit_record,
        )
    )


def test_exact_frame_replay_passes() -> None:
    (
        expected,
        climate,
        ecology,
        meta,
        neighbors,
        config,
    ) = run_first()

    observed, replay = replay_frame_transaction(
        expected_result=expected,
        episode_id="episode-frame",
        random_seed=717,
        grid=GRID,
        climate_state=climate,
        ecology_state=ecology,
        meta_state=meta,
        target_viability=1_000_000.0,
        neighbors=neighbors,
        config=config,
    )

    assert replay.passed
    assert (
        observed.commit_record.commit_digest
        == expected.commit_record.commit_digest
    )


def test_frame_replay_rejects_changed_grid() -> None:
    (
        expected,
        climate,
        ecology,
        meta,
        neighbors,
        config,
    ) = run_first()

    _, replay = replay_frame_transaction(
        expected_result=expected,
        episode_id="episode-frame",
        random_seed=717,
        grid=changed_grid(),
        climate_state=climate,
        ecology_state=ecology,
        meta_state=meta,
        target_viability=1_000_000.0,
        neighbors=neighbors,
        config=config,
    )

    assert not replay.passed
    assert (
        replay.observed_commit_digest
        != replay.expected_commit_digest
    )


def test_episode_identity_mismatch_is_rejected() -> None:
    climate, ecology, meta, neighbors, config = (
        initial_inputs()
    )

    try:
        advance_frame_transaction(
            episode_id="wrong-episode",
            random_seed=717,
            grid=GRID,
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


def test_attempt_budget_closes_frame_transaction() -> None:
    first, _, _, _, neighbors, config = run_first(
        budget=1
    )

    assert first.meta_state.closed
    assert (
        first.meta_state.final_verdict
        == FrameVerdict.BUDGET_EXHAUSTED
    )

    try:
        advance_frame_transaction(
            episode_id="episode-frame",
            random_seed=717,
            grid=GRID,
            climate_state=first.climate_state,
            ecology_state=first.ecology_state,
            meta_state=first.meta_state,
            target_viability=1_000_000.0,
            neighbors=neighbors,
            config=config,
            previous_ecology_record_digest=(
                first.ecology_record.record_digest
            ),
            previous_commit_digest=(
                first.commit_record.commit_digest
            ),
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError(
            "Closed episode accepted another frame."
        )


def test_commit_tampering_invalidates_digest() -> None:
    result, _, _, _, _, _ = run_first()

    payload = result.commit_record.to_dict()
    payload["random_seed"] = 0

    tampered = FrameCommitRecord.from_dict(
        payload
    )

    assert not tampered.validate_digest()


def test_repeated_frames_are_bit_identical() -> None:
    first = run_first()[0]
    second = run_first()[0]

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
    assert (
        first.ecology_record.record_digest
        == second.ecology_record.record_digest
    )
    assert (
        first.commit_record.commit_digest
        == second.commit_record.commit_digest
    )
